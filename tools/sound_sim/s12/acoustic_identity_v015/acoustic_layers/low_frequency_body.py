"""Causal synthetic low-frequency engine-body resonators."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace


_BODY_PROFILES: Mapping[str, Mapping[str, tuple[tuple[float, float, float], ...]]] = {
    "ferrari_458": {
        "engine_body": ((95.0, 4.0, 0.08),),
        "exhaust_pressure": ((125.0, 4.5, 0.18), (160.0, 3.5, 0.10)),
        "mechanical_weight": ((190.0, 3.5, 0.06),),
    },
    "hellcat": {
        "engine_body": ((50.0, 2.2, 0.55),),
        "exhaust_pressure": ((73.0, 2.5, 0.45),),
        "mechanical_weight": ((105.0, 3.0, 0.18),),
    },
    "rx7_fd": {
        "engine_body": ((84.0, 3.0, 0.08),),
        "exhaust_pressure": ((128.0, 4.0, 0.35),),
        "mechanical_weight": ((168.0, 3.0, 0.12),),
    },
}
_COMPONENT_INPUTS: Mapping[str, Mapping[str, tuple[str, ...]]] = {
    "ferrari_458": {
        "engine_body": (),
        "exhaust_pressure": ("left_bank", "right_bank"),
        "mechanical_weight": ("metallic",),
    },
    "hellcat": {
        "engine_body": (),
        "exhaust_pressure": ("exhaust",),
        "mechanical_weight": ("mechanical",),
    },
    "rx7_fd": {
        "engine_body": (),
        "exhaust_pressure": ("rotary",),
        "mechanical_weight": ("turbine",),
    },
}
_SCOPE = "synthetic; uncalibrated; not OEM reproduction"
_PRESSURE_PROFILES: Mapping[str, Mapping[str, float]] = {
    "ferrari_458": {"pulse_gain": 0.26, "exhaust_hz": 132.0, "exhaust_gain": 0.68, "body_hz": 96.0, "body_gain": 0.34, "radiation_gain": 0.58},
    "hellcat": {"pulse_gain": 1.12, "exhaust_hz": 74.0, "exhaust_gain": 1.05, "body_hz": 51.0, "body_gain": 0.92, "radiation_gain": 1.08},
    "rx7_fd": {"pulse_gain": 0.31, "exhaust_hz": 128.0, "exhaust_gain": 0.48, "body_hz": 86.0, "body_gain": 0.28, "radiation_gain": 0.48},
}


def apply_low_frequency_body(
    render: SourceRender,
    vehicle_id: str,
    trace: VehicleStateTrace | None = None,
    sample_rate_hz: int = 48000,
) -> SourceRender:
    """Add a causal low-frequency layer; a trace enables pressure coupling."""
    render.validate()
    if vehicle_id not in _BODY_PROFILES:
        raise ValueError(f"unsupported vehicle_id: {vehicle_id!r}")
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 1000:
        raise ValueError("sample_rate_hz must be an integer >= 1000")
    if trace is not None:
        return _apply_pressure_chain(render, vehicle_id, trace, sample_rate_hz)

    components = {}
    for name, modes in _BODY_PROFILES[vehicle_id].items():
        source = _component_source(render, _COMPONENT_INPUTS[vehicle_id][name])
        component = np.zeros_like(render.pressure, dtype=np.float64)
        for frequency_hz, quality, gain in modes:
            component += gain * _causal_resonator(source, frequency_hz, quality, sample_rate_hz)
        components[name] = component
    body = sum(components.values(), np.zeros_like(render.pressure, dtype=np.float64))
    diagnostics = dict(render.diagnostics)
    diagnostics.update(
        {
            "low_frequency_body_model": "causal_damped_resonator_bank",
            "low_frequency_body_modes_hz": tuple(
                mode[0] for modes in _BODY_PROFILES[vehicle_id].values() for mode in modes
            ),
            "low_frequency_body_scope": _SCOPE,
        }
    )
    for name, component in components.items():
        diagnostics[f"{name}_modes_hz"] = tuple(mode[0] for mode in _BODY_PROFILES[vehicle_id][name])
        diagnostics[f"{name}_energy"] = float(np.sum(np.square(component)))
    return SourceRender(
        pressure=np.asarray(render.pressure, dtype=np.float64) + body,
        stems={**render.stems, **components, "low_frequency_body": body},
        diagnostics=diagnostics,
    ).validate()


def _apply_pressure_chain(
    render: SourceRender, vehicle_id: str, trace: VehicleStateTrace, sample_rate_hz: int
) -> SourceRender:
    """Route state-dependent pressure through exhaust, body, then radiation."""
    trace.validate()
    count = render.pressure.shape[0]
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    load = np.interp(time_s, trace.time_s, trace.load)
    throttle = np.interp(time_s, trace.time_s, trace.throttle)
    profile = _PRESSURE_PROFILES[vehicle_id]
    source = _component_source(render, _COMPONENT_INPUTS[vehicle_id]["exhaust_pressure"])
    pressure_state = (0.18 + 0.82 * load) * (0.35 + 0.65 * throttle) * np.clip(rpm / 1800.0, 0.45, 1.25)
    pressure_pulse = profile["pulse_gain"] * pressure_state[:, np.newaxis] * source
    exhaust_coupling = profile["exhaust_gain"] * _causal_resonator(pressure_pulse, profile["exhaust_hz"], 2.6, sample_rate_hz)
    body_resonance = profile["body_gain"] * _causal_resonator(exhaust_coupling, profile["body_hz"], 2.1, sample_rate_hz)
    radiation = profile["radiation_gain"] * (exhaust_coupling + body_resonance)
    diagnostics = dict(render.diagnostics)
    diagnostics.update(
        {
            "low_frequency_body_model": "state_dependent_pressure_exhaust_body_radiation",
            "low_frequency_body_scope": _SCOPE,
            "pressure_chain": "pressure_pulse -> exhaust_coupling -> body_resonance -> radiation",
            "pressure_state_variation": float(np.std(pressure_pulse)),
            "pressure_state_mean": float(np.mean(pressure_state)),
            "pressure_exhaust_frequency_hz": profile["exhaust_hz"],
            "pressure_body_frequency_hz": profile["body_hz"],
        }
    )
    return SourceRender(
        pressure=np.asarray(render.pressure, dtype=np.float64) + radiation,
        stems={
            **render.stems,
            "pressure_pulse": pressure_pulse,
            "exhaust_coupling": exhaust_coupling,
            "body_resonance": body_resonance,
            "radiation": radiation,
            "low_frequency_body": radiation,
        },
        diagnostics=diagnostics,
    ).validate()


def _component_source(render: SourceRender, stem_names: tuple[str, ...]) -> np.ndarray:
    if not stem_names:
        return np.asarray(render.pressure, dtype=np.float64)
    missing = [name for name in stem_names if name not in render.stems]
    if missing:
        raise ValueError(f"render is missing required low-frequency stem(s): {', '.join(missing)}")
    return sum((np.asarray(render.stems[name], dtype=np.float64) for name in stem_names), np.zeros_like(render.pressure))


def _causal_resonator(
    pressure: np.ndarray, frequency_hz: float, quality: float, sample_rate_hz: int
) -> np.ndarray:
    """Second-order bandpass recurrence using present and past samples only."""
    radius = float(np.exp(-np.pi * frequency_hz / (quality * sample_rate_hz)))
    feedback = 2.0 * radius * np.cos(2.0 * np.pi * frequency_hz / sample_rate_hz)
    drive = 1.0 - radius
    output = np.zeros_like(pressure, dtype=np.float64)
    previous_input = np.zeros(2, dtype=np.float64)
    previous_previous_input = np.zeros(2, dtype=np.float64)
    previous_output = np.zeros(2, dtype=np.float64)
    previous_previous_output = np.zeros(2, dtype=np.float64)
    for index, current_input in enumerate(pressure):
        output[index] = (
            drive * (current_input - previous_previous_input)
            + feedback * previous_output
            - radius * radius * previous_previous_output
        )
        previous_previous_input, previous_input = previous_input, current_input
        previous_previous_output, previous_output = previous_output, output[index]
    return output
