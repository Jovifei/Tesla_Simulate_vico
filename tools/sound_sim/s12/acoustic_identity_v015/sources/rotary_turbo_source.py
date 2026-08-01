"""Synthetic, uncalibrated RX-7 FD-inspired two-rotor turbo source."""

from __future__ import annotations

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace


def render_rx7_fd(trace: VehicleStateTrace, sample_rate_hz: int = 48000) -> SourceRender:
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
    combustion_drive = 0.30 + 0.70 * load
    combustion_pressure_ratio = combustion_drive / np.maximum(load, 0.05)
    first_train = np.floor(phase).astype(np.int64)
    second_train = np.floor(phase + 0.5).astype(np.int64)
    primary_events = np.flatnonzero(np.r_[True, np.diff(first_train) > 0])
    offset_events = np.flatnonzero(np.r_[True, np.diff(second_train) > 0])
    impulses = np.zeros(count)
    impulses[primary_events] += combustion_drive[primary_events]
    impulses[offset_events] += 0.82 * combustion_drive[offset_events]
    pole = float(np.exp(-1.0 / (0.030 * sample_rate_hz)))
    envelope = np.zeros(count)
    for sample in range(1, count):
        envelope[sample] = pole * envelope[sample - 1] + impulses[sample]
    rotary_mono = 0.090 * envelope * (
        np.sin(2.0 * np.pi * phase * 2.0) + np.sin(2.0 * np.pi * phase * 4.0)
    )
    rotary = np.column_stack((rotary_mono, 0.74 * rotary_mono))
    housing_decay_s = 0.080
    housing_pole = float(np.exp(-1.0 / (housing_decay_s * sample_rate_hz)))
    housing_envelope = np.zeros(count)
    for sample in range(1, count):
        housing_envelope[sample] = housing_pole * housing_envelope[sample - 1] + impulses[sample]
    housing_event_rate_compensation = 30.0 / (np.maximum(rpm, 950.0) * housing_decay_s)
    housing_radiation_compensation = np.power(4000.0 / np.maximum(rpm, 950.0), 0.55)
    housing_activity = housing_envelope * housing_event_rate_compensation * housing_radiation_compensation
    housing_mono = 0.20 * (rpm > 0.0) * housing_activity * (
        np.sin(2.0 * np.pi * phase * 72.0)
        + 0.38 * np.sin(2.0 * np.pi * phase * 96.0)
    )
    rotor_housing = np.column_stack((housing_mono, 0.70 * housing_mono))

    primary_spool = np.zeros(count)
    secondary_spool = np.zeros(count)
    lift_state = np.zeros(count)
    primary_target = load * throttle * np.clip(rpm / 5200.0, 0.0, 1.1)
    secondary_gate = np.clip((rpm - 4300.0) / 1100.0, 0.0, 1.0) * np.clip((load - 0.35) / 0.45, 0.0, 1.0)
    secondary_target = primary_target * secondary_gate
    for sample in range(1, count):
        primary_spool[sample] = primary_spool[sample - 1] + (primary_target[sample] - primary_spool[sample - 1]) / (0.16 * sample_rate_hz)
        secondary_spool[sample] = secondary_spool[sample - 1] + (secondary_target[sample] - secondary_spool[sample - 1]) / (0.31 * sample_rate_hz)
        release = max((throttle[sample - 1] - throttle[sample]) * sample_rate_hz, 0.0)
        lift_state[sample] = lift_state[sample - 1] + (0.12 * release - lift_state[sample - 1] / 0.28) / sample_rate_hz
    turbo_phase = np.cumsum((7.0 + 10.0 * primary_spool + 12.0 * secondary_spool) * rpm / 60.0) / sample_rate_hz
    turbo_mono = 0.146 * combustion_pressure_ratio * (0.55 * primary_spool + secondary_spool) * np.sin(2.0 * np.pi * turbo_phase)
    turbo = np.column_stack((0.62 * turbo_mono, turbo_mono))
    turbine_mono = 0.107 * combustion_pressure_ratio * (0.30 * primary_spool + 0.85 * secondary_spool) * np.sin(2.0 * np.pi * turbo_phase * 2.0 + 0.25)
    turbine = np.column_stack((turbine_mono, 0.58 * turbine_mono))
    lift_mono = 0.101 * combustion_pressure_ratio * lift_state * np.sin(2.0 * np.pi * (900.0 + 1300.0 * lift_state) * time_s)
    lift = np.column_stack((0.70 * lift_mono, lift_mono))
    pressure = rotary + rotor_housing + turbo + turbine + lift
    window_samples = min(count, sample_rate_hz // 2)
    steady = pressure[-window_samples:, 0] * np.hanning(window_samples)
    spectrum = np.square(np.abs(np.fft.rfft(steady)))
    frequencies = np.fft.rfftfreq(steady.size, 1.0 / sample_rate_hz)
    engine_hz = float(np.mean(rpm[-window_samples:]) / 60.0)
    integer_energy = sum(spectrum[np.abs(frequencies - order * engine_hz) <= 2.5].sum() for order in np.arange(1.0, 25.0))
    half_energy = sum(spectrum[np.abs(frequencies - order * engine_hz) <= 2.5].sum() for order in np.arange(1.5, 24.5, 1.0))
    total_order_energy = integer_energy + half_energy
    engaged = np.flatnonzero(secondary_spool >= 0.05)
    render = SourceRender(
        pressure=pressure,
        stems={"rotary": rotary, "rotor_housing": rotor_housing, "turbo": turbo, "turbine": turbine, "lift": lift},
        diagnostics={
            "vehicle_id": "rx7_fd",
            "scope": "synthetic; uncalibrated; not OEM reproduction",
            "rotary_event_model": "two_phase_offset_rotary_trains",
            "rotary_event_count": int(primary_events.size + offset_events.size),
            "rotary_event_rate_hz": float(2.0 * np.mean(rpm) / 60.0),
            "rotary_phase_offset_cycles": 0.5,
            "narrowband_integer_share_of_integer_plus_half": float(integer_energy / total_order_energy) if total_order_energy else 0.0,
            "narrowband_half_share_of_integer_plus_half": float(half_energy / total_order_energy) if total_order_energy else 0.0,
            "turbo_state_start": float(primary_spool[0]),
            "turbo_state_end": float(primary_spool[-1]),
            "turbo_state_peak": float(np.max(primary_spool)),
            "secondary_spool_peak": float(np.max(secondary_spool)),
            "secondary_engagement_time_s": float(time_s[engaged[0]] - time_s[0]) if engaged.size else 0.0,
            "lift_state_peak": float(np.max(lift_state)),
            "combustion_load_floor": 0.30,
            "rotor_housing_model": "event_excited_phase_coupled_housing_resonances",
        },
    )
    return render.validate()
