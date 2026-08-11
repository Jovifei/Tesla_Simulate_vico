"""Stage-J named review package contract tests."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
import zipfile

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_j.named_review import (
    REVIEW_GAIN_LINEAR,
    build_stage_j_named_review,
)


def test_named_review_builds_three_vehicles_with_explicit_louder_copy(tmp_path: Path) -> None:
    result = build_stage_j_named_review(tmp_path / "review", duration_s=1.0)
    assert result["status"] in {"WAITING_FOR_JOVI_STAGE_J_NAMED_REVIEW", "PARTIAL / AUTOMATED_GATE_FAIL"}
    assert result["requested_review_gain_linear"] == REVIEW_GAIN_LINEAR
    for vehicle_id in ("c63_w204", "gtr_r35", "lfa"):
        vehicle = result["vehicles"][vehicle_id]
        assert Path(vehicle["baseline_review_wav"]).is_file()
        assert Path(vehicle["candidate_review_wav"]).is_file()
        assert Path(vehicle["metrics_json"]).is_file()
        assert vehicle["review_loudness"]["requested_gain_linear"] == REVIEW_GAIN_LINEAR


def test_named_review_rejects_nonpositive_gain_and_writes_no_fake_feedback(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="review gain"):
        build_stage_j_named_review(tmp_path / "review", duration_s=1.0, requested_review_gain_linear=0.0)
    assert not (tmp_path / "review" / "Jovi_Stage_J_Named_Feedback.csv").exists()


def test_named_review_freezes_manifest_before_zip_and_sha_receipt(tmp_path: Path) -> None:
    root = tmp_path / "review"
    build_stage_j_named_review(root, duration_s=1.0)
    manifest_bytes = (root / "artifact_manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    assert "sha256" not in manifest
    assert "zip_sha256" not in manifest
    with zipfile.ZipFile(root / "S12_Stage_J_Named_Review.zip") as archive:
        assert archive.read("artifact_manifest.json") == manifest_bytes
        assert "S12_Stage_J_Named_Review.zip" not in archive.namelist()
    for line in (root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected
