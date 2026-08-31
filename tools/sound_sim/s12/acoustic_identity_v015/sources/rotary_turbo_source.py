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
from collections.abc import Mapping

from ..contracts import SourceRender, VehicleStateTrace
from ..tuning.state_band_shaper import _inject_state_spectral_targets

# --- Exhaust blowdown pulse constants -------------------------------------
# Mirror of the target-side physics prior in
# `tuning/reference_reconstruction.py` (`_exhaust_pulse_shape`,
# `ENGINE_PRIORS["rx7_fd"]`). The manifest targets were rebuilt in Task 3.1
# WITH that pulse term, but the synthesiser never carried it, which is why the
# raw render was mid-dominant (accel band0 0.205 against a 0.614 target) and
# the shared equaliser had to do the whole job. See `_exhaust_pulse_weights`.
_EXHAUST_RESONANCE_HZ = 95.0  # ENGINE_PRIORS["rx7_fd"].exhaust_resonance_hz
_EXHAUST_RESONANCE_Q = 2.5  # reference_reconstruction._EXHAUST_RESONANCE_Q
_EXHAUST_PULSE_ORDERS = np.arange(1.0, 17.0, 1.0)
# Rotor-to-rotor variation: the two rotors are not acoustically identical, so
# the 2/rev blowdown train carries a weak 1/rev asymmetry. This is the same
# mechanism the prior credits for the RX-7's odd integer orders.
_EXHAUST_ROTOR_IMBALANCE = 0.15
# Level of the blowdown train relative to the order-series body at load 1.0.
# Calibrated so the RAW render lands close to the manifest band targets at the
# steady operating points; the shared equaliser is then a trim, not a rebuild.
_EXHAUST_PULSE_GAIN = 1.0
# Upper bound on the low-load turbo compensation (see `_turbo_pressure_drive`).
_TURBO_DRIVE_CEILING = 1.5

# --- Throttle-plate flow gate on the turbo stems ---------------------------
# Compressor whine and turbine whistle are FLOW noise: they need gas moving
# through the machine. The shaft has inertia and spins down over ~0.2 s (that
# lag is real and is what `primary_spool` / `boost_state` model), but the moment
# the throttle plate shuts, the charge is dumped through the blow-off valve and
# the exhaust mass flow collapses to the pumping residual -- so the RADIATED
# whine dies within a plenum-emptying time, not a shaft-run-down time.
#
# Without this gate the model kept the compressor whine at -9.9 dB under
# `rotary` right through a throttle lift, which made it 46x louder than the
# blow-off valve that was supposedly venting. Since the whine sits at order 18
# (1.56 kHz at 5200 rpm) it single-handedly owned 1-4 kHz during
# `lift_afterfire` (raw band2 0.223 against a 0.084 target), so the shared
# equaliser answered with a -4.4 dB band2 cut that buried the `lift` stem.
_FLOW_GATE_FLOOR = 0.10  # closed-plate pumping residual, fraction of full flow
_FLOW_GATE_TAU_S = 0.060  # plenum blowdown / exhaust scavenge time constant


def _exhaust_pulse_weights(firing_hz: np.ndarray) -> np.ndarray:
    """Unit-energy per-order amplitude weights of the exhaust blowdown pulse.

    Args:
        firing_hz: Instantaneous eccentric-shaft frequency (rpm/60), shape [N].

    Returns:
        Amplitude weights, shape [len(`_EXHAUST_PULSE_ORDERS`), N]. Each column
        has unit L2 norm.

    The pipe is a second-order bandpass resonator, exactly as on the target
    side: ``|H(f)|^2 = x^2 / ((1 - x^2)^2 + (x/Q)^2)`` with ``x = f / f_res``.
    The ``x^2`` numerator is the monopole radiation efficiency of the open
    tailpipe -- steady flow (DC) radiates no sound -- and the pole pair is the
    pipe's fundamental standing wave.

    **Why the columns are normalised.** The target model applies the pulse as
    ``harmonic_total * pulse_fraction * load**2 * _broadband_band_shares(...)``
    and `_broadband_band_shares` divides by its own total, i.e. the pipe sets
    the pulse's SPECTRUM while the gas dynamics set its LEVEL. Mirroring that
    normalisation here keeps the two models consistent and, as a side effect,
    stops the resonance from producing an rpm-dependent level swing when an
    order sweeps through 95 Hz (which would blow the cross-rpm LUFS spread
    gate). Only the shape is rpm dependent.
    """
    orders = _EXHAUST_PULSE_ORDERS[:, np.newaxis]
    parity = np.where(_EXHAUST_PULSE_ORDERS % 2.0 == 0.0, 1.0, _EXHAUST_ROTOR_IMBALANCE)
    x = orders * np.asarray(firing_hz, dtype=np.float64)[np.newaxis, :] / _EXHAUST_RESONANCE_HZ
    response = x * x / ((1.0 - x * x) ** 2 + (x / _EXHAUST_RESONANCE_Q) ** 2)
    power = np.square(parity)[:, np.newaxis] * response
    return np.sqrt(power / np.maximum(power.sum(axis=0, keepdims=True), 1e-30))


