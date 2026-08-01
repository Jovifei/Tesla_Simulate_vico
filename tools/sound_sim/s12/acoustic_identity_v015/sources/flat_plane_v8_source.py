"""Synthetic, uncalibrated Ferrari 458-inspired flat-plane source."""

from __future__ import annotations

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace


def render_ferrari_458(trace: VehicleStateTrace, sample_rate_hz: int = 48000) -> SourceRender:
    """Render finite stereo pre-PTR pressure; this is not OEM reproduction."""
    trace.validate()
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    count = int(round((trace.time_s[-1] - trace.time_s[0]) * sample_rate_hz)) + 1
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    load = np.interp(time_s, trace.time_s, trace.load)
    combustion_drive = 0.25 + 0.75 * load
    phase = np.cumsum(rpm) / (60.0 * sample_rate_hz)
    high_rpm_mix = np.clip((rpm - 3000.0) / 5000.0, 0.0, 1.0)
    energy_redistribution = 1.0 - 0.55 * high_rpm_mix
    event_rate_compensation = np.where(
        rpm < 3000.0,
        3000.0 / np.maximum(rpm, 900.0),
        1.0 + 0.20 * high_rpm_mix,
    )
    event_id = np.floor(phase * 4.0).astype(np.int64)
    event_samples = np.flatnonzero(np.r_[True, np.diff(event_id) > 0])
    left_impulses = np.zeros(count)
    right_impulses = np.zeros(count)
    for sample in event_samples:
        (left_impulses if event_id[sample] % 2 == 0 else right_impulses)[sample] = combustion_drive[sample]

    pole = float(np.exp(-1.0 / (0.023 * sample_rate_hz)))
    left_envelope = np.zeros(count)
    right_envelope = np.zeros(count)
    for sample in range(1, count):
        left_envelope[sample] = pole * left_envelope[sample - 1] + left_impulses[sample]
        right_envelope[sample] = pole * right_envelope[sample - 1] + right_impulses[sample]
    carrier = np.sin(2.0 * np.pi * phase * 2.0) + 0.38 * np.sin(2.0 * np.pi * phase * 6.0)
    low_band_weight = 1.0 - 0.35 * high_rpm_mix
    left_mono = 0.085 * event_rate_compensation * energy_redistribution * low_band_weight * left_envelope * carrier
    right_mono = 0.085 * event_rate_compensation * energy_redistribution * low_band_weight * right_envelope * carrier
    left_bank = np.column_stack((left_mono, 0.32 * left_mono))
    right_bank = np.column_stack((0.32 * right_mono, right_mono))

    metallic_impulses = (left_impulses + right_impulses) * (rpm > 0.0)
    metallic_radius = float(np.exp(-1.0 / (0.014 * sample_rate_hz)))

    def damped_mode(frequency_hz: float) -> np.ndarray:
        angle = 2.0 * np.pi * frequency_hz / sample_rate_hz
        feedback = 2.0 * metallic_radius * np.cos(angle)
        decay = metallic_radius**2
        drive = np.sin(angle) * metallic_impulses
        response = np.zeros(count)
        for sample in range(count):
            previous = response[sample - 1] if sample >= 1 else 0.0
            previous_two = response[sample - 2] if sample >= 2 else 0.0
            response[sample] = feedback * previous - decay * previous_two + drive[sample]
        return response

    metallic_resonance = damped_mode(2350.0) + 0.32 * damped_mode(3820.0)
    idle_crack_mix = np.clip((3000.0 - rpm) / 2100.0, 0.0, 1.0)
    metallic_gain = 0.063 * (1.0 + 2.5 * idle_crack_mix) * energy_redistribution * (1.10 + 0.90 * high_rpm_mix) * np.power(np.maximum(rpm, 500.0) / 3000.0, 0.75)
    metallic_mono = metallic_gain * metallic_resonance
    metallic = np.column_stack((0.72 * metallic_mono, metallic_mono))
    render = SourceRender(
        pressure=left_bank + right_bank + metallic,
        stems={"left_bank": left_bank, "right_bank": right_bank, "metallic": metallic},
        diagnostics={
            "vehicle_id": "ferrari_458",
            "scope": "synthetic; uncalibrated; not OEM reproduction",
            "event_order_direction": "forward",
            "whole_engine_interval_degrees": 90.0,
            "event_count": int(event_samples.size),
            "metallic_model": "impulse_driven_damped_resonator",
            "metallic_impulse_count": int(np.count_nonzero(metallic_impulses)),
            "rpm_energy_redistribution": "analytic low-band-to-metallic crossfade; no frame normalization",
            "event_rate_compensation": "analytic per-event amplitude law; no measured-output normalization",
            "combustion_load_floor": 0.25,
        },
    )
    return render.validate()
