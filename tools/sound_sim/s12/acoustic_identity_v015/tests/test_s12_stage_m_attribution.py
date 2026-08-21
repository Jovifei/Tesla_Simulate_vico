from tools.sound_sim.s12.acoustic_identity_v015.stage_m.attribution import attribute_vehicle_failure, build_eight_vehicle_attribution


def test_missing_reference_is_not_portrayed_as_vehicle_deterioration() -> None:
    record = attribute_vehicle_failure("c63_w204", None, scenario="acceleration")
    assert record["target"] is None
    assert record["candidate_error"] is None
    assert record["improvement"] is None
    assert "A" not in record["failure_category"]
    assert record["category_assessment"]["B"]["state"] == "unassessable"


def test_lfa_asg_is_resolved_and_ferrari_actual_event_failure_is_visible() -> None:
    lfa = attribute_vehicle_failure("lfa", {}, scenario="shift", source_metrics={"event": {"qualification": {"eligible": True, "wrong_condition_event_count": 0}, "event_count": 3}})
    assert lfa["category_assessment"]["I"]["state"] == "resolved"
    ferrari = attribute_vehicle_failure("ferrari_458", {}, scenario="shift", source_metrics={"event": {"qualification": {"eligible": False, "missing_expected_event_count": 2}}})
    assert "I" in ferrari["failure_category"]


def test_eight_vehicle_attribution_has_every_required_scenario_field() -> None:
    vehicles = ["ferrari_458", "hellcat", "rx7_fd", "supra_jza80", "aventador_lp700", "c63_w204", "gtr_r35", "lfa"]
    records = build_eight_vehicle_attribution({vehicle: {} for vehicle in vehicles}, {}, {}, {})
    assert len(records) == 32
    assert {"vehicle_id", "scenario", "target", "parent_actual", "candidate_actual", "parent_error", "candidate_error", "improvement", "hard_gate", "failure_category", "evidence", "parameter_reachability", "recommended_action", "uncertainty"} <= set(records[0])
