"""Stage AG: source-causal vehicle identity layer for S12.

The current S12 renderer already produces convincing mechanical combustion sound,
but several vehicle configurations can still inherit too much of the same sonic
body because the late mechanical/body stage is shared.  Stage AG keeps the
existing ``EngineAcoustics`` renderer as the authority and adds an explicit,
opt-in engine-order identity source around it.

This is method-level clean-room work inspired by:
- engine-sim: engine topology, firing order and exhaust path determine identity;
- EONE/order-based engine-sound work: compact per-engine-order timbre is useful;
- PTR: firing-aligned pulse structure should remain the source anchor;
- SenaTaka/engine-simulator: engine-specific harmonic/noise/resonance modes.

No third-party source code, presets, audio, model weights or proprietary assets
are copied here.  ``legacy`` is byte-preserving.  ``vehicle_identity_v1`` is a
DIAGNOSTIC_ONLY candidate until Jovi listens and accepts it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import numpy as np
from scipy import signal

from ..stage_ad.engine_sim_acoustics import EngineAcoustics, causal_fractional_delay

IDENTITY_MODE_LEGACY = "legacy"
IDENTITY_MODE_V1 = "vehicle_identity_v1"
IDENTITY_MODES = frozenset({IDENTITY_MODE_LEGACY, IDENTITY_MODE_V1})


@dataclass(frozen=True)
class VehicleIdentityProfile:
    """Small interpretable engine-order identity source.

    ``orders`` are conventional engine orders relative to crankshaft rotational
    frequency.  They deliberately follow cylinder/firing topology instead of a
    single shared harmonic recipe.
    """

    vehicle: str
    primary_engine_order: float
    orders: tuple[tuple[float, float, float], ...]
    identity_mix: float
    broadband_mix: float
    broadband_band_hz: tuple[float, float]
    stereo_delay_samples: float
    rationale: str


# Hellcat is deliberately a zero-delta profile: the already-reviewed baseline
# remains the anchor.  The other cars receive distinct order structures rather
# than merely a different EQ/master gain.
VEHICLE_IDENTITY_PROFILES: dict[str, VehicleIdentityProfile] = {
    "hellcat": VehicleIdentityProfile(
        vehicle="hellcat",
        primary_engine_order=4.0,
        orders=((4.0, 1.0, 0.0), (2.0, 0.42, 0.40), (8.0, 0.22, 0.0)),
        identity_mix=0.0,
        broadband_mix=0.0,
        broadband_band_hz=(900.0, 3200.0),
        stereo_delay_samples=0.0,
        rationale=(
            "Cross-plane V8 reference anchor; keep current Hellcat PCM unchanged. "
            "Its existing low-order chest body and supercharger path remain authority."
        ),
    ),
    "ferrari_458": VehicleIdentityProfile(
        vehicle="ferrari_458",
        primary_engine_order=4.0,
        orders=(
            (4.0, 1.00, 0.00),
            (8.0, 0.52, 0.18),
            (12.0, 0.24, 0.55),
            (16.0, 0.10, 0.90),
            (2.0, 0.05, 1.20),
        ),
        identity_mix=0.18,
        broadband_mix=0.035,
        broadband_band_hz=(2200.0, 6200.0),
        stereo_delay_samples=5.0,
        rationale=(
            "Flat-plane V8: suppress the shared V8 half-order rumble and emphasize "
            "the even firing E4 family plus higher-order exhaust edge."
        ),
    ),
    "lfa": VehicleIdentityProfile(
        vehicle="lfa",
        primary_engine_order=5.0,
        orders=(
            (5.0, 1.00, 0.00),
            (10.0, 0.58, 0.22),
            (15.0, 0.31, 0.58),
            (20.0, 0.16, 1.00),
            (2.5, 0.03, 1.30),
        ),
        identity_mix=0.21,
        broadband_mix=0.030,
        broadband_band_hz=(3000.0, 9000.0),
        stereo_delay_samples=4.0,
        rationale=(
            "Even-firing V10: center identity on E5 and dense high orders while "
            "keeping low sub-order energy deliberately weak."
        ),
    ),
    "gtr_r35": VehicleIdentityProfile(
        vehicle="gtr_r35",
        primary_engine_order=3.0,
        orders=(
            (3.0, 1.00, 0.00),
            (6.0, 0.43, 0.30),
            (9.0, 0.18, 0.75),
            (1.5, 0.13, 1.05),
        ),
        identity_mix=0.16,
        broadband_mix=0.070,
        broadband_band_hz=(1400.0, 5600.0),
        stereo_delay_samples=7.0,
        rationale=(
            "Even-firing twin-turbo V6: E3 body with moderate E6/E9 definition; "
            "retain more load-dependent broadband energy because the base renderer "
            "already carries explicit turbo/BOV sources."
        ),
    ),
}


def vehicle_identity_signature(vehicle: str) -> dict:
    if vehicle not in VEHICLE_IDENTITY_PROFILES:
        raise ValueError(f"unsupported identity vehicle: {vehicle}")
    return asdict(VEHICLE_IDENTITY_PROFILES[vehicle])


def _finite_curve(values: np.ndarray, size: int) -> np.ndarray:
    curve = np.asarray(values, dtype=np.float64).reshape(-1)
    if curve.size < 2 or not np.all(np.isfinite(curve)):
        raise ValueError("identity input curve must contain finite samples")
    if curve.size != size:
        curve = np.interp(
            np.linspace(0.0, 1.0, size),
            np.linspace(0.0, 1.0, curve.size),
            curve,
        )
    return curve


def _band_limited_noise(
    rng: np.random.Generator,
    size: int,
    sr: int,
    band_hz: tuple[float, float],
) -> np.ndarray:
    low, high = map(float, band_hz)
    nyquist = 0.5 * sr
    low = max(20.0, min(low, nyquist * 0.85))
    high = max(low + 20.0, min(high, nyquist * 0.95))
    if high <= low:
        return np.zeros(size, dtype=np.float64)
    sos = signal.butter(2, [low, high], btype="bandpass", fs=sr, output="sos")
    return signal.sosfilt(sos, rng.normal(0.0, 1.0, size))


def synthesize_vehicle_identity_layer(
    vehicle: str,
    rpm_curve: np.ndarray,
    throttle_curve: np.ndarray,
    *,
    sr: int = 48_000,
    seed: int = 20260908,
) -> np.ndarray:
    """Return a finite stereo identity layer in [-0.94, 0.94]."""
    if vehicle not in VEHICLE_IDENTITY_PROFILES:
        raise ValueError(f"unsupported identity vehicle: {vehicle}")
    profile = VEHICLE_IDENTITY_PROFILES[vehicle]
    n = int(max(len(np.asarray(rpm_curve).reshape(-1)), len(np.asarray(throttle_curve).reshape(-1))))
    if n < 2:
        raise ValueError("identity render needs at least two samples")
    rpm = _finite_curve(rpm_curve, n)
    throttle = np.clip(_finite_curve(throttle_curve, n), 0.0, 1.0)

    crank_hz = np.maximum(rpm, 0.0) / 60.0
    crank_phase = 2.0 * np.pi * np.cumsum(crank_hz) / float(sr)

    tonal = np.zeros(n, dtype=np.float64)
    weight_sum = 0.0
    for order, weight, phase in profile.orders:
        tonal += float(weight) * np.sin(float(order) * crank_phase + float(phase))
        weight_sum += abs(float(weight))
    if weight_sum > 0.0:
        tonal /= weight_sum

    # Engine-order energy increases with load and, more gently, with speed.
    rpm_norm = np.clip(rpm / max(float(np.max(rpm)), 1.0), 0.0, 1.0)
    envelope = (0.28 + 0.72 * np.power(throttle, 0.72)) * (
        0.62 + 0.38 * np.sqrt(rpm_norm)
    )
    tonal *= envelope

    layer = tonal
    if profile.broadband_mix > 0.0:
        rng = np.random.default_rng(int(seed))
        noise = _band_limited_noise(rng, n, int(sr), profile.broadband_band_hz)
        noise_peak = float(np.max(np.abs(noise)))
        if noise_peak > 1e-15:
            noise /= noise_peak
        # Modulate the noise with the primary order so it remains tied to the
        # combustion lifecycle rather than becoming a generic hiss/EQ layer.
        order_gate = 0.35 + 0.65 * np.abs(
            np.sin(profile.primary_engine_order * crank_phase)
        )
        layer = layer + profile.broadband_mix * noise * envelope * order_gate

    peak = float(np.max(np.abs(layer)))
    if peak > 1e-15:
        layer = layer / peak * 0.94

    right = (
        causal_fractional_delay(layer, profile.stereo_delay_samples)
        if profile.stereo_delay_samples > 0.0
        else layer.copy()
    )
    stereo = np.column_stack([layer, right])
    if not np.all(np.isfinite(stereo)):
        raise RuntimeError("vehicle identity layer produced non-finite PCM")
    return stereo


class VehicleIdentityEngine:
    """Opt-in identity wrapper around the established EngineAcoustics renderer.

    The wrapper is intentionally conservative:
    - ``legacy`` returns the base renderer bytes unchanged;
    - ``vehicle_identity_v1`` also returns Hellcat unchanged;
    - Ferrari/LFA/GT-R use a bounded convex source blend, never a master gain;
    - the existing numerical-fix flags keep their original meaning.
    """

    def __init__(
        self,
        vehicle_type: str = "ferrari_458",
        sr: int = 48_000,
        *,
        identity_mode: str = IDENTITY_MODE_V1,
        numerical_fixes: Iterable[str] = (),
        seed: int = 20260908,
    ) -> None:
        if identity_mode not in IDENTITY_MODES:
            raise ValueError(f"unknown identity mode: {identity_mode}")
        if vehicle_type not in VEHICLE_IDENTITY_PROFILES:
            raise ValueError(f"unsupported identity vehicle: {vehicle_type}")
        self.vehicle_type = vehicle_type
        self.sr = int(sr)
        self.identity_mode = identity_mode
        self.seed = int(seed)
        self.base = EngineAcoustics(
            vehicle_type=vehicle_type,
            sr=sr,
            numerical_fixes=tuple(numerical_fixes),
        )

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
        finally:
            np.random.set_state(state)

        profile = VEHICLE_IDENTITY_PROFILES[self.vehicle_type]
        if self.identity_mode == IDENTITY_MODE_LEGACY or profile.identity_mix <= 0.0:
            return base_pcm

        n = base_pcm.shape[0]
        rpm = _finite_curve(rpm_curve, n)
        throttle = _finite_curve(throttle_curve, n)
        identity = synthesize_vehicle_identity_layer(
            self.vehicle_type,
            rpm,
            throttle,
            sr=self.sr,
            seed=self.seed,
        )
        base = base_pcm.astype(np.float64) / 32767.0
        mix = float(profile.identity_mix)
        # Convex source blend: no post-hoc master boost and no per-track gain
        # compensation.  Both source terms are already bounded to +/-0.94.
        combined = (1.0 - mix) * base + mix * identity
        combined = np.clip(combined, -0.94, 0.94)
        return (combined * 32767.0).astype(np.int16)
