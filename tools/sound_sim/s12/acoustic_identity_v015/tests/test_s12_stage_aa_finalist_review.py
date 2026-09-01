from __future__ import annotations

from tools.sound_sim.s12.acoustic_identity_v015.stage_aa.finalist_review import build_finalist_review


def test_finalist_review_is_diagnostic_and_keeps_matlab_pending_when_unverified() -> None:
    payload = build_finalist_review()
    assert payload["schema"] == "s12.stage_aa.professional_finalist_review.v1"
    assert payload["finalists"] == ["AA-C1", "AA-C2", "AA-C3"]
    assert payload["status"] == "DIAGNOSTIC_ONLY"
    assert payload["matlab"]["status"] == "MATLAB_FINALIST_RECEIPT_PENDING"
    assert payload["human_approval"] == "PENDING"
    assert payload["metrics"]
