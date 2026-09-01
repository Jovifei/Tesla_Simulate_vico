from __future__ import annotations

from tools.sound_sim.s12.acoustic_identity_v015.stage_aa.hellcat_root_cause import build_hellcat_root_cause_report


def test_root_cause_report_is_hellcat_only_and_parameter_free() -> None:
    payload = build_hellcat_root_cause_report()
    assert payload["schema"] == "s12.stage_aa.hellcat_root_cause.v1"
    assert payload["vehicle"] == "hellcat"
    assert payload["parameter_changes_applied"] is False
    assert payload["primary_root_cause"] == "PRESSURE_BASELINE_REMOVAL_PLUS_FROZEN_PTR_ATTENUATION"
    assert {item["id"] for item in payload["findings"]} >= {"low_frequency_body", "pressure_120_400", "blower_tonal_artifact", "dynamic_range"}
    assert payload["reference_contract"]["order_gate"] == "NOT_QUALIFIED"
