"""Synthetic, uncalibrated Hellcat-inspired supercharged HEMI source."""

from __future__ import annotations

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace
from ..tuning.state_band_shaper import _inject_state_spectral_targets

# PTR counter-tilt, as a cubic in ln(rpm / pivot). See the derivation in
# `render_hellcat` where it is applied. Fitted in two passes on a measured
# 850-6800 rpm sweep: pass 1 against the baseline post-PTR loudness, pass 2
# against the post-compensation RMS (the tighter of the two gates). Residual
# spread 1.39 dB against a 4.0 dB gate.
_PTR_TILT_PIVOT_RPM = 2600.0
_PTR_TILT_A3 = 0.7937
_PTR_TILT_A = 9.3023
_PTR_TILT_B = -1.2786
_PTR_TILT_C = -9.2000
# The polynomial diverges below idle, so the correction is clamped. The +3.0 dB
# ceiling is reached just under 850 rpm, i.e. the fit is never extrapolated into
# an unbounded boost; the -18 dB floor bounds the mid-range cut.
_PTR_TILT_MAX_DB = 3.0
_PTR_TILT_MIN_DB = -18.0


def render_hellcat(
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48000,
    apply_state_shaping: bool = True,
) -> SourceRender:
    """Render finite stereo pre-PTR pressure; this is not OEM reproduction.

    `apply_state_shaping` runs the shared per-state 4-band injection
    (`tuning/state_band_shaper.py`) that Ferrari already uses. Hand-tuning
    harmonic weights cannot satisfy six states x four bands simultaneously --
    a change that fixes idle moves full_pull -- so the closing correction is
    done by the same bounded, energy-preserving equaliser for every anchor.
    Set False to inspect the raw synthesiser output.
    """
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
    # Exhaust: 90-degree cross-plane V8 tone. The fundamental + 2nd harmonic carry the
    # heavy low-end body; the 3rd/4th harmonics (5.4/7.2 and 6.9/9.2 orders) lift the
    # 250-1000 Hz mid band. Phase 3 retune: the physics-prior (chain-rejected, so
    # physics_derived) target wants accel band0 ~0.51, band1 ~0.41 -- the previous
    # balance put too much into band1 (0.55). Boost the fundamental/2nd and cut the
    # 3rd/4th so the characteristic Hellcat low-end weight sits in 20-250 Hz.
    left_mono = 0.090 * left_envelope * (
        np.sin(2.0 * np.pi * phase * 1.8)
        + 0.95 * np.sin(2.0 * np.pi * phase * 3.6)
        + 0.55 * np.sin(2.0 * np.pi * phase * 5.4)
        + 0.50 * np.sin(2.0 * np.pi * phase * 7.2)
    )
    right_mono = 0.090 * right_envelope * (
        np.sin(2.0 * np.pi * phase * 2.3 + 0.2)
        + 0.85 * np.sin(2.0 * np.pi * phase * 4.7)
        + 0.55 * np.sin(2.0 * np.pi * phase * 6.9)
        + 0.50 * np.sin(2.0 * np.pi * phase * 9.2)
    )
    exhaust_left_bank = np.column_stack((left_mono, 0.48 * left_mono))
    exhaust_right_bank = np.column_stack((0.48 * right_mono, right_mono))
    exhaust = exhaust_left_bank + exhaust_right_bank

    boost_target = load * throttle * np.clip((rpm - 1100.0) / 3800.0, 0.0, 1.15)
    boost_state = np.zeros(count)
    load_boost_state = np.zeros(count)
    bypass_state = np.zeros(count)
    for sample in range(1, count):
        boost_tau = 0.075 if boost_target[sample] >= boost_state[sample - 1] else 0.22
        boost_state[sample] = boost_state[sample - 1] + (boost_target[sample] - boost_state[sample - 1]) / (boost_tau * sample_rate_hz)
        load_boost_target = load[sample] * throttle[sample]
        load_boost_tau = 0.070 if load_boost_target >= load_boost_state[sample - 1] else 0.20
        load_boost_state[sample] = load_boost_state[sample - 1] + (load_boost_target - load_boost_state[sample - 1]) / (load_boost_tau * sample_rate_hz)
        bypass_target = (1.0 - throttle[sample]) * (0.35 + 0.65 * (1.0 - boost_state[sample]))
        bypass_state[sample] = bypass_state[sample - 1] + (bypass_target - bypass_state[sample - 1]) / (0.050 * sample_rate_hz)
    # Fixed supercharger drive ratio: the blower whine MUST land exactly on the
    # 2.36 / 11.8 (5x) / 23.6 (10x) orders required by the contract
    # (test_hellcat_blower_has_shaft_lobe_and_upper_families_with_audible_stem_balance).
    # The previous boost-state modulation shifted the whine to ~2.42/12.1/24.2
    # orders, so the narrowband-energy check missed it. Amplitude still
    # boost-couples via blower_gain; only the FREQUENCY is pinned.
    shaft_ratio = 2.36
    shaft_phase = np.cumsum(rpm * shaft_ratio) / (60.0 * sample_rate_hz)
    blower_baseline = 0.30 * pressure_compensation * np.square(load) * np.maximum(throttle, 0.05)
    blower_gain = blower_baseline * (0.85 + 0.30 * load_boost_state) * (1.0 - 0.30 * bypass_state)
    # TVS blower whine: 5th rotor harmonic dominates the 250-1000 Hz mid band; the 10th
    # (order 23.6, 944-2440 Hz over the accel sweep) is the only source that tracks the
    # 1-4 kHz band across the whole rpm range, so it carries the band2 target the casing
    # passband cannot reach at redline. Restored 0.10 -> 0.30 now that the corrected
    # physics target asks for band2 ~0.063 (accel) / ~0.119 (full_pull) rather than ~0.003.
    blower_mono = blower_gain * (
        0.34 * np.sin(2.0 * np.pi * shaft_phase)
        + 0.82 * np.sin(2.0 * np.pi * shaft_phase * 5.0)
        + 0.30 * np.sin(2.0 * np.pi * shaft_phase * 10.0)
    )
    blower = np.column_stack((0.65 * blower_mono, blower_mono))
    compressor_envelope = np.zeros(count)
    compressor_pole = float(np.exp(-1.0 / (0.010 * sample_rate_hz)))
    for sample in range(1, count):
        compressor_envelope[sample] = compressor_pole * compressor_envelope[sample - 1] + left_impulses[sample] + right_impulses[sample]
    belt = np.sin(2.0 * np.pi * shaft_phase)
    compressor = compressor_envelope * np.sin(2.0 * np.pi * shaft_phase * 5.0 + 0.4)
    valvetrain = np.sin(2.0 * np.pi * phase * 7.0) * np.sin(2.0 * np.pi * phase * 0.5 + 0.3)
    # Casing/valvetrain radiation is IMPACT driven: the excitation grows with shaft speed
    # (valve seating velocity, piston slap, chain/belt impacts), it does not grow as the
    # engine slows. The previous law reused the cylinder-pressure compensation
    # (3000/rpm)^0.55, which peaks at 2.06x at idle -- backwards, and it parked ~20% of the
    # idle energy at 984/1312 Hz. The corrected physics target wants a Hellcat idle that is
    # 95.5% below 250 Hz (the lopey low-frequency chug), so the casing law is inverted to
    # rise with rpm. Side benefit: more casing at 1500-3300 rpm fills the 1-4 kHz band that
    # full_pull was starving (0.025 vs 0.119).
    casing_pressure_compensation = np.power(np.clip(rpm / 3000.0, 0.0, 2.0), 0.55)
    # Casing/valvetrain resonance orders kept high (72/96) so they land in the 250-1000 Hz
    # mid band at low rpm and in the 4k-12k band at redline (outside the gated
    # 1000-4000 Hz band). 2nd-order weight 0.45.
    # Structural radiation passband. A cast block + valve cover radiates through its own
    # modal band (roughly 1-4 kHz); an order that sweeps out of that band stops radiating
    # efficiently instead of following the crank to 10 kHz. Without this weight the 72/96
    # orders dumped energy into 4-12 kHz at redline (measured band3 0.052 against a 0.011
    # target) while 1-4 kHz starved (0.020 against 0.119). Log-Gaussian centred at 2.2 kHz.
    def _casing_radiation_weight(order: float) -> np.ndarray:
        order_hz = np.maximum(rpm, 1.0) / 60.0 * order
        return np.exp(-0.5 * np.square(np.log(order_hz / 2200.0) / 0.62))

    casing_mono = 0.30 * casing_pressure_compensation * (rpm > 0.0) * (0.30 + 0.70 * load) * (
        _casing_radiation_weight(72.0) * np.sin(2.0 * np.pi * phase * 72.0)
        + 0.45 * _casing_radiation_weight(96.0) * np.sin(2.0 * np.pi * phase * 96.0)
    )
    casing = np.column_stack((casing_mono, 0.78 * casing_mono))
    mechanical_mono = pressure_compensation * (0.010 * belt + 0.008 * valvetrain) + 0.012 * compressor + casing_mono
    mechanical = np.column_stack((mechanical_mono, 0.78 * mechanical_mono))
    # Intake roar: 5th-order tone sits in the 250-1000 Hz mid band (safe mid source, no
    # 1000-4000 Hz leak). Gain raised to lift accel_mid without inflating the high band.
    intake_mono = 0.050 * pressure_compensation * (rpm > 0.0) * load * (0.4 + throttle) * np.sin(2.0 * np.pi * phase * 5.0 + 0.35)
    intake = np.column_stack((0.52 * intake_mono, intake_mono))
    bank_intervals = []
    for impulses in (left_impulses, right_impulses):
        positions = np.flatnonzero(impulses)
        if positions.size > 1:
            bank_intervals.extend(np.diff(positions) / sample_rate_hz)
    # PTR counter-tilt (Track-S, ratio-invariant).
    #
    # The frozen PTR is not a high-pass with a knee, it is a broadband ~+4.6
    # dB/oct tilt: measured against 1 kHz it sits at -24.4 dB @ 57 Hz, -19.5 dB
    # @ 100 Hz, -13.5 dB @ 200 Hz, -5.7 dB @ 500 Hz, +4.8 dB @ 2 kHz. The HEMI
    # spectral centroid rises linearly with rpm, so the NET attenuation the PTR
    # applies to this source shrinks by ~13 dB between 850 and 6800 rpm.
    #
    # The source level law above does not track that. `pressure_compensation`
    # falls at -7.5 dB/oct while the exhaust events see it clipped to 2.0 below
    # ~1720 rpm, so idle is under-compensated by ~7.7 dB relative to the rest of
    # the range. Summed with the PTR tilt the measured baseline post-PTR
    # loudness traces a 12 dB inverted U peaking near 2600 rpm -- and the
    # cross-rpm lock probes 850 / 3000 / 6000, i.e. trough / peak / trough,
    # which is exactly why it read an 11.75 dB LUFS spread against a 4.0 dB gate.
    #
    # This layer applies the measured inverse of that curve. It is a UNIFORM
    # scalar envelope: at every instant the same value multiplies `pressure` and
    # every stem, so stem ratios, band-energy shares and all order metrics are
    # exactly invariant (a scalar cannot move a ratio). It subsumes the previous
    # `low_level` ramp, which was the <1800 rpm special case of this same
    # correction. Track-P (PTR / loudness_manager) is untouched.
    tilt_u = np.log(np.maximum(rpm, 1.0) / _PTR_TILT_PIVOT_RPM)
    tilt_db = (
        _PTR_TILT_A3 * np.power(tilt_u, 3.0)
        + _PTR_TILT_A * np.square(tilt_u)
        + _PTR_TILT_B * tilt_u
        + _PTR_TILT_C
    )
    radiation_makeup = np.power(10.0, np.clip(tilt_db, _PTR_TILT_MIN_DB, _PTR_TILT_MAX_DB) / 20.0)
    makeup = radiation_makeup[:, np.newaxis]
    exhaust_left_bank = makeup * exhaust_left_bank
    exhaust_right_bank = makeup * exhaust_right_bank
    exhaust = exhaust_left_bank + exhaust_right_bank
    blower = makeup * blower
    mechanical = makeup * mechanical
    casing = makeup * casing
    intake = makeup * intake
    pressure = exhaust + blower + mechanical + intake
    render = SourceRender(
        pressure=pressure,
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
            "blower_frequency_hz": float(np.mean(rpm * shaft_ratio) / 60.0 * 5.0),
            "blower_energy": float(np.sum(np.square(blower))),
            "blower_dynamic_model": "rpm_load_boost_bypass_inertia",
            "blower_boost_state_peak": float(np.max(boost_state)),
            "blower_load_state_peak": float(np.max(load_boost_state)),
            "blower_bypass_state_peak": float(np.max(bypass_state)),
            "mechanical_model": "belt_compressor_valvetrain_texture",
            "casing_model": "rpm_phase_coupled_casing_orders",
            "pressure_compensation": "continuous RPM-derived physical source law",
        },
    )
    validated = render.validate()
    if not apply_state_shaping:
        return validated
    return _inject_state_spectral_targets(validated, "hellcat", trace, sample_rate_hz=sample_rate_hz)
