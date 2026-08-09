"""Source-classified synthetic engine pressure excitation for the v0.4 pre-PTR chain."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

from s12_acoustic_audition import PressureTrace


ROOT = Path(__file__).resolve().parent
STATE_SCHEMA_PATH = ROOT / "engine_state_schema.json"
ORDER_PROFILE_PATH = ROOT / "order_profile.json"
PARAMETERS_PATH = ROOT / "engine_excitation_parameters.json"


def load_json_package(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _value(parameters: dict, name: str) -> float:
    return float(parameters["parameters"][name]["value"])


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class EngineStateInput:
    case_id: str
    timestamp: tuple[float, ...]
    rpm: tuple[float, ...]
    speed: tuple[float, ...]
    acceleration: tuple[float, ...]
    load: tuple[float, ...]
    throttle: tuple[float, ...]

    def validate(self, sample_rate_hz: int) -> None:
        fields = (self.timestamp, self.rpm, self.speed, self.acceleration, self.load, self.throttle)
        if not self.case_id or len(self.timestamp) < 2 or len({len(field) for field in fields}) != 1:
            raise ValueError("engine state requires aligned non-empty fields")
        if not all(math.isfinite(value) for field in fields for value in field):
            raise ValueError("engine state must be finite")
        if any(later <= earlier for earlier, later in zip(self.timestamp, self.timestamp[1:])):
            raise ValueError("engine state timestamp must be strictly increasing")
        if any(value <= 0.0 for value in self.rpm) or any(value < 0.0 for value in self.speed):
            raise ValueError("RPM must be positive and speed nonnegative")
        if any(not 0.0 <= value <= 1.0 for field in (self.load, self.throttle) for value in field):
            raise ValueError("load and throttle must be normalized")
        period = 1.0 / sample_rate_hz
        if any(abs((later - earlier) - period) > 1e-12 for earlier, later in zip(self.timestamp, self.timestamp[1:])):
            raise ValueError("engine state must use the contracted sample rate")


def build_default_engine_state_cases() -> dict[str, EngineStateInput]:
    schema = load_json_package(STATE_SCHEMA_PATH)
    rate = int(_value(schema, "sample_rate_hz"))
    speed_per_rpm = _value(schema, "speed_per_rpm_mps")
    cases = {}
    for name, profile in schema["case_profiles"].items():
        count = round(float(profile["duration_s"]) * rate)
        fraction = [index / (count - 1) for index in range(count)]
        rpm = tuple(float(profile["rpm"][0]) + (float(profile["rpm"][1]) - float(profile["rpm"][0])) * item for item in fraction)
        load = tuple(float(profile["load"][0]) + (float(profile["load"][1]) - float(profile["load"][0])) * item for item in fraction)
        speed = tuple(item * speed_per_rpm for item in rpm)
        acceleration = ((speed[1] - speed[0]) * rate,) + tuple((now - previous) * rate for previous, now in zip(speed, speed[1:]))
        state = EngineStateInput(name, tuple(index / rate for index in range(count)), rpm, speed, acceleration, load, load)
        state.validate(rate)
        cases[name] = state
    return cases


def generate_engine_excitation(state: EngineStateInput) -> PressureTrace:
    """Generate order, harmonic, load, speed, and transient pressure before PTR."""
    state_schema = load_json_package(STATE_SCHEMA_PATH)
    parameters = load_json_package(PARAMETERS_PATH)
    profile = load_json_package(ORDER_PROFILE_PATH)
    rate = int(_value(state_schema, "sample_rate_hz"))
    state.validate(rate)
    phase = 0.0
    transient = 0.0
    samples = []
    for index, rpm in enumerate(state.rpm):
        phase += 2.0 * math.pi * rpm / 60.0 / rate
        order_sum = 0.0
        load = (state.load[index] + state.throttle[index]) * 0.5
        for item in profile["parameters"].values():
            order = float(item["order"])
            high_order = max(0.0, order - 1.0)
            balance = 1.0 + high_order * load * _value(parameters, "high_order_load_gain")
            order_sum += float(item["amplitude"]) * balance * math.sin(order * phase + float(item["phase_rad"]))
        rpm_rate = 0.0 if index == 0 else (rpm - state.rpm[index - 1]) * rate
        desired = _value(parameters, "transient_gain") * (
            abs(state.acceleration[index]) / _value(parameters, "acceleration_reference_mps2")
            + abs(rpm_rate) / _value(parameters, "rpm_rate_reference")
        ) * (_value(parameters, "transient_load_floor") + load * _value(parameters, "transient_load_span"))
        time_constant = _value(parameters, "attack_s") if desired > transient else _value(parameters, "decay_s")
        transient += (desired - transient) / max(1.0, time_constant * rate)
        speed_mode = _value(parameters, "speed_mode_floor") + _value(parameters, "speed_mode_span") * min(1.0, state.speed[index] / _value(parameters, "speed_cruise_mps"))
        amplitude = _value(parameters, "base_pressure_pa") + load * _value(parameters, "load_pressure_span_pa")
        samples.append(speed_mode * amplitude * order_sum + transient * math.sin(_value(parameters, "transient_carrier_order") * phase))
    return PressureTrace.uniform(
        "engine_excitation.v04:" + state.case_id, samples, rate,
        sum(state.rpm) / len(state.rpm) / 60.0, "engine_exhaust_port",
        ("synthetic", "uncalibrated", "offline", "not_realtime_qualified",
         "engine_state_schema_sha256=" + _sha256(STATE_SCHEMA_PATH),
         "order_profile_sha256=" + _sha256(ORDER_PROFILE_PATH),
         "excitation_parameters_sha256=" + _sha256(PARAMETERS_PATH)),
    )
