"""Stage-J named feedback validation."""

from pathlib import Path

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_j.feedback_contract import validate_stage_j_feedback


def test_feedback_template_is_waiting_and_empty_scores_are_allowed(tmp_path: Path) -> None:
    path = tmp_path / "feedback.csv"
    path.write_text(
        "file_id,vehicle_id,identity_1_5,low_frequency_weight_1_5,high_frequency_harshness_1_5,artifact_freedom_1_5,keep_or_change,notes\n"
        "c63_w204_StageJ_Candidate_v1_Review_60s,c63_w204,,,,,,\n",
        encoding="utf-8",
    )
    result = validate_stage_j_feedback(path)
    assert result["status"] == "WAITING_FOR_JOVI_STAGE_J_NAMED_REVIEW"


def test_feedback_rejects_out_of_range_score(tmp_path: Path) -> None:
    path = tmp_path / "feedback.csv"
    path.write_text(
        "file_id,vehicle_id,identity_1_5,low_frequency_weight_1_5,high_frequency_harshness_1_5,artifact_freedom_1_5,keep_or_change,notes\n"
        "lfa_StageJ_Candidate_v1_Review_60s,lfa,6,,,,keep,too high\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="1-5"):
        validate_stage_j_feedback(path)
