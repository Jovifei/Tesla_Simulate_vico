"""Focused contract tests for named Stage L feedback intake."""

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_l.feedback_contract import (
    FeedbackContractError,
    validate_feedback_rows,
)


def test_feedback_contract_rejects_zero_score() -> None:
    row = {
        "package_id": "s12-stage-l-hellcat-intake-roughness-v1",
        "listener_id": "Jovi",
        "file_id": "02_StageL_Candidate_60s.wav",
        "vehicle_id": "hellcat_inspired",
        "supercharger_intake_likeness_1_5": "0",
        "whine_presence_1_5": "3",
        "whine_naturalness_1_5": "3",
        "low_frequency_weight_1_5": "3",
        "crossplane_pulse_naturalness_1_5": "3",
        "roughness_naturalness_1_5": "3",
        "shift_naturalness_1_5": "3",
        "high_frequency_harshness_1_5": "3",
        "loudness_balance_1_5": "3",
        "artifact_freedom_1_5": "3",
        "keep_or_change": "change",
        "notes": "",
    }

    with pytest.raises(FeedbackContractError, match="1-5"):
        validate_feedback_rows([row])
