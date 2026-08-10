from __future__ import annotations

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.sources.supercharger_whine_v2 import render_supercharger_whine_v2
from tools.sound_sim.s12.acoustic_identity_v015.stage_h.perceptual_metrics import compute_hellcat_perceptual_metrics


def _trace(duration_s: float = 0.8, sample_rate_hz: int = 48000) -> VehicleStateTrace:
    time_s = np.arange(int(duration_s * sample_rate_hz) + 1, dtype=np.float64) / sample_rate_hz
    rpm = np.linspace(1800.0, 5800.0, time_s.size)
    load = np.linspace(0.25, 0.95, time_s.size)
    throttle = load.copy()
    phase = np.cumsum(rpm) / (60.0 * sample_rate_hz)
    return VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s))


def test_hellcat_perceptual_metrics_are_finite_and_track_orders() -> None:
    trace = _trace()
    time_s = trace.time_s
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    load = np.interp(time_s, trace.time_s, trace.load)
    throttle = np.interp(time_s, trace.time_s, trace.throttle)
    phase = np.cumsum(rpm) / (60.0 * 48000.0)
    render = render_supercharger_whine_v2(rpm, load, throttle, phase, 48000, {
        "blower_gain_scale": 1.12,
        "blower_boost_mix": 1.15,
        "lobe_family_mix": 1.05,
        "upper_family_tilt_db": -2.0,
        "sideband_depth": 0.10,
        "boost_attack_s": 0.075,
        "boost_release_s": 0.24,
        "bypass_release_gain": 0.10,
    })
    metrics = compute_hellcat_perceptual_metrics(render, trace)
    assert metrics["shaft_order_error"] < 0.01
    assert metrics["lobe_order_error"] < 0.01
    assert metrics["upper_order_error"] < 0.01
    assert 0.05 <= metrics["sideband_to_main_ratio"] <= 0.20
    assert float(metrics["blower_load_correlation"]) >= 0.82
    assert np.isfinite(float(metrics["upper_band_short_time_peak"]))
