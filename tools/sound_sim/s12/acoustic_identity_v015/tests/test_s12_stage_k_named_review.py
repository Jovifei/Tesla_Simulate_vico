"""Stage-K four-vehicle named review package contract tests."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import wave
import zipfile

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_k.feedback_contract import FEEDBACK_FIELDS
from tools.sound_sim.s12.acoustic_identity_v015.stage_k.named_review import (
    REVIEW_GAIN_LINEAR,
    STAGE_K_REVIEW_VEHICLES,
    build_stage_k_named_review,
)


@pytest.fixture(scope="module")
def named_package(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, object]]:
    root = tmp_path_factory.mktemp("stage_k_named") / "review"
    return root, build_stage_k_named_review(root, duration_s=2.0)


def test_named_review_builds_four_vehicles_and_required_audio(named_package: tuple[Path, dict[str, object]]) -> None:
    _, result = named_package

    assert result["package_id"] == "S12_Stage_K_Named_Review_v1"
    assert result["status"] in {
        "WAITING_FOR_JOVI_STAGE_K_NAMED_REVIEW",
        "PARTIAL / AUTOMATED_GATE_FAIL",
        "UNQUALIFIED_DIAGNOSTIC_ONLY",
    }
    assert result["requested_review_gain_linear"] == REVIEW_GAIN_LINEAR
    root = Path(result["output_root"])
    for vehicle_id in STAGE_K_REVIEW_VEHICLES:
        vehicle = result["vehicles"][vehicle_id]
        for filename in (
            "Baseline_60s.wav",
            "StageK_Candidate_60s.wav",
            "Low_Load_12s.wav",
            "High_Load_12s.wav",
            "Shift_12s.wav",
            "Lift_Deceleration_12s.wav",
        ):
            path = root / vehicle["directory"] / filename
            assert path.is_file(), path
            with wave.open(str(path), "rb") as stream:
                assert (stream.getframerate(), stream.getnchannels(), stream.getsampwidth()) == (48000, 2, 3)
        assert vehicle["review_loudness"]["requested_gain_linear"] == REVIEW_GAIN_LINEAR
        assert vehicle["review_loudness"]["pair_common"] is True


def test_named_review_writes_blank_feedback_and_no_human_result(named_package: tuple[Path, dict[str, object]]) -> None:
    root, result = named_package
    feedback = root / "06_Feedback" / "Jovi_Stage_K_Named_Feedback.csv"
    with feedback.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert rows
    assert tuple(rows[0]) == FEEDBACK_FIELDS
    assert all(not row["notes"] and not row["keep_or_change"] for row in rows)
    assert result["human_feedback_present"] is False
    assert result["named_review_status"] == "WAITING_FOR_JOVI_STAGE_K_NAMED_REVIEW"


def test_named_review_manifest_sums_and_zip_are_consistent(named_package: tuple[Path, dict[str, object]]) -> None:
    root, result = named_package
    manifest_path = root / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["provenance"] == "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction"
    assert manifest["sealed_key_read"] is False
    with zipfile.ZipFile(root / "S12_Stage_K_Named_Review.zip") as archive:
        assert archive.read("artifact_manifest.json") == manifest_path.read_bytes()
        assert "S12_Stage_K_Named_Review.zip" not in archive.namelist()
    for line in (root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == digest
    assert Path(result["zip"]).is_file()


def test_named_review_records_automatic_status_and_file_level_loudness(named_package: tuple[Path, dict[str, object]]) -> None:
    root, result = named_package
    manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert manifest["automatic_gate_status"] == "PARTIAL / AUTOMATED_GATE_FAIL"
    assert manifest["qualified_for_profile_freeze"] is False
    for vehicle_id in STAGE_K_REVIEW_VEHICLES:
        vehicle = result["vehicles"][vehicle_id]
        files = vehicle["review_loudness"]["files"]
        expected = {
            "Baseline_60s.wav",
            "StageK_Candidate_60s.wav",
            "Low_Load_12s.wav",
            "High_Load_12s.wav",
            "Shift_12s.wav",
            "Lift_Deceleration_12s.wav",
        } | set(vehicle["diagnostic_wavs"])
        assert set(files) == expected
        for evidence in files.values():
            assert set(evidence) >= {
                "raw_lufs", "final_lufs", "raw_peak_dbfs", "final_peak_dbfs",
                "requested_gain_db", "actual_gain_db", "headroom_limited",
            }


def test_named_review_rejects_invalid_gain_without_creating_template(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="review gain"):
        build_stage_k_named_review(tmp_path / "review", duration_s=2.0, requested_review_gain_linear=0.0)
    assert not (tmp_path / "review").exists()
