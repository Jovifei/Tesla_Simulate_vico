"""Human-guided engineering objective for Stage X/Y.

The validated Jovi feedback is converted into bounded engineering priorities.
It never grants R1 qualification, Profile Freeze, or an OEM likeness claim.
Feedback with unusable reference audio (for example speech-contaminated RX-7
material) is rejected fail-closed.
"""

from __future__ import annotations

from typing import Any

import numpy as np

FEEDBACK_SCHEMA = "s12.stage_y.human_feedback_objective.v1"

_PROBLEM_DIMENSIONS: dict[str, tuple[str, ...]] = {
    "低频无冲击": ("low_frequency_body", "120_400_pressure_attack"),
    "机械感不足": ("mechanical_texture", "idle_life"),
    "固定电子哨声": ("synthetic_artifact", "forced_induction_identity"),
    "太刺": ("synthetic_artifact", "mid_band_congestion"),
    "太薄": ("low_frequency_body", "120_400_pressure_attack", "mechanical_texture"),
    "回火不自然": ("afterfire_naturalness",),
}

_UNUSABLE_AGREEMENTS = {"无法判断", "REFERENCE_UNUSABLE", "HUMAN_DATA_QUALITY_BLOCKED"}


def normalize_feedback(feedback: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize one vehicle-level feedback row into a deterministic record."""
    source = dict(feedback or {})
    problems = source.get("problems") or []
    if isinstance(problems, str):
        problems = [problems]
    problems = [str(item).strip() for item in problems if str(item).strip()]
    agreement = str(source.get("software_agreement", "")).strip()
    notes = str(source.get("notes") or source.get("note_summary") or "").strip()
    usable = bool(problems or notes) and agreement not in _UNUSABLE_AGREEMENTS
    lowered = notes.lower()
    if any(token in lowered for token in ("讲话", "人声", "speech", "not engine")):
        usable = False
    return {
        "schema": FEEDBACK_SCHEMA,
        "vehicle_id": source.get("vehicle_id"),
        "software_agreement": agreement or None,
        "identity": source.get("identity"),
        "realism": source.get("realism"),
        "preference": source.get("preference"),
        "problems": sorted(set(problems)),
        "notes": notes,
        "usable_for_engineering_objective": usable,
        "qualification_scope": "R2/R3 engineering guidance only",
    }


def feedback_dimension_weights(feedback: dict[str, Any] | None) -> dict[str, float]:
    """Return normalized dimension priorities inferred from validated problems."""
    record = normalize_feedback(feedback)
    if not record["usable_for_engineering_objective"]:
        return {}
    weights: dict[str, float] = {}
    for problem in record["problems"]:
        dimensions = _PROBLEM_DIMENSIONS.get(problem, ())
        if not dimensions:
            continue
        share = 1.0 / len(dimensions)
        for dimension in dimensions:
            weights[dimension] = weights.get(dimension, 0.0) + share
    total = sum(weights.values())
    if total <= 0.0:
        return {}
    return {name: value / total for name, value in sorted(weights.items())}


def evaluate_feedback_alignment(
    dimension_medians: dict[str, float],
    feedback: dict[str, Any] | None,
    *,
    maximum_adjustment: float = 0.05,
) -> dict[str, Any]:
    """Score whether candidate movement addresses the human-reported problems.

    Dimension values use the comparator convention: negative is closer to the
    reference than the parent.  The feedback adjustment is intentionally
    bounded to five percentage points by default, so human guidance can rank
    technically similar candidates but cannot override failed hard gates or a
    large reference-supported regression.
    """
    record = normalize_feedback(feedback)
    weights = feedback_dimension_weights(feedback)
    evidence: dict[str, Any] = {}
    weighted_support = 0.0
    covered_weight = 0.0
    for dimension, weight in weights.items():
        value = dimension_medians.get(dimension, float("nan"))
        if not np.isfinite(value):
            evidence[dimension] = {
                "status": "NOT_AVAILABLE",
                "weight": weight,
                "value": None,
            }
            continue
        support = float(np.clip(-float(value) / 0.20, -1.0, 1.0))
        evidence[dimension] = {
            "status": "EVALUATED",
            "weight": weight,
            "value": float(value),
            "support": support,
        }
        weighted_support += weight * support
        covered_weight += weight
    normalized_support = weighted_support / covered_weight if covered_weight else 0.0
    adjustment = float(maximum_adjustment * normalized_support) if weights else 0.0
    return {
        "schema": FEEDBACK_SCHEMA,
        "feedback": record,
        "dimension_weights": weights,
        "dimension_evidence": evidence,
        "coverage_fraction": covered_weight,
        "normalized_support": normalized_support,
        "objective_adjustment": adjustment,
        "automatic_tuning_eligible": False,
        "profile_update": "FORBIDDEN",
        "scope": (
            "bounded engineering ranking aid only; no timing change without "
            "synchronised RPM/load/throttle/gear"
        ),
    }


def combine_reference_and_feedback_objective(
    reference_objective: float | None,
    dimension_medians: dict[str, float],
    feedback: dict[str, Any] | None,
) -> dict[str, Any]:
    """Combine the reference objective with a bounded human-guidance term."""
    alignment = evaluate_feedback_alignment(dimension_medians, feedback)
    combined = None
    if reference_objective is not None and np.isfinite(reference_objective):
        combined = float(reference_objective) + float(alignment["objective_adjustment"])
    return {
        "reference_improvement_fraction": reference_objective,
        "feedback_adjustment": alignment["objective_adjustment"],
        "combined_engineering_objective": combined,
        "feedback_alignment": alignment,
        "formal_selection_eligible": False,
    }


__all__ = [
    "FEEDBACK_SCHEMA",
    "combine_reference_and_feedback_objective",
    "evaluate_feedback_alignment",
    "feedback_dimension_weights",
    "normalize_feedback",
]
