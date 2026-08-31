"""Fail-closed Stage X/Y engineering preselection gate.

Every hard gate is backed by an observed field. Missing evidence is a failure;
there are no default-True escape paths. Scenario windows and independent
recording sessions are counted separately.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .human_feedback_objective import evaluate_feedback_alignment
from .multi_reference_comparator import DIMENSIONS
from .selection_contract import evaluate_selection_eligibility

KEY_DIMENSIONS = (
    "low_frequency_body",
    "120_400_pressure_attack",
    "mid_band_congestion",
)
DIMENSION_REGRESSION_LIMIT = 0.10

GATE_SCHEMA = "s12.stage_y.engineering_gate.v2"
HARD_GATES = (
    "finite_pcm",
    "clipping_zero",
    "parent_sha_different",
    "post_ptr_exists",
    "block_no_click",
    "wrong_condition_afterfire_zero",
    "raw_monitor_separated",
    "parameter_consumed",
    "scenario_compatible",
    "reference_not_speech_contaminated",
)
SOFT_GATES = (
    "independent_reference_count_at_least_2",
    "median_improvement_at_least_15pct",
    "key_dimensions_not_regressed",
    "no_clean_reference_severe_regression",
    "tonality_penalty_reduced",
    "monitor_idle_audible",
    "human_feedback_consistent",
)


def _explicit_bool(record: dict[str, Any], name: str) -> bool:
    """Only the literal boolean True satisfies an evidence-backed gate."""
    return record.get(name) is True


def _finite_dimension(dimension_medians: dict[str, Any], name: str) -> float | None:
    value = dimension_medians.get(name)
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return numeric if np.isfinite(numeric) else None


def evaluate_engineering_preselection(
    best_record: dict[str, Any],
    *,
    architecture: str,
    valid_reference_count: int,
    reference_evidence_level: str,
    independent_reference_count: int | None = None,
    wrong_condition_afterfire_count: int | None = None,
    monitor_idle_rms: float | None = None,
    monitor_idle_floor: float = 1.0e-4,
    human_feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply evidence-backed hard and soft gates to one rendered candidate."""
    comparison = best_record.get("comparison") or {}
    objective = comparison.get("improvement_fraction")
    dimension_medians = comparison.get("dimension_median_relative_error") or {}

    independent_count = (
        int(independent_reference_count)
        if independent_reference_count is not None
        else int(best_record.get("independent_reference_count", valid_reference_count))
    )
    wrong_condition_count = (
        int(wrong_condition_afterfire_count)
        if wrong_condition_afterfire_count is not None
        else int(best_record.get("wrong_condition_afterfire_count", -1))
    )
    idle_rms = (
        float(monitor_idle_rms)
        if monitor_idle_rms is not None
        else best_record.get("monitor_idle_rms")
    )
    feedback = human_feedback if human_feedback is not None else best_record.get("human_feedback")
    feedback_alignment = evaluate_feedback_alignment(dimension_medians, feedback)

    hard: dict[str, bool] = {
        "finite_pcm": _explicit_bool(best_record, "finite"),
        "clipping_zero": best_record.get("clipping_samples") == 0,
        "parent_sha_different": _explicit_bool(best_record, "parent_sha_different"),
        "post_ptr_exists": _explicit_bool(best_record, "post_ptr_exists"),
        "block_no_click": _explicit_bool(best_record, "click_ok"),
        "wrong_condition_afterfire_zero": wrong_condition_count == 0,
        "raw_monitor_separated": _explicit_bool(best_record, "raw_monitor_separated"),
        "parameter_consumed": (
            _explicit_bool(best_record, "parameter_consumed")
            and int(best_record.get("consumed_parameter_count", 0)) > 0
        ),
        "scenario_compatible": _explicit_bool(best_record, "scenario_compatible"),
        "reference_not_speech_contaminated": (
            _explicit_bool(best_record, "reference_clean")
            and valid_reference_count > 0
        ),
    }

    objective_numeric = None
    try:
        if objective is not None and np.isfinite(float(objective)):
            objective_numeric = float(objective)
    except (TypeError, ValueError, OverflowError):
        objective_numeric = None

    key_values = [_finite_dimension(dimension_medians, name) for name in KEY_DIMENSIONS]
    finite_dimension_values = [
        value
        for name in DIMENSIONS
        if name != "runtime_cost"
        for value in [_finite_dimension(dimension_medians, name)]
        if value is not None
    ]
    synthetic_artifact = _finite_dimension(dimension_medians, "synthetic_artifact")
    feedback_record = feedback_alignment["feedback"]
    feedback_required = bool(feedback_record.get("usable_for_engineering_objective"))
    feedback_consistent = (
        not feedback_required
        or (
            feedback_alignment["coverage_fraction"] >= 0.50
            and feedback_alignment["normalized_support"] >= 0.0
        )
    )

    soft: dict[str, bool] = {
        "independent_reference_count_at_least_2": independent_count >= 2,
        "median_improvement_at_least_15pct": bool(
            objective_numeric is not None and objective_numeric >= 0.15
        ),
        "key_dimensions_not_regressed": bool(
            key_values
            and all(value is not None and value <= 0.05 for value in key_values)
        ),
        "no_clean_reference_severe_regression": bool(
            finite_dimension_values
            and all(value <= DIMENSION_REGRESSION_LIMIT for value in finite_dimension_values)
        ),
        "tonality_penalty_reduced": bool(
            synthetic_artifact is not None and synthetic_artifact <= 0.0
        ),
        "monitor_idle_audible": bool(
            idle_rms is not None
            and np.isfinite(float(idle_rms))
            and float(idle_rms) >= monitor_idle_floor
        ),
        "human_feedback_consistent": feedback_consistent,
    }

    hard_gates_passed = all(hard.values())
    eligibility = evaluate_selection_eligibility(
        hard_gates_passed=hard_gates_passed,
        valid_reference_count=independent_count,
        median_improvement_fraction=objective_numeric,
        reference_evidence_level=reference_evidence_level,
    )
    failed_hard = sorted(name for name, passed in hard.items() if not passed)
    failed_soft = sorted(name for name, passed in soft.items() if not passed)
    if eligibility["selection_eligible"] and failed_soft:
        eligibility = dict(eligibility)
        eligibility["selection_eligible"] = False
        eligibility["blocking_reasons"] = list(eligibility["blocking_reasons"]) + [
            f"SOFT_GATE_{name.upper()}" for name in failed_soft
        ]

    evidence = {
        "finite": best_record.get("finite"),
        "clipping_samples": best_record.get("clipping_samples"),
        "parent_sha_different": best_record.get("parent_sha_different"),
        "post_ptr_exists": best_record.get("post_ptr_exists"),
        "click_ok": best_record.get("click_ok"),
        "wrong_condition_afterfire_count": wrong_condition_count,
        "raw_monitor_separated": best_record.get("raw_monitor_separated"),
        "parameter_consumed": best_record.get("parameter_consumed"),
        "consumed_parameter_count": best_record.get("consumed_parameter_count"),
        "scenario_compatible": best_record.get("scenario_compatible"),
        "reference_clean": best_record.get("reference_clean"),
        "bound_reference_case_count": valid_reference_count,
        "independent_reference_count": independent_count,
        "monitor_idle_rms": idle_rms,
    }
    return {
        "schema": GATE_SCHEMA,
        "architecture": architecture,
        "hard_gates": hard,
        "failed_hard_gates": failed_hard,
        "hard_gates_passed": hard_gates_passed,
        "soft_gates": soft,
        "failed_soft_gates": failed_soft,
        "evidence": evidence,
        "objective": objective_numeric,
        "dimension_median_relative_error": dimension_medians,
        "human_feedback_alignment": feedback_alignment,
        "eligibility": eligibility,
        "status": (
            "R2_ENGINEERING_PRESELECTION"
            if eligibility["selection_eligible"]
            else "NO_R2_ENGINEERING_CANDIDATE_IMPROVED"
        ),
        "scope": (
            "engineering preselection only; synthetic; uncalibrated; "
            "not OEM reproduction; no Profile Freeze"
        ),
    }


__all__ = [
    "GATE_SCHEMA",
    "HARD_GATES",
    "SOFT_GATES",
    "evaluate_engineering_preselection",
]
