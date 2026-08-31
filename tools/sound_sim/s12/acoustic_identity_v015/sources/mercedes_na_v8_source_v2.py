"""Synthetic C63 W204 M156 cross-plane V8 source for Stage J.

This is a deterministic, event-driven pre-PTR source.  It is deliberately an
acoustic study, not a recording, calibration, or OEM reproduction.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace


_DEFAULTS = {
    "bank_phase_offset_deg": 0.0,
    "pulse_width_scale": 1.0,
    "bark_resonance_scale": 1.0,
    "mechanical_texture_scale": 1.0,
    "high_rpm_growth_scale": 1.0,
}
_RANGES = {
    "bank_phase_offset_deg": (-45.0, 45.0),
    "pulse_width_scale": (0.60, 1.80),
    "bark_resonance_scale": (0.50, 1.60),
    "mechanical_texture_scale": (0.50, 1.80),
    "high_rpm_growth_scale": (0.50, 1.80),
}
_BANK_PATTERN = np.asarray((0, 1, 0, 1, 1, 0, 1, 0), dtype=np.int64)


def render_c63_w204_v2(
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48000,
    overrides: Mapping[str, float] | None = None,
) -> SourceRender:
    """Render a finite synthetic M156 pre-PTR pressure and named stems.

    The eight-event cross-plane bank pattern schedules pressure pulses.  The
    AMG bark and mechanical components are driven by those pulses but use
    RPM-integrated moving orders, never a fixed-frequency centre tone.
    """
    trace.validate()
    if not isinstance(sample_rate_hz, int) or isinstance(sample_rate_hz, bool) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    values = _validated_overrides(overrides)
    count = int(round((trace.time_s[-1] - trace.time_s[0]) * sample_rate_hz)) + 1
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    load = np.interp(time_s, trace.time_s, trace.load)
    throttle = np.interp(time_s, trace.time_s, trace.throttle)
    phase_rev = np.cumsum(rpm) / (60.0 * sample_rate_hz)

    left_pulses, right_pulses, event_count = _cross_plane_bank_pulses(
        phase_rev, rpm, load, throttle, sample_rate_hz, values
    )
    pulse_width_s = 0.00165 * values["pulse_width_scale"]
    left_envelope = _decay_envelope(left_pulses, pulse_width_s, sample_rate_hz)
    right_envelope = _decay_envelope(right_pulses, pulse_width_s * 0.88, sample_rate_hz)
    pulse_envelope = left_envelope + right_envelope

    high_rpm = np.clip((rpm - 2600.0) / 4200.0, 0.0, 1.0)
    bark_growth = 1.0 + (values["high_rpm_growth_scale"] - 1.0) * high_rpm
    left_phase = 2.0 * np.pi * phase_rev
    right_phase = left_phase + np.deg2rad(values["bank_phase_offset_deg"])

    # Each component is phase/order coupled.  The unequal bank orders and
    # cross-plane pulse schedule retain the loping left/right cadence.
    exhaust_left = 0.068 * left_envelope * (
        np.sin(left_phase * 1.70) + 0.42 * np.sin(left_phase * 3.40 + 0.31)
    )
    exhaust_right = 0.068 * right_envelope * (
        np.sin(right_phase * 2.30 + 0.18) + 0.38 * np.sin(right_phase * 4.60 + 0.52)
    )
    exhaust_left_bank = np.column_stack((exhaust_left, 0.45 * exhaust_left))
    exhaust_right_bank = np.column_stack((0.45 * exhaust_right, exhaust_right))
    exhaust = exhaust_left_bank + exhaust_right_bank

    bark_order = 7.60 * values["bark_resonance_scale"]
    bark_mode = (
        np.sin(left_phase * bark_order + 0.24)
        + 0.47 * np.sin(left_phase * bark_order * 1.82 + 0.71)
        + 0.21 * np.sin(right_phase * bark_order * 2.54 + 1.03)
    )
    bark_mono = 0.046 * pulse_envelope * (0.14 + 0.86 * throttle) * bark_growth * bark_mode
    bark = np.column_stack((0.61 * bark_mono, bark_mono))

    # Valve-train and accessory texture has deterministic phase beating rather
    # than broadband noise.  It stays audible after a closed-throttle lift.
    mechanical_mode = (
        0.64 * np.sin(left_phase * 9.25 + 0.18 * np.sin(left_phase * 0.5))
        + 0.36 * np.sin(right_phase * 13.70 + 0.37)
    )
    mechanical_mono = (
        0.010
        * values["mechanical_texture_scale"]
        * (0.33 + 0.67 * load)
        * (0.35 + 0.65 * high_rpm)
        * mechanical_mode
    )
    mechanical = np.column_stack((mechanical_mono, 0.73 * mechanical_mono))

    lift_envelope, closed_throttle_event_count = _closed_throttle_envelope(throttle, rpm, sample_rate_hz)
    lift_mono = 0.016 * lift_envelope * np.sin(left_phase * 5.35 + 0.48)
    lift = np.column_stack((lift_mono, 0.58 * lift_mono))

    state = _state_label(throttle)
    usage = {
        name: "active" if not np.isclose(values[name], default) else "inactive"
        for name, default in _DEFAULTS.items()
    }
    render = SourceRender(
        pressure=exhaust + bark + mechanical + lift,
        stems={
            "exhaust": exhaust,
            "exhaust_left_bank": exhaust_left_bank,
            "exhaust_right_bank": exhaust_right_bank,
            "bark": bark,
            "mechanical": mechanical,
            "closed_throttle_tail": lift,
        },
        diagnostics={
            "vehicle_id": "c63_w204",
            "scope": "synthetic; uncalibrated; not OEM reproduction",
            "engine": "M156 6.2L naturally aspirated V8",
            "bank_timing": "cross_plane_v8_event_pulses",
            "event_count": event_count,
            "closed_throttle_event_count": closed_throttle_event_count,
            "moving_order_model": True,
            "state": state,
            "parameter_usage": usage,
            "candidate_source_overrides": dict(values),
        },
    )
    return render.validate()


def _validated_overrides(overrides: Mapping[str, float] | None) -> dict[str, float]:
    if overrides is None:
        return dict(_DEFAULTS)
    if not isinstance(overrides, Mapping):
        raise ValueError("overrides must be a mapping")
    unknown = set(overrides) - set(_DEFAULTS)
    if unknown:
        raise ValueError(f"unsupported C63 overrides: {sorted(unknown)!r}")
    values = dict(_DEFAULTS)
    for name, raw_value in overrides.items():
        value = float(raw_value)
        if not np.isfinite(value):
            raise ValueError(f"override {name!r} must be finite")
        low, high = _RANGES[name]
        if not low <= value <= high:
            raise ValueError(f"override {name!r} must be in [{low}, {high}]")
        values[name] = value
    return values


def _cross_plane_bank_pulses(
    phase_rev: np.ndarray,
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    sample_rate_hz: int,
    values: Mapping[str, float],
) -> tuple[np.ndarray, np.ndarray, int]:
    count = phase_rev.size
    event_id = np.floor(phase_rev * 4.0).astype(np.int64)
    positions = np.flatnonzero(np.r_[True, np.diff(event_id) > 0])
    left = np.zeros(count, dtype=np.float64)
    right = np.zeros(count, dtype=np.float64)
    for position in positions:
        amplitude = (0.32 + 0.68 * load[position]) * (0.28 + 0.72 * throttle[position])
        bank = _BANK_PATTERN[event_id[position] % _BANK_PATTERN.size]
        if bank == 0:
            left[position] += amplitude
        else:
            offset_s = (values["bank_phase_offset_deg"] / 360.0) * 60.0 / max(rpm[position], 1.0)
            shifted = int(np.clip(round(position + offset_s * sample_rate_hz), 0, count - 1))
            right[shifted] += amplitude
    return left, right, int(positions.size)


def _decay_envelope(pulses: np.ndarray, decay_s: float, sample_rate_hz: int) -> np.ndarray:
    envelope = np.zeros_like(pulses)
    pole = float(np.exp(-1.0 / max(decay_s * sample_rate_hz, 1.0)))
    for index in range(1, pulses.size):
        envelope[index] = pole * envelope[index - 1] + pulses[index]
    return envelope


def _closed_throttle_envelope(throttle: np.ndarray, rpm: np.ndarray, sample_rate_hz: int) -> tuple[np.ndarray, int]:
    events = np.flatnonzero((np.diff(throttle, prepend=throttle[0]) < -0.35) & (rpm > 2200.0))
    pulses = np.zeros_like(throttle)
    pulses[events] = 1.0
    return _decay_envelope(pulses, 0.115, sample_rate_hz), int(events.size)


def _state_label(throttle: np.ndarray) -> str:
    if float(np.mean(throttle)) < 0.15:
        return "idle"
    if throttle[-1] < 0.15:
        return "closed_throttle"
    return "acceleration"
