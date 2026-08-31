from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_p.acceptance import (
    comparator_replay,
    fixture_stage_o_consumption,
    security_matrix,
    validate_stage_n_receipts,
)


REPO = Path(__file__).resolve().parents[5]
STAGE_N = REPO / "tasks/reports/runtime/s12-stage-n-professional-comparator"
STAGE_M_MANIFEST = Path(
    os.environ.get(
        "S12_STAGE_M_EXTERNAL_MANIFEST",
        r"E:\Tesla_speed\review_packages\s12-stage-m-comparator-and-calibration-v1\artifact_manifest.json",
    )
)
PACKAGE = Path(
    os.environ.get(
        "S12_STAGE_P_EXTERNAL_PACKAGE",
        r"E:\Tesla_speed\review_packages\s12-stage-p-system-acceptance-v1",
    )
)
UAT = Path(
    os.environ.get(
        "S12_STAGE_P_EXTERNAL_UAT",
        r"E:\Tesla_speed\review_packages\s12-stage-p-jovi-uat-v1",
    )
)
P_OUTPUT = REPO / "tasks/reports/runtime/s12-stage-p-system-acceptance"

STAGE_M_EXTERNAL_AVAILABLE = STAGE_M_MANIFEST.is_file()
STAGE_P_EXTERNAL_AVAILABLE = (
    (PACKAGE / "webmushra_package_manifest.json").is_file()
    and (PACKAGE / "SHA256SUMS").is_file()
)
UAT_EXTERNAL_AVAILABLE = (UAT / "manifest.json").is_file()


@pytest.mark.skipif(
    not (STAGE_M_EXTERNAL_AVAILABLE and STAGE_P_EXTERNAL_AVAILABLE),
    reason=(
        "external Stage-M/Stage-P review packages are unavailable; set "
        "S12_STAGE_M_EXTERNAL_MANIFEST and S12_STAGE_P_EXTERNAL_PACKAGE "
        "to run the receipt-integration contract"
    ),
)
def test_stage_p_receipt_validation_is_closed() -> None:
    result = validate_stage_n_receipts(STAGE_N, STAGE_M_MANIFEST, PACKAGE)
    assert result["status"] == "PASS"
    assert result["candidate_count"] == 8
    assert result["cross_tool_same_fixture"] is True
    assert result["real_reference_or_absolute_spl_claim"] is False


def test_stage_p_comparator_replay_is_eight_by_five() -> None:
    result = comparator_replay(
        STAGE_N / "comparator_results.json",
        P_OUTPUT / "stage_p_comparator_replay.json",
    )
    assert result["status"] == "PASS"
    assert result["vehicle_count"] == 8
    assert result["scenario_count"] == 40
    assert result["no_truth_percentage"] is True


@pytest.mark.skipif(
    not STAGE_P_EXTERNAL_AVAILABLE,
    reason=(
        "external Stage-P review package is unavailable; set "
        "S12_STAGE_P_EXTERNAL_PACKAGE to run the security integration contract"
    ),
)
def test_stage_p_security_matrix_is_fail_closed() -> None:
    result = security_matrix(PACKAGE, P_OUTPUT / "stage_p_feedback_security.json")
    assert result["status"] == "PASS"
    assert result["case_count"] == 15
    assert result["fail_closed"] is True


@pytest.mark.skipif(
    not STAGE_P_EXTERNAL_AVAILABLE,
    reason=(
        "external Stage-P review package is unavailable; set "
        "S12_STAGE_P_EXTERNAL_PACKAGE to run the fixture-consumption contract"
    ),
)
def test_stage_p_fixture_consumption_is_not_human_feedback() -> None:
    result = fixture_stage_o_consumption(PACKAGE, P_OUTPUT)
    assert (
        result["status"]
        == "FIXTURE_ONLY_NOT_HUMAN_FEEDBACK_NOT_TUNING_AUTHORITY"
    )
    assert result["accepted_rows"] == 8
    assert result["human_feedback_available"] is False
    assert result["tuning_authority"] is False


def test_stage_p_repo_delivery_contract_is_present() -> None:
    required_reports = {
        "S12_Stage_P_System_Acceptance_Report.md",
        "S12_Stage_P_Baseline_Audit.md",
        "S12_Stage_P_Comparator_Replay.md",
        "stage_p_exact_tip_test_evidence.json",
        "stage_p_tool_receipt_validation.json",
        "stage_p_comparator_replay.json",
        "stage_p_webmushra_roundtrip.json",
        "stage_p_feedback_security_tests.json",
        "stage_p_reproducibility.json",
        "stage_p_uat_manifest.json",
        "stage_p_fixture_stage_o_receipt.json",
        "stage_p_gate_matrix.json",
        "stage_p_artifact_manifest.json",
    }
    assert required_reports.issubset(
        {path.name for path in P_OUTPUT.iterdir()}
    )
    matrix = json.loads(
        (P_OUTPUT / "stage_p_gate_matrix.json").read_text(encoding="utf-8")
    )
    assert matrix["final_status"] == [
        "SYSTEM_ACCEPTANCE_PASSED",
        "READY_FOR_JOVI_UAT",
        "HUMAN_ACOUSTIC_QUALIFICATION_PENDING",
        "NOT_PROFILE_FREEZE_READY",
    ]
    assert matrix["gates"]["H_real_jovi_feedback"] == "PENDING"
    baseline = json.loads(
        (P_OUTPUT / "stage_p_baseline_state.json").read_text(encoding="utf-8")
    )
    assert (
        "worktree E:/Tesla_speed/worktrees/s12-stage-p-system-acceptance"
        in baseline["worktree_list_porcelain"]
    )


@pytest.mark.skipif(
    not (STAGE_P_EXTERNAL_AVAILABLE and UAT_EXTERNAL_AVAILABLE),
    reason=(
        "external Stage-P/UAT delivery packages are unavailable; set "
        "S12_STAGE_P_EXTERNAL_PACKAGE and S12_STAGE_P_EXTERNAL_UAT "
        "to run the external-delivery contract"
    ),
)
def test_stage_p_external_delivery_contract_is_present() -> None:
    assert (PACKAGE / "SHA256SUMS").is_file()
    assert (PACKAGE / "results" / "mushra.csv").is_file()
    assert (PACKAGE / "results" / "lss.csv").is_file()
    assert (PACKAGE / "results" / "normalized_import_result.json").is_file()
    assert {
        "START_REVIEW.ps1",
        "STOP_REVIEW.ps1",
        "OPEN_REVIEW.ps1",
        "IMPORT_RESULTS.ps1",
        "CHECK_STATUS.ps1",
        "README_JOVI.md",
        "SHA256SUMS",
    }.issubset({path.name for path in UAT.iterdir()})
    manifest = json.loads((UAT / "manifest.json").read_text(encoding="utf-8"))
    assert (
        manifest["human_acoustic_qualification_status"]
        == "HUMAN_ACOUSTIC_QUALIFICATION_PENDING"
    )
    assert manifest["expected_result_paths"]["official_webmushra"]
    assert "Docker CLI not found" in (UAT / "START_REVIEW.ps1").read_text(
        encoding="utf-8"
    )
    assert "Docker Desktop daemon unavailable" in (
        UAT / "START_REVIEW.ps1"
    ).read_text(encoding="utf-8")
    assert "manifest SHA" in (UAT / "CHECK_STATUS.ps1").read_text(
        encoding="utf-8"
    )
    assert "package SHA binding" in (
        UAT / "IMPORT_RESULTS.ps1"
    ).read_text(encoding="utf-8")
