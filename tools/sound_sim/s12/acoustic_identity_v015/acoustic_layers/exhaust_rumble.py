"""State-dependent, pressure-coupled low-frequency exhaust rumble."""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfilt

from ..contracts import SourceRender, VehicleStateTrace
from .realism_profiles import get_realism_profile


_SCOPE = "synthetic; uncalibrated; not OEM reproduction"


def apply_exhaust_rumble(
    render: SourceRender,
    vehicle_id: str,
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48000,
) -> SourceRender:
    """Add a bounded 30–90 Hz component driven by existing exhaust pressure."""
    render.validate()
    trace.validate()
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    profile = get_realism_profile(vehicle_id)
    count = render.pressure.shape[0]
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    load = np.interp(time_s, trace.time_s, trace.load)
    throttle = np.interp(time_s, trace.time_s, trace.throttle)
    source = _source_stem(render)
    band = butter(
        2,
        (profile.rumble.low_hz / (sample_rate_hz / 2.0), profile.rumble.high_hz / (sample_rate_hz / 2.0)),
        btype="band",
        output="sos",
    )
    shaped = sosfilt(band, np.tanh(2.5 * source), axis=0)
    rpm_env = 0.20 + 0.80 * np.clip(rpm / 4000.0, 0.0, 1.2)
    state_env = (0.20 + 0.55 * load + 0.25 * throttle) * rpm_env
    rumble = profile.rumble.gain * 1.6 * shaped * state_env[:, np.newaxis]
    diagnostics = dict(render.diagnostics)
    diagnostics.update(
        {
            "exhaust_rumble_model": "pressure_stem_state_envelope_bandpass",
            "exhaust_rumble_scope": _SCOPE,
            "rumble_band_hz": (profile.rumble.low_hz, profile.rumble.high_hz),
            "rumble_energy": float(np.sum(np.square(rumble))),
            "rumble_load_mean": float(np.mean(load)),
            "rumble_throttle_mean": float(np.mean(throttle)),
        }
    )
    return SourceRender(
        pressure=np.asarray(render.pressure, dtype=np.float64) + rumble,
        stems={**render.stems, "exhaust_rumble": rumble},
        diagnostics=diagnostics,
    ).validate()


def _source_stem(render: SourceRender) -> np.ndarray:
    for name in ("pressure_pulse", "exhaust_pressure", "exhaust", "left_bank", "rotary"):
        if name in render.stems:
            return np.asarray(render.stems[name], dtype=np.float64)
    return np.asarray(render.pressure, dtype=np.float64)


__all__ = ("apply_exhaust_rumble",)
