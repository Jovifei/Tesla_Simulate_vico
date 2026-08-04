"""Deterministic closed-throttle exhaust-pressure transients."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace


_PROFILES: Mapping[str, Mapping[str, float]] = {
    "ferrari_458": {"min_rpm": 4200.0, "cluster_stride": 21.0, "gain": 0.060, "low_hz": 115.0, "high_hz": 1550.0, "stereo": 0.72},
    "hellcat": {"min_rpm": 3300.0, "cluster_stride": 17.0, "gain": 0.095, "low_hz": 78.0, "high_hz": 920.0, "stereo": 0.62},
    "rx7_fd": {"min_rpm": 4300.0, "cluster_stride": 25.0, "gain": 0.045, "low_hz": 135.0, "high_hz": 2050.0, "stereo": 0.70},
}
_SCOPE = "synthetic; uncalibrated; not OEM reproduction"


def apply_afterfire(
    render: SourceRender, vehicle_id: str, trace: VehicleStateTrace, sample_rate_hz: int = 48000
) -> SourceRender:
    """Add finite pop/crackle pressure events only after a hot throttle-close."""
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
    throttle = np.interp(time_s, trace.time_s, trace.throttle)
    phase = np.cumsum(rpm) / (60.0 * sample_rate_hz)
    thermal = _thermal_proxy(rpm, load, sample_rate_hz)
    closed = throttle < 0.12
    closure = np.r_[False, (throttle[:-1] >= 0.12) & closed[1:]]
    close_memory = np.zeros(count, dtype=np.float64)
    for index in range(1, count):
        close_memory[index] = max(float(closure[index]), close_memory[index - 1] - 1.0 / (0.52 * sample_rate_hz))
    profile = _PROFILES[vehicle_id]
    event_id = np.floor(phase * 4.0).astype(np.int64)
    starts = np.flatnonzero(np.r_[True, np.diff(event_id) > 0])
    impulses = np.zeros(count, dtype=np.float64)
    for sample in starts:
        eligible = closed[sample] and close_memory[sample] > 0.0 and rpm[sample] >= profile["min_rpm"] and thermal[sample] >= 0.16
        cluster = event_id[sample] % int(profile["cluster_stride"]) in (0, 1, 4)
        if eligible and cluster:
            impulses[sample] = profile["gain"] * thermal[sample] * np.clip((rpm[sample] - profile["min_rpm"]) / 2600.0, 0.25, 1.0)
    low = _ring(impulses, profile["low_hz"], 0.040, sample_rate_hz)
    high = _ring(impulses, profile["high_hz"], 0.012, sample_rate_hz)
    mono = low + 0.42 * high
    afterfire = np.column_stack((mono, profile["stereo"] * mono))
    diagnostics = dict(render.diagnostics)
    diagnostics.update(
        {
            "afterfire_model": "thermal_high_rpm_closed_throttle_event_clusters",
            "afterfire_scope": _SCOPE,
            "afterfire_event_count": int(np.count_nonzero(impulses)),
            "afterfire_thermal_peak": float(np.max(thermal)),
            "afterfire_closed_throttle_samples": int(np.count_nonzero(closed)),
        }
    )
    return SourceRender(
        pressure=np.asarray(render.pressure, dtype=np.float64) + afterfire,
        stems={**render.stems, "afterfire": afterfire},
        diagnostics=diagnostics,
    ).validate()


def _thermal_proxy(rpm: np.ndarray, load: np.ndarray, sample_rate_hz: int) -> np.ndarray:
    target = np.clip((rpm - 1200.0) / 5800.0, 0.0, 1.0) * (0.18 + 0.82 * load)
    state = np.zeros_like(target, dtype=np.float64)
    for index in range(1, target.size):
        state[index] = state[index - 1] + (target[index] - state[index - 1]) / (0.22 * sample_rate_hz)
    return state


def _ring(impulses: np.ndarray, frequency_hz: float, decay_s: float, sample_rate_hz: int) -> np.ndarray:
    radius = float(np.exp(-1.0 / (decay_s * sample_rate_hz)))
    feedback = 2.0 * radius * np.cos(2.0 * np.pi * frequency_hz / sample_rate_hz)
    output = np.zeros_like(impulses, dtype=np.float64)
    for index, impulse in enumerate(impulses):
        previous = output[index - 1] if index else 0.0
        previous_two = output[index - 2] if index > 1 else 0.0
        output[index] = feedback * previous - radius * radius * previous_two + impulse * np.sin(2.0 * np.pi * frequency_hz / sample_rate_hz)
    return output
