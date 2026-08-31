from tools.sound_sim.s12.acoustic_identity_v015.stage_m.audit import audit_qualification_callgraph, build_gate_matrix, gate_source_matrix, signal_domain_matrix, validate_named_feedback

def test_callgraph_exposes_missing_reference_gate() -> None:
    audit = audit_qualification_callgraph()
    assert audit["fail_closed"]["reference_distance_enters_hard_gate"] is False
    assert "candidate_search" in audit["nodes"]

def test_absent_feedback_is_not_a_human_pass() -> None:
    receipt = validate_named_feedback([], set())
    assert receipt == {"accepted": False, "reason": "WAITING_FOR_JOVI_NAMED_REVIEW", "content_read": False, "human_pass": False}

def test_gate_matrix_stays_diagnostic_when_automatic_gates_fail() -> None:
    matrix = build_gate_matrix({}, {"accepted": False})
    assert set(matrix.values()) == {"DIAGNOSTIC_ONLY"}


def test_reference_distance_is_explicitly_not_a_round2_hard_gate() -> None:
    matrix = gate_source_matrix()
    assert matrix["gates"]["reference_distance"]["hard_gate"] is False
    assert matrix["qualification_defect"] == "reference_distance_is_not_a_required_round2_hard_gate"


def test_review_gain_copy_cannot_be_an_analysis_signal() -> None:
    assert signal_domain_matrix()["comfort_review_copy"]["analysis_allowed"] is False
