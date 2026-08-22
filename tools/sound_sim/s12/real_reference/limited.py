"""R2 limited comparison adapter over the existing Stage-N comparator core."""
from __future__ import annotations

from typing import Any

import numpy as np

from tools.sound_sim.s12.acoustic_comparator.core import ComparisonCase, compare_signals

from .qualification import ReferenceQualificationError, qualify_r2_reference


def compare_r2_signals(
    reference: np.ndarray,
    candidate: np.ndarray,
    case: ComparisonCase,
    reference_record: dict[str, Any],
    *,
    candidate_scenario: str | None = None,
) -> dict[str, Any]:
    """Compare an authorised R2 pair while withholding R1-only conclusions."""

    gate = qualify_r2_reference(reference_record)
    if not gate["eligible"]:
        raise ReferenceQualificationError(
            f"reference {reference_record.get('recording_id', '<unknown>')} is not R2-eligible: "
            + ", ".join(gate["missing"])
        )
    result = compare_signals(
        reference,
        candidate,
        case,
        candidate_scenario=candidate_scenario,
        candidate_domain="unaltered_analysis_signal",
    )
    result["reference_qualification"] = {
        "level": "R2",
        "order_hard_gate": False,
        "allowed_metric_groups": gate["allowed_metric_groups"],
        "automatic_tuning_eligible": False,
        "human_feedback_required": True,
    }
    result["uncertainty"]["identity_score_available"] = False
    result["uncertainty"]["digital_domain_relative_only"] = True
    result["order"]["qualification"] = "NOT_QUALIFIED_R2_NO_SYNCHRONIZED_RPM"
    result["order"]["used_for_gate"] = False
    result["recommendation_status"] = "WITHHELD_UNTIL_HUMAN_FEEDBACK_AND_R1_OR_REFERENCE_REVIEW"
    return result


__all__ = ["compare_r2_signals"]
