from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.sound_sim.s12.real_reference.professional_guided_feedback import (
    GuidedFeedbackError,
    validate_guided_feedback,
)


ROOT = Path(__file__).resolve().parents[4] / "tasks" / "reports" / "runtime" / "S12_Professional_Comparison_Dashboard_v1"


def _valid_feedback(tmp_path: Path) -> tuple[Path, Path]:
    metrics_path = ROOT / "professional_pair_metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    rows = []
    for pair in metrics["pairs"]:
        rows.append({
            "pair_id": pair["pair_id"],
            "file_id": pair["file_id"],
            "vehicle_id": pair["vehicle_id"],
            "reference_sha256": pair["reference_sha256"],
            "candidate_sha256": pair["candidate_sha256"],
            "software_agreement": "部分符合",
            "identity": 72,
            "realism": 64,
            "problems": ["太闷", "机械感不足"],
            "preference": "候选",
            "notes": "软件方向基本符合听感。",
        })
    feedback = {
        "schema_version": "s12-professional-jovi-guided-feedback-v1",
        "package_manifest_sha256": metrics["manifest_sha256"],
        "evidence_level": "R3",
        "status": "READY_FOR_REVIEW",
        "automatic_tuning_eligible": False,
        "profile_update": "FORBIDDEN",
        "audio_submit_gate": {"status": "PASS"},
        "rows": rows,
    }
    path = tmp_path / "Jovi_Guided_Feedback.json"
    path.write_text(json.dumps(feedback, ensure_ascii=False), encoding="utf-8")
    return path, metrics_path


def test_guided_feedback_import_validates_all_rows_and_summarizes_problems(tmp_path: Path) -> None:
    feedback, metrics = _valid_feedback(tmp_path)
    receipt = validate_guided_feedback(feedback, metrics)
    assert receipt["status"] == "VALIDATED_R2_R3_GUIDED_FEEDBACK"
    assert receipt["feedback_rows"] == 9
    assert receipt["vehicle_summary"]["hellcat"]["rows"] == 3
    assert receipt["problem_summary"]["太闷"] == 9
    assert receipt["parameter_changes"] == 0
    assert receipt["automatic_tuning_eligible"] is False


def test_guided_feedback_rejects_not_ready_audio_gate(tmp_path: Path) -> None:
    feedback, metrics = _valid_feedback(tmp_path)
    payload = json.loads(feedback.read_text(encoding="utf-8"))
    payload["audio_submit_gate"]["status"] = "NOT_SUBMITTED"
    feedback.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(GuidedFeedbackError, match="audio gate"):
        validate_guided_feedback(feedback, metrics)


def test_guided_feedback_rejects_out_of_range_identity_and_authority_escalation(tmp_path: Path) -> None:
    feedback, metrics = _valid_feedback(tmp_path)
    payload = json.loads(feedback.read_text(encoding="utf-8"))
    payload["rows"][0]["identity"] = 101
    feedback.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(GuidedFeedbackError, match="identity"):
        validate_guided_feedback(feedback, metrics)
    payload["rows"][0]["identity"] = 72
    payload["automatic_tuning_eligible"] = True
    feedback.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(GuidedFeedbackError, match="automatic tuning"):
        validate_guided_feedback(feedback, metrics)


def test_guided_feedback_accepts_one_aggregate_row_per_vehicle(tmp_path: Path) -> None:
    metrics_path = ROOT / "professional_pair_metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    rows = []
    for vehicle_id in ("ferrari_458", "hellcat", "rx7_fd"):
        vehicle_pairs = [p for p in metrics["pairs"] if p["vehicle_id"] == vehicle_id]
        rows.append({
            "vehicle_id": vehicle_id,
            "pair_ids": [p["pair_id"] for p in vehicle_pairs],
            "file_ids": [p["file_id"] for p in vehicle_pairs],
            "reference_sha256s": [p["reference_sha256"] for p in vehicle_pairs],
            "candidate_sha256s": [p["candidate_sha256"] for p in vehicle_pairs],
            "software_agreement": "符合",
            "identity": 80,
            "realism": 70,
            "problems": ["太闷"],
            "preference": "候选",
            "notes": "按车型汇总。",
            "review_ready": True,
        })
    payload = {
        "schema_version": "s12-professional-jovi-guided-feedback-v2",
        "feedback_scope": "vehicle",
        "package_manifest_sha256": metrics["manifest_sha256"],
        "evidence_level": "R3",
        "status": "READY_FOR_REVIEW",
        "automatic_tuning_eligible": False,
        "profile_update": "FORBIDDEN",
        "audio_submit_gate": {"status": "PASS"},
        "rows": rows,
    }
    path = tmp_path / "vehicle_feedback.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    receipt = validate_guided_feedback(path, metrics_path)
    assert receipt["status"] == "VALIDATED_R2_R3_GUIDED_FEEDBACK"
    assert receipt["feedback_scope"] == "vehicle"
    assert receipt["feedback_rows"] == 3


