import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_m.feedback import validate_named_feedback


def _row() -> dict[str, object]:
    return {
        "listener_id": "jovi", "playback_device": "headphones", "windows_volume": "50", "playback_endpoint": "USB DAC",
        "vehicle_id": "c63_w204", "scenario": "acceleration", "baseline_file": "parent.wav", "candidate_file": "candidate.wav",
        "candidate_sha256": "a" * 64, "identity_score": 3, "realism_score": 3, "low_frequency_score": 3,
        "mechanical_score": 3, "shift_score": 3, "afterfire_score": 3, "artifact_score": 3, "preference": "candidate", "notes": "named test",
    }


def test_named_feedback_checks_sha_and_never_declares_human_pass() -> None:
    receipt = validate_named_feedback([_row()], {"candidate.wav": "a" * 64})
    assert receipt["accepted"] is True
    assert receipt["human_pass"] is False


def test_duplicate_or_bad_sha_feedback_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        validate_named_feedback([_row(), _row()], {"candidate.wav": "a" * 64})
    with pytest.raises(ValueError, match="SHA"):
        validate_named_feedback([_row()], {"candidate.wav": "b" * 64})
