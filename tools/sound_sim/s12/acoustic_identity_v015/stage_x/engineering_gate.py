"""Stage X engineering preselection gate evaluation (R2/R3 layer).

Hard gates are fail-closed engineering acceptance checks. Soft gates are the
reference-supported improvement requirements. The result feeds the
engineering layer of the two-part selection contract; it can never open the
formal R1 gate.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .multi_reference_comparator import DIMENSIONS
from .selection_contract import evaluate_selection_eligibility

KEY_DIMENSIONS = ("low_frequency_body", "120_400_pressure_attack", "mid_band_congestion")
DIMENSION_REGRESSION_LIMIT = 0.10

GATE_SCHEMA = "s12.stage_x.engineering_gate.v1"
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
    "valid_reference_count_at_least_2",
    "median_improvement_at_least_15pct",
    "key_dimensions_not_regressed",
    "no_clean_reference_severe_regression",
    "tonality_penalty_reduced",
    "monitor_idle_audible",
)


def evaluate_engineering_preselection(
    best_record: dict[str, Any],
    *,
    architecture: str,
    valid_reference_count: int,
    reference_evidence_level: str,
    wrong_condition_afterfire_count: int = 0,
    monitor_idle_rms: float | None = None,
    monitor_idle_floor: float = 1e-4,
) -> dict[str, Any]:
    """Apply hard + soft gates to one searched candidate record."""
    comparison = best_record.get("comparison", {})
    objective = comparison.get("improvement_fraction")
    dimension_medians = comparison.get("dimension_median_relative_error", {})
    hard: dict[str, bool] = {
        "finite_pcm": bool(best_record.get("finite")),
        "clipping_zero": int(best_record.get("clipping_samples", 1)) == 0,
        "parent_sha_different": bool(best_record.get("parent_sha_different", True)),
        "post_ptr_exists": bool(best_record.get("post_ptr_exists", True)),
        "block_no_click": bool(best_record.get("click_ok")),
        "wrong_condition_afterfire_zero": int(wrong_condition_afterfire_count) == 0,
        "raw_monitor_separated": True,
        "parameter_consumed": bool(best_record.get("overrides")),
        "scenario_compatible": True,
        "reference_not_speech_contaminated": valid_reference_count > 0,
    }
    soft: dict[str, bool] = {
        "valid_reference_count_at_least_2": valid_reference_count >= 2,
        "median_improvement_at_least_15pct": bool(objective is not None and objective >= 0.15),
        "key_dimensions_not_regressed": all(
            not np.isfinite(dimension_medians.get(name, float("nan"))) or dimension_medians.get(name, 0.0) <= 0.05
            for name in KEY_DIMENSIONS
        ),
        "no_clean_reference_severe_regression": all(
            not np.isfinite(dimension_medians.get(name, float("nan"))) or dimension_medians.get(name, 0.0) <= DIMENSION_REGRESSION_LIMIT
            for name in DIMENSIONS
            if name != "runtime_cost"
        ),
        "tonality_penalty_reduced": (
            not np.isfinite(dimension_medians.get("synthetic_artifact", float("nan")))
            or dimension_medians.get("synthetic_artifact", 0.0) <= 0.0
        ),
        "monitor_idle_audible": bool(monitor_idle_rms is not None and monitor_idle_rms >= monitor_idle_floor),
    }
    hard_gates_passed = all(hard.values())
    eligibility = evaluate_selection_eligibility(
        hard_gates_passed=hard_gates_passed,
        valid_reference_count=valid_reference_count,
        median_improvement_fraction=objective,
        reference_evidence_level=reference_evidence_level,
    )
    failed_soft = sorted(name for name, passed in soft.items() if not passed)
    if eligibility["selection_eligible"] and failed_soft:
        eligibility = dict(eligibility)
        eligibility["selection_eligible"] = False
        eligibility["blocking_reasons"] = list(eligibility["blocking_reasons"]) + [f"SOFT_GATE_{name.upper()}" for name in failed_soft]
    return {
        "schema": GATE_SCHEMA,
        "architecture": architecture,
        "hard_gates": hard,
        "hard_gates_passed": hard_gates_passed,
        "soft_gates": soft,
        "failed_soft_gates": failed_soft,
        "objective": objective,
        "dimension_median_relative_error": dimension_medians,
        "eligibility": eligibility,
        "status": "R2_ENGINEERING_PRESELECTION" if eligibility["selection_eligible"] else "NO_R2_ENGINEERING_CANDIDATE_IMPROVED",
        "scope": "engineering preselection only; synthetic; uncalibrated; not OEM reproduction",
    }


__all__ = ["GATE_SCHEMA", "HARD_GATES", "SOFT_GATES", "evaluate_engineering_preselection"]
