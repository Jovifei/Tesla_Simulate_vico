"""Focused regression tests for Stage W-C closure/recovery metadata."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
RUNTIME = ROOT / "tasks" / "reports" / "runtime" / "s12-stage-w"
TESTED_CODE_EVIDENCE_HEAD = "24f2c41bccfc26b13a821d959b2f4400d7eb264b"
METADATA_REPAIR_BASE = "7d4e49b52b73696af703a1380d83663208c5a897"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_live_head_resolution_and_commit_roles_are_explicit() -> None:
    state = _json(RUNTIME / "execution_state.json")

    assert state.get("current_head") == "HEAD"
    assert state.get("current_head_role") == "live_worktree_head"
    assert state.get("current_head_resolution_command") == "git rev-parse HEAD"
    assert state.get("metadata_repair_base") == METADATA_REPAIR_BASE
    assert state.get("tested_code_evidence_head") == TESTED_CODE_EVIDENCE_HEAD


def test_w9_receipt_is_bound_to_tested_code_evidence_head() -> None:
    receipt = _json(RUNTIME / "phase_receipts" / "W9_FINAL_QUALIFICATION.json")

    assert receipt.get("head") == TESTED_CODE_EVIDENCE_HEAD
    assert receipt.get("head_role") == "tested_code_evidence_head"


def test_w6_commit_is_source_backed_and_w7_is_terminal_skip() -> None:
    state = _json(RUNTIME / "execution_state.json")
    phases = state["phases"]
    status_vocabulary = state.get("phase_status_vocabulary", [])

    assert phases["W6_HELLCAT_BAKEOFF"].get("commit") == TESTED_CODE_EVIDENCE_HEAD
    assert phases["W6_HELLCAT_BAKEOFF"].get("commit_role") == "tested_code_evidence_head"
    assert phases["W7_FERRARI_RX7_MIGRATION"].get("status") == "SKIPPED_NO_SELECTED_ARCHITECTURE"
    assert phases["W7_FERRARI_RX7_MIGRATION"].get("evidence_role") == "unselected_preselection_diagnostic_evidence"
    assert "SKIPPED_NO_SELECTED_ARCHITECTURE" in status_vocabulary


def test_historical_phase_times_remain_null_with_explicit_provenance() -> None:
    state = _json(RUNTIME / "execution_state.json")
    phases = state["phases"]
    historical = (
        "W0_RECOVERY_AUDIT",
        "W1_PERSISTENT_STREAMING",
        "W2_EVENT_TORQUE_AND_FIRING",
        "W3_FROZEN_PTR_INTEGRATION",
        "W4_PATH_AND_AFTERFIRE",
        "W5_TIMBRE_AND_FORCED_INDUCTION",
        "W7_FERRARI_RX7_MIGRATION",
        "W8_RESEARCH_AND_OBSIDIAN",
    )

    for phase_name in historical:
        phase = phases[phase_name]
        assert phase["started_at"] is None
        assert phase["completed_at"] is None
        assert phase.get("timing_status") == "HISTORICAL_NOT_RECORDED"


def test_resume_and_receipt_readme_state_long_task_and_receipt_scope() -> None:
    resume = (RUNTIME / "EXECUTION_RESUME.md").read_text(encoding="utf-8")
    receipts_readme = (RUNTIME / "phase_receipts" / "README.md").read_text(encoding="utf-8")

    assert "do_not_rerun_long_tasks" in resume
    assert "full S12 regression" in resume
    assert "3000-block equivalence test" in resume
    assert "unless code/evidence inputs change or a new final qualification is authorized" in resume
    assert "One JSON receipt is kept for each completed phase" not in receipts_readme
    assert "W9" in receipts_readme
    assert "execution_state.json" in receipts_readme


def test_terminal_status_and_selection_boundary_are_preserved() -> None:
    state = _json(RUNTIME / "execution_state.json")
    receipt = _json(RUNTIME / "phase_receipts" / "W9_FINAL_QUALIFICATION.json")

    expected = "STAGE_W_CONTINUOUS_EXECUTION_COMPLETE / NO_ARCHITECTURE_CANDIDATE_PASSED / NOT_R1_QUALIFIED"
    assert state["overall_status"] == expected
    assert state.get("selected_architecture") is None
    assert receipt["qualification_boundary"]["selected_architecture"] is None
    assert state.get("audit_provenance", {}).get("repair_kind") == "stage_w_c_closure_metadata_repair"
