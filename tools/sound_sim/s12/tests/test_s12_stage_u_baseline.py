from __future__ import annotations

from pathlib import Path

from tools.sound_sim.s12.real_reference.stage_u_baseline import (
    STAGE_U_BASELINE_COMMIT,
    audit_stage_u_baseline,
)


ROOT = Path(__file__).resolve().parents[4]


def test_stage_u_baseline_audit_records_exact_parent_state() -> None:
    audit = audit_stage_u_baseline(ROOT)
    assert audit["baseline_commit"] == STAGE_U_BASELINE_COMMIT
    assert audit["branch"] == "agent/s12-stage-u-true-comparator-calibration"
    assert audit["baseline_is_ancestor"] is True
    assert audit["ferrari_458"]["candidate_audio_rendered"] is False
    assert audit["hellcat"]["candidate_audio_rendered"] is False
    assert audit["rx7_fd"]["manual_candidate_present"] is True
    assert audit["rx7_fd"]["source_modified"] is False
    assert audit["objective_before_after_claim"] == "NOT_CLAIMED"
