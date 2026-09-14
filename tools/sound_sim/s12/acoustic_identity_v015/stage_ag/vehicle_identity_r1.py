"""Stage AG-R1 reference-remediation vehicle identity candidate.

Stage AG v1 proved that engine-order identity can separate vehicle families, but
its first governed Reference run exposed three regressions.  The important root
cause is not the 3% guard: v1 attenuated its source by throttle/RPM and then
normalized every rendered identity layer back to a 0.94 peak.  Constant-RPM
traces also used the trace maximum as the RPM normalization denominator.  Those
two operations largely erased the intended state dependence, especially at
idle.

R1 keeps v1 unchanged as negative evidence and introduces a new explicit mode:
``vehicle_identity_v1r1``.  R1:

- uses vehicle redline for absolute RPM state;
- keeps a small non-zero idle identity source, without per-track peak recovery;
- applies a sample-wise convex blend;
- attenuates only the added GT-R identity source near full load, where the base
  renderer already contains turbo/BOV identity;
- preserves the Hellcat anchor byte-for-byte.

No master/global gain, post-EQ matching, Reference-dependent fitting, downloaded
samples, model weights or third-party audio are introduced here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import numpy as np

from ..stage_ad.engine_sim_acoustics import EngineAcoustics, causal_fractional_delay
from .vehicle_identity import (
    IDENTITY_MODE_LEGACY,
    VEHICLE_IDENTITY_PROFILES,
    _band_limited_noise,
    _finite_curve,
)

IDENTITY_MODE_V1R1 = "vehicle_identity_v1r1"
IDENTITY_MODES_R1 = frozenset({IDENTITY_MODE_LEGACY, IDENTITY_MODE_V1R1})


@dataclass(frozen=True)
class VehicleIdentityR1Control:
    vehicle: str
    redline_rpm: float
    load_floor: float
    speed_floor: float
    high_load_start: float
    high_load_mix_scale: float
    rationale: str


R1_CONTROLS: dict[str, VehicleIdentityR1Control] = {
    "hellcat": VehicleIdentityR1Control(
        "hellcat",
        6500.0,
        0.16,
        0.30,
        0.75,
        1.0,
        "Protected anchor: identity_mix remains zero, so R1 must be byte-identical.",
    ),
    "ferrari_458": VehicleIdentityR1Control(
        "ferrari_458",
        9000.0,
        0.16,
        0.30,
        0.75,
        1.0,
        "Keep flat-plane order identity at speed/load while avoiding v1 idle peak recovery.",
    ),
    "lfa": VehicleIdentityR1Control(
        "lfa",
        9500.0,
        0.16,
        0.30,
        0.75,
        1.0,
        "Keep V10 upper-order identity while preserving low-energy hot-idle behavior.",
    ),
    "gtr_r35": VehicleIdentityR1Control(
        "gtr_r35",
        7200.0,
        0.16,
        0.30,
        0.75,
        0.68,
        "At full load the base turbo/BOV path is already distinctive; reduce only the added R1 source.",
    ),
}


def vehicle_identity_r1_signature(vehicle: str) -> dict:
    if vehicle not in VEHICLE_IDENTITY_PROFILES or vehicle not in R1_CONTROLS:
        raise ValueError(f"unsupported R1 identity vehicle: {vehicle}")
    return {
        "schema": "s12.stage_ag.vehicle_identity_r1.v1",
        "identity_mode": IDENTITY_MODE_V1R1,
        "base_v1_profile": asdict(VEHICLE_IDENTITY_PROFILES[vehicle]),
        "state_control": asdict(R1_CONTROLS[vehicle]),
        "amplitude_policy": "ABSOLUTE_STATE_ENVELOPE_NO_PER_TRACK_IDENTITY_PEAK_NORMALIZATION",
        "blend_policy": "SAMPLEWISE_CONVEX_SOURCE_BLEND",
    }


def _state_envelope(
    vehicle: str,
    rpm: np.ndarray,
    throttle: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return source envelope and sample-wise blend scale in [0, 1]."""
    control = R1_CONTROLS[vehicle]
    rpm_norm = np.clip(np.asarray(rpm, dtype=np.float64) / control.redline_rpm, 0.0, 1.0)
    throttle = np.clip(np.asarray(throttle, dtype=np.float64), 0.0, 1.0)

    load = control.load_floor + (1.0 - control.load_floor) * np.power(throttle, 0.72)
    speed = control.speed_floor + (1.0 - control.speed_floor) * np.sqrt(rpm_norm)
    envelope = np.clip(load * speed, 0.0, 1.0)

    start = float(control.high_load_start)
    if control.high_load_mix_scale >= 1.0:
        blend_scale = np.ones_like(throttle)
    else:
        u = np.clip((throttle - start) / max(1.0 - start, 1e-9), 0.0, 1.0)
        # Smoothstep avoids an audible knee in a future block/real-time implementation.
        u = u * u * (3.0 - 2.0 * u)
        blend_scale = 1.0 - u * (1.0 - control.high_load_mix_scale)
    return envelope, np.clip(blend_scale, 0.0, 1.0)


