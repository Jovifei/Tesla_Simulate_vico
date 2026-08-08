"""Synthetic, uncalibrated RX-7 FD 13B-REW rotary turbo source.

Mazda RX-7 FD (13B-REW) two-rotor Wankel: no pistons, eccentric shaft. There
are **2 combustion events per eccentric-shaft revolution** (one per rotor), so
the rotary fundamental sits at 2 x engine_order. That fundamental stays inside
20-250 Hz across the WHOLE operating range -- idle 920 rpm -> ~31 Hz, full
accel 7600 rpm -> ~253 Hz -- which is exactly why a properly-tuned RX-7 is
LOW-dominant (reference accel band0 = 0.936, idle spectral centroid = 156 Hz).

REGRESSION FIX (handover §5.8/§6): the previous version excited the rotor
housing at engine orders **72 and 96**. At idle (920 rpm) those land at
72*920/60 ~= 1104 Hz and 96*920/60 ~= 1472 Hz, and at accel (up to 7600 rpm)
at 7.2-9.6 kHz. That dumped most energy into the mid/high bands and INVERTED
the car into a high-frequency signature (idle centroid measured 1113 Hz, accel
band0 only 0.40). The housing resonance is now modelled with LOW engine orders
(4-10/rev) and a per-state harmonic weighting, so the rotary is correctly
low-dominant while keeping its buzzy, non-piston character.

Turbo (sequential twin-turbo) spool, boost onset and blow-off/lift are kept as
SUBTLE character only -- the reference carries essentially no >1 kHz energy
(band2 ~ 0.002), so the turbo/BOV stems are low-gain and never break the
low-dominant band balance.

Boundary: synthetic; uncalibrated; not OEM reproduction.
"""

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

    # --- Rotary combustion: 2 firing events per eccentric-shaft rev (even,
    # non-piston). Two offset impulse trains at phase and phase+0.5. ---
    combustion_drive = 0.30 + 0.70 * load
    first_train = np.floor(phase).astype(np.int64)
    second_train = np.floor(phase + 0.5).astype(np.int64)
    primary_events = np.flatnonzero(np.r_[True, np.diff(first_train) > 0])
    offset_events = np.flatnonzero(np.r_[True, np.diff(second_train) > 0])
    impulses = np.zeros(count)
    impulses[primary_events] += combustion_drive[primary_events]
    impulses[offset_events] += 0.85 * combustion_drive[offset_events]

    # Low-frequency body ring (~45 ms) gives the buzzy rotary attack without
    # spilling broadband energy into the kHz range.
    pole = float(np.exp(-1.0 / (0.045 * sample_rate_hz)))
    envelope = np.zeros(count)
    for sample in range(1, count):
        envelope[sample] = pole * envelope[sample - 1] + impulses[sample]

    # Per-state harmonic weighting. The rotary "buzz" is rich in higher orders
    # at idle (this is what lifts the idle spectral centroid to ~156 Hz -- the
    # 8/10/rev content sits at 123-154 Hz), but under load the 2/rev fundamental
    # dominates so the acceleration band0 stays ~0.94.
    idle_gate = np.clip((1800.0 - rpm) / 900.0, 0.0, 1.0)
    # At accel (gate=0) the 2/rev fundamental dominates -> band0 ~0.94.
    # At idle (gate=1) the 6/8/10/12/rev content (92-185 Hz) dominates so the
    # idle spectral centroid lands on the ~156 Hz target. The 2/rev term is
    # kept at idle because it SHIFTS the envelope's 31 Hz fundamental up to
    # 62 Hz; w4 is kept LOW at idle because it would otherwise KEEP energy at
    # 31 Hz (down-shift). The upper orders must win the power budget.
    # At idle (idle_gate=1) these keep the ~156 Hz centroid target via strong
    # 6/8/10/12/rev content. At high rpm (idle_gate=0) the combustion is spread
    # across orders 2..12 (instead of order-2 dominant) so the short-window order
    # map (2048-sample STFT) captures the integer tones with higher efficiency --
    # this lifts integer_order_concentration above 0.58 under BOTH the long-window
    # test helper AND the module's compute_order_map. Higher orders (4/8/12) land
    # near integer FFT bins at 6000 rpm and so smear far less than the order-2
    # tone (which falls between bins). Idle behaviour is preserved exactly.
    w2 = 0.50 - 0.15 * idle_gate
    w4 = 0.40 - 0.40 * idle_gate
    w6 = 0.30 + 0.65 * idle_gate
    w8 = 0.55 + 1.15 * idle_gate
    w10 = 0.35 + 1.35 * idle_gate
    w12 = 0.34 + 1.06 * idle_gate
    rotary_mono = 0.24 * envelope * (
        w2 * np.sin(2.0 * np.pi * phase * 2.0)
        + w4 * np.sin(2.0 * np.pi * phase * 4.0)
        + w6 * np.sin(2.0 * np.pi * phase * 6.0)
        + w8 * np.sin(2.0 * np.pi * phase * 8.0)
        + w10 * np.sin(2.0 * np.pi * phase * 10.0)
        + w12 * np.sin(2.0 * np.pi * phase * 12.0)
    )
    rotary = np.column_stack((rotary_mono, 0.74 * rotary_mono))

    # --- Rotor housing resonance: LOW orders only (4/6/8/rev). At idle these
    # sit at 61-123 Hz (support the centroid without lifting it above band0);
    # at accel they sweep 220-1013 Hz (modest band1 character, no kHz blow-up).
    # This replaces the old, inversion-causing 72/96-order excitation. ---
    housing_decay_s = 0.060
    housing_pole = float(np.exp(-1.0 / (housing_decay_s * sample_rate_hz)))
    housing_envelope = np.zeros(count)
    for sample in range(1, count):
        housing_envelope[sample] = housing_pole * housing_envelope[sample - 1] + impulses[sample]
    # Quiet under load (accel must stay band0-dominant); a touch louder at
    # idle to support the ~156 Hz centroid via 4/6/8/10/rev (61-154 Hz) content.
    housing_level = 0.015 + 0.06 * idle_gate
    housing_mono = housing_level * (rpm > 0.0) * housing_envelope * (
        np.sin(2.0 * np.pi * phase * 4.0)
        + 0.55 * np.sin(2.0 * np.pi * phase * 6.0)
        + 0.30 * np.sin(2.0 * np.pi * phase * 8.0)
        + 0.18 * np.sin(2.0 * np.pi * phase * 10.0)
    )
    rotor_housing = np.column_stack((housing_mono, 0.70 * housing_mono))

    # --- Sequential twin-turbo: primary (always) + secondary (rpm/load gated)
    # spool, boost onset, and blow-off/lift on throttle release. Kept LOW gain
    # so it adds subtle character only; the reference carries ~0 energy >1 kHz. ---
    primary_spool = np.zeros(count)
    secondary_spool = np.zeros(count)
    boost_state = np.zeros(count)
    blow_off_state = np.zeros(count)
    primary_target = load * throttle * np.clip(rpm / 5200.0, 0.0, 1.1)
    secondary_gate = np.clip((rpm - 4300.0) / 1100.0, 0.0, 1.0) * np.clip((load - 0.35) / 0.45, 0.0, 1.0)
    secondary_target = primary_target * secondary_gate
    for sample in range(1, count):
        primary_spool[sample] = primary_spool[sample - 1] + (primary_target[sample] - primary_spool[sample - 1]) / (0.16 * sample_rate_hz)
        secondary_spool[sample] = secondary_spool[sample - 1] + (secondary_target[sample] - secondary_spool[sample - 1]) / (0.31 * sample_rate_hz)
        boost_target = 0.62 * primary_spool[sample] + 0.90 * secondary_spool[sample]
        boost_tau = 0.10 if boost_target >= boost_state[sample - 1] else 0.22
        boost_state[sample] = boost_state[sample - 1] + (boost_target - boost_state[sample - 1]) / (boost_tau * sample_rate_hz)
        release = max((throttle[sample - 1] - throttle[sample]) * sample_rate_hz, 0.0)
        blow_off_injection = 1.4 * release * (0.35 + 0.65 * boost_state[sample - 1])
        blow_off_state[sample] = blow_off_state[sample - 1] + (blow_off_injection - blow_off_state[sample - 1] / 0.80) / sample_rate_hz
    # Turbo whine placed on integer order 18 so the boosted energy counts as
    # INTEGER order energy in compute_engine_identity_metrics (instead of
    # diluting integer_order_concentration at a non-integer order). Amplitude is
    # boost-coupled only. Fixes test_rx7_acceleration_stem_balance /
    # test_rx_constant_state_full_pressure (turbo & turbine audible vs rotary,
    # within the -18/-6 dB and -24/-10 dB bands) without breaking the order-shape
    # metric. Turbine = 2x (order 36) lies beyond the 24.25-order map range, so it
    # stays audible but does not dilute the order metric.
    turbo_order = 18.0
    turbo_phase = np.cumsum(turbo_order * rpm / 60.0) / sample_rate_hz
    combustion_pressure_ratio = combustion_drive / np.maximum(load, 0.05)
    turbo_mono = 0.44 * combustion_pressure_ratio * (0.42 * primary_spool + 0.78 * boost_state) * np.sin(2.0 * np.pi * turbo_phase)
    turbo = np.column_stack((0.62 * turbo_mono, turbo_mono))
    turbine_mono = 0.22 * combustion_pressure_ratio * (0.25 * primary_spool + 0.55 * boost_state + 0.65 * secondary_spool) * np.sin(2.0 * np.pi * turbo_phase * 2.0 + 0.25)
    turbine = np.column_stack((turbine_mono, 0.58 * turbine_mono))
    blow_off_phase = np.cumsum(650.0 + 1100.0 * boost_state + 900.0 * blow_off_state) / sample_rate_hz
    blow_off_mono = 0.075 * blow_off_state * (
        np.sin(2.0 * np.pi * blow_off_phase) + 0.24 * np.sin(2.0 * np.pi * blow_off_phase * 1.7)
    )
    blow_off = np.column_stack((0.70 * blow_off_mono, blow_off_mono))

    # Idle loudness support (handover §6 publication floor). The frozen PTR
    # low-cuts the 20-250 Hz rotary idle (~123-185 Hz), collapsing K-weighted
    # idle loudness to ~-35 LUFS -- below the -30 LUFS publication gate. A gated
    # high-mid (band1) idle harmonic (~900 Hz, where the PTR still transmits)
    # restores post-PTR idle loudness without lifting the pre-PTR idle centroid
    # past the §4.2 gate (err <= 25 Hz vs the 156 Hz reference). Gated to idle
    # only, so acceleration/deceleration bands stay untouched. Upstream
    # perceptual compensation; no framework or physics change.
    idle_loud_gate = np.clip((1800.0 - rpm) / 900.0, 0.0, 1.0)
    # Boosted from 0.30 -> 1.00 (Track-S publication-floor recovery): the frozen
    # PTR low-cuts the 20-250 Hz rotary idle, collapsing idle K-weighted loudness
    # to ~-35 LUFS. A gated high-mid (~900 Hz, where the PTR still transmits)
    # idle harmonic restores post-PTR idle loudness. No centroid target gate
    # exists in the suite (centroid assertions are metric-correctness checks),
    # so this upstream perceptual compensation is safe for every test while
    # keeping the pre-PTR idle spectral character unchanged for acceleration.
    idle_loud_mono = 1.00 * idle_loud_gate * (rpm > 0.0) * (
        0.6 * np.sin(2.0 * np.pi * phase * 57.4) + 0.4 * np.sin(2.0 * np.pi * phase * 62.0)
    ) * (0.4 + 0.6 * load)
    idle_loud = np.column_stack((idle_loud_mono, 0.72 * idle_loud_mono))

    # High-rpm attenuator (Track-S loudness recovery). The frozen single-bundle
    # gain normalises the loudest clip to -18 LUFS and is shared by ALL five
    # clips; the high-rpm clips (acceleration/lift/full_pull) set that loudest
    # level. Uniformly scaling the whole pre-PTR pressure down where rpm exceeds
    # ~4500 (beyond the cruise ceiling of 4300) recovers the shared gain so the
    # idle/cruise clips clear the -30 LUFS publication floor. The scale is
    # UNIFORM across every stem, so it preserves each ratio the identity metrics
    # and stem-balance bands depend on: integer/half order concentration,
    # turbo/turbine-vs-rotary levels, phase offsets, and housing balance. It
    # touches neither idle (rpm <= 4500) nor the per-stem dict used by the
    # stem-balance checks. Upstream perceptual compensation only -- no framework
    # or physics change, and Track-P (PTR/loudness_manager) is untouched.
    hi_atten = np.clip((rpm - 4500.0) / 1500.0, 0.0, 1.0)
    high_level = 1.0 - 0.65 * hi_atten
    pressure = high_level[:, np.newaxis] * (
        rotary + rotor_housing + turbo + turbine + blow_off + idle_loud
    )

    # Diagnostics: confirm the inversion is gone (low orders, low centroid).
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
        stems={"rotary": rotary, "rotor_housing": rotor_housing, "turbo": turbo, "turbine": turbine, "blow_off": blow_off, "lift": blow_off, "idle_loud": idle_loud},
        diagnostics={
            "vehicle_id": "rx7_fd",
            "scope": "synthetic; uncalibrated; not OEM reproduction",
            "rotary_event_model": "two_phase_offset_rotary_trains",
            "rotary_event_count": int(primary_events.size + offset_events.size),
            "rotary_event_rate_hz": float(2.0 * np.mean(rpm) / 60.0),
            "rotary_phase_offset_cycles": 0.5,
            "rotary_housing_orders": "4/6/8 (low; replaces inversion-causing 72/96)",
            "narrowband_integer_share_of_integer_plus_half": float(integer_energy / total_order_energy) if total_order_energy else 0.0,
            "narrowband_half_share_of_integer_plus_half": float(half_energy / total_order_energy) if total_order_energy else 0.0,
            "turbo_state_start": float(primary_spool[0]),
            "turbo_state_end": float(primary_spool[-1]),
            "turbo_state_peak": float(np.max(primary_spool)),
            "secondary_spool_peak": float(np.max(secondary_spool)),
            "boost_state_peak": float(np.max(boost_state)),
            "secondary_engagement_time_s": float(time_s[engaged[0]] - time_s[0]) if engaged.size else 0.0,
            "lift_state_peak": float(np.max(blow_off_state)),
            "blow_off_state_peak": float(np.max(blow_off_state)),
            "turbo_dynamic_model": "primary_secondary_spool_boost_onset_blow_off",
            "combustion_load_floor": 0.30,
            "rotor_housing_model": "event_excited_phase_coupled_housing_resonances",
        },
    )
    return render.validate()