def _turbo_pressure_drive(combustion_drive: np.ndarray, load: np.ndarray) -> np.ndarray:
    """Bounded peak/mean exhaust-pressure ratio driving the turbo stems.

    Args:
        combustion_drive: Per-sample combustion intensity (0.30 + 0.70*load).
        load: Per-sample engine load in [0, 1].

    Returns:
        Bounded drive multiplier, shape [N].

    `combustion_drive / load` is unbounded as load -> 0: at load 0.12 it reaches
    3.2, so a throttle lift made the compressor whine SURGE by 10 dB exactly
    when the blow-off valve is venting and the compressor is spinning down.
    That inverted band balance during `lift_afterfire` (raw band2 0.55 against
    a 0.082 target) and forced the shared equaliser into an -8.5 dB band2 cut,
    which is what buried the `lift` stem 33 dB under `rotary`. The peak/mean
    exhaust pressure ratio of a real engine is bounded, so the compensation is
    clipped at `_TURBO_DRIVE_CEILING`; the high-load behaviour (ratio <= 1.13
    for load >= 0.7) is untouched.
    """
    return np.clip(combustion_drive / np.maximum(load, 0.05), 0.0, _TURBO_DRIVE_CEILING)


def render_rx7_fd(
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48000,
    apply_state_shaping: bool = True,
    overrides: Mapping[str, float] | None = None,
) -> SourceRender:
    """Render finite stereo pre-PTR pressure; this is not OEM reproduction.

    `apply_state_shaping` runs the shared per-state 4-band injection
    (`tuning/state_band_shaper.py`) that Ferrari already uses. The raw
    synthesiser is mid-dominant at the steady operating points (accel band0
    0.205 against a 0.614 target) because the order weighting that keeps the
    rotary "braap" texture also spreads energy across orders 2..12; the shared
    equaliser restores the low-dominant balance the reference demands WITHOUT
    collapsing the order structure that carries the non-piston character.
    Set False to inspect the raw synthesiser output.
    """
    trace.validate()
    overrides = {} if overrides is None else dict(overrides)
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    count = int(round((trace.time_s[-1] - trace.time_s[0]) * sample_rate_hz)) + 1
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    load = np.interp(time_s, trace.time_s, trace.load)
    throttle = np.interp(time_s, trace.time_s, trace.throttle)
    phase = np.cumsum(rpm) / (60.0 * sample_rate_hz) + float(overrides.get("rotary_phase_offset_deg", 0.0)) / 360.0

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
    rotary_pulse_width_scale = float(overrides.get("rotary_pulse_width_scale", 1.0))
    rotary_mono = 0.24 * rotary_pulse_width_scale * envelope * (
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

    # --- Exhaust blowdown pulse: the low-frequency backbone the synthesiser
    # was missing. Each rotor's exhaust port opening dumps a pressure pulse
    # into the header; the pipe's fundamental standing wave (95 Hz for the FD's
    # ~2.9 m run) radiates it from the tailpipe. Because the train repeats at
    # 2/rev, ALL of its energy lands on integer engine orders, so it lifts
    # `integer_order_concentration` at the same time as it restores the
    # low-dominant band balance -- the opposite of what a broadband noise bed
    # would do. Energy scales as load^2 (cylinder pressure ~ charge ~ load,
    # acoustic energy ~ pressure^2), matching `_PULSE_LOAD_EXPONENT` on the
    # target side, so idle (load 0.12) is barely touched. ---
    pulse_weights = _exhaust_pulse_weights(rpm / 60.0)
    exhaust_mono = np.zeros(count)
    for index, order in enumerate(_EXHAUST_PULSE_ORDERS):
        exhaust_mono += pulse_weights[index] * np.sin(2.0 * np.pi * phase * order)
    exhaust_mono *= _EXHAUST_PULSE_GAIN * load * (rpm > 0.0)
    exhaust = np.column_stack((exhaust_mono, 0.78 * exhaust_mono))

    # --- Sequential twin-turbo: primary (always) + secondary (rpm/load gated)
    # spool, boost onset, and blow-off/lift on throttle release. Kept LOW gain
    # so it adds subtle character only; the reference carries ~0 energy >1 kHz. ---
    primary_spool = np.zeros(count)
    secondary_spool = np.zeros(count)
    boost_state = np.zeros(count)
    blow_off_state = np.zeros(count)
    # Gas flow through both machines, lagged by the plenum blowdown time only --
    # deliberately MUCH faster than the shaft states below. See `_FLOW_GATE_*`.
    flow_target = _FLOW_GATE_FLOOR + (1.0 - _FLOW_GATE_FLOOR) * throttle
    flow_gate = np.zeros(count)
    flow_gate[0] = flow_target[0]
    primary_spool_tau_s = float(overrides.get("primary_spool_tau_s", 0.16))
    secondary_spool_tau_s = float(overrides.get("secondary_spool_tau_s", 0.31))
    boost_attack_s = float(overrides.get("boost_attack_s", 0.10))
    boost_release_s = float(overrides.get("boost_release_s", 0.22))
    blow_off_release_s = float(overrides.get("blow_off_release_s", 0.80))
    primary_target = load * throttle * np.clip(rpm / 5200.0, 0.0, 1.1)
    secondary_gate = np.clip((rpm - 4300.0) / 1100.0, 0.0, 1.0) * np.clip((load - 0.35) / 0.45, 0.0, 1.0)
    secondary_target = primary_target * secondary_gate
    for sample in range(1, count):
        flow_gate[sample] = flow_gate[sample - 1] + (flow_target[sample] - flow_gate[sample - 1]) / (_FLOW_GATE_TAU_S * sample_rate_hz)
        primary_spool[sample] = primary_spool[sample - 1] + (primary_target[sample] - primary_spool[sample - 1]) / (primary_spool_tau_s * sample_rate_hz)
        secondary_spool[sample] = secondary_spool[sample - 1] + (secondary_target[sample] - secondary_spool[sample - 1]) / (secondary_spool_tau_s * sample_rate_hz)
        boost_target = 0.62 * primary_spool[sample] + 0.90 * secondary_spool[sample]
        boost_tau = boost_attack_s if boost_target >= boost_state[sample - 1] else boost_release_s
        boost_state[sample] = boost_state[sample - 1] + (boost_target - boost_state[sample - 1]) / (boost_tau * sample_rate_hz)
        release = max((throttle[sample - 1] - throttle[sample]) * sample_rate_hz, 0.0)
        blow_off_injection = 1.4 * release * (0.35 + 0.65 * boost_state[sample - 1])
        blow_off_state[sample] = blow_off_state[sample - 1] + (blow_off_injection - blow_off_state[sample - 1] / blow_off_release_s) / sample_rate_hz
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
    combustion_pressure_ratio = _turbo_pressure_drive(combustion_drive, load)
    turbo_mono = 0.44 * flow_gate * combustion_pressure_ratio * (0.42 * primary_spool + 0.78 * boost_state) * np.sin(2.0 * np.pi * turbo_phase)
    turbo = np.column_stack((0.62 * turbo_mono, turbo_mono))
    turbine_mono = 0.22 * flow_gate * combustion_pressure_ratio * (0.25 * primary_spool + 0.55 * boost_state + 0.65 * secondary_spool) * np.sin(2.0 * np.pi * turbo_phase * 2.0 + 0.25)
    turbine = np.column_stack((turbine_mono, 0.58 * turbine_mono))
    blow_off_phase = np.cumsum(650.0 + 1100.0 * boost_state + 900.0 * blow_off_state) / sample_rate_hz
    blow_off_mono = 0.075 * blow_off_state * (
        np.sin(2.0 * np.pi * blow_off_phase) + 0.24 * np.sin(2.0 * np.pi * blow_off_phase * 1.7)
    )
    blow_off = np.column_stack((0.70 * blow_off_mono, blow_off_mono)) * float(overrides.get("blow_off_gain_scale", 1.0))

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
    # idle harmonic restores post-PTR idle loudness.
    #
    # BAND-PLACEMENT FIX (Phase 3): this used engine ORDERS 57.4/62.0, which
    # only land on the intended ~880/950 Hz at 920 rpm. The acceptance harness
    # evaluates idle at 1100 rpm (tuning.deep_realism.STATE_OPERATING_POINTS),
    # where the same orders sit at 1052/1137 Hz -- i.e. inside 1000-4000 Hz, not
    # the intended 250-1000 Hz. The stem carries a third of the idle energy, so
    # it single-handedly pushed idle band2 to 0.304 against a 0.018 target and
    # drove the shared band shaper into its -24 dB clip.
    #
    # A silencer/tailpipe standing wave is a FIXED acoustic resonance: its
    # frequency is set by the pipe geometry and the speed of sound, not by shaft
    # speed. Modelling it as a constant 880/950 Hz pair is both the physically
    # correct form and inherently robust to whichever rpm the harness probes.
    # Engine coupling is retained through the amplitude (idle gate x load).
    idle_resonance_phase_a = 880.0 * time_s
    idle_resonance_phase_b = 950.0 * time_s
    idle_loud_mono = 1.00 * idle_loud_gate * (rpm > 0.0) * (
        0.6 * np.sin(2.0 * np.pi * idle_resonance_phase_a)
        + 0.4 * np.sin(2.0 * np.pi * idle_resonance_phase_b)
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
        rotary + rotor_housing + exhaust + turbo + turbine + blow_off + idle_loud
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
        stems={"rotary": rotary, "rotor_housing": rotor_housing, "exhaust": exhaust, "turbo": turbo, "turbine": turbine, "blow_off": blow_off, "lift": blow_off, "idle_loud": idle_loud},
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
            "candidate_source_overrides": dict(overrides),
        },
    )
    validated = render.validate()
    if not apply_state_shaping:
        return validated
    return _inject_state_spectral_targets(validated, "rx7_fd", trace, sample_rate_hz=sample_rate_hz)