def synthesize_vehicle_identity_layer_r1(
    vehicle: str,
    rpm_curve: np.ndarray,
    throttle_curve: np.ndarray,
    *,
    sr: int = 48_000,
    seed: int = 20260908,
    return_receipt: bool = False,
) -> np.ndarray | tuple[np.ndarray, dict[str, float | int]]:
    """Render the R1 source without track-relative peak recovery."""
    if vehicle not in VEHICLE_IDENTITY_PROFILES or vehicle not in R1_CONTROLS:
        raise ValueError(f"unsupported R1 identity vehicle: {vehicle}")
    profile = VEHICLE_IDENTITY_PROFILES[vehicle]
    n = int(max(len(np.asarray(rpm_curve).reshape(-1)), len(np.asarray(throttle_curve).reshape(-1))))
    if n < 2:
        raise ValueError("R1 identity render needs at least two samples")
    rpm = _finite_curve(rpm_curve, n)
    throttle = np.clip(_finite_curve(throttle_curve, n), 0.0, 1.0)
    envelope, _ = _state_envelope(vehicle, rpm, throttle)

    crank_hz = np.maximum(rpm, 0.0) / 60.0
    crank_phase = 2.0 * np.pi * np.cumsum(crank_hz) / float(sr)

    tonal = np.zeros(n, dtype=np.float64)
    weight_sum = 0.0
    for order, weight, phase in profile.orders:
        tonal += float(weight) * np.sin(float(order) * crank_phase + float(phase))
        weight_sum += abs(float(weight))
    if weight_sum > 0.0:
        tonal /= weight_sum
    layer = tonal * envelope

    if profile.broadband_mix > 0.0:
        rng = np.random.default_rng(int(seed))
        noise = _band_limited_noise(rng, n, int(sr), profile.broadband_band_hz)
        noise_peak = float(np.max(np.abs(noise)))
        if noise_peak > 1e-15:
            noise /= noise_peak
        order_gate = 0.35 + 0.65 * np.abs(
            np.sin(profile.primary_engine_order * crank_phase)
        )
        layer = layer + profile.broadband_mix * noise * envelope * order_gate

    # Unlike v1, do not normalize this track back to 0.94.  Clipping is only a
    # hard numerical safety bound and therefore cannot amplify idle/low-load audio.
    identity_clip_mask = np.abs(layer) > 0.94 + 1e-12
    clipped_layer = np.clip(layer, -0.94, 0.94)
    identity_clip_error = layer - clipped_layer
    right = (
        causal_fractional_delay(clipped_layer, profile.stereo_delay_samples)
        if profile.stereo_delay_samples > 0.0
        else clipped_layer.copy()
    )
    stereo = np.column_stack([clipped_layer, right])
    if not np.all(np.isfinite(stereo)):
        raise RuntimeError("R1 vehicle identity layer produced non-finite samples")
    if return_receipt:
        return stereo, {
            "identity_layer_preclip_peak": float(np.max(np.abs(layer))),
            "identity_layer_clip_count": int(np.count_nonzero(identity_clip_mask)),
            "identity_layer_clip_error": float(np.max(np.abs(identity_clip_error))),
            "identity_layer_clip_error_rms": float(np.sqrt(np.mean(identity_clip_error * identity_clip_error))),
        }
    return stereo


