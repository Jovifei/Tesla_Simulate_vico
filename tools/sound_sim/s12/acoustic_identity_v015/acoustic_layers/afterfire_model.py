"""Deterministic hot closed-throttle exhaust-pressure transients."""

from __future__ import annotations

import numpy as np
from scipy.signal import lfilter

from ..contracts import SourceRender, VehicleStateTrace
from .realism_profiles import REALISM_PROFILES, get_realism_profile


_SCOPE = "synthetic; uncalibrated; not OEM reproduction"


def apply_afterfire(
    render: SourceRender,
    vehicle_id: str,
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48000,
) -> SourceRender:
    """Add state-dependent, architecture-specific deterministic pop/crackle events."""
    render.validate()
    trace.validate()
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    profile = get_realism_profile(vehicle_id).afterfire
    count = render.pressure.shape[0]
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    load = np.interp(time_s, trace.time_s, trace.load)
    throttle = np.interp(time_s, trace.time_s, trace.throttle)
    thermal = _thermal_proxy(rpm, load, sample_rate_hz)
    closed = throttle < 0.15
    closure = np.r_[False, (throttle[:-1] >= 0.15) & closed[1:]]
    close_memory = _close_memory(closure, sample_rate_hz)
    phase = np.cumsum(rpm) / (60.0 * sample_rate_hz)
    event_id = np.floor(phase * profile.events_per_rev).astype(np.int64)
    starts = np.flatnonzero(np.r_[True, np.diff(event_id) > 0])
    impulses = np.zeros(count, dtype=np.float64)
    if starts.size:
        cluster = np.isin(event_id[starts] % profile.cluster_stride, (0, 1, 4))
        eligible = (
            closed[starts]
            & (close_memory[starts] > 0.0)
            & (rpm[starts] >= profile.min_rpm)
            & (thermal[starts] >= 0.16)
            & cluster
        )
        selected = starts[eligible]
        if selected.size:
            impulses[selected] = profile.gain * thermal[selected] * np.clip(
                (rpm[selected] - profile.min_rpm) / 2600.0, 0.25, 1.0
            )
    low = _ring(impulses, profile.low_hz, 0.040, sample_rate_hz)
    high = _ring(impulses, profile.high_hz, 0.012, sample_rate_hz)
    mono = low + 0.42 * high
    afterfire = np.column_stack((mono, profile.stereo * mono))
    centroid = _spectral_centroid(mono, sample_rate_hz)
    onset = np.flatnonzero(np.abs(mono) > 0.0)
    total_energy = float(np.sum(np.square(mono)))
    diagnostics = dict(render.diagnostics)
    diagnostics.update(
        {
            "afterfire_model": "thermal_high_rpm_closed_throttle_deterministic_architecture_events",
            "afterfire_scope": _SCOPE,
            "afterfire_event_count": int(np.count_nonzero(impulses)),
            "afterfire_thermal_peak": float(np.max(thermal)),
            "afterfire_closed_throttle_samples": int(np.count_nonzero(closed)),
            "afterfire_centroid_hz": centroid,
            "afterfire_onset_s": float(time_s[onset[0]]) if onset.size else None,
            "afterfire_decay_ratio": _decay_ratio(mono),
            "afterfire_events_per_rev": profile.events_per_rev,
        }
    )
    return SourceRender(
        pressure=np.asarray(render.pressure, dtype=np.float64) + afterfire,
        stems={**render.stems, "afterfire": afterfire},
        diagnostics=diagnostics,
    ).validate()


def _thermal_proxy(rpm: np.ndarray, load: np.ndarray, sample_rate_hz: int) -> np.ndarray:
    target = np.clip((rpm - 1200.0) / 5800.0, 0.0, 1.0) * (0.18 + 0.82 * load)
    alpha = 1.0 / (0.22 * sample_rate_hz)
    return lfilter([alpha], [1.0, -(1.0 - alpha)], target)


def _close_memory(closure: np.ndarray, sample_rate_hz: int) -> np.ndarray:
    indices = np.arange(closure.size, dtype=np.int64)
    last = np.maximum.accumulate(np.where(closure, indices, -1))
    age = indices - last
    memory = np.clip(1.0 - age / (0.52 * sample_rate_hz), 0.0, 1.0)
    return np.where(last >= 0, memory, 0.0)


def _ring(impulses: np.ndarray, frequency_hz: float, decay_s: float, sample_rate_hz: int) -> np.ndarray:
    radius = float(np.exp(-1.0 / (decay_s * sample_rate_hz)))
    feedback = 2.0 * radius * np.cos(2.0 * np.pi * frequency_hz / sample_rate_hz)
    drive = impulses * np.sin(2.0 * np.pi * frequency_hz / sample_rate_hz)
    return lfilter([1.0], [1.0, -feedback, radius * radius], drive)


def _spectral_centroid(signal: np.ndarray, sample_rate_hz: int) -> float:
    if not np.any(signal):
        return 0.0
    windowed = signal * np.hanning(signal.size)
    energy = np.square(np.abs(np.fft.rfft(windowed)))
    frequencies = np.fft.rfftfreq(signal.size, 1.0 / sample_rate_hz)
    total = float(energy.sum())
    return float(np.sum(frequencies * energy) / total) if total else 0.0


def _decay_ratio(signal: np.ndarray) -> float:
    energy = np.square(signal)
    if not np.any(energy):
        return 0.0
    split = max(1, int(round(signal.size * 0.75)))
    return float(energy[split:].sum() / energy.sum())


__all__ = ("REALISM_PROFILES", "apply_afterfire")
