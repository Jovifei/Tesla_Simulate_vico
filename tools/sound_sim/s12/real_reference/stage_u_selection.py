"""Fail-closed Stage U candidate selection; never select merely the least bad candidate."""
from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any, Mapping, Sequence


_REFERENCE_REQUIREMENTS = {
    "ferrari_458": (3, 2),
    "hellcat": (3, 2),
    "rx7_fd": (5, 3),
}


def select_candidates(results: Sequence[Mapping[str, Any]], *, severe_regression_fraction: float = 0.10) -> dict[str, Any]:
    """Select only candidates with required multi-reference measurable improvement."""

    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in results:
        grouped[(str(row["vehicle_id"]), str(row["candidate_id"]))].append(row)
    qualified: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for (vehicle_id, candidate_id), rows in sorted(grouped.items()):
        improvements = [float(row["absolute_improvement"]) for row in rows]
        parent_distances = [max(float(row["parent_distance"]), 1e-12) for row in rows]
        requirement = _REFERENCE_REQUIREMENTS.get(vehicle_id)
        expected_reference_count, required = requirement if requirement is not None else (0, 0)
        reference_ids = [str(row.get("reference_id") or "") for row in rows]
        distinct_reference_count = len({reference_id for reference_id in reference_ids if reference_id})
        improved_count = sum(value > 0.0 for value in improvements)
        severe_regression = any(value < -severe_regression_fraction * parent for value, parent in zip(improvements, parent_distances))
        professional_bound = all(bool(row.get("professional_bound")) for row in rows)
        hard_gates = all(bool(row.get("hard_gates_pass")) for row in rows)
        result = {
            "vehicle_id": vehicle_id,
            "candidate_id": candidate_id,
            "reference_count": len(rows),
            "distinct_reference_count": distinct_reference_count,
            "expected_reference_count": expected_reference_count,
            "required_improvement_count": required,
            "improved_reference_count": improved_count,
            "median_absolute_improvement": float(median(improvements)),
            "worst_case_absolute_improvement": float(min(improvements)),
            "severe_regression": severe_regression,
            "professional_bound": professional_bound,
            "hard_gates_pass": hard_gates,
            "per_reference": [dict(row) for row in rows],
        }
        duplicate_coverage = len(reference_ids) != distinct_reference_count
        exact_coverage = requirement is not None and len(rows) == expected_reference_count and distinct_reference_count == expected_reference_count
        if not exact_coverage:
            result["status"] = "REFERENCE_COVERAGE_NOT_QUALIFIED"
            if requirement is None:
                result["selection_reason"] = f"unsupported vehicle reference requirement: {vehicle_id}"
            elif duplicate_coverage:
                result["selection_reason"] = f"duplicate reference_id coverage; expected {expected_reference_count} distinct clean references"
            else:
                result["selection_reason"] = f"expected {expected_reference_count} distinct clean references; received {distinct_reference_count}"
            rejected.append(result)
        elif professional_bound and hard_gates and improved_count >= required and result["median_absolute_improvement"] > 0.0 and not severe_regression:
            result["status"] = "QUALIFIED_FOR_SELECTION"
            qualified.append(result)
        else:
            result["status"] = "NO_MEASURABLE_IMPROVEMENT"
            result["selection_reason"] = (
                f"requires at least {required} numerically improved references with professional/hard gates, "
                "positive median improvement, and no severe regression"
            )
            rejected.append(result)
    qualified_by_vehicle: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in qualified:
        qualified_by_vehicle[row["vehicle_id"]].append(row)
    for vehicle_id, rows in sorted(qualified_by_vehicle.items()):
        ordered = sorted(rows, key=lambda row: (-row["median_absolute_improvement"], -row["worst_case_absolute_improvement"], row["candidate_id"]))
        winner = ordered[0]
        winner["status"] = "R2_COMPARATOR_DRIVEN_CANDIDATE_READY"
        selected.append(winner)
        for alternate in ordered[1:]:
            alternate["status"] = "QUALIFIED_NOT_SELECTED"
            alternate["selection_reason"] = f"lower median/worst-case improvement than {winner['candidate_id']}"
            rejected.append(alternate)
    failure_status = "NO_MEASURABLE_IMPROVEMENT"
    if rejected and all(row["status"] == "REFERENCE_COVERAGE_NOT_QUALIFIED" for row in rejected):
        failure_status = "REFERENCE_COVERAGE_NOT_QUALIFIED"
    return {
        "schema_version": "s12-stage-u-selection-v1",
        "status": "R2_COMPARATOR_DRIVEN_CANDIDATE_READY" if selected else failure_status,
        "selected_candidates": selected,
        "rejected_candidates": rejected,
        "automatic_tuning_eligible": False,
        "profile_candidate_ready": False,
        "abx_ready": False,
        "abx_reason": "loudness-matched audition copies are not created by Stage U selection",
        "order_status": "ORDER_COMPARISON_NOT_QUALIFIED",
    }


__all__ = ["select_candidates"]
