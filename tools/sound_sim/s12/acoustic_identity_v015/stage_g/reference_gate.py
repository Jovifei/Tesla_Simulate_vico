"""Final-PCM reference distance and automatic Stage-G gate."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from .candidate_profiles import ANCHOR_IDS, StageGCandidateProfile, load_stage_g_candidate
from .reference_targets import REFERENCE_STATE_IDS, load_reference_state_target

BANDS = ((20.0, 250.0), (250.0, 1000.0), (1000.0, 4000.0), (4000.0, 12000.0))


def band_distance(actual: Sequence[float], target: Sequence[float]) -> float:
    actual_array = np.asarray(actual, dtype=np.float64)
    target_array = np.asarray(target, dtype=np.float64)
    if actual_array.shape != (4,) or target_array.shape != (4,) or not np.all(np.isfinite(actual_array)) or not np.all(np.isfinite(target_array)):
        raise ValueError("band distance requires four finite shares")
    return float(math.sqrt(0.25 * np.sum(np.square(actual_array - target_array))))


def compare_state_features(target: Sequence[float], stage_c: Sequence[float], stage_g: Sequence[float]) -> dict[str, object]:
    target_values = [float(value) for value in target]
    baseline = [float(value) for value in stage_c]
    candidate = [float(value) for value in stage_g]
    baseline_distance = band_distance(baseline, target_values)
    candidate_distance = band_distance(candidate, target_values)
    return {
        "target": target_values,
        "actual_stage_c": baseline,
        "actual_stage_g": candidate,
        "signed_error": [a - b for a, b in zip(candidate, target_values)],
        "absolute_error": [abs(a - b) for a, b in zip(candidate, target_values)],
        "stage_c_distance": baseline_distance,
        "stage_g_distance": candidate_distance,
        "improvement_ratio": (baseline_distance - candidate_distance) / max(baseline_distance, 1e-12),
        "availability": "eligible",
    }


def evaluate_reference_gate(
    evidence_root: str | Path,
    candidate_paths: Mapping[str, str | Path],
) -> dict[str, object]:
    """Evaluate all nine vehicle/state pairs without fallback or zero-fill."""
    root = Path(evidence_root)
    states: dict[str, object] = {}
    improvements: list[float] = []
    missing: list[str] = []
    for vehicle_id in ANCHOR_IDS:
        candidate_path = Path(candidate_paths[vehicle_id]).resolve()
        candidate = load_stage_g_candidate(candidate_path)
        reference_path = candidate_path.parents[2] / str(candidate.reference_target["path"])
        reference_sha = candidate.reference_target["sha256"]
        for state_id in REFERENCE_STATE_IDS:
            key = f"{vehicle_id}/{state_id}"
            target = load_reference_state_target(reference_path, vehicle_id, state_id, reference_sha)
            evidence_path = root / vehicle_id / "reference_evidence.json"
            if target is None or not evidence_path.is_file():
                states[key] = {"availability": "not_available", "target": None, "actual_stage_c": None, "actual_stage_g": None, "improvement_ratio": None}
                missing.append(key)
                continue
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            try:
                c = evidence["roles"]["stage_c"]["feature_extractor"]["segments"][state_id]["band_shares"]
                g = evidence["roles"]["stage_g"]["feature_extractor"]["segments"][state_id]["band_shares"]
            except (KeyError, TypeError) as exc:
                raise ValueError(f"labelled final-PCM evidence is incomplete for {key}") from exc
            result = compare_state_features(target.band_shares, c, g)
            result["reference_provenance"] = dict(target.provenance)
            result["source_sha256"] = target.source_sha256
            states[key] = result
            improvements.append(float(result["improvement_ratio"]))
    mean_improvement = float(np.mean(improvements)) if improvements else float("nan")
    no_worse = bool(improvements) and all(value >= -0.10 for value in improvements)
    gates = {
        "all_nine_states_available": not missing,
        "mean_improvement_at_least_30_percent": bool(improvements) and mean_improvement >= 0.30,
        "no_state_worse_than_10_percent": no_worse,
    }
    status = "PASS" if all(gates.values()) else "PARTIAL / AUTOMATED_GATE_FAIL"
    return {
        "schema_version": "s12-stage-g-reference-distance-1",
        "domain": "final_pcm",
        "bands_hz": [list(band) for band in BANDS],
        "states": states,
        "missing_states": missing,
        "mean_improvement_ratio": mean_improvement if np.isfinite(mean_improvement) else None,
        "gates": gates,
        "status": status,
        "provenance": "B/R2 relative features; C/synthetic candidate; uncalibrated; not OEM reproduction",
    }


__all__ = ("BANDS", "band_distance", "compare_state_features", "evaluate_reference_gate")
