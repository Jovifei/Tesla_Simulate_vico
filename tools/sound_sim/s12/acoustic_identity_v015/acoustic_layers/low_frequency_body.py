"""Causal synthetic low-frequency engine-body resonators."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from ..contracts import SourceRender


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


def apply_low_frequency_body(
    render: SourceRender, vehicle_id: str, sample_rate_hz: int = 48000
) -> SourceRender:
    """Add a causal 40--200 Hz resonator bank without changing source stems."""
    render.validate()
    if vehicle_id not in _BODY_PROFILES:
        raise ValueError(f"unsupported vehicle_id: {vehicle_id!r}")
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 1000:
        raise ValueError("sample_rate_hz must be an integer >= 1000")

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
