from __future__ import annotations

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.contracts import SourceRender, VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_i.perceptual_metrics import (
    compute_stage_i_perceptual_metrics,
)


def _stereo(mono: np.ndarray) -> np.ndarray:
    return np.column_stack((0.7 * mono, mono))


def test_metrics_measure_orders_clusters_state_ratios_and_probe_times() -> None:
    sample_rate_hz = 48000
    duration_s = 1.2
    count = int(duration_s * sample_rate_hz)
    time_s = np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.linspace(2200.0, 4800.0, count)
    load = np.where(time_s < 0.30, 0.12, np.where(time_s < 0.90, 0.85, 0.30))
    throttle = load.copy()
    engine_phase = np.cumsum(rpm / 60.0) / sample_rate_hz
    shaft_phase = 2.36 * engine_phase
    lobe_phase = 11.8 * engine_phase
    upper_phase = 23.6 * engine_phase
    envelope = 0.08 + 0.72 * load
    shaft = 0.10 * envelope * np.sin(2.0 * np.pi * shaft_phase)
    lobe = 0.20 * envelope * (
        np.sin(2.0 * np.pi * lobe_phase)
        + 0.28 * np.sin(2.0 * np.pi * 11.66 * engine_phase)
        + 0.28 * np.sin(2.0 * np.pi * 11.94 * engine_phase)
    )
    upper = 0.04 * envelope * np.sin(2.0 * np.pi * upper_phase)
    sidebands = 0.08 * envelope * (
        np.sin(2.0 * np.pi * (lobe_phase + 4.0 * engine_phase))
        + np.sin(2.0 * np.pi * (lobe_phase - 4.0 * engine_phase))
    )
    bypass = np.zeros(count, dtype=np.float64)
    bypass[int(0.90 * sample_rate_hz):int(1.10 * sample_rate_hz)] = np.linspace(
        0.10, 0.0, int(0.20 * sample_rate_hz), endpoint=False
    )
    blower = shaft + lobe + upper + sidebands + bypass
    exhaust = 0.32 * np.sin(2.0 * np.pi * 92.0 * time_s)
    rumble = 0.08 * np.sin(2.0 * np.pi * 58.0 * time_s)
    pressure = _stereo(blower + exhaust + rumble)
    stems = {
        "blower": _stereo(blower),
        "blower_shaft": _stereo(shaft),
        "blower_lobe_family": _stereo(lobe),
        "blower_upper_family": _stereo(upper),
        "blower_sidebands": _stereo(sidebands),
        "blower_bypass_release": _stereo(bypass),
        "exhaust": _stereo(exhaust),
        "exhaust_rumble": _stereo(rumble),
    }
    render = SourceRender(pressure=pressure, stems=stems, diagnostics={})
    trace = VehicleStateTrace(
        time_s=time_s,
        rpm=rpm,
        load=load,
        throttle=throttle,
        acceleration_mps2=np.gradient(rpm, time_s),
    )
    masks = {
        "idle": time_s < 0.30,
        "acceleration": (time_s >= 0.30) & (time_s < 0.70),
        "full_pull": (time_s >= 0.70) & (time_s < 0.90),
    }
    probe_command = np.zeros(800, dtype=np.float64)
    probe_command[100:450] = 1.0
    boost_response = np.zeros_like(probe_command)
    boost_response[100:200] = np.linspace(0.0, 1.0, 100, endpoint=False)
    boost_response[200:450] = 1.0
    boost_response[450:750] = np.linspace(1.0, 0.0, 300, endpoint=False)
    bypass_gate = np.zeros(800, dtype=np.float64)
    bypass_gate[450:] = 1.0
    bypass_response = np.zeros_like(bypass_gate)
    bypass_response[450:650] = np.linspace(1.0, 0.0, 200, endpoint=False)

    metrics = compute_stage_i_perceptual_metrics(
        render,
        trace,
        sample_rate_hz=sample_rate_hz,
        state_masks=masks,
        response_probe={
            "sample_rate_hz": 1000,
            "boost_response": boost_response,
            "boost_command": probe_command,
            "bypass_response": bypass_response,
            "bypass_gate": bypass_gate,
        },
    )

    assert float(metrics["shaft_order_error"]) < 0.01
    assert float(metrics["lobe_order_error"]) < 0.01
    assert float(metrics["blower_to_exhaust_ratio_acceleration_db"]) > float(metrics["blower_to_exhaust_ratio_idle_db"])
    assert 0.0 < float(metrics["single_ridge_concentration"]) <= 1.0
    assert 0.0 < float(metrics["order_cluster_width_ratio"]) < 0.05
    assert 0.0 < float(metrics["sideband_to_main_ratio"]) < 1.0
    assert abs(float(metrics["boost_attack_10_90_s"]) - 0.080) <= 0.003
    assert abs(float(metrics["boost_release_90_10_s"]) - 0.240) <= 0.003
    assert abs(float(metrics["bypass_decay_90_10_s"]) - 0.160) <= 0.003
    assert int(metrics["bypass_event_count"]) == 1
    for name, value in metrics.items():
        if isinstance(value, (float, int)):
            assert np.isfinite(float(value)), name


def test_metrics_fail_closed_when_required_state_mask_is_missing() -> None:
    audio = np.zeros((64, 2), dtype=np.float64)
    render = SourceRender(audio, {"blower": audio}, {})
    time_s = np.arange(64, dtype=np.float64) / 48000.0
    trace = VehicleStateTrace(time_s, np.ones(64) * 1000.0, np.zeros(64), np.zeros(64), np.zeros(64))
    with np.testing.assert_raises(ValueError):
        compute_stage_i_perceptual_metrics(render, trace, state_masks={"idle": np.ones(64, dtype=bool)})
