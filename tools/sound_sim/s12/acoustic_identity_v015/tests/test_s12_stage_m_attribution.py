from tools.sound_sim.s12.acoustic_identity_v015.stage_m.attribution import attribute_vehicle_failure


def test_missing_reference_is_not_portrayed_as_vehicle_deterioration() -> None:
    record = attribute_vehicle_failure("c63_w204", None, scenario="acceleration")
    assert record["target"] is None
    assert record["candidate_error"] is None
    assert record["improvement"] is None
    assert "B" in record["failure_category"]


def test_lfa_attribution_keeps_asg_category_and_hellcat_stays_stage_l() -> None:
    assert "I" in attribute_vehicle_failure("lfa", None, scenario="shift")["failure_category"]
    hellcat = attribute_vehicle_failure("hellcat", None, scenario="lift_afterfire")
    assert "J" in hellcat["failure_category"]
    assert "Stage-L" in hellcat["evidence"]["source"]
