from __future__ import annotations

from tools.sound_sim.s12.acoustic_identity_v015.stage_aa.dynamic_contract import build_raw_dynamic_contract


def test_raw_dynamic_contract_preserves_relative_level_and_required_transient_fields() -> None:
    payload = build_raw_dynamic_contract()
    assert payload["schema"] == "s12.stage_aa.raw_dynamic_contract.v1"
    assert payload["loudness_matching"] is False
    assert set(payload["variants"]) == {"parent", "stage_z_final", "aa_c3"}
    for metrics in payload["variants"].values():
        assert metrics["idle_to_wot_rms_delta"] is not None
        assert metrics["idle_to_wot_peak_delta"] is not None
        assert metrics["tip_in_attack"] is not None
        assert metrics["shift_attack"] is not None
        assert metrics["lift_decay"] is not None
        assert metrics["idle_return_time"] is not None
