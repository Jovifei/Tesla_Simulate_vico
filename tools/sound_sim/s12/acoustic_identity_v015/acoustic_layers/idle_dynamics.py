"""Deterministic idle-cycle and mechanical pressure layers."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace


_PROFILES: Mapping[str, Mapping[str, float]] = {
    "ferrari_458": {"events_per_rev": 4.0, "seed": 1.7, "variation": 0.12, "jitter_ms": 0.30, "combustion_gain": 0.020, "accessory_order": 1.65, "valve_hz": 1850.0, "crank_order": 1.0},
    "hellcat": {"events_per_rev": 4.0, "seed": 4.1, "variation": 0.18, "jitter_ms": 0.55, "combustion_gain": 0.040, "accessory_order": 2.36, "valve_hz": 930.0, "crank_order": 0.5},
    "rx7_fd": {"events_per_rev": 2.0, "seed": 7.3, "variation": 0.10, "jitter_ms": 0.42, "combustion_gain": 0.017, "accessory_order": 1.35, "valve_hz": 1320.0, "crank_order": 1.5},
}
_SCOPE = "synthetic; uncalibrated; not OEM reproduction"


def apply_idle_dynamics(
    render: SourceRender, vehicle_id: str, trace: VehicleStateTrace, sample_rate_hz: int = 48000
) -> SourceRender:
    """Add vehicle-specific cycle fluctuation and engine-phase mechanical idle layers."""
    render.validate()
    trace.validate()
    if vehicle_id not in _PROFILES:
        raise ValueError(f"unsupported vehicle_id: {vehicle_id!r}")
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    count = render.pressure.shape[0]
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    load = np.interp(time_s, trace.time_s, trace.load)
    profile = _PROFILES[vehicle_id]
    idle = np.clip((1850.0 - rpm) / 850.0, 0.0, 1.0)
    phase = np.cumsum(rpm) / (60.0 * sample_rate_hz)
    event_id = np.floor(phase * profile["events_per_rev"]).astype(np.int64)
    starts = np.flatnonzero(np.r_[True, np.diff(event_id) > 0])
    impulses = np.zeros(count, dtype=np.float64)
    variation_values: list[float] = []
    jitter_values: list[int] = []
    for sample in starts:
        cycle = event_id[sample]
        variation = np.sin(cycle * 12.9898 + profile["seed"]) * profile["variation"]
        jitter = int(round(np.sin(cycle * 78.233 + profile["seed"] * 3.0) * profile["jitter_ms"] * sample_rate_hz / 1000.0))
        target = min(max(sample + jitter, 0), count - 1)
        impulses[target] += idle[sample] * (0.55 + 0.45 * load[sample]) * (1.0 + variation)
        variation_values.append(float(variation))
        jitter_values.append(jitter)
    combustion_mono = profile["combustion_gain"] * _ring(impulses, profile["valve_hz"] * 0.47, 0.028, sample_rate_hz)
    combustion = np.column_stack((combustion_mono, 0.79 * combustion_mono))
    accessory_mono = 0.006 * idle * (0.55 + load) * (
        np.sin(2.0 * np.pi * phase * profile["accessory_order"]) + 0.28 * np.sin(2.0 * np.pi * phase * profile["accessory_order"] * 2.0)
    )
    accessory = np.column_stack((0.70 * accessory_mono, accessory_mono))
    valvetrain_mono = 0.010 * idle * _ring(impulses, profile["valve_hz"], 0.010, sample_rate_hz)
    valvetrain = np.column_stack((valvetrain_mono, 0.66 * valvetrain_mono))
    crank_mono = 0.010 * idle * (0.65 + 0.35 * load) * np.sin(2.0 * np.pi * phase * profile["crank_order"])
    crank = np.column_stack((0.88 * crank_mono, crank_mono))
    idle_layer = combustion + accessory + valvetrain + crank
    diagnostics = dict(render.diagnostics)
    diagnostics.update(
        {
            "idle_dynamics_model": "deterministic_cycle_variation_engine_phase_mechanics",
            "idle_scope": _SCOPE,
            "idle_cycle_amplitude_std": float(np.std(variation_values)) if variation_values else 0.0,
            "idle_phase_jitter_samples_peak": float(max((abs(value) for value in jitter_values), default=0)),
            "idle_event_count": int(np.count_nonzero(impulses)),
        }
    )
    return SourceRender(
        pressure=np.asarray(render.pressure, dtype=np.float64) + idle_layer,
        stems={**render.stems, "idle_combustion_variation": combustion, "idle_accessory": accessory, "idle_valvetrain": valvetrain, "idle_crank": crank},
        diagnostics=diagnostics,
    ).validate()


def _ring(impulses: np.ndarray, frequency_hz: float, decay_s: float, sample_rate_hz: int) -> np.ndarray:
    radius = float(np.exp(-1.0 / (decay_s * sample_rate_hz)))
    feedback = 2.0 * radius * np.cos(2.0 * np.pi * frequency_hz / sample_rate_hz)
    output = np.zeros_like(impulses, dtype=np.float64)
    for index, impulse in enumerate(impulses):
        previous = output[index - 1] if index else 0.0
        previous_two = output[index - 2] if index > 1 else 0.0
        output[index] = feedback * previous - radius * radius * previous_two + impulse * np.sin(2.0 * np.pi * frequency_hz / sample_rate_hz)
    return output
