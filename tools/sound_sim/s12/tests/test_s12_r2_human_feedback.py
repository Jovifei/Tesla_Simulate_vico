from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.sound_sim.s12.real_reference.anchor_ab_validate import validate_anchor_ab_package
from tools.sound_sim.s12.real_reference.r2_human_feedback import (
    FeedbackImportError,
    build_limited_parameter_recommendations,
    validate_anchor_feedback,
    write_feedback_outputs,
)
from tools.sound_sim.s12.tests.test_s12_anchor_ab_validate import _make_package


def _valid_feedback(package: Path) -> dict:
    manifest = json.loads((package / "anchor_ab_zh_manifest.json").read_text(encoding="utf-8"))
    trials = []
    for trial in manifest["trials"]:
        trials.append(
            {
                "trial_id": trial["trial_id"],
                "vehicle_id": trial["vehicle_id"],
                "file_id": f"{trial['trial_id']}-reference-vs-candidate",
                "reference_audio": {
                    "relative_path": f"audio/{trial['vehicle_id']}/{trial['trial_id']}/reference.wav",
                    "audition_sha256": trial["reference_audition_sha256"],
                    "original_sha256": trial["reference_original_wav_sha256"],
                },
                "candidate_audio": {
                    "relative_path": f"audio/{trial['vehicle_id']}/{trial['trial_id']}/candidate.wav",
                    "audition_sha256": trial["candidate_audition_sha256"],
                },
                "scores": {dimension: "3" for dimension in manifest["scoring_dimensions"]},
                "preference": "参考声音更好",
                "comment": "候选低频偏轻，换挡还需要检查。",
            }
        )
    return {
        "schema_version": "s12-stage-s-human-feedback-zh.v1",
        "test_id": manifest["test_id"],
        "listener_id": "JOVI-TEST-01",
        "package_manifest_sha256": "".join([]),
        "evidence_level": manifest["evidence_level"],
        "package_status": "READY_FOR_REVIEW",
        "automatic_tuning_eligible": False,
        "profile_update": "FORBIDDEN",
        "incomplete_trial_ids": [],
        "trials": trials,
    }


def test_feedback_import_validates_sha_bound_nine_trials(tmp_path: Path) -> None:
    package = _make_package(tmp_path)
    feedback = _valid_feedback(package)
    manifest_path = package / "anchor_ab_zh_manifest.json"
    import hashlib

    feedback["package_manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    feedback_path = tmp_path / "jovi_feedback.json"
    feedback_path.write_text(json.dumps(feedback, ensure_ascii=False), encoding="utf-8")
    receipt = validate_anchor_feedback(feedback_path, package)
    assert receipt["status"] == "VALIDATED_R3_HUMAN_FEEDBACK"
    assert receipt["feedback_rows"] == 9
    assert receipt["problem_categories"]
    assert receipt["automatic_tuning_eligible"] is False
    assert receipt["parameter_changes"] == 0


def test_feedback_import_rejects_incomplete_draft(tmp_path: Path) -> None:
    package = _make_package(tmp_path)
    feedback = _valid_feedback(package)
    feedback["package_status"] = "DRAFT_INCOMPLETE"
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(feedback, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(FeedbackImportError, match="READY_FOR_REVIEW"):
        validate_anchor_feedback(path, package)


def test_feedback_import_rejects_authority_escalation(tmp_path: Path) -> None:
    package = _make_package(tmp_path)
    feedback = _valid_feedback(package)
    feedback["automatic_tuning_eligible"] = True
    path = tmp_path / "unsafe.json"
    path.write_text(json.dumps(feedback, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(FeedbackImportError, match="automatic tuning"):
        validate_anchor_feedback(path, package)


def test_waiting_outputs_with_no_feedback_are_empty_and_fail_closed(tmp_path: Path) -> None:
    package = _make_package(tmp_path)
    output = tmp_path / "out"
    paths = write_feedback_outputs(package, output)
    gate = json.loads(paths["gate"].read_text(encoding="utf-8"))
    recommendations = json.loads(paths["recommendations"].read_text(encoding="utf-8"))
    assert gate["status"] == "WAITING_FOR_JOVI_HUMAN_FEEDBACK"
    assert recommendations["status"] == "WITHHELD_NO_JOVI_FEEDBACK"
    assert recommendations["recommendations"] == []
    assert recommendations["parameter_changes"] == 0
    assert "等待" in paths["report"].read_text(encoding="utf-8")


def test_recommendations_never_emit_numeric_tuning(tmp_path: Path) -> None:
    package = _make_package(tmp_path)
    feedback = _valid_feedback(package)
    import hashlib

    feedback["package_manifest_sha256"] = hashlib.sha256((package / "anchor_ab_zh_manifest.json").read_bytes()).hexdigest()
    path = tmp_path / "valid.json"
    path.write_text(json.dumps(feedback, ensure_ascii=False), encoding="utf-8")
    receipt = validate_anchor_feedback(path, package)
    recommendations = build_limited_parameter_recommendations(receipt)
    assert recommendations["parameter_changes"] == 0
    assert recommendations["automatic_tuning_eligible"] is False
    assert all("value" not in item for item in recommendations["recommendations"])
