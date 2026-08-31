"""Synthetic Stage-K Mercedes-AMG C63 W204 (M156) source.

The M156 is represented as an event-driven cross-plane V8.  Stage J exposed
``bark_resonance_scale``; that name was misleading because it moved the bark
order instead of changing a resonator's level or decay.  Stage K keeps the
bank event train and replaces that control with explicit primary order,
partial mix, event decay and high-RPM compression controls.

This module is an offline C/synthetic source.  It is uncalibrated and is not
an OEM reproduction.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace


_DEFAULTS = {
    "bank_phase_offset_deg": 0.0,
    "pulse_width_scale": 1.0,
    "bark_primary_order": 7.60,
    "bark_upper_partial_mix": 0.12,
    "bark_decay_ms": 7.0,
    "mechanical_upper_tilt_db": -6.0,
    "high_rpm_compression": 0.50,
    "mechanical_texture_scale": 1.0,
    "high_rpm_growth_scale": 1.0,
}
_RANGES = {
    "bank_phase_offset_deg": (-45.0, 45.0),
    "pulse_width_scale": (0.60, 1.80),
    "bark_primary_order": (7.20, 7.80),
    "bark_upper_partial_mix": (0.06, 0.20),
    "bark_decay_ms": (4.0, 12.0),
    "mechanical_upper_tilt_db": (-9.0, -3.0),
    "high_rpm_compression": (0.35, 0.65),
    "mechanical_texture_scale": (0.50, 1.80),
    "high_rpm_growth_scale": (0.50, 1.80),
}
_BANK_PATTERN = np.asarray((0, 1, 0, 1, 1, 0, 1, 0), dtype=np.int64)


def render_c63_w204_v3(
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48000,
    overrides: Mapping[str, float] | None = None,
) -> SourceRender:
    """Render a deterministic, event-driven C63 pre-PTR source.

    The low-frequency exhaust and closed-throttle event train intentionally
    retain Stage-J timing.  Bark upper partials and mechanical upper modes are
    independently shaped so high-frequency roughness can be reduced without
    erasing the M156 body.
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
    growth = 1.0 + (values["high_rpm_growth_scale"] - 1.0) * high_rpm
    # Compression acts only on the growth delta, not on the fixed low-RPM
    # bark.  This narrows the idle-to-redline span without a final gain hack.
    growth = 1.0 + (growth - 1.0) * (1.0 - 0.55 * values["high_rpm_compression"] * high_rpm)
    # The control remains observable even when the growth seed is unity: a
    # higher compression value gently narrows high-RPM bark dynamics around
    # its nominal level, without touching the bank pressure train.
    growth *= 1.0 - 0.25 * (values["high_rpm_compression"] - 0.50) * high_rpm
    left_phase = 2.0 * np.pi * phase_rev
    right_phase = left_phase + np.deg2rad(values["bank_phase_offset_deg"])

    # This block is intentionally identical in structure and coefficients to
    # Stage J v2: cross-plane pressure identity and LF body remain protected.
    exhaust_left = 0.068 * left_envelope * (
        np.sin(left_phase * 1.70) + 0.42 * np.sin(left_phase * 3.40 + 0.31)
    )
    exhaust_right = 0.068 * right_envelope * (
        np.sin(right_phase * 2.30 + 0.18) + 0.38 * np.sin(right_phase * 4.60 + 0.52)
    )
    # Preserve each event's onset position while applying a short, causal
    # exhaust-path rise time.  This is a fixed source-domain propagation
    # effect, not a tunable broadband EQ or a post-PTR gain.
    exhaust_left_bank = np.column_stack(
        (_one_pole_smooth(exhaust_left, 0.00002, sample_rate_hz),
         _one_pole_smooth(0.45 * exhaust_left, 0.00002, sample_rate_hz))
    )
    exhaust_right_bank = np.column_stack(
        (_one_pole_smooth(0.45 * exhaust_right, 0.00002, sample_rate_hz),
         _one_pole_smooth(exhaust_right, 0.00002, sample_rate_hz))
    )
    exhaust = exhaust_left_bank + exhaust_right_bank

    # Bark is an event-shaped primary mode plus low-level, damped upper
    # partials.  All oscillators use the integrated RPM phase; no fixed tone
    # or stochastic noise is added.
    bark_events = _decay_envelope(left_pulses + right_pulses, values["bark_decay_ms"] / 1000.0, sample_rate_hz)
    # A sub-millisecond deterministic attack models the finite valve/exhaust
    # rise time and removes the v2 impulse edge that made the upper band harsh.
    bark_events = _one_pole_smooth(bark_events, 0.00080, sample_rate_hz)
    bark_primary = 0.86 * np.sin(left_phase * values["bark_primary_order"] + 0.24)
    upper_mode = (
        0.62 * np.sin(left_phase * values["bark_primary_order"] * 1.82 + 0.71)
        + 0.28 * np.sin(right_phase * values["bark_primary_order"] * 2.54 + 1.03)
    )
    bark_mode = bark_primary + values["bark_upper_partial_mix"] * upper_mode
    bark_level = 0.085
    bark_mono = bark_level * bark_events * (0.14 + 0.86 * throttle) * growth * bark_mode
    bark = np.column_stack((0.61 * bark_mono, bark_mono))

    # Mechanical texture is split into a stable lower mode and a quieter
    # upper mode.  The tilt parameter changes only the upper mode's amplitude.
    mechanical_low = (
        0.68 * np.sin(left_phase * 4.10 + 0.18 * np.sin(left_phase * 0.5))
        + 0.32 * np.sin(right_phase * 5.70 + 0.37)
    )
    mechanical_upper = (
        0.64 * np.sin(left_phase * 9.25 + 0.18 * np.sin(left_phase * 0.5))
        + 0.36 * np.sin(right_phase * 13.70 + 0.37)
    )
    upper_gain = float(10.0 ** (values["mechanical_upper_tilt_db"] / 20.0))
    mechanical_mode = mechanical_low + 0.85 * upper_gain * mechanical_upper
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
            "bark_primary": np.column_stack((0.61 * bark_events * (0.14 + 0.86 * throttle) * growth * bark_level * bark_primary, bark_events * (0.14 + 0.86 * throttle) * growth * bark_level * bark_primary)),
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
            "bark_model": "event_driven_primary_plus_damped_partials",
            "noise_model": "none_deterministic_event_driven",
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


def _one_pole_smooth(signal: np.ndarray, time_constant_s: float, sample_rate_hz: int) -> np.ndarray:
    """Causal event attack smoothing used only on the bark envelope."""
    output = np.zeros_like(signal)
    pole = float(np.exp(-1.0 / max(time_constant_s * sample_rate_hz, 1.0)))
    for index in range(1, signal.size):
        output[index] = pole * output[index - 1] + (1.0 - pole) * signal[index]
    return output


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


__all__ = ("render_c63_w204_v3",)
