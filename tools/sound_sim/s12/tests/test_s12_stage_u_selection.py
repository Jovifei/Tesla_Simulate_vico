from __future__ import annotations

import pytest

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


@pytest.mark.parametrize(
    ("vehicle_id", "reference_count", "required_improvements"),
    [("ferrari_458", 3, 2), ("hellcat", 3, 2), ("rx7_fd", 5, 3)],
)
def test_selection_requires_exact_distinct_reference_coverage_and_fixed_threshold(
    vehicle_id: str,
    reference_count: int,
    required_improvements: int,
) -> None:
    rows = [
        _row(vehicle_id, "candidate", f"reference-{index}", 0.05 if index < required_improvements else -0.001)
        for index in range(reference_count)
    ]

    outcome = select_candidates(rows)

    selected = outcome["selected_candidates"][0]
    assert selected["reference_count"] == reference_count
    assert selected["distinct_reference_count"] == reference_count
    assert selected["required_improvement_count"] == required_improvements


@pytest.mark.parametrize(
    ("rows", "reason_fragment"),
    [
        ([_row("hellcat", "candidate", "a", 0.1), _row("hellcat", "candidate", "b", 0.1)], "expected 3 distinct"),
        ([_row("hellcat", "candidate", "a", 0.1), _row("hellcat", "candidate", "a", 0.1), _row("hellcat", "candidate", "b", 0.1)], "duplicate"),
        ([_row("rx7_fd", "candidate", str(index), 0.1) for index in range(4)], "expected 5 distinct"),
    ],
)
def test_incomplete_or_duplicate_reference_coverage_fails_closed(rows: list[dict], reason_fragment: str) -> None:
    outcome = select_candidates(rows)

    assert outcome["selected_candidates"] == []
    rejected = outcome["rejected_candidates"][0]
    assert rejected["status"] == "REFERENCE_COVERAGE_NOT_QUALIFIED"
    assert reason_fragment in rejected["selection_reason"]
    assert outcome["automatic_tuning_eligible"] is False
    assert outcome["order_status"] == "ORDER_COMPARISON_NOT_QUALIFIED"


def test_selection_keeps_only_best_qualified_candidate_per_vehicle() -> None:
    outcome = select_candidates([
        _row("hellcat", "good", "a", 0.10), _row("hellcat", "good", "b", 0.08), _row("hellcat", "good", "c", -0.01),
        _row("hellcat", "better", "a", 0.12), _row("hellcat", "better", "b", 0.11), _row("hellcat", "better", "c", -0.01),
    ])
    assert [row["candidate_id"] for row in outcome["selected_candidates"]] == ["better"]
    assert any(row["candidate_id"] == "good" and row["status"] == "QUALIFIED_NOT_SELECTED" for row in outcome["rejected_candidates"])
