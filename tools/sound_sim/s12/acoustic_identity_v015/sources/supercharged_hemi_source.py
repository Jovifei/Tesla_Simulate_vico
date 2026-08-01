"""Synthetic, uncalibrated Hellcat-inspired supercharged HEMI source."""

from __future__ import annotations

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace


def render_hellcat(trace: VehicleStateTrace, sample_rate_hz: int = 48000) -> SourceRender:
    """Render finite stereo pre-PTR pressure; this is not OEM reproduction."""
    trace.validate()
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    count = int(round((trace.time_s[-1] - trace.time_s[0]) * sample_rate_hz)) + 1
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    load = np.interp(time_s, trace.time_s, trace.load)
    throttle = np.interp(time_s, trace.time_s, trace.throttle)
    phase = np.cumsum(rpm) / (60.0 * sample_rate_hz)
    pressure_compensation = np.power(3000.0 / np.maximum(rpm, 850.0), 1.25)
    event_pressure_compensation = np.minimum(pressure_compensation, 2.0)
    event_id = np.floor(phase * 4.0).astype(np.int64)
    event_samples = np.flatnonzero(np.r_[True, np.diff(event_id) > 0])
    bank_pattern = np.array((0, 1, 0, 1, 1, 0, 1, 0), dtype=np.int64)
    left_impulses = np.zeros(count)
    right_impulses = np.zeros(count)
    for sample in event_samples:
        target = left_impulses if bank_pattern[event_id[sample] % bank_pattern.size] == 0 else right_impulses
        target[sample] = event_pressure_compensation[sample] * (0.45 + 0.55 * load[sample])

    left_envelope = np.zeros(count)
    right_envelope = np.zeros(count)
    left_pole = float(np.exp(-1.0 / (0.040 * sample_rate_hz)))
    right_pole = float(np.exp(-1.0 / (0.028 * sample_rate_hz)))
    for sample in range(1, count):
        left_envelope[sample] = left_pole * left_envelope[sample - 1] + left_impulses[sample]
        right_envelope[sample] = right_pole * right_envelope[sample - 1] + right_impulses[sample]
    left_mono = 0.055 * left_envelope * (
        np.sin(2.0 * np.pi * phase * 1.8) + 0.38 * np.sin(2.0 * np.pi * phase * 3.6)
    )
    right_mono = 0.055 * right_envelope * (
        np.sin(2.0 * np.pi * phase * 2.3 + 0.2) + 0.31 * np.sin(2.0 * np.pi * phase * 4.7)
    )
    exhaust_left_bank = np.column_stack((left_mono, 0.48 * left_mono))
    exhaust_right_bank = np.column_stack((0.48 * right_mono, right_mono))
    exhaust = exhaust_left_bank + exhaust_right_bank

    shaft_phase = np.cumsum(rpm * 2.36) / (60.0 * sample_rate_hz)
    blower_gain = 0.086 * pressure_compensation * np.square(load) * np.maximum(throttle, 0.05)
    blower_mono = blower_gain * (
        0.34 * np.sin(2.0 * np.pi * shaft_phase)
        + 0.94 * np.sin(2.0 * np.pi * shaft_phase * 5.0)
        + 0.38 * np.sin(2.0 * np.pi * shaft_phase * 10.0)
    )
    blower = np.column_stack((0.65 * blower_mono, blower_mono))
    compressor_envelope = np.zeros(count)
    compressor_pole = float(np.exp(-1.0 / (0.010 * sample_rate_hz)))
    for sample in range(1, count):
        compressor_envelope[sample] = compressor_pole * compressor_envelope[sample - 1] + left_impulses[sample] + right_impulses[sample]
    belt = np.sin(2.0 * np.pi * shaft_phase)
    compressor = compressor_envelope * np.sin(2.0 * np.pi * shaft_phase * 5.0 + 0.4)
    valvetrain = np.sin(2.0 * np.pi * phase * 7.0) * np.sin(2.0 * np.pi * phase * 0.5 + 0.3)
    casing_pressure_compensation = np.power(3000.0 / np.maximum(rpm, 850.0), 0.55)
    casing_mono = 0.030 * casing_pressure_compensation * (rpm > 0.0) * (0.30 + 0.70 * load) * (
        np.sin(2.0 * np.pi * phase * 72.0) + 0.35 * np.sin(2.0 * np.pi * phase * 96.0)
    )
    casing = np.column_stack((casing_mono, 0.78 * casing_mono))
    mechanical_mono = pressure_compensation * (0.010 * belt + 0.008 * valvetrain) + 0.012 * compressor + casing_mono
    mechanical = np.column_stack((mechanical_mono, 0.78 * mechanical_mono))
    intake_mono = 0.026 * pressure_compensation * (rpm > 0.0) * load * (0.4 + throttle) * np.sin(2.0 * np.pi * phase * 5.0 + 0.35)
    intake = np.column_stack((0.52 * intake_mono, intake_mono))
    bank_intervals = []
    for impulses in (left_impulses, right_impulses):
        positions = np.flatnonzero(impulses)
        if positions.size > 1:
            bank_intervals.extend(np.diff(positions) / sample_rate_hz)
    render = SourceRender(
        pressure=exhaust + blower + mechanical + intake,
        stems={
            "exhaust": exhaust,
            "exhaust_left_bank": exhaust_left_bank,
            "exhaust_right_bank": exhaust_right_bank,
            "blower": blower,
            "mechanical": mechanical,
            "casing": casing,
            "intake": intake,
        },
        diagnostics={
            "vehicle_id": "hellcat",
            "scope": "synthetic; uncalibrated; not OEM reproduction",
            "bank_timing": "cross_plane_irregular",
            "bank_interval_variation_s": float(np.std(bank_intervals)) if len(bank_intervals) >= 2 else 0.0,
            "blower_order_families": (2.36, 11.8, 23.6),
            "blower_frequency_hz": float(np.mean(rpm) / 60.0 * 11.8),
            "blower_energy": float(np.sum(np.square(blower))),
            "mechanical_model": "belt_compressor_valvetrain_texture",
            "casing_model": "rpm_phase_coupled_casing_orders",
            "pressure_compensation": "continuous RPM-derived physical source law",
        },
    )
    return render.validate()
