import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_m.callgraph import audit_qualification_callgraph, validate_gate_origin


def test_callgraph_names_all_required_round2_source_files() -> None:
    audit = audit_qualification_callgraph()
    assert set(audit["source_files"]) == {
        "stage_k/candidate_search.py", "scripts/qualify_stage_k_candidates.py", "stage_k/round2_propagation.py",
        "stage_k/round2_legacy_anchors.py", "stage_k/round2_remaining_sources.py", "stage_k/round2_package.py", "stage_k/round2_remaining_package.py",
    }
    assert len(audit["m2_answers"]) == 10


@pytest.mark.parametrize("gate", [
    {"name": "reference_distance", "domain": "unbound", "trace_bound": False},
    {"name": "idle_bytes", "domain": "loudness_matched_audition_signal", "trace_bound": True},
    {"name": "event_timing", "domain": "source", "trace_bound": False},
])
def test_invalid_gate_origins_are_rejected(gate: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        validate_gate_origin(gate)
