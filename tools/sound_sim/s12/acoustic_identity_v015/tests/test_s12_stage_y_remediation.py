"""Focused Stage-Y correctness contracts for the closed-loop remediation."""

from __future__ import annotations

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.stage_x.candidate_search import SEARCH_SCENES
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.human_feedback_objective import (
    combine_reference_and_feedback_objective,
    evaluate_feedback_alignment,
    normalize_feedback,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.multi_reference_comparator import (
    CANONICAL_BAND_EDGES_HZ,
    compare_case,
    timbre_metrics,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.reference_governance import (
    classify_reference_evidence,
    summarize_reference_cases,
)


def test_canonical_bands_are_explicit_positive_width_pairs() -> None:
    assert len(CANONICAL_BAND_EDGES_HZ) == 4
    assert all(hi > lo for lo, hi in CANONICAL_BAND_EDGES_HZ)


def test_canonical_band_shares_have_no_zero_width_artifacts() -> None:
    sample_rate = 48000
    t = np.arange(sample_rate * 2, dtype=np.float64) / sample_rate
    signal = (
        0.5 * np.sin(2 * np.pi * 100.0 * t)
        + 0.3 * np.sin(2 * np.pi * 600.0 * t)
        + 0.2 * np.sin(2 * np.pi * 2500.0 * t)
        + 0.1 * np.sin(2 * np.pi * 6500.0 * t)
    )
    shares = timbre_metrics(signal, sample_rate)["canonical_band_shares"]
    assert len(shares) == 4
    assert all(value > 0.0 for value in shares)
    assert abs(sum(shares) - 1.0) < 1e-9


def test_spectral_flux_responds_to_shape_change_not_only_level_change() -> None:
    sample_rate = 48000
    half = sample_rate
    t = np.arange(half, dtype=np.float64) / sample_rate
    first = np.sin(2 * np.pi * 200.0 * t)
    shape_change = np.concatenate((first, np.sin(2 * np.pi * 2400.0 * t)))
    level_change = np.concatenate((first, 0.3 * first))
    shape_flux = timbre_metrics(shape_change, sample_rate)["spectral_flux"]
    level_flux = timbre_metrics(level_change, sample_rate)["spectral_flux"]
    assert shape_flux > level_flux


def test_roughness_uses_time_modulation_axis() -> None:
    sample_rate = 48000
    t = np.arange(sample_rate * 2, dtype=np.float64) / sample_rate
    carrier = np.sin(2 * np.pi * 500.0 * t)
    steady = carrier
    modulated = carrier * (0.55 + 0.45 * np.sin(2 * np.pi * 35.0 * t))
    steady_roughness = timbre_metrics(steady, sample_rate)["roughness_proxy"]
    modulated_roughness = timbre_metrics(modulated, sample_rate)["roughness_proxy"]
    assert modulated_roughness > steady_roughness


def test_persistent_narrowband_whine_is_observable() -> None:
    sample_rate = 48000
    t = np.arange(sample_rate * 2, dtype=np.float64) / sample_rate
    rng = np.random.default_rng(12)
    whine = np.sin(2 * np.pi * 1800.0 * t) + 0.02 * rng.standard_normal(t.size)
    broadband = rng.standard_normal(t.size)
    whine_metrics = timbre_metrics(whine, sample_rate)
    broadband_metrics = timbre_metrics(broadband, sample_rate)
    assert whine_metrics["persistent_tone_ratio"] > broadband_metrics["persistent_tone_ratio"]
    assert whine_metrics["narrowband_whine_proxy"] > broadband_metrics["narrowband_whine_proxy"]


def test_compare_case_emits_whine_metrics_and_v2_version() -> None:
    sample_rate = 48000
    t = np.arange(sample_rate, dtype=np.float64) / sample_rate
    reference = np.sin(2 * np.pi * 220.0 * t)
    parent = np.sin(2 * np.pi * 1800.0 * t)
    candidate = 0.8 * np.sin(2 * np.pi * 220.0 * t) + 0.2 * parent
    result = compare_case(reference, parent, candidate, sample_rate, candidate_id="P3")
    assert result["metric_version"] == "s12.stage_y.comparator_metrics.v2"
    assert "persistent_tone_ratio" in result["metrics"]
    assert "narrowband_whine_proxy" in result["metrics"]


def test_video_derived_manifest_cannot_promote_itself_to_r2() -> None:
    result = classify_reference_evidence({
        "source_level": "R2",
        "source_url": "https://www.youtube.com/watch?v=example",
        "extraction": "yt-dlp bestaudio followed by ffmpeg WAV decode",
        "rights_status": "R2_RELATIVE_REVIEW_ONLY",
    })
    assert result["declared_evidence_level"] == "R2"
    assert result["effective_evidence_level"] == "R3"
    assert "VIDEO_DERIVED_REFERENCE_CANNOT_BE_PROMOTED" in result["downgrade_reasons"]


def test_independent_reference_count_deduplicates_scenario_windows() -> None:
    cases = [
        {
            "status": "BOUND",
            "scenario": "hot_idle",
            "source_id": "recording-A",
            "recording_session_id": "session-A",
            "audio_sha256": "a" * 64,
            "evidence_level": "R2",
        },
        {
            "status": "BOUND",
            "scenario": "steady_low",
            "source_id": "recording-A",
            "recording_session_id": "session-A",
            "audio_sha256": "a" * 64,
            "evidence_level": "R2",
        },
        {
            "status": "BOUND",
            "scenario": "full_pull",
            "source_id": "recording-B",
            "recording_session_id": "session-B",
            "audio_sha256": "b" * 64,
            "evidence_level": "R2",
        },
    ]
    summary = summarize_reference_cases(cases)
    assert summary["bound_scenario_count"] == 3
    assert summary["bound_case_count"] == 3
    assert summary["unique_audio_sha_count"] == 2
    assert summary["independent_recording_session_count"] == 2
    assert summary["selection_reference_count"] == 2
    assert summary["independent_source_gate_passed"] is True


def test_jovi_feedback_is_bounded_and_rx7_speech_row_is_blocked() -> None:
    hellcat = {
        "vehicle_id": "hellcat",
        "software_agreement": "部分符合",
        "problems": ["机械感不足", "低频无冲击", "固定电子哨声", "回火不自然"],
        "notes": "低频怠速轰鸣不如原车，固定电子哨声仍明显。",
    }
    dimensions = {
        "low_frequency_body": -0.20,
        "120_400_pressure_attack": -0.20,
        "mechanical_texture": -0.10,
        "synthetic_artifact": -0.20,
        "forced_induction_identity": -0.10,
        "afterfire_naturalness": -0.05,
    }
    combined = combine_reference_and_feedback_objective(0.12, dimensions, hellcat)
    assert 0.0 < combined["feedback_adjustment"] <= 0.05
    assert combined["combined_engineering_objective"] > 0.12
    assert combined["formal_selection_eligible"] is False

    rx7 = normalize_feedback({
        "vehicle_id": "rx7_fd",
        "software_agreement": "无法判断",
        "notes": "RX7这个片段是别人在讲话，不是真正车型声浪。",
    })
    assert rx7["usable_for_engineering_objective"] is False
    alignment = evaluate_feedback_alignment({}, rx7)
    assert alignment["dimension_weights"] == {}
    assert alignment["objective_adjustment"] == 0.0


def test_search_scene_contract_includes_full_dynamic_loop() -> None:
    bound = {scenario for _, scenario, _ in SEARCH_SCENES}
    assert {
        "hot_idle",
        "steady_low",
        "steady_mid",
        "steady_high",
        "tip_in",
        "full_pull",
        "shift",
        "lift",
        "afterfire",
        "idle_return",
    } == bound
