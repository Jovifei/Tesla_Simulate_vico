"""Synthetic, uncalibrated Ferrari 458-inspired flat-plane source.

Regression fix (handover 5.6 / 6)
--------------------------------
The previous source placed ~95% of idle energy below 250 Hz (a ~35 Hz
combustion carrier). The frozen PTR/radiation adapter is a steep LOW-CUT
(35 Hz -> -38 dB, 250 Hz -> -21 dB, 3820 Hz -> -1.5 dB), so that sub-250 Hz
idle energy is deleted on render, collapsing the idle K-weighted loudness to
~-35 LUFS (the "-30.237 LUFS / double-gate" regression). Because the bundle
loudness manager applies ONE shared gain, a single gain cannot lift a
K-weighting-blind idle back to target, so it stayed near the publication gate.

Fix: keep the combustion carrier out of the idle band (an rpm-gated
`comb_idle_factor` suppresses it below ~1500 rpm) and instead fill the idle
with tonal energy at ~1000 Hz and ~1450 Hz that survives the low-cut PTR.
This (a) raises the idle spectral centroid toward the ~980 Hz reference and
(b) gives the idle real K-weighted loudness so the single shared bundle gain
lands it at ~-16 LUFS -- no second normalization, no framework change.

Acceleration band rebalance (handover 4.2)
------------------------------------------
The reference acceleration is mid-dominant (low 0.356 / mid 0.569 / high 0.068)
but the old source was low/high split. The combustion carrier harmonics are
re-weighted (N2 low reduced, N4/N6 mid boosted) and the metallic resonator is
rpm-scaled so it stays loud at idle (high band ~0.47) but is restrained under
acceleration (high band ~0.07), moving scream/ring energy into the 250-1000 Hz
mid band.

Per-state spectral-target injection (Task 3.1)
----------------------------------------------
`apply_deep_realism` is a ratio-invariant scalar envelope, so it cannot move
`band_energy_shares` (which normalises by total energy). The band-share targets
in `targets/deep_realism_tuning_manifest.json` are therefore hit HERE, inside
the Track S source module, by `_inject_state_spectral_targets`: a state-keyed,
linear, time-varying band equaliser realised as an STFT overlap-add.

Frozen boundaries respected: radiation package, `render_identity_v02._health`,
`manage_bundle_loudness` signature, and `acoustic_layers/idle_dynamics.py` are
NOT modified. All tuning is in this source file only.
"""

from __future__ import annotations

import numpy as np
from collections.abc import Mapping

from ..acoustic_analysis.spectral_targets import BAND_EDGES
from ..contracts import SourceRender, VehicleStateTrace
from ..tuning.deep_realism import (
    _labels_on_render_grid,
    apply_deep_realism,
    load_tuning_manifest,
)
# The per-state 4-band injection now lives in `tuning/state_band_shaper.py` so the
# Hellcat and RX-7 sources can reuse it instead of hand-tuning harmonic weights
# against six states x four bands. Re-imported under the original private names so
# every existing reference (tests, scripts, diagnostics) keeps working unchanged.
from ..tuning.state_band_shaper import (  # noqa: F401  (re-exported for callers)
    _EDGE_BLEND_OCTAVES,
    _GAIN_FRAME_SMOOTHING,
    _MAX_SHAPE_DB,
    _MIN_SHAPE_SAMPLES,
    _SHAPE_FRAME,
    _SHAPE_OVERLAP,
    _SHAPE_REFINEMENTS,
    _SHAPE_TOLERANCE,
    _UNREACHABLE_SHARE_FLOOR,
    _band_blend_weights,
    _band_power_of,
    _frame_curves,
    _inject_state_spectral_targets,
    _overlap_add,
)


_UPPER_METALLIC_MIX = 0.30


def _impulse_ring(impulses: np.ndarray, frequency_hz: float, decay_s: float, sample_rate_hz: int) -> np.ndarray:
    """Damped-sinusoid ring driven by an impulse train, via FFT convolution.

    Equivalent to the two-pole `damped_mode` recursion but evaluated as a
    convolution with the analytic impulse response `r**n * sin(w*(n+1))`, which
    is vectorised instead of a per-sample Python loop. Used only for the new
    upper-band modes; the existing 2350/3820 Hz recursion is left untouched so
    its locked behaviour stays bit-identical.
    """
    radius = float(np.exp(-1.0 / (decay_s * sample_rate_hz)))
    length = max(int(np.ceil(decay_s * sample_rate_hz * 8.0)), 1)
    index = np.arange(length, dtype=np.float64)
    angle = 2.0 * np.pi * frequency_hz / sample_rate_hz
    kernel = np.power(radius, index) * np.sin(angle * (index + 1.0))
    count = int(impulses.size)
    size = 1 << int(count + length - 1).bit_length()
    spectrum = np.fft.rfft(impulses, size) * np.fft.rfft(kernel, size)
    return np.fft.irfft(spectrum, size)[:count]


