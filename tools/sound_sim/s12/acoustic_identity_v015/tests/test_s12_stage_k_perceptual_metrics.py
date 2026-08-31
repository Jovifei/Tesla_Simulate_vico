from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_k.perceptual_metrics import (
    compute_stage_k_perceptual_metrics,
    evaluate_stage_k_hard_gates,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_k.candidate_search import (
    select_stage_k_candidate,
)
from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.sources.mercedes_na_v8_source_v3 import render_c63_w204_v3
from tools.sound_sim.s12.acoustic_identity_v015.sources.nissan_parallel_twin_turbo_v6_source_v3 import render_gtr_r35_v3
from tools.sound_sim.s12.acoustic_identity_v015.sources.supercharger_whine_v4 import render_supercharger_whine_v4


def _fixture(duration_s: float = 1.0, sample_rate_hz: int = 4000):
    count = int(duration_s * sample_rate_hz)
    time_s = np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.linspace(1000.0, 5000.0, count)
    load = np.where(time_s < 0.25, 0.15, np.where(time_s < 0.75, 0.85, 0.20))
    throttle = load.copy()
    phase = np.cumsum(rpm / 60.0) / sample_rate_hz
    pressure = 0.22 * np.sin(2.0 * np.pi * phase) + 0.06 * np.sin(2.0 * np.pi * 7.6 * phase)
    pressure = np.column_stack((pressure, pressure * 0.9))
    exhaust = np.column_stack((0.16 * np.sin(2.0 * np.pi * 1.2 * phase),) * 2)
    blower = np.column_stack((0.08 * load * np.sin(2.0 * np.pi * 11.8 * phase),) * 2)
    stems = {
        "exhaust": exhaust,
        "blower": blower,
        "exhaust_rumble": exhaust * 0.25,
    }
    render = SimpleNamespace(
        pressure=pressure,
        stems=stems,
        diagnostics={"vehicle_id": "hellcat", "sample_rate_hz": sample_rate_hz},
    )
    trace = SimpleNamespace(time_s=time_s, rpm=rpm, load=load, throttle=throttle)
    return render, trace


def test_metrics_cover_state_level_band_order_roughness_events_and_pcm_health() -> None:
    render, trace = _fixture()
    metrics = compute_stage_k_perceptual_metrics(render, trace, sample_rate_hz=4000)
    for key in (
        "state_rms",
        "state_lufs",
        "low_load_high_load_delta_db",
        "band_shares",
        "spectral_centroid_hz",
        "order_ridge_error",
        "tonal_prominence",
        "spectral_roughness",
        "event_inter_onset_interval_s",
        "event_inter_onset_cv",
        "transition_dip_db",
        "transition_overshoot_db",
        "transition_settling_s",
        "pcm_health",
    ):
        assert key in metrics
    assert set(metrics["band_shares"]) == {"20_250", "250_1000", "1000_4000", "4000_12000"}
    assert metrics["pcm_health"]["finite"] is True
    assert 0.0 <= metrics["spectral_roughness"]


def test_metrics_interpolate_sparse_trace_and_expose_hellcat_specific_fields() -> None:
    render, trace = _fixture()
    sparse = SimpleNamespace(
        time_s=trace.time_s[::100], rpm=trace.rpm[::100], load=trace.load[::100], throttle=trace.throttle[::100]
    )
    metrics = compute_stage_k_perceptual_metrics(render, sparse, sample_rate_hz=4000, vehicle_id="hellcat")
    for key in ("blower_exhaust_ratio_db", "blower_load_correlation", "sideband_main_ratio"):
        assert key in metrics["vehicle_metrics"]
        assert np.isfinite(float(metrics["vehicle_metrics"][key]))


def test_hard_gates_fail_closed_and_search_is_order_independent() -> None:
    parent = {
        "state_regression": {"idle": 0.0, "acceleration": 0.0, "full_pull": 0.0},
        "parameters": {"gain": 0.0},
    }
    good = {
        "candidate_id": "b",
        "parameters": {"gain": 0.20},
        "metrics": {"hard_gates": {"pcm": True}, "state_regression": {"idle": 0.01}, "vehicle_error": 0.2, "blower_load_correlation": 0.9},
    }
    better = {
        "candidate_id": "a",
        "parameters": {"gain": 0.10},
        "metrics": {"hard_gates": {"pcm": True}, "state_regression": {"idle": 0.01}, "vehicle_error": 0.2, "blower_load_correlation": 0.9},
    }
    bad = {
        "candidate_id": "z",
        "parameters": {"gain": 0.01},
        "metrics": {"hard_gates": {"pcm": False}, "state_regression": {"idle": 0.0}, "vehicle_error": 0.0},
    }
    assert evaluate_stage_k_hard_gates({"pcm_health": {"finite": True, "clipping_count": 0}}, "hellcat")["all_pass"] is False
    assert select_stage_k_candidate([good, bad, better], parent, "hellcat")["candidate_id"] == "a"
    assert select_stage_k_candidate([better, good, bad], parent, "hellcat")["candidate_id"] == "a"


def test_search_rejects_unbounded_candidate_lists() -> None:
    with pytest.raises(ValueError, match="64"):
        select_stage_k_candidate(
            [
                {"candidate_id": str(i), "parameters": {}, "metrics": {"hard_gates": {"pcm": True}}}
                for i in range(65)
            ],
            {},
            "c63_w204",
        )


def test_vehicle_metrics_use_the_stage_k_source_stem_names() -> None:
    time_s = np.linspace(0.0, 1.0, 81)
    trace = VehicleStateTrace(
        time_s,
        np.linspace(1800.0, 6200.0, time_s.size),
        np.linspace(0.25, 0.90, time_s.size),
        np.linspace(0.30, 0.95, time_s.size),
        np.gradient(np.linspace(1800.0, 6200.0, time_s.size) / 60.0, time_s),
    )
    c63 = render_c63_w204_v3(trace, sample_rate_hz=8000)
    gtr = render_gtr_r35_v3(trace, sample_rate_hz=8000)
    c63_metrics = compute_stage_k_perceptual_metrics(c63, trace, 8000, vehicle_id="c63_w204")
    gtr_metrics = compute_stage_k_perceptual_metrics(gtr, trace, 8000, vehicle_id="gtr_r35")
    assert c63_metrics["vehicle_metrics"]["bark_upper_partial_ratio"] > 0.0
    assert gtr_metrics["vehicle_metrics"]["turbo_a_activity"] > 0.0
    assert gtr_metrics["vehicle_metrics"]["turbo_b_activity"] > 0.0
    assert gtr_metrics["vehicle_metrics"]["turbo_exhaust_ratio_db"] > -100.0


def test_hellcat_sideband_metric_is_an_rms_ratio() -> None:
    count = 8000
    rpm = np.full(count, 4200.0)
    load = np.full(count, 0.85)
    throttle = np.full(count, 0.90)
    phase = np.cumsum(rpm) / (60.0 * count)
    render = render_supercharger_whine_v4(rpm, load, throttle, phase, 8000, {"sideband_main_ratio": 0.12})
    trace = VehicleStateTrace(
        np.arange(count, dtype=np.float64) / 8000.0,
        rpm,
        load,
        throttle,
        np.zeros(count),
    )
    metrics = compute_stage_k_perceptual_metrics(render, trace, 8000, vehicle_id="hellcat")
    assert 0.08 <= metrics["vehicle_metrics"]["sideband_main_ratio"] <= 0.18
