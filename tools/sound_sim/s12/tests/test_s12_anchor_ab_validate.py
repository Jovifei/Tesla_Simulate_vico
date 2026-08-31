from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path

import pytest

from tools.sound_sim.s12.real_reference.anchor_ab_validate import (
    AnchorABValidationError,
    validate_anchor_ab_package,
)


DIMENSIONS = [
    "车型身份",
    "真实感",
    "低频重量",
    "机械感",
    "怠速生命感",
    "加速攻击性",
    "换挡真实感",
    "回火自然度",
    "合成器感/伪影",
    "偏好",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_wav(path: Path, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8_000)
        handle.writeframes((value.to_bytes(2, "little", signed=True)) * 16)


def _make_package(tmp_path: Path) -> Path:
    package = tmp_path / "anchor_ab_zh_v1"
    trials = []
    for vehicle_id, prefix in (("ferrari_458", "ferrari"), ("hellcat", "hellcat"), ("rx7_fd", "rx7")):
        for index in range(1, 4):
            trial_id = f"{prefix}_{index:02d}"
            ref = package / "audio" / vehicle_id / trial_id / "reference.wav"
            candidate = package / "audio" / vehicle_id / trial_id / "candidate.wav"
            _write_wav(ref, index)
            _write_wav(candidate, index + 10)
            trials.append(
                {
                    "trial_id": trial_id,
                    "test_id": "S12-R3-ANCHOR-AB-ZH-20260823",
                    "file_id": f"{trial_id}-reference-vs-candidate",
                    "vehicle_id": vehicle_id,
                    "reference_audition_path": str(ref),
                    "reference_audition_sha256": _sha256(ref),
                    "candidate_audition_path": str(candidate),
                    "candidate_audition_sha256": _sha256(candidate),
                    "reference_original_wav_path_alias": f"external/{trial_id}.wav",
                    "reference_original_wav_sha256": "a" * 64,
                    "reference_start_s": float(index),
                    "reference_duration_s": 5.0,
                    "listener_id": None,
                    "feedback": None,
                }
            )
    manifest = {
        "schema_version": "s12-stage-s-anchor-ab-zh.v1",
        "package_status": "WAITING_FOR_JOVI_HUMAN_FEEDBACK",
        "evidence_level": "R3",
        "test_id": "S12-R3-ANCHOR-AB-ZH-20260823",
        "language": "zh-CN",
        "package_policy": {
            "raw_reference_media_external_only": True,
            "analysis_signal_unaltered": True,
            "order_hard_gate": False,
            "automatic_tuning_eligible": False,
            "profile_update": "FORBIDDEN",
        },
        "scoring_dimensions": DIMENSIONS,
        "trials": trials,
    }
    manifest_path = package / "anchor_ab_zh_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readme = package / "README_中文.md"
    readme.write_text("# 中文人耳 A/B\n请填写反馈 JSON。\n", encoding="utf-8")
    manifest_sha = _sha256(manifest_path)
    page = package / "index.html"
    page.write_text(
        "<!doctype html><meta charset='utf-8'>"
        f"<script>var PACKAGE_SHA = '{manifest_sha}';</script>"
        "生成并下载反馈 JSON s12-stage-s-human-feedback-zh.v1 "
        + " ".join(trial["trial_id"] for trial in trials),
        encoding="utf-8",
    )
    receipt = package / "anchor_ab_zh_receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": "s12-stage-s-anchor-ab-receipt.v1",
                "package_status": manifest["package_status"],
                "test_id": manifest["test_id"],
                "manifest_path": str(manifest_path),
                "manifest_sha256": manifest_sha,
                "readme_path": str(readme),
                "readme_sha256": _sha256(readme),
                "trial_count": 9,
                "vehicle_counts": {"ferrari_458": 3, "hellcat": 3, "rx7_fd": 3},
                "trials": [
                    {
                        "trial_id": trial["trial_id"],
                        "reference_audition_sha256": trial["reference_audition_sha256"],
                        "candidate_audition_sha256": trial["candidate_audition_sha256"],
                    }
                    for trial in trials
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return package


def test_anchor_ab_validation_accepts_manifest_page_and_18_clips(tmp_path: Path) -> None:
    result = validate_anchor_ab_package(_make_package(tmp_path))
    assert result["status"] == "VALIDATION_PASS"
    assert result["trial_count"] == 9
    assert result["clip_count"] == 18
    assert result["vehicle_counts"] == {"ferrari_458": 3, "hellcat": 3, "rx7_fd": 3}
    assert result["sha_checks"]["failed"] == []
    assert result["page_checks"]["status"] == "PASS"


def test_anchor_ab_validation_rejects_tampered_clip(tmp_path: Path) -> None:
    package = _make_package(tmp_path)
    path = package / "audio" / "hellcat" / "hellcat_02" / "candidate.wav"
    path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises(AnchorABValidationError, match="SHA"):
        validate_anchor_ab_package(package)


def test_anchor_ab_validation_rejects_missing_page(tmp_path: Path) -> None:
    package = _make_package(tmp_path)
    (package / "index.html").unlink()
    with pytest.raises(AnchorABValidationError, match="index.html"):
        validate_anchor_ab_package(package)