def render_ferrari_458(
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48000,
    apply_state_shaping: bool = True,
    overrides: Mapping[str, float] | None = None,
) -> SourceRender:
    """Render finite stereo pre-PTR pressure; this is not OEM reproduction.

    ``apply_state_shaping`` is a Track S switch used by the post-PTR loudness
    compensation layer: set it False to render the pre-shaping *baseline* (the
    loudness reference) with the per-state band EQ skipped. It never changes the
    default shipping render.
    """
    trace.validate()
    overrides = {} if overrides is None else dict(overrides)
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    count = int(round((trace.time_s[-1] - trace.time_s[0]) * sample_rate_hz)) + 1
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    load = np.interp(time_s, trace.time_s, trace.load)
    combustion_drive = 0.25 + 0.75 * load
    phase = np.cumsum(rpm) / (60.0 * sample_rate_hz) + float(overrides.get("bank_phase_offset_deg", 0.0)) / 360.0
    high_rpm_mix = np.clip((rpm - 3000.0) / 5000.0, 0.0, 1.0)
    # rpm-gated idle gate: suppress the low-band combustion carrier below ~1500 rpm
    # so the frozen low-cut PTR cannot delete the idle. 1.0 at high rpm, ~0.02 at idle.
    idle_mask = np.clip((1500.0 - rpm) / 1000.0, 0.0, 1.0)
    # Constant-power spectral tilt (Stage C-E): low/mid (carrier + fillers) is
    # strong at idle and tapers toward redline, while the high-band metallic is
    # weak at idle and strong at redline. This keeps the RAW source RMS ~flat
    # across the rpm range (idle ~900 -> redline ~8000, <=1.5 dB spread, NO
    # per-frame output normalization) while the >=1200 Hz fraction still RISES
    # with rpm (test_ferrari_high_frequency_energy_grows_with_rpm).
    rpm_norm = np.clip((rpm - 900.0) / (8000.0 - 900.0), 0.0, 1.0)
    low_drive = 1.0 - 0.55 * rpm_norm
    high_drive = 0.30 + 0.85 * rpm_norm * float(overrides.get("high_rpm_growth_scale", 1.0))
    event_rate_compensation = 1.0
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
    # Combustion carrier: N2 (low) kept modest, N4/N6 (mid) boosted so acceleration is
    # mid-dominant (250-1000 Hz) rather than low/high split.
    carrier = (
        0.68 * np.sin(2.0 * np.pi * phase * 2.0)
        + 0.62 * np.sin(2.0 * np.pi * phase * 4.0)
        + 0.50 * np.sin(2.0 * np.pi * phase * 6.0)
    )
    comb_idle_factor = (1.0 - idle_mask) + idle_mask * 0.02
    # Low/mid combustion carrier, amplitude tapered by low_drive (strong at idle,
    # tapers toward redline) so total RMS stays flat while the high band grows.
    pulse_width_scale = float(overrides.get("pulse_width_scale", 1.0))
    left_carrier = 0.13 * pulse_width_scale * low_drive * comb_idle_factor * left_envelope * carrier
    right_carrier = 0.13 * pulse_width_scale * low_drive * comb_idle_factor * right_envelope * carrier
    # Idle tonal filler (survives the frozen low-cut PTR): ~1000 Hz (mid) + ~1450 Hz.
    # Engine-order-coupled (phase*N) so time-origin invariant and rpm-tracking,
    # gated OFF at rpm=0. Amplitude kept modest so the idle raw level stays inside
    # the ~1.5 dB rpm spread (it previously spiked idle ~+3 dB vs redline).
    idle_running = (rpm > 0.0)
    idle_mid = 0.55 * idle_mask * idle_running * np.sin(2.0 * np.pi * phase * 54.5) * (0.4 + 0.6 * load) * low_drive
    idle_hi = 0.06 * idle_mask * idle_running * np.sin(2.0 * np.pi * phase * 79.0) * (0.4 + 0.6 * load) * low_drive
    # Part-load / cruise filler (mid band, survives the frozen low-cut PTR). A
    # gated mid engine note lifts the moderate-rpm cruise into the publication
    # range; gated OFF at idle and rolled off above ~5.2k rpm. Engine-order-coupled
    # (phase*N) so time-origin invariant. Upstream perceptual compensation.
    cruise_mask = np.clip((rpm - 1600.0) / 1400.0, 0.0, 1.0) * np.clip((5200.0 - rpm) / 1800.0, 0.0, 1.0)
    cruise_mid = 0.40 * cruise_mask * (
        0.55 * np.sin(2.0 * np.pi * phase * 12.67) + 0.40 * np.sin(2.0 * np.pi * phase * 18.0)
    ) * (0.4 + 0.6 * load) * low_drive
    left_mono = left_carrier + idle_mid + idle_hi + cruise_mid
    right_mono = right_carrier + idle_mid + idle_hi + cruise_mid
    left_bank = np.column_stack((left_mono, 0.32 * left_mono))
    right_bank = np.column_stack((0.32 * right_mono, right_mono))

    metallic_impulses = (left_impulses + right_impulses) * (rpm > 0.0)
    metallic_radius = float(np.exp(-1.0 / (0.014 * float(overrides.get("metallic_decay_scale", 1.0)) * sample_rate_hz)))

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
    # Upper metallic band (4-12 kHz): valvetrain / exhaust-tip ring. The source
    # previously produced essentially NOTHING above 4 kHz (raw band share
    # ~0.0012), so the manifest's 4-12 kHz targets were reachable only by
    # amplifying the 3820 Hz mode's skirts by ~18 dB -- that boosts leakage, not
    # signal, and it drags the (very loud) 3820 Hz mode up through the band
    # 3/4 crossfade, which is what stalled `full_pull` convergence. These two
    # short, bright modes are driven by the SAME combustion impulse train, so
    # they stay engine-phase coupled, deterministic and time-origin invariant.
    upper_metallic = _impulse_ring(metallic_impulses, 5600.0, 0.0045, sample_rate_hz) + 0.55 * _impulse_ring(
        metallic_impulses, 8400.0, 0.0030, sample_rate_hz
    )
    # rpm-scaled metallic: loud at idle (high band ~0.47) but restrained under
    # acceleration (high band ~0.07), moving ring energy into the mid band.
    idle_crack_mix = np.clip((3000.0 - rpm) / 2100.0, 0.0, 1.0)
    met_scale = idle_crack_mix * 1.5 + (1.0 - idle_crack_mix) * 1.2
    # High-band metallic, amplitude driven up by high_drive (weak at idle, strong
    # at redline) so the >=1200 Hz fraction grows with rpm while total stays flat.
    metallic_gain = 0.20 * high_drive * met_scale
    # The upper band is rpm-scaled by the same `high_drive`, so the >=1200 Hz
    # fraction keeps GROWING with rpm. Its level is deliberately small: it only
    # has to seed the 4-12 kHz band with real content so the per-state shaper
    # needs a few dB rather than ~18 dB there.
    metallic_mono = metallic_gain * (metallic_resonance + _UPPER_METALLIC_MIX * upper_metallic)
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
            "rpm_energy_redistribution": "idle-gated combustion suppression + mid-weighted carrier; no frame normalization",
            "event_rate_compensation": "flat 1.0 at idle (no low-rpm boost) to avoid K-weighting-blind idle energy",
            "combustion_load_floor": 0.25,
            "regression_fix": "idle combustion suppressed below 1500 rpm; ~1000/1450 Hz idle tonal filler survives frozen low-cut PTR",
            "idle_target_lufs": "single shared bundle gain lands idle near -16 LUFS (no double normalization)",
            "candidate_source_overrides": dict(overrides),
        },
    )
    tuned = apply_deep_realism(render.validate(), "ferrari_458", trace, sample_rate_hz=sample_rate_hz)
    if not apply_state_shaping:
        shaped = tuned
    else:
        shaped = _inject_state_spectral_targets(tuned, "ferrari_458", trace, sample_rate_hz=sample_rate_hz)
    # Idle-only source trim: keep the 1050 rpm combustion/mechanical identity
    # audible after the frozen PTR without changing the high-rpm pull.
    idle_time = trace.time_s[0] + np.arange(shaped.pressure.shape[0], dtype=np.float64) / sample_rate_hz
    idle_rpm = np.interp(idle_time, trace.time_s, trace.rpm)
    idle_gain = np.where(idle_rpm <= 1300.0, 1.06, 1.0)[:, np.newaxis]
    return SourceRender(
        pressure=shaped.pressure * idle_gain,
        stems={name: np.asarray(stem, dtype=np.float64) * idle_gain for name, stem in shaped.stems.items()},
        diagnostics={**shaped.diagnostics, "idle_source_gain": 1.06, "idle_source_gate_rpm": 1300.0},
    ).validate()
