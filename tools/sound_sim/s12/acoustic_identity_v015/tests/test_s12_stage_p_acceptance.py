from __future__ import annotations

import json
from pathlib import Path

from tools.sound_sim.s12.acoustic_identity_v015.stage_p.acceptance import (
    comparator_replay,
    fixture_stage_o_consumption,
    security_matrix,
    validate_stage_n_receipts,
)


REPO = Path(__file__).resolve().parents[5]
STAGE_N = REPO / "tasks/reports/runtime/s12-stage-n-professional-comparator"
STAGE_M_MANIFEST = Path(r"E:\Tesla_speed\review_packages\s12-stage-m-comparator-and-calibration-v1\artifact_manifest.json")
PACKAGE = Path(r"E:\Tesla_speed\review_packages\s12-stage-p-system-acceptance-v1")
P_OUTPUT = REPO / "tasks/reports/runtime/s12-stage-p-system-acceptance"


def test_stage_p_receipt_validation_is_closed() -> None:
    result = validate_stage_n_receipts(STAGE_N, STAGE_M_MANIFEST, PACKAGE)
    assert result["status"] == "PASS"
    assert result["candidate_count"] == 8
    assert result["cross_tool_same_fixture"] is True
    assert result["real_reference_or_absolute_spl_claim"] is False


def test_stage_p_comparator_replay_is_eight_by_five() -> None:
    result = comparator_replay(STAGE_N / "comparator_results.json", P_OUTPUT / "stage_p_comparator_replay.json")
    assert result["status"] == "PASS"
    assert result["vehicle_count"] == 8
    assert result["scenario_count"] == 40
    assert result["no_truth_percentage"] is True


def test_stage_p_security_matrix_is_fail_closed() -> None:
    result = security_matrix(PACKAGE, P_OUTPUT / "stage_p_feedback_security.json")
    assert result["status"] == "PASS"
    assert result["case_count"] == 15
    assert result["fail_closed"] is True


def test_stage_p_fixture_consumption_is_not_human_feedback() -> None:
    result = fixture_stage_o_consumption(PACKAGE, P_OUTPUT)
    assert result["status"] == "FIXTURE_ONLY_NOT_HUMAN_FEEDBACK_NOT_TUNING_AUTHORITY"
    assert result["accepted_rows"] == 8
    assert result["human_feedback_available"] is False
    assert result["tuning_authority"] is False
