from __future__ import annotations

from tools.sound_sim.s12.acoustic_identity_v015.stage_aa.reference_contract import build_reference_diagnostic_contract


def test_canonical_reference_contract_preserves_levels_and_separates_review_domains() -> None:
    payload = build_reference_diagnostic_contract()
    assert payload["schema"] == "s12.stage_aa.reference_diagnostic_contract.v1"
    assert payload["evidence_counts"] == {"R1": 0, "R2": 8, "R3": 15}
    assert payload["order_gate"] == "NOT_QUALIFIED"
    assert payload["timbre_review"]["loudness_matching"] is True
    assert payload["dynamic_review"]["loudness_matching"] is False
    assert payload["r1_status"] == "MISSING"
    assert payload["external_audio_embedded"] is False
    assert payload["hellcat_r2_records"]
    assert all(record["level"] == "R2" for record in payload["hellcat_r2_records"])
