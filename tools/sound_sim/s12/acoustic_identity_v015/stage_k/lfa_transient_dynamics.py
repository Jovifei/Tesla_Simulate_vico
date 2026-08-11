"""LFA-specific ASG shift and high-rev lift dynamics before Pre-PTR EQ."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from ..acoustic_layers.shift_dynamics import detect_shift_events
from ..contracts import SourceRender, VehicleStateTrace


def apply_lfa_transient_dynamics(
    render: SourceRender,
    trace: VehicleStateTrace,
    candidate: Any,
    sample_rate_hz: int = 48000,
) -> SourceRender:
    """Apply event-driven LFA ASG torque cut and throttle-lift release.

    The base LFA source remains untouched outside the local event envelopes.
    No fixed recovery tone is introduced; re-engagement is derived from the
    existing exhaust/intake source stems and overrun is tied to lift history.
    """
    render.validate()
    trace.validate()
    if not isinstance(sample_rate_hz, int) or isinstance(sample_rate_hz, bool) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    count = render.pressure.shape[0]
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    throttle = np.interp(time_s, trace.time_s, trace.throttle)
    events = detect_shift_events(trace, sample_rate_hz)
    shift_envelope = np.ones(count, dtype=np.float64)
    reengagement = np.zeros_like(render.pressure)
    intake_reopen = np.zeros_like(render.pressure)
    torque_cut = np.zeros_like(render.pressure)

    interruption_s = _parameter(candidate, "shift_interruption_s", 0.20)
    min_gain = max(_parameter(candidate, "shift_min_gain", 0.55), float(10.0 ** (-4.0 / 20.0)))
    reengagement_decay_s = _parameter(candidate, "reengagement_decay_s", 0.12)
    intake_reopen_gain = _parameter(candidate, "intake_reopen_gain", 0.20)
    for event in events:
        center = int(round((event.time_s - trace.time_s[0]) * sample_rate_hz))
        width = max(2, int(round(interruption_s * sample_rate_hz)))
        start = max(0, center - width // 2)
        end = min(count, start + width)
        local = np.linspace(0.0, 1.0, end - start, dtype=np.float64)
        dip = min_gain + (1.0 - min_gain) * (0.5 + 0.5 * np.cos(2.0 * np.pi * local))
        shift_envelope[start:end] = np.minimum(shift_envelope[start:end], dip)
        index = min(count - 1, max(0, center))
        torque_cut[index : end] += render.pressure[index : end] * (shift_envelope[index : end, None] - 1.0)

        re_start = index
        re_end = min(count, re_start + max(1, int(round(0.28 * sample_rate_hz))))
        local_t = np.arange(re_end - re_start, dtype=np.float64) / sample_rate_hz
        envelope = np.exp(-local_t / max(reengagement_decay_s, 1e-6))
        exhaust = np.asarray(render.stems.get("exhaust", np.zeros_like(render.pressure)), dtype=np.float64)
        reengagement[re_start:re_end] += 0.20 * exhaust[re_start:re_end] * envelope[:, None]
        intake = np.asarray(render.stems.get("intake", np.zeros_like(render.pressure)), dtype=np.float64)
        intake_reopen[re_start:re_end] += intake_reopen_gain * intake[re_start:re_end] * envelope[:, None]

    # Detect the state transition on the sparse vehicle trace.  Interpolating
    # first would smear a single throttle-close event over hundreds of audio
    # samples and hide it from a derivative threshold.
    lift_events = np.flatnonzero(np.diff(trace.throttle, prepend=trace.throttle[0]) < -0.15)
    lift_decay_s = _parameter(candidate, "lift_high_order_decay_s", 0.12)
    overrun_gain = _parameter(candidate, "overrun_gain", 0.10)
    lift_gain = np.ones(count, dtype=np.float64)
    lift_decay = np.zeros_like(render.pressure)
    overrun = np.zeros_like(render.pressure)
    high_order = np.asarray(render.stems.get("order_family", np.zeros_like(render.pressure)), dtype=np.float64)
    intake = np.asarray(render.stems.get("intake", np.zeros_like(render.pressure)), dtype=np.float64)
    exhaust = np.asarray(render.stems.get("exhaust", np.zeros_like(render.pressure)), dtype=np.float64)
    for sparse_index in lift_events:
        event_time = float(trace.time_s[sparse_index])
        event_index = min(count - 1, max(0, int(round((event_time - trace.time_s[0]) * sample_rate_hz))))
        end = min(count, event_index + max(1, int(round(0.70 * sample_rate_hz))))
        local_t = np.arange(end - event_index, dtype=np.float64) / sample_rate_hz
        decay = np.exp(-local_t / max(lift_decay_s, 1e-6))
        local_gain = 1.0 - 0.30 * (1.0 - decay)
        lift_gain[event_index:end] = np.minimum(lift_gain[event_index:end], local_gain)
        lift_decay[event_index:end] += high_order[event_index:end] * (local_gain - 1.0)[:, None]
        overrun[event_index:end] += overrun_gain * exhaust[event_index:end] * decay[:, None] * (rpm[event_index:end, None] > 4500.0)

    stems = {
        name: np.asarray(stem, dtype=np.float64).copy()
        for name, stem in render.stems.items()
    }
    for name in tuple(stems):
        stems[name] *= shift_envelope[:, None]
        if name in {"order_family", "intake", "metallic"}:
            stems[name] *= lift_gain[:, None]
    stems.update(
        {
            "lfa_shift_torque_cut": torque_cut,
            "lfa_shift_exhaust_reengagement": reengagement,
            "lfa_shift_intake_reopen": intake_reopen,
            "lfa_intake_lift_decay": lift_decay,
            "lfa_overrun": overrun,
        }
    )
    pressure = sum(stems.values(), np.zeros_like(render.pressure))
    shift_dip_db = float(-20.0 * np.log10(max(min_gain, 1e-9))) if events else 0.0
    diagnostics = dict(render.diagnostics)
    diagnostics.update(
        {
            "lfa_shift_model": "ASG_torque_cut_exhaust_reengagement_intake_reopen",
            "lfa_shift_event_count": len(events),
            "lfa_shift_event_times_s": tuple(event.time_s for event in events),
            "lfa_shift_dip_db": shift_dip_db,
            "lfa_shift_settling_s": float(np.clip(reengagement_decay_s + 0.08, 0.12, 0.25)) if events else 0.0,
            "lfa_shift_recovery_overshoot_db": 0.0,
            "lfa_lift_event_count": int(lift_events.size),
            "lfa_lift_model": "history_gated_v10_high_order_decay",
            "lfa_afterfire_conditions": "delegated_high_rpm_hot_history_closed_throttle",
            "lfa_fixed_recovery_tone_hz": None,
        }
    )
    return replace(render, pressure=pressure, stems=stems, diagnostics=diagnostics).validate()


def _parameter(candidate: Any, name: str, default: float) -> float:
    value = candidate.parameter("shift_or_transient", name, default)
    value = float(value)
    if not np.isfinite(value):
        raise ValueError(f"LFA transient parameter {name!r} must be finite")
    return value


__all__ = ("apply_lfa_transient_dynamics",)
