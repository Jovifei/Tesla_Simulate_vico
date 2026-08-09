"""v0.5 operating-point-driven excitation generated before PTR/radiation."""

from __future__ import annotations

import hashlib
import math

from engine_excitation import EngineStateInput, ORDER_PROFILE_PATH, PARAMETERS_PATH, STATE_SCHEMA_PATH, load_json_package
from engine_operating_points.library import OperatingPointLibrary
from s12_acoustic_audition import PressureTrace


def _value(package: dict, name: str) -> float:
    return float(package["parameters"][name]["value"])


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_product_demo_states(library: OperatingPointLibrary) -> dict[str, EngineStateInput]:
    """Materialize the C/synthetic product demos from the operating library."""
    schema = load_json_package(STATE_SCHEMA_PATH)
    sample_rate_hz = int(_value(schema, "sample_rate_hz"))
    speed_per_rpm = _value(schema, "speed_per_rpm_mps")
    states = {}
    for name, profile in library.raw["demo_profiles"].items():
        frame_count = round(float(profile["duration_s"]) * sample_rate_hz)
        ramp = [index / (frame_count - 1) for index in range(frame_count)]
        rpm = tuple(float(profile["rpm"][0]) + (float(profile["rpm"][1]) - float(profile["rpm"][0])) * fraction for fraction in ramp)
        load = tuple(float(profile["load"][0]) + (float(profile["load"][1]) - float(profile["load"][0])) * fraction for fraction in ramp)
        speed = tuple(value * speed_per_rpm for value in rpm)
        acceleration = ((speed[1] - speed[0]) * sample_rate_hz,) + tuple((current - previous) * sample_rate_hz for previous, current in zip(speed, speed[1:]))
        state = EngineStateInput(name, tuple(index / sample_rate_hz for index in range(frame_count)), rpm, speed, acceleration, load, load)
        state.validate(sample_rate_hz)
        states[name] = state
    return states


def generate_product_excitation(state: EngineStateInput, library: OperatingPointLibrary) -> PressureTrace:
    """Apply RPM/load interpolation and order/transient synthesis before PTR."""
    schema = load_json_package(STATE_SCHEMA_PATH)
    parameters = load_json_package(PARAMETERS_PATH)
    profile = load_json_package(ORDER_PROFILE_PATH)
    sample_rate_hz = int(_value(schema, "sample_rate_hz"))
    state.validate(sample_rate_hz)
    phase = 0.0
    transient = 0.0
    samples = []
    for index, rpm in enumerate(state.rpm):
        phase += 2.0 * math.pi * rpm / 60.0 / sample_rate_hz
        effective_load = (state.load[index] + state.throttle[index]) * 0.5
        operating_point = library.evaluate(rpm, effective_load)
        order_sum = 0.0
        for order_profile in profile["parameters"].values():
            order = float(order_profile["order"])
            high_order = max(0.0, order - 1.0)
            harmonic_scale = operating_point.harmonic_gain if order > 1.0 else 1.0
            balance = 1.0 + high_order * effective_load * _value(parameters, "high_order_load_gain")
            order_sum += float(order_profile["amplitude"]) * operating_point.excitation_gain * harmonic_scale * balance * math.sin(order * phase + float(order_profile["phase_rad"]))
        rpm_rate = 0.0 if index == 0 else (rpm - state.rpm[index - 1]) * sample_rate_hz
        target_transient = _value(parameters, "transient_gain") * operating_point.transient_gain * (
            abs(state.acceleration[index]) / _value(parameters, "acceleration_reference_mps2")
            + abs(rpm_rate) / _value(parameters, "rpm_rate_reference")
        ) * (_value(parameters, "transient_load_floor") + effective_load * _value(parameters, "transient_load_span"))
        time_constant = _value(parameters, "attack_s") if target_transient > transient else _value(parameters, "decay_s")
        transient += (target_transient - transient) / max(1.0, time_constant * sample_rate_hz)
        speed_mode = _value(parameters, "speed_mode_floor") + _value(parameters, "speed_mode_span") * min(1.0, state.speed[index] / _value(parameters, "speed_cruise_mps"))
        samples.append(speed_mode * order_sum + transient * math.sin(_value(parameters, "transient_carrier_order") * phase))
    return PressureTrace.uniform(
        "engine_product_excitation.v05:" + state.case_id, samples, sample_rate_hz,
        sum(state.rpm) / len(state.rpm) / 60.0, "engine_exhaust_port",
        ("synthetic", "uncalibrated", "offline", "not_realtime_qualified",
         "engine_state_schema_sha256=" + _sha256(STATE_SCHEMA_PATH),
         "order_profile_sha256=" + _sha256(ORDER_PROFILE_PATH),
         "excitation_parameters_sha256=" + _sha256(PARAMETERS_PATH),
         "operating_point_library_sha256=" + library.library_hash),
    )


def project_order_amplitude(trace: PressureTrace, state: EngineStateInput, order: float) -> float:
    """Deterministically project a pre-PTR order amplitude for causal tests."""
    if trace.sample_rate_hz is None or len(trace.pressure_pa) != len(state.rpm):
        raise ValueError("order projection requires aligned uniform excitation")
    phase = 0.0
    phases = []
    for rpm in state.rpm:
        phase += 2.0 * math.pi * rpm / 60.0 / trace.sample_rate_hz
        phases.append(phase)
    scale = 2.0 / len(trace.pressure_pa)
    sine = scale * sum(sample * math.sin(order * value) for sample, value in zip(trace.pressure_pa, phases))
    cosine = scale * sum(sample * math.cos(order * value) for sample, value in zip(trace.pressure_pa, phases))
    return math.hypot(sine, cosine) / math.sqrt(2.0)