class VehicleIdentityR1Engine:
    """Reference-remediated opt-in wrapper around the established renderer."""

    def __init__(
        self,
        vehicle_type: str = "ferrari_458",
        sr: int = 48_000,
        *,
        identity_mode: str = IDENTITY_MODE_V1R1,
        numerical_fixes: Iterable[str] = (),
        seed: int = 20260908,
    ) -> None:
        if identity_mode not in IDENTITY_MODES_R1:
            raise ValueError(f"unknown R1 identity mode: {identity_mode}")
        if vehicle_type not in VEHICLE_IDENTITY_PROFILES:
            raise ValueError(f"unsupported R1 identity vehicle: {vehicle_type}")
        self.vehicle_type = vehicle_type
        self.sr = int(sr)
        self.identity_mode = identity_mode
        self.seed = int(seed)
        self.base = EngineAcoustics(
            vehicle_type=vehicle_type,
            sr=sr,
            numerical_fixes=tuple(numerical_fixes),
        )
        self.last_identity_receipt = {
            "post_identity_mix_peak": None,
            "post_identity_clip_count": 0,
            "post_identity_clip_error": 0.0,
            "post_identity_clip_error_rms": 0.0,
            "identity_layer_preclip_peak": None,
            "identity_layer_clip_count": 0,
            "identity_layer_clip_error": 0.0,
            "identity_layer_clip_error_rms": 0.0,
        }
        self.last_base_pcm = None

    @property
    def redline(self) -> float:
        return float(self.base.redline)

    def render_track(
        self,
        rpm_curve: np.ndarray,
        throttle_curve: np.ndarray,
        duration: float,
        shift_events: list | None = None,
        afterfire_events: list | None = None,
        bov_events: list | None = None,
    ) -> np.ndarray:
        state = np.random.get_state()
        np.random.seed(self.seed)
        try:
            base_pcm = self.base.render_track(
                rpm_curve,
                throttle_curve,
                duration,
                shift_events=shift_events,
                afterfire_events=afterfire_events,
                bov_events=bov_events,
            )
            self.last_base_pcm = np.array(base_pcm, dtype=np.int16, copy=True)
        finally:
            np.random.set_state(state)

        profile = VEHICLE_IDENTITY_PROFILES[self.vehicle_type]
        if self.identity_mode == IDENTITY_MODE_LEGACY or profile.identity_mix <= 0.0:
            self.last_identity_receipt = {
                "post_identity_mix_peak": float(np.max(np.abs(base_pcm)) / 32767.0),
                "post_identity_clip_count": 0,
                "post_identity_clip_error": 0.0,
                "post_identity_clip_error_rms": 0.0,
                "identity_layer_preclip_peak": 0.0,
                "identity_layer_clip_count": 0,
                "identity_layer_clip_error": 0.0,
                "identity_layer_clip_error_rms": 0.0,
            }
            return base_pcm

        n = base_pcm.shape[0]
        rpm = _finite_curve(rpm_curve, n)
        throttle = np.clip(_finite_curve(throttle_curve, n), 0.0, 1.0)
        identity, identity_receipt = synthesize_vehicle_identity_layer_r1(
            self.vehicle_type,
            rpm,
            throttle,
            sr=self.sr,
            seed=self.seed,
            return_receipt=True,
        )
        _, blend_scale = _state_envelope(self.vehicle_type, rpm, throttle)
        mix_curve = np.clip(float(profile.identity_mix) * blend_scale, 0.0, 0.25)

        base = base_pcm.astype(np.float64) / 32767.0
        combined = (1.0 - mix_curve[:, None]) * base + mix_curve[:, None] * identity
        clip_mask = np.abs(combined) > 0.94 + 1e-12
        clip_output = np.clip(combined, -0.94, 0.94)
        clip_error = combined - clip_output
        self.last_identity_receipt = {
            **identity_receipt,
            "post_identity_mix_peak": float(np.max(np.abs(combined))),
            "post_identity_clip_count": int(np.count_nonzero(clip_mask)),
            "post_identity_clip_error": float(np.max(np.abs(clip_error))),
            "post_identity_clip_error_rms": float(np.sqrt(np.mean(clip_error * clip_error))),
        }
        return (clip_output * 32767.0).astype(np.int16)
