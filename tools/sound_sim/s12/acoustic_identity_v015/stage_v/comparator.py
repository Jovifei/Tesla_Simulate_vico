"""Three-way raw-signal comparison for Reference/Parent/Candidate evidence."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from ...acoustic_comparator.core import ComparisonCase, compare_signals
from ..event_domain.diagnostics import compare_parent_candidate


def compare_three_way(
    reference: np.ndarray | None,
    parent: np.ndarray,
    candidate: np.ndarray,
    case: ComparisonCase,
) -> dict[str, Any]:
    """Return three explicit pair results; identical Parent/Candidate is rejected."""

    parent_values = np.asarray(parent, dtype=np.float64)
    candidate_values = np.asarray(candidate, dtype=np.float64)
    if parent_values.shape != candidate_values.shape:
        raise ValueError("parent and candidate shapes differ")
    parent_delta = compare_parent_candidate(parent_values, candidate_values, case.sample_rate_hz)
    parent_case = replace(case, candidate_id="legacy_parent")
    candidate_case = replace(case, candidate_id="event_candidate")
    internal_case = replace(
        case,
        reference_id="legacy_parent",
        candidate_id="event_candidate",
        reference_kind="synthetic_parent",
        reference_provenance="legacy_parent_raw",
    )
    pairs = {
        "reference_parent": compare_signals(reference, parent_values, parent_case, candidate_scenario=case.scenario),
        "reference_candidate": compare_signals(reference, candidate_values, candidate_case, candidate_scenario=case.scenario),
        "parent_candidate": {"difference_rms": parent_delta["difference_rms"], "delta": parent_delta, "rich": compare_signals(parent_values, candidate_values, internal_case, candidate_scenario=case.scenario)},
    }
    return {
        "schema": "s12.stage_v.three_way_comparison.v1",
        "scope": "synthetic; uncalibrated; not OEM reproduction",
        "analysis_signal": "unaltered_analysis_signal",
        "pairs": pairs,
        "parent_candidate_difference_rms": parent_delta["difference_rms"],
        "reference_available": reference is not None,
    }


__all__ = ["compare_three_way"]
