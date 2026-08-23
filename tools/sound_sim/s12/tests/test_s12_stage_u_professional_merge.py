from __future__ import annotations

import pytest

from tools.sound_sim.s12.real_reference.stage_u_professional_merge import merge_professional_triad_results


def _metric(value: float) -> dict:
    return {"metrics": {"loudness_sone": value, "sharpness_acum": value, "roughness_asper": value, "fluctuation_vacil": value, "tone_to_noise_ratio_db": value, "prominence_ratio_db": value}}


def test_professional_merge_binds_same_sha_and_reports_candidate_improvement() -> None:
    legacy = [{"reference_id": "r", "candidate_id": "c", "vehicle_id": "hellcat", "scenario": "launch", "reference_sha256": "a", "parent_sha256": "b", "candidate_sha256": "c", "parent_distance": 0.50, "candidate_distance": 0.25, "absolute_improvement": 0.25, "relative_improvement": 0.5, "hard_gates_pass": True}]
    matlab = {
        "results": [
            {"clip_id": "reference::r", "input_sha256": "a", **_metric(10.0)},
            {"clip_id": "parent::r", "input_sha256": "b", **_metric(20.0)},
            {"clip_id": "candidate::r::c", "input_sha256": "c", **_metric(15.0)},
        ]
    }
    mosqito = {"results": [
        {"clip_id": "reference::r", "input_sha256": "a", **_metric(10.0)},
        {"clip_id": "parent::r", "input_sha256": "b", **_metric(20.0)},
        {"clip_id": "candidate::r::c", "input_sha256": "c", **_metric(15.0)},
    ]}
    manifest = {"clips": [
        {"clip_id": "reference::r", "sha256": "a"},
        {"clip_id": "parent::r", "sha256": "b"},
        {"clip_id": "candidate::r::c", "sha256": "c"},
    ]}
    audio_features = {"results": [{
        "reference_id": "r", "candidate_id": "c", "professional_bound": True,
        "parent_distance": 1.0, "candidate_distance": 0.5,
        "sha_binding": {"reference": "a", "parent": "b", "candidate": "c"},
    }]}
    result = merge_professional_triad_results(legacy, manifest, matlab, mosqito, audio_features)
    row = result["results"][0]
    assert row["professional_bound"] is True
    assert row["candidate_distance"] < row["parent_distance"]
    assert row["absolute_improvement"] > 0.0
    assert "audioFeatureExtractor" in row["professional_components"]


def test_professional_merge_rejects_sha_mismatch() -> None:
    legacy = [{"reference_id": "r", "candidate_id": "c", "vehicle_id": "hellcat", "scenario": "launch", "reference_sha256": "a", "parent_sha256": "b", "candidate_sha256": "c", "parent_distance": 0.5, "candidate_distance": 0.4, "absolute_improvement": 0.1, "relative_improvement": 0.2, "hard_gates_pass": True}]
    manifest = {"clips": [{"clip_id": "reference::r", "sha256": "a"}, {"clip_id": "parent::r", "sha256": "b"}, {"clip_id": "candidate::r::c", "sha256": "c"}]}
    rows = [{"clip_id": "reference::r", "input_sha256": "wrong", **_metric(1.0)}, {"clip_id": "parent::r", "input_sha256": "b", **_metric(1.0)}, {"clip_id": "candidate::r::c", "input_sha256": "c", **_metric(1.0)}]
    audio_features = {"results": [{"reference_id": "r", "candidate_id": "c", "professional_bound": True, "parent_distance": 1.0, "candidate_distance": 0.5, "sha_binding": {"reference": "a", "parent": "b", "candidate": "c"}}]}
    result = merge_professional_triad_results(legacy, manifest, {"results": rows}, {"results": rows}, audio_features)
    assert result["results"][0]["professional_bound"] is False


@pytest.mark.parametrize("legacy_sha", [None, "wrong"])
def test_professional_merge_rejects_missing_or_mismatched_legacy_component_sha(legacy_sha: str | None) -> None:
    legacy = {
        "reference_id": "r", "candidate_id": "c", "vehicle_id": "hellcat", "scenario": "launch",
        "reference_sha256": "a", "parent_sha256": "b", "candidate_sha256": "c",
        "parent_distance": 0.5, "candidate_distance": 0.4, "absolute_improvement": 0.1,
        "relative_improvement": 0.2, "hard_gates_pass": True,
    }
    if legacy_sha is None:
        legacy.pop("candidate_sha256")
    else:
        legacy["candidate_sha256"] = legacy_sha
    manifest = {"clips": [{"clip_id": "reference::r", "sha256": "a"}, {"clip_id": "parent::r", "sha256": "b"}, {"clip_id": "candidate::r::c", "sha256": "c"}]}
    rows = [{"clip_id": "reference::r", "input_sha256": "a", **_metric(1.0)}, {"clip_id": "parent::r", "input_sha256": "b", **_metric(2.0)}, {"clip_id": "candidate::r::c", "input_sha256": "c", **_metric(1.5)}]
    audio_features = {"results": [{"reference_id": "r", "candidate_id": "c", "professional_bound": True, "parent_distance": 1.0, "candidate_distance": 0.5, "sha_binding": {"reference": "a", "parent": "b", "candidate": "c"}}]}

    result = merge_professional_triad_results([legacy], manifest, {"results": rows}, {"results": rows}, audio_features)

    row = result["results"][0]
    assert row["professional_bound"] is False
    assert row["professional_binding_status"] == "LEGACY_SHA_NOT_BOUND"
    assert result["automatic_tuning_eligible"] is False
    assert result["order_status"] == "ORDER_COMPARISON_NOT_QUALIFIED"
    assert result["abx_ready"] is False
