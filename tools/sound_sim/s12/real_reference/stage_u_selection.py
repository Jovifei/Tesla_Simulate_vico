"""Fail-closed Stage U candidate selection; never select merely the least bad candidate."""
from __future__ import annotations

import math
from collections import defaultdict
from statistics import median
from typing import Any, Mapping, Sequence


def _required_improvements(vehicle_id: str, reference_count: int) -> int:
    if vehicle_id == "rx7_fd":
        return max(3, math.ceil(reference_count * 3.0 / 5.0))
    return max(1, math.ceil(reference_count * 2.0 / 3.0))


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
        required = _required_improvements(vehicle_id, len(rows))
        improved_count = sum(value > 0.0 for value in improvements)
        severe_regression = any(value < -severe_regression_fraction * parent for value, parent in zip(improvements, parent_distances))
        professional_bound = all(bool(row.get("professional_bound")) for row in rows)
        hard_gates = all(bool(row.get("hard_gates_pass")) for row in rows)
        result = {
            "vehicle_id": vehicle_id,
            "candidate_id": candidate_id,
            "reference_count": len(rows),
            "required_improvement_count": required,
            "improved_reference_count": improved_count,
            "median_absolute_improvement": float(median(improvements)),
            "worst_case_absolute_improvement": float(min(improvements)),
            "severe_regression": severe_regression,
            "professional_bound": professional_bound,
            "hard_gates_pass": hard_gates,
            "per_reference": [dict(row) for row in rows],
        }
        if professional_bound and hard_gates and improved_count >= required and result["median_absolute_improvement"] > 0.0 and not severe_regression:
            result["status"] = "QUALIFIED_FOR_SELECTION"
            qualified.append(result)
        else:
            result["status"] = "NO_MEASURABLE_IMPROVEMENT"
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
    return {
        "schema_version": "s12-stage-u-selection-v1",
        "status": "R2_COMPARATOR_DRIVEN_CANDIDATE_READY" if selected else "NO_MEASURABLE_IMPROVEMENT",
        "selected_candidates": selected,
        "rejected_candidates": rejected,
        "automatic_tuning_eligible": False,
        "profile_candidate_ready": False,
        "order_status": "ORDER_COMPARISON_NOT_QUALIFIED",
    }


__all__ = ["select_candidates"]
