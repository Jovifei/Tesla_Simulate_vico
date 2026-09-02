from __future__ import annotations

from tools.sound_sim.s12.acoustic_identity_v015.stage_aa.candidate_audit import build_candidate_audit


def test_candidate_audit_keeps_four_candidates_and_hard_gates() -> None:
    payload = build_candidate_audit(duration_s=0.25, scenes=("full_load",))
    assert payload["schema"] == "s12.stage_aa.candidate_audit.v1"
    assert payload["candidate_ids"] == ["AA-C0", "AA-C1", "AA-C2", "AA-C3"]
    assert all(item["hard_gates"]["passed"] for item in payload["candidates"])
    assert payload["candidate_boundary"]["master_gain"] is False
    assert payload["diagnostic_preference"] in payload["candidate_ids"]
