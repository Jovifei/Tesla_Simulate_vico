"""Final-PCM reference distance for Stage-J named candidates."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import math
from pathlib import Path

import numpy as np

from ..acoustic_analysis.reference_feature_extractor import extract_reference_features
from ..stage_g.reference_targets import load_reference_state_target

BANDS_HZ = ((20.0, 250.0), (250.0, 1000.0), (1000.0, 4000.0), (4000.0, 12000.0))
WINDOWS_S = {"idle": (0.0, 8.0), "acceleration": (8.0, 26.0), "afterfire": (36.0, 46.0)}


def compute_stage_j_reference_distance(
    vehicle_id: str,
    stage_c_wav: str | Path,
    stage_j_wav: str | Path,
    target_path: str | Path,
) -> dict[str, object]:
    """Compare Stage-C and Stage-J final PCM against relative stock targets."""
    target = Path(target_path)
    target_sha = hashlib.sha256(target.read_bytes()).hexdigest()
    baseline = extract_reference_features(Path(stage_c_wav), segments=WINDOWS_S)
    candidate = extract_reference_features(Path(stage_j_wav), segments=WINDOWS_S)
    rows: dict[str, object] = {}
    improvements: list[float] = []
    for state_id in WINDOWS_S:
        state_target = load_reference_state_target(target, vehicle_id, state_id, target_sha)
        if state_target is None:
            rows[state_id] = _unavailable()
            continue
        target_bands = list(state_target.band_shares)
        actual_c = _bands(baseline, state_id)
        actual_j = _bands(candidate, state_id)
        distance_c = _distance(actual_c, target_bands)
        distance_j = _distance(actual_j, target_bands)
        improvement = (distance_c - distance_j) / max(distance_c, 1e-12)
        improvements.append(improvement)
        rows[state_id] = {
            "availability": "eligible",
            "target": {"band_shares": target_bands, "spectral_centroid_hz": state_target.spectral_centroid_hz},
            "actual_stage_c": {"band_shares": actual_c, "spectral_centroid_hz": _centroid(baseline, state_id)},
            "actual_stage_j": {"band_shares": actual_j, "spectral_centroid_hz": _centroid(candidate, state_id)},
            "signed_error": [actual_j[i] - target_bands[i] for i in range(4)],
            "absolute_error": [abs(actual_j[i] - target_bands[i]) for i in range(4)],
            "stage_c_distance": distance_c,
            "stage_j_distance": distance_j,
            "improvement_ratio": improvement,
            "reference_provenance": dict(state_target.provenance),
        }
    mean_improvement = float(np.mean(improvements)) if improvements else None
    gates = {
        "all_required_states_available": len(improvements) == len(WINDOWS_S),
        "mean_improvement_at_least_30_percent": mean_improvement is not None and mean_improvement >= 0.30,
        "no_state_worse_than_10_percent": all(value >= -0.10 for value in improvements),
    }
    return {
        "schema_version": "s12-stage-j-reference-distance-1",
        "vehicle_id": vehicle_id,
        "domain": "final_pcm",
        "bands_hz": [list(band) for band in BANDS_HZ],
        "windows_s": {name: list(bounds) for name, bounds in WINDOWS_S.items()},
        "states": rows,
        "mean_improvement_ratio": mean_improvement,
        "gates": gates,
        "automatic_status": "PASS" if all(gates.values()) else "PARTIAL / AUTOMATED_GATE_FAIL",
        "reference_target_sha256": target_sha,
        "provenance": "B/R2 relative features; microphone/AGC dependent; synthetic; uncalibrated; not OEM reproduction",
    }


def _bands(features: Mapping[str, object], state_id: str) -> list[float]:
    row = _segment(features, state_id)
    values = row.get("band_shares")
    if not isinstance(values, (list, tuple)) or len(values) != 4:
        raise ValueError(f"missing four band shares for {state_id}")
    return [float(value) for value in values]


def _centroid(features: Mapping[str, object], state_id: str) -> float:
    value = _segment(features, state_id).get("spectral_centroid_hz")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"missing spectral centroid for {state_id}")
    return float(value)


def _segment(features: Mapping[str, object], state_id: str) -> Mapping[str, object]:
    segments = features.get("segments")
    if not isinstance(segments, Mapping) or not isinstance(segments.get(state_id), Mapping):
        raise ValueError(f"reference extractor missing state {state_id}")
    return segments[state_id]  # type: ignore[return-value]


def _distance(actual: list[float], target: list[float]) -> float:
    return float(math.sqrt(0.25 * sum((a - t) ** 2 for a, t in zip(actual, target, strict=True))))


def _unavailable() -> dict[str, object]:
    return {"availability": "not_available", "target": None, "actual_stage_c": None, "actual_stage_j": None, "signed_error": None, "absolute_error": None, "stage_c_distance": None, "stage_j_distance": None, "improvement_ratio": None, "reference_provenance": None}


__all__ = ("BANDS_HZ", "WINDOWS_S", "compute_stage_j_reference_distance")
