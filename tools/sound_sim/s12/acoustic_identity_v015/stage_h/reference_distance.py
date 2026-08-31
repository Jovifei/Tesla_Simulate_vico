"""Final-PCM Stage-H reference-distance calculation."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Mapping

import numpy as np

from ..acoustic_analysis.reference_feature_extractor import extract_reference_features
from ..stage_g.reference_targets import load_reference_state_target


BANDS = ((20.0, 250.0), (250.0, 1000.0), (1000.0, 4000.0), (4000.0, 12000.0))
WINDOWS = {"idle": (0.0, 8.0), "acceleration": (8.0, 26.0), "afterfire": (36.0, 46.0)}


def compute_stage_h_reference_distance(
    stage_g_wav: str | Path,
    stage_h_wav: str | Path,
    target_path: str | Path,
    *,
    vehicle_id: str = "hellcat",
    windows: Mapping[str, tuple[float, float]] = WINDOWS,
) -> dict[str, object]:
    """Compare Stage-G and Stage-H final PCM against relative target bands."""
    target_file = Path(target_path)
    target_sha = _sha256(target_file)
    baseline = extract_reference_features(Path(stage_g_wav), segments=windows)
    candidate = extract_reference_features(Path(stage_h_wav), segments=windows)
    rows: dict[str, object] = {}
    distances: list[tuple[float, float]] = []
    for state_id in windows:
        target = load_reference_state_target(target_file, vehicle_id, state_id, target_sha)
        if target is None:
            rows[state_id] = {"availability": "not_available", "target": None, "actual_stage_g": None, "actual_stage_h": None, "improvement_ratio": None}
            continue
        actual_g = [float(value) for value in baseline["segments"][state_id]["band_shares"]]  # type: ignore[index]
        actual_h = [float(value) for value in candidate["segments"][state_id]["band_shares"]]  # type: ignore[index]
        target_bands = [float(value) for value in target.band_shares]
        d_g = _distance(actual_g, target_bands)
        d_h = _distance(actual_h, target_bands)
        improvement = (d_g - d_h) / max(d_g, 1e-12)
        distances.append((d_g, d_h))
        rows[state_id] = {
            "availability": "eligible",
            "target": {"band_shares": target_bands, "spectral_centroid_hz": target.spectral_centroid_hz},
            "actual_stage_g": {"band_shares": actual_g, "spectral_centroid_hz": float(baseline["segments"][state_id]["spectral_centroid_hz"])},  # type: ignore[index]
            "actual_stage_h": {"band_shares": actual_h, "spectral_centroid_hz": float(candidate["segments"][state_id]["spectral_centroid_hz"])},  # type: ignore[index]
            "signed_error": [actual_h[i] - target_bands[i] for i in range(4)],
            "absolute_error": [abs(actual_h[i] - target_bands[i]) for i in range(4)],
            "stage_g_distance": d_g,
            "stage_h_distance": d_h,
            "improvement_ratio": improvement,
            "reference_provenance": dict(target.provenance),
        }
    average = float(np.mean([(base - candidate) / max(base, 1e-12) for base, candidate in distances])) if distances else None
    return {
        "schema_version": "s12-stage-h-reference-distance-1",
        "vehicle_id": vehicle_id,
        "domain": "final_pcm",
        "bands_hz": [list(band) for band in BANDS],
        "windows_s": {name: list(bounds) for name, bounds in windows.items()},
        "vehicles": {vehicle_id: rows},
        "average_improvement_ratio": average,
        "automatic_status": "PASS" if average is not None and average >= 0.30 and all(_state_pass(value) for value in rows.values()) else "PARTIAL / AUTOMATED_GATE_FAIL",
        "reference_target_sha256": target_sha,
        "provenance": "B/R2 relative features; microphone/AGC dependent; synthetic candidate; uncalibrated; not OEM reproduction",
    }


def _distance(actual: list[float], target: list[float]) -> float:
    return float(math.sqrt(0.25 * sum((a - t) ** 2 for a, t in zip(actual, target))))


def _state_pass(row: object) -> bool:
    if not isinstance(row, Mapping) or row.get("availability") != "eligible":
        return True
    improvement = row.get("improvement_ratio")
    return isinstance(improvement, (int, float)) and float(improvement) >= -0.10


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = ("BANDS", "WINDOWS", "compute_stage_h_reference_distance")
