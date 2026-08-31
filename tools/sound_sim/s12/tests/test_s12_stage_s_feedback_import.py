from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.sound_sim.s12.real_reference.build_r2_ab_package import (
    DIMENSIONS,
    DIMENSION_LABELS_ZH,
    write_chinese_ab_page,
)
from tools.sound_sim.s12.real_reference.feedback_import import (
    FeedbackValidationError,
    validate_human_feedback,
)


TEST_ID = "s12-stage-s-r2-ab-test"
CASE_ID = "rx7sim_fixture"
REFERENCE_SHA = "a" * 64
CANDIDATE_SHA = "b" * 64


def _write_package(tmp_path: Path) -> tuple[Path, Path, Path, dict[str, object]]:
    package = tmp_path / "package"
    package.mkdir()
    study = {
        "schema_version": "s12-stage-s-r2-ab-package-v1",
        "status": "WAITING_FOR_JOVI_HUMAN_FEEDBACK",
        "language": "zh-CN",
        "test_id": TEST_ID,
        "cases": [
            {
                "case_id": CASE_ID,
                "vehicle_id": "rx7_fd",
                "scenario": "full_pull",
                "reference": {"source_sha256": REFERENCE_SHA},
                "candidate": {"source_sha256": CANDIDATE_SHA},
            }
        ],
    }
    study_path = package / "study_manifest.json"
    study_path.write_text(json.dumps(study, sort_keys=True), encoding="utf-8")
    study_sha = hashlib.sha256(study_path.read_bytes()).hexdigest()
    binding = {
        "schema_version": "s12-stage-s-r2-ab-package-v1",
        "status": "WAITING_FOR_JOVI_HUMAN_FEEDBACK",
        "test_id": TEST_ID,
        "study_manifest_sha256": study_sha,
        "required_binding": [
            "study_manifest_sha256",
            "test_id",
            "case_id",
            "reference_sha256",
            "candidate_sha256",
            "listener_id",
            "playback_device",
            "windows_volume",
            "playback_endpoint",
            "system_audio_effects",
            *DIMENSIONS,
        ],
        "cases": {
            CASE_ID: {
                "vehicle_id": "rx7_fd",
                "scenario": "full_pull",
                "reference_sha256": REFERENCE_SHA,
                "candidate_sha256": CANDIDATE_SHA,
            }
        },
    }
    binding_path = package / "feedback_binding.json"
    binding_path.write_text(json.dumps(binding, sort_keys=True), encoding="utf-8")
    scores = {dimension: 4 for dimension in DIMENSIONS}
    feedback = {
        "schema_version": "s12-stage-s-human-feedback-zh.v1",
        "test_id": TEST_ID,
        "package_manifest_sha256": study_sha,
        "exported_at_utc": "2026-08-23T00:00:00Z",
        "listener_id": "Jovi-test-only",
        "playback_device": "测试耳机",
        "windows_volume": "40%",
        "playback_endpoint": "USB",
        "system_audio_effects": "关闭",
        "evidence_level": "R2",
        "package_status": "READY_FOR_REVIEW",
        "automatic_tuning_eligible": False,
        "profile_update": "FORBIDDEN",
        "cases": [
            {
                "case_id": CASE_ID,
                "vehicle_id": "rx7_fd",
                "scenario": "full_pull",
                "reference_sha256": REFERENCE_SHA,
                "candidate_sha256": CANDIDATE_SHA,
                "scores": scores,
                "preference": "参考声音更好",
                "notes_zh": "测试合同，不是真人听审结果。",
            }
        ],
    }
    feedback_path = tmp_path / "feedback.json"
    feedback_path.write_text(json.dumps(feedback, ensure_ascii=False), encoding="utf-8")
    return study_path, binding_path, feedback_path, feedback


def test_chinese_page_exports_playback_metadata_and_machine_score_keys(tmp_path: Path) -> None:
    study = {
        "test_id": TEST_ID,
        "schema_version": "s12-stage-s-r2-ab-package-v1",
        "status": "WAITING_FOR_JOVI_HUMAN_FEEDBACK",
        "language": "zh-CN",
        "cases": [
            {
                "case_id": CASE_ID,
                "vehicle_id": "rx7_fd",
                "scenario": "full_pull",
                "reference": {"source_sha256": REFERENCE_SHA, "audition_path": "audio/ref.wav", "audition_sha256": REFERENCE_SHA},
                "candidate": {"source_sha256": CANDIDATE_SHA, "audition": {"audition_path": "audio/candidate.wav", "audition_sha256": CANDIDATE_SHA}},
            }
        ],
        "dimensions": [{"id": dimension, "label_zh": DIMENSION_LABELS_ZH[dimension]} for dimension in DIMENSIONS],
    }
    page = write_chinese_ab_page(tmp_path, study)
    html = page.read_text(encoding="utf-8")
    for label in ("播放设备", "系统音量", "输出端点", "系统音效"):
        assert label in html
    for key in ("playback_device", "windows_volume", "playback_endpoint", "system_audio_effects", "scores"):
        assert key in html
    assert "车型身份" in html
    assert "lang=\"zh-CN\"" in html


def test_validate_human_feedback_returns_sha_bound_r2_receipt(tmp_path: Path) -> None:
    study_path, binding_path, feedback_path, _ = _write_package(tmp_path)
    receipt = validate_human_feedback(feedback_path, study_path, binding_path)
    assert receipt["status"] == "VALIDATED_R2_HUMAN_FEEDBACK"
    assert receipt["feedback_rows"] == 1
    assert receipt["case_id"] == CASE_ID
    assert receipt["scores"]["vehicle_identity"] == 4
    assert receipt["automatic_tuning_eligible"] is False
    assert receipt["profile_update"] == "FORBIDDEN"


def test_validate_human_feedback_rejects_missing_playback_binding(tmp_path: Path) -> None:
    study_path, binding_path, feedback_path, feedback = _write_package(tmp_path)
    feedback["playback_device"] = ""
    feedback_path.write_text(json.dumps(feedback), encoding="utf-8")
    with pytest.raises(FeedbackValidationError, match="playback_device"):
        validate_human_feedback(feedback_path, study_path, binding_path)


def test_validate_human_feedback_rejects_binding_case_map_drift(tmp_path: Path) -> None:
    study_path, binding_path, feedback_path, _ = _write_package(tmp_path)
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    binding["cases"] = {}
    binding_path.write_text(json.dumps(binding), encoding="utf-8")
    with pytest.raises(FeedbackValidationError, match="case map"):
        validate_human_feedback(feedback_path, study_path, binding_path)


def test_validate_human_feedback_rejects_duplicate_case(tmp_path: Path) -> None:
    study_path, binding_path, feedback_path, feedback = _write_package(tmp_path)
    feedback["cases"].append(dict(feedback["cases"][0]))
    feedback_path.write_text(json.dumps(feedback), encoding="utf-8")
    with pytest.raises(FeedbackValidationError, match="duplicate feedback case"):
        validate_human_feedback(feedback_path, study_path, binding_path)
