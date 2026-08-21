from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.sound_sim.s12.acoustic_identity_v015.stage_o.feedback_intake import (
    PLAYBACK_METADATA_FIELDS,
    validate_feedback_entry,
)
from tools.sound_sim.s12.acoustic_comparator.listening.webmushra_export import RATING_DIMENSIONS


def test_no_submission_is_a_non_reading_waiting_state() -> None:
    receipt = validate_feedback_entry(binding={"package_manifest_sha256": "a" * 64})
    assert receipt["status"] == "WAITING_FOR_JOVI_FEEDBACK"
    assert receipt["human_feedback_available"] is False
    assert receipt["content_read"] is False
    assert receipt["no_source_change"] is True
    assert receipt["required_playback_metadata"] == list(PLAYBACK_METADATA_FIELDS)


def test_submission_requires_all_playback_metadata(tmp_path: Path) -> None:
    submission = tmp_path / "Jovi_Stage_M_Named_Feedback.csv"
    submission.write_text("listener_id\nJovi\n", encoding="utf-8")
    receipt = validate_feedback_entry(
        binding={"package_manifest_sha256": "a" * 64},
        named_csv=submission,
        metadata={"playback_device": "headphones"},
    )
    assert receipt["status"] == "REJECTED_MISSING_PLAYBACK_METADATA"
    assert receipt["content_read"] is False
    assert set(receipt["missing_playback_metadata"]) == set(PLAYBACK_METADATA_FIELDS) - {"playback_device"}


def test_fixture_status_cannot_be_promoted(tmp_path: Path) -> None:
    tmp = Path(__file__).resolve().parents[5] / "tasks" / "reports" / "runtime" / "s12-stage-n-professional-comparator"
    binding = json.loads((tmp / "webmushra_package_manifest.json").read_text(encoding="utf-8"))
    raw = tmp_path / "fixture_mushra.csv"
    lss = tmp_path / "fixture_lss.csv"
    with raw.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["session_test_id", "listener_id", "trial_id", "rating_stimulus", "rating_score"])
        writer.writeheader()
        writer.writerow({"session_test_id": binding["test_id"], "listener_id": "fixture-listener", "trial_id": "V01", "rating_stimulus": "stage_m_candidate", "rating_score": "50"})
    with lss.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["session_test_id", "listener_id", "trial_id", "stimuli_rating", "stimuli", "rating_time"])
        writer.writeheader()
        for dimension in (*RATING_DIMENSIONS, "identity_guess"):
            writer.writerow({"session_test_id": binding["test_id"], "listener_id": "fixture-listener", "trial_id": f"V01_{dimension}", "stimuli_rating": "hellcat" if dimension == "identity_guess" else "50", "stimuli": "stage_m_candidate", "rating_time": "1.0"})
    receipt = validate_feedback_entry(
        binding=binding,
        mushra_csv=raw,
        lss_csv=lss,
        metadata={field: "documented" for field in PLAYBACK_METADATA_FIELDS},
    )
    assert receipt["status"] == "REJECTED_FIXTURE_OR_SYNTHETIC_INPUT"
    assert receipt["human_feedback_available"] is False
