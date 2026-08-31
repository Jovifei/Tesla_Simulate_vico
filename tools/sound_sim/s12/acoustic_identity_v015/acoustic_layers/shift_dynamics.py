"""Deterministic RPM-step transmission dynamics before the frozen PTR adapter."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, sosfilt

from ..contracts import SourceRender, VehicleStateTrace
from .realism_profiles import get_realism_profile


@dataclass(frozen=True)
class ShiftEvent:
    time_s: float
    sample_index: int
    rpm_before: float
    rpm_after: float
    rpm_drop: float


_DERIVATIVE_THRESHOLD_RPM_PER_S = -1500.0
_MIN_DROP_RPM = 250.0
_MIN_STEP_S = 0.020
_MAX_STEP_S = 0.250
_RECOVERY_WINDOW_S = 0.350
_REFRACTORY_S = 0.500


def detect_shift_events(trace: VehicleStateTrace, sample_rate_hz: int = 48000) -> tuple[ShiftEvent, ...]:
    """Detect local RPM drops that have a later recovery, not ordinary lift-off."""
    trace.validate()
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 1000:
        raise ValueError("sample_rate_hz must be an integer >= 1000")
    derivative = np.gradient(trace.rpm, trace.time_s)
    candidates = (derivative < _DERIVATIVE_THRESHOLD_RPM_PER_S) & (trace.throttle > 0.30)
    indices = np.flatnonzero(candidates)
    if not indices.size:
        return ()
    groups: list[tuple[int, int]] = []
    start = int(indices[0])
    previous = start
    for index in indices[1:]:
        index = int(index)
        if index != previous + 1:
            groups.append((start, previous))
            start = index
        previous = index
    groups.append((start, previous))

    events: list[ShiftEvent] = []
    last_time = -float("inf")
    for start, end in groups:
        duration = float(trace.time_s[end] - trace.time_s[start])
        if duration < _MIN_STEP_S or duration > _MAX_STEP_S:
            continue
        before_index = max(0, start - 1)
        after_index = min(trace.rpm.size - 1, end + 1)
        rpm_before = float(trace.rpm[before_index])
        rpm_after = float(trace.rpm[after_index])
        drop = rpm_before - rpm_after
        if drop < max(_MIN_DROP_RPM, 0.04 * max(rpm_before, 1.0)):
            continue
        recovery_end = min(trace.rpm.size - 1, end + int(np.ceil(_RECOVERY_WINDOW_S / np.median(np.diff(trace.time_s)))))
        if float(np.max(trace.rpm[after_index : recovery_end + 1])) - rpm_after < 0.30 * drop:
            continue
        if float(trace.time_s[start]) - last_time < _REFRACTORY_S:
            continue
        local = start + int(np.argmin(derivative[start : end + 1]))
        time_s = float(trace.time_s[local])
        events.append(ShiftEvent(time_s, int(round(time_s * sample_rate_hz)), rpm_before, rpm_after, drop))
        last_time = time_s
    return tuple(events)


def apply_shift_dynamics(
    render: SourceRender,
    vehicle_id: str,
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48000,
) -> SourceRender:
    """Apply torque interruption, mechanical impact, and recovery boom stems."""
    render.validate()
    trace.validate()
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    profile = get_realism_profile(vehicle_id)
    count = render.pressure.shape[0]
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    events = detect_shift_events(trace, sample_rate_hz)
    envelope = np.ones(count, dtype=np.float64)
    impact = np.zeros_like(render.pressure, dtype=np.float64)
    boom = np.zeros_like(render.pressure, dtype=np.float64)
    for event in events:
        start = max(0, int(round((event.time_s - profile.shift.jerk_s / 3.0 - trace.time_s[0]) * sample_rate_hz)))
        end = min(count, int(round((event.time_s + profile.shift.jerk_s - trace.time_s[0]) * sample_rate_hz)))
        if end <= start:
            continue
        width = end - start
        dip_end = max(1, int(round(width * 0.40)))
        envelope[start : start + dip_end] = np.minimum(envelope[start : start + dip_end], np.linspace(1.0, 0.22, dip_end))
        envelope[start + dip_end : end] = np.minimum(envelope[start + dip_end : end], np.linspace(0.22, 1.0, width - dip_end))
        index = min(count - 1, max(0, int(round((event.time_s - trace.time_s[0]) * sample_rate_hz))))
        impulse = np.zeros((count, 2), dtype=np.float64)
        impulse[index, :] = profile.shift.impact_gain * 0.50
        impact += sosfilt(butter(2, 350.0 / (sample_rate_hz / 2.0), btype="low", output="sos"), impulse, axis=0)
        boom_start = min(count, index + int(round(0.040 * sample_rate_hz)))
        boom_end = min(count, index + int(round(0.180 * sample_rate_hz)))
        if boom_end > boom_start:
            duration = (boom_end - boom_start) / sample_rate_hz
            t = np.arange(boom_end - boom_start, dtype=np.float64) / sample_rate_hz
            local = np.sin(2.0 * np.pi * profile.shift.recovery_hz * t) * np.exp(-6.0 * t / max(duration, 1.0 / sample_rate_hz))
            local *= np.maximum(0.0, 1.0 - t / max(duration, 1.0 / sample_rate_hz))
            boom[boom_start:boom_end, 0] += profile.shift.recovery_gain * 0.40 * local
            boom[boom_start:boom_end, 1] += profile.shift.recovery_gain * 0.36 * local

    interruption = np.asarray(render.pressure, dtype=np.float64) * (envelope[:, np.newaxis] - 1.0)
    pressure = np.asarray(render.pressure, dtype=np.float64) * envelope[:, np.newaxis] + impact + boom
    stems = {name: np.asarray(stem, dtype=np.float64) * envelope[:, np.newaxis] for name, stem in render.stems.items()}
    stems.update(
        {
            "shift_torque_interruption": interruption,
            "shift_impact": impact,
            "shift_recovery_boom": boom,
        }
    )
    diagnostics = dict(render.diagnostics)
    diagnostics.update(
        {
            "shift_model": "local_rpm_drop_recovery_transmission_event",
            "shift_event_count": len(events),
            "shift_event_times_s": tuple(event.time_s for event in events),
            "shift_rpm_drops": tuple(event.rpm_drop for event in events),
            "shift_gearbox": profile.shift.gearbox,
            "shift_impact_energy": float(np.sum(np.square(impact))),
            "shift_recovery_boom_energy": float(np.sum(np.square(boom))),
        }
    )
    return SourceRender(pressure=pressure, stems=stems, diagnostics=diagnostics).validate()


__all__ = ("ShiftEvent", "apply_shift_dynamics", "detect_shift_events")
