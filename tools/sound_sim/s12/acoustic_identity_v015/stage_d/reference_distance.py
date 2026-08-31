"""Reference-to-candidate band distance in final-PCM feature space."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math

import numpy as np


def band_distance(actual: Sequence[float], target: Sequence[float]) -> float:
    actual_array = np.asarray(actual, dtype=np.float64)
    target_array = np.asarray(target, dtype=np.float64)
    if actual_array.shape != (4,) or target_array.shape != (4,):
        raise ValueError("band distance requires four finite band shares")
    if not np.all(np.isfinite(actual_array)) or not np.all(np.isfinite(target_array)):
        raise ValueError("band shares must be finite")
    return float(math.sqrt(0.25 * np.sum(np.square(actual_array - target_array))))


def summarize_reference_distance(stage_c: Mapping[str, float], candidate: Mapping[str, float]) -> dict[str, object]:
    if set(stage_c) != set(candidate) or not stage_c:
        raise ValueError("reference states must match and be non-empty")
    stage_c_values = np.asarray(list(stage_c.values()), dtype=np.float64)
    candidate_values = np.asarray(list(candidate.values()), dtype=np.float64)
    baseline = float(np.mean(stage_c_values))
    current = float(np.mean(candidate_values))
    improvement = (baseline - current) / max(baseline, 1e-12)
    state_improvements = {
        state: (float(stage_c[state]) - float(candidate[state])) / max(float(stage_c[state]), 1e-12)
        for state in stage_c
    }
    passes = improvement >= 0.30 and all(value >= -0.10 for value in state_improvements.values())
    return {
        "stage_c_mean_distance": baseline,
        "candidate_mean_distance": current,
        "improvement_ratio": improvement,
        "state_improvements": state_improvements,
        "passes": bool(passes),
    }