def test_guided_feedback_normalizes_html_number_input_strings(tmp_path: Path) -> None:
    metrics_path = ROOT / "professional_pair_metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    rows = []
    for vehicle_id in ("ferrari_458", "hellcat", "rx7_fd"):
        vehicle_pairs = [p for p in metrics["pairs"] if p["vehicle_id"] == vehicle_id]
        rows.append({
            "vehicle_id": vehicle_id,
            "pair_ids": [p["pair_id"] for p in vehicle_pairs],
            "file_ids": [p["file_id"] for p in vehicle_pairs],
            "reference_sha256s": [p["reference_sha256"] for p in vehicle_pairs],
            "candidate_sha256s": [p["candidate_sha256"] for p in vehicle_pairs],
            "software_agreement": "部分符合",
            "identity": "30",
            "realism": "10",
            "problems": [],
            "preference": "候选",
            "notes": "来自浏览器 number input。",
            "review_ready": True,
        })
    payload = {
        "schema_version": "s12-professional-jovi-guided-feedback-v2",
        "feedback_scope": "vehicle",
        "package_manifest_sha256": metrics["manifest_sha256"],
        "evidence_level": "R3",
        "status": "READY_FOR_REVIEW",
        "automatic_tuning_eligible": False,
        "profile_update": "FORBIDDEN",
        "audio_submit_gate": {"status": "PASS"},
        "rows": rows,
    }
    path = tmp_path / "html_number_input_feedback.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    receipt = validate_guided_feedback(path, metrics_path)
    assert receipt["vehicle_summary"]["ferrari_458"]["identity_mean"] == 30
    assert receipt["vehicle_summary"]["rx7_fd"]["realism_mean"] == 10


def _vehicle_feedback_with_topics(metrics: dict, topics: object) -> dict:
    rows = []
    for vehicle_id in ("ferrari_458", "hellcat", "rx7_fd"):
        vehicle_pairs = [p for p in metrics["pairs"] if p["vehicle_id"] == vehicle_id]
        rows.append({
            "vehicle_id": vehicle_id,
            "pair_ids": [p["pair_id"] for p in vehicle_pairs],
            "file_ids": [p["file_id"] for p in vehicle_pairs],
            "reference_sha256s": [p["reference_sha256"] for p in vehicle_pairs],
            "candidate_sha256s": [p["candidate_sha256"] for p in vehicle_pairs],
            "software_agreement": "部分符合",
            "identity": 30,
            "realism": 20,
            "problems": [],
            "focus_topics": topics,
            "preference": "候选",
            "notes": "主题反馈。",
            "review_ready": True,
        })
    return {
        "schema_version": "s12-professional-jovi-guided-feedback-v3",
        "feedback_scope": "vehicle",
        "package_manifest_sha256": metrics["manifest_sha256"],
        "evidence_level": "R3",
        "status": "READY_FOR_REVIEW",
        "automatic_tuning_eligible": False,
        "profile_update": "FORBIDDEN",
        "audio_submit_gate": {"status": "PASS"},
        "rows": rows,
    }


def test_guided_feedback_v3_preserves_focus_topics(tmp_path: Path) -> None:
    metrics_path = ROOT / "professional_pair_metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    path = tmp_path / "topics.json"
    path.write_text(json.dumps(_vehicle_feedback_with_topics(metrics, ["怠速", "音色/机械感"]), ensure_ascii=False), encoding="utf-8")
    receipt = validate_guided_feedback(path, metrics_path)
    assert receipt["schema_version"] == "s12-professional-jovi-guided-feedback-receipt-v3"
    assert receipt["rows"][0]["focus_topics"] == ["怠速", "音色/机械感"]


def test_guided_feedback_v3_rejects_unknown_or_empty_focus_topics(tmp_path: Path) -> None:
    metrics_path = ROOT / "professional_pair_metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    path = tmp_path / "topics.json"
    payload = _vehicle_feedback_with_topics(metrics, ["未知主题"])
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(GuidedFeedbackError, match="focus_topics"):
        validate_guided_feedback(path, metrics_path)
    payload = _vehicle_feedback_with_topics(metrics, [])
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(GuidedFeedbackError, match="focus_topics"):
        validate_guided_feedback(path, metrics_path)


def test_guided_feedback_v2_without_topics_remains_legacy_compatible(tmp_path: Path) -> None:
    feedback, metrics = _valid_feedback(tmp_path)
    receipt = validate_guided_feedback(feedback, metrics)
    assert receipt["status"] == "VALIDATED_R2_R3_GUIDED_FEEDBACK"
    assert all(row.get("focus_topics") is None for row in receipt["rows"])
