"""Bounded, deterministic Stage-G diagnostic coordinate descent."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from .candidate_profiles import StageGCandidateProfile


Objective = Callable[[StageGCandidateProfile], float]


def coordinate_descent_candidate(candidate: StageGCandidateProfile, objective: Objective, max_passes: int = 2) -> tuple[StageGCandidateProfile, dict[str, object]]:
    """Try only declared parameter bounds and accept strict objective decreases.

    This helper never touches common EQ/LF/rumble/PTR parameters.  It is kept
    deterministic by using the profile's JSON insertion order and two fixed
    probes (20% toward each bound); failed gates remain a diagnostic result.
    """
    if max_passes < 0 or max_passes > 2:
        raise ValueError("Stage-G optimizer max_passes must be 0..2")
    current = candidate; current_score = float(objective(current)); attempts: list[dict[str, object]] = []
    for pass_index in range(max_passes):
        changed = False
        for qualified in current.requested_parameters():
            if qualified.startswith("loudness."):
                section, name = "loudness", qualified.rsplit(".", 1)[1]; entry = current.payload["loudness"]["transient_peak_shaper"][name]
            else:
                section, name = qualified.rsplit(".", 1); entry = current.payload[section][name]
            low, high = float(entry["range"][0]), float(entry["range"][1]); value = float(entry["value"]); span = high - low
            probes = (max(low, value - 0.20 * span), min(high, value + 0.20 * span))
            for probe in probes:
                if probe == value: continue
                trial = current.with_parameter(section, name, probe); score = float(objective(trial)); attempts.append({"pass": pass_index + 1, "parameter": qualified, "value": probe, "objective": score})
                if score < current_score:
                    current, current_score, changed = trial, score, True
                    break
        if not changed: break
    return current, {"passes": max_passes, "accepted_candidate_id": current.candidate_id, "objective": current_score, "attempts": attempts, "bounded": True, "status": "diagnostic_candidate_only"}


__all__ = ("coordinate_descent_candidate",)
