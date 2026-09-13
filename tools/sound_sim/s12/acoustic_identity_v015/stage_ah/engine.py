"""AG-R1 composition with source-local interventions and a fixed-parent scale."""
from __future__ import annotations

import hashlib
import json

import numpy as np
from scipy.signal import welch

from ..stage_ag.vehicle_identity_r1 import VehicleIdentityR1Engine, IDENTITY_MODE_V1R1
from .output_guard import LEGACY_CLIP_V1
from .source_policy import SourcePolicy, VARIANTS, pcm_sha256, signature, validate_events


def spectrum_report(values: np.ndarray, sr: int = 48_000) -> dict:
    """Linear-power stereo average (not cancellation-prone mono downmix).

    Uncalibrated digital levels only. Do not interpret these as dB SPL or a
    percentage of vehicle realism. Stem energies do not add due to correlation.
    """
    x = np.asarray(values, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    if len(x) < 32 or not np.all(np.isfinite(x)):
        raise ValueError("spectrum input too short or non-finite")
    nperseg = min(16384, len(x))
    frequencies, psd = welch(x, fs=sr, nperseg=nperseg, axis=0)
    power = psd.mean(axis=1)
    mask = (frequencies >= 20) & (frequencies <= 250)
    low = np.flatnonzero(mask)
    total = max(float(power.sum()), 1e-30)
    peak_bin = int(low[np.argmax(power[low])]) if len(low) else 0
    selected = sorted(low, key=lambda k: power[k], reverse=True)[:5]
    broad = np.flatnonzero((frequencies >= 20) & (frequencies <= 600))
    broad_peak = int(broad[np.argmax(power[broad])]) if len(broad) else 0
    silent = not bool(np.any(x))
    return {
        "silence": silent,
        "body_20_600_peak_hz": None if silent else float(frequencies[broad_peak]),
        "body_20_600_ratio": float(power[broad].sum() / total),
        "rms_digital": float(np.sqrt(np.mean(x * x))),
        "dc_digital": float(np.mean(x)),
        "welch_bin_hz": float(sr / nperseg),
        "lf_20_250_ratio": float(power[mask].sum() / total),
        "lf_peak_hz": None if silent else float(frequencies[peak_bin]),
        "lf_top_bins_hz": [] if silent else [float(frequencies[k]) for k in selected],
        "peak_digital": float(np.max(np.abs(x))),
        "level_kind": "UNCALIBRATED_DIGITAL_NOT_SPL",
    }


def input_sha(rpm, throttle, duration, events) -> str:
    digest = hashlib.sha256()
    for curve in (rpm, throttle):
        a = np.ascontiguousarray(curve, dtype="<f8")
        digest.update(str(a.shape).encode())
        digest.update(a.tobytes())
    digest.update(json.dumps([float(duration), events], sort_keys=True).encode())
    return digest.hexdigest()


class RemediationEngine(VehicleIdentityR1Engine):
    """Preserves AG-R1 identity parameters; no second renderer or fit path.

    Each candidate first renders its identical parent trace to obtain a fixed
    normalization denominator. This is a comparison control, NOT a tunable gain.
    It prevents removing a resonance from amplifying every remaining source.
    The inherited whole-track engine remains offline, not realtime-qualified.
    """

    def __init__(self, vehicle_type="ferrari_458", sr=48_000, *,
                 identity_mode=IDENTITY_MODE_V1R1, numerical_fixes=(), seed=20260908,
                 variant="r1_baseline", collect=True,
                 output_policy=LEGACY_CLIP_V1):
        if variant not in VARIANTS or identity_mode != IDENTITY_MODE_V1R1:
            raise ValueError("AH requires an explicit variant and AG-R1 identity mode")
        if int(sr) != 48_000 or int(seed) < 0:
            raise ValueError("AH qualification currently requires 48 kHz and seed >= 0")
        super().__init__(vehicle_type, sr, identity_mode=identity_mode,
                         numerical_fixes=numerical_fixes, seed=seed)
        self.variant, self.collect, self.output_policy = variant, collect, output_policy
        self.numerical_fixes = tuple(numerical_fixes)
        self.last_report = {}

    def render_track(self, rpm_curve, throttle_curve, duration,
                     shift_events=None, afterfire_events=None, bov_events=None):
        if not np.isfinite(duration) or duration <= 0:
            raise ValueError("duration must be finite and positive")
        for curve in (rpm_curve, throttle_curve):
            if not np.asarray(curve).size or not np.all(np.isfinite(curve)):
                raise ValueError("curves must be nonempty and finite")
        validate_events(afterfire_events, duration)
        args = (rpm_curve, throttle_curve, duration, shift_events, afterfire_events, bov_events)
        anchor = SourcePolicy(self.vehicle_type, "r1_baseline", seed=self.seed,
                              collect=self.collect, output_policy=LEGACY_CLIP_V1,
                              sample_rate=self.sr)
        self.base._source_policy = anchor
        try:
            parent_pcm = super().render_track(*args)
            if self.variant == "r1_baseline" and self.output_policy == LEGACY_CLIP_V1:
                policy, pcm = anchor, parent_pcm
            else:
                parent_peak = anchor.receipt["pre_saturation_peak"]
                policy = SourcePolicy(self.vehicle_type, self.variant, seed=self.seed,
                                      parent_peak=parent_peak, collect=self.collect,
                                      output_policy=self.output_policy,
                                      sample_rate=self.sr)
                self.base._source_policy = policy
                pcm = super().render_track(*args)
        finally:
            self.base._source_policy = None
        self.last_report = {
            "vehicle": self.vehicle_type,
            "variant": self.variant,
            "source_variant": self.variant,
            "output_policy": self.output_policy,
            "rpm_min_max": [float(np.min(rpm_curve)), float(np.max(rpm_curve))],
            "throttle_min_max": [float(np.min(throttle_curve)), float(np.max(throttle_curve))],
            "nominal_body_band_hz": [self.base.mechanical_resonance_freq * .7,
                                     self.base.mechanical_resonance_freq * 1.5],
            "firing_order": self.base.cylinders / 2.,
            "expected_firing_hz_min_max": [float(np.min(rpm_curve)) / 60. * self.base.cylinders / 2.,
                                            float(np.max(rpm_curve)) / 60. * self.base.cylinders / 2.],
            "input_sha256": input_sha(rpm_curve, throttle_curve, duration,
                                      [shift_events, afterfire_events, bov_events]),
            "trace_sha256": input_sha(rpm_curve, throttle_curve, duration,
                                       [shift_events, afterfire_events, bov_events]),
            "sample_rate_hz": self.sr,
            "sample_count": int(len(parent_pcm)),
            "seed": self.seed,
            "flags": list(self.numerical_fixes),
            "parent_pcm_sha256": pcm_sha256(parent_pcm),
            "candidate_pcm_sha256": pcm_sha256(pcm),
            "pre_identity_pcm_sha256": (
                pcm_sha256(self.last_base_pcm)
                if self.last_base_pcm is not None
                else None
            ),
            "signature": signature(self.vehicle_type, self.variant, self.output_policy),
            "normalization": policy.receipt,
            "parent_pre_saturation_peak": anchor.receipt["pre_saturation_peak"],
            "parent_peak": anchor.receipt["pre_saturation_peak"],
            "candidate_raw_peak": policy.receipt.get("pre_saturation_peak"),
            "parent_output_policy": anchor.output_policy,
            "parent_spectrum": spectrum_report(parent_pcm.astype(float) / 32767.),
            "candidate_spectrum": spectrum_report(pcm.astype(float) / 32767.),
            "parent_stems": {name: spectrum_report(x) for name, x in anchor.stems.items()},
            "candidate_stems": {name: spectrum_report(x) for name, x in policy.stems.items()},
            "post_identity_mix_peak": self.last_identity_receipt.get("post_identity_mix_peak"),
            "identity_layer_preclip_peak": self.last_identity_receipt.get("identity_layer_preclip_peak"),
            "identity_layer_clip_count": self.last_identity_receipt.get("identity_layer_clip_count", 0),
            "identity_layer_clip_error": self.last_identity_receipt.get("identity_layer_clip_error", 0.0),
            "identity_layer_clip_error_rms": self.last_identity_receipt.get("identity_layer_clip_error_rms", 0.0),
            "post_identity_clip_count": self.last_identity_receipt.get("post_identity_clip_count", 0),
            "post_identity_clip_error": self.last_identity_receipt.get("post_identity_clip_error", 0.0),
            "post_identity_clip_error_rms": self.last_identity_receipt.get("post_identity_clip_error_rms", 0.0),
            "note": "Correlated stem energies are not additive; fixed peak != proven noise",
        }
        return pcm
