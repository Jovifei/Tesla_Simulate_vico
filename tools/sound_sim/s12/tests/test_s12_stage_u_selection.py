from __future__ import annotations

from tools.sound_sim.s12.real_reference.stage_u_selection import select_candidates


def _row(vehicle: str, candidate: str, reference: str, improvement: float) -> dict:
    return {
        "vehicle_id": vehicle,
        "candidate_id": candidate,
        "reference_id": reference,
        "absolute_improvement": improvement,
        "candidate_distance": 0.4 - improvement,
        "parent_distance": 0.4,
        "professional_bound": True,
        "hard_gates_pass": True,
    }


def test_candidate_without_required_reference_improvement_is_rejected() -> None:
    outcome = select_candidates([_row("hellcat", "bad", "a", -0.02), _row("hellcat", "bad", "b", -0.01), _row("hellcat", "bad", "c", 0.02)])
    assert outcome["selected_candidates"] == []
    assert outcome["rejected_candidates"][0]["status"] == "NO_MEASURABLE_IMPROVEMENT"


def test_candidate_requires_two_of_three_hellcat_references_and_no_severe_regression() -> None:
    outcome = select_candidates([_row("hellcat", "good", "a", 0.10), _row("hellcat", "good", "b", 0.08), _row("hellcat", "good", "c", -0.01)])
    assert outcome["selected_candidates"][0]["candidate_id"] == "good"


def test_selection_keeps_only_best_qualified_candidate_per_vehicle() -> None:
    outcome = select_candidates([
        _row("hellcat", "good", "a", 0.10), _row("hellcat", "good", "b", 0.08), _row("hellcat", "good", "c", -0.01),
        _row("hellcat", "better", "a", 0.12), _row("hellcat", "better", "b", 0.11), _row("hellcat", "better", "c", -0.01),
    ])
    assert [row["candidate_id"] for row in outcome["selected_candidates"]] == ["better"]
    assert any(row["candidate_id"] == "good" and row["status"] == "QUALIFIED_NOT_SELECTED" for row in outcome["rejected_candidates"])
