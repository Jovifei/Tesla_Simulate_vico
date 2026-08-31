"""Stage-I Hellcat candidate distance in final-PCM reference space."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import math
from pathlib import Path

import numpy as np

from ..acoustic_analysis.reference_feature_extractor import extract_reference_features
from ..stage_g.reference_targets import load_reference_state_target


BANDS = (
    (20.0, 250.0),
    (250.0, 1000.0),
    (1000.0, 4000.0),
    (4000.0, 12000.0),
)
WINDOWS = {
    "idle": (0.0, 8.0),
    "acceleration": (8.0, 26.0),
    "afterfire": (36.0, 46.0),
}
CANDIDATE_IDS = (
    "I6-A Balanced",
    "I6-B Whine Forward",
    "I6-C Softer Mechanical",
)


def compute_stage_i_reference_distance(
    stage_h_wav: str | Path,
    stage_i_wavs: Mapping[str, str | Path],
    target_path: str | Path,
    *,
    vehicle_id: str = "hellcat",
) -> dict[str, object]:
    """Compare Stage H and all three Stage I final-PCM cycles.

    Only relative four-band shares are compared. Absolute recording loudness is
    deliberately excluded because the B/R2 targets are microphone/AGC dependent.
    """
    if set(stage_i_wavs) != set(CANDIDATE_IDS):
        raise ValueError(f"Stage-I candidate IDs must be exactly {CANDIDATE_IDS}")

    target_file = Path(target_path)
    target_sha = _sha256(target_file)
    baseline = extract_reference_features(Path(stage_h_wav), segments=WINDOWS)
    candidate_features = {
        candidate_id: extract_reference_features(Path(wav_path), segments=WINDOWS)
        for candidate_id, wav_path in stage_i_wavs.items()
    }

    candidates: dict[str, object] = {}
    for candidate_id in CANDIDATE_IDS:
        rows: dict[str, object] = {}
        improvements: list[float] = []
        for state_id in WINDOWS:
            target = load_reference_state_target(
                target_file,
                vehicle_id,
                state_id,
                target_sha,
            )
            if target is None:
                rows[state_id] = _not_available_row()
                continue

            actual_h = _band_shares(baseline, state_id)
            actual_i = _band_shares(candidate_features[candidate_id], state_id)
            target_bands = [float(value) for value in target.band_shares]
            distance_h = _distance(actual_h, target_bands)
            distance_i = _distance(actual_i, target_bands)
            improvement = (distance_h - distance_i) / max(distance_h, 1.0e-12)
            improvements.append(improvement)
            rows[state_id] = {
                "availability": "eligible",
                "target": {
                    "band_shares": target_bands,
                    "spectral_centroid_hz": float(target.spectral_centroid_hz),
                },
                "actual_stage_h": {
                    "band_shares": actual_h,
                    "spectral_centroid_hz": _centroid(baseline, state_id),
                },
                "actual_stage_i": {
                    "band_shares": actual_i,
                    "spectral_centroid_hz": _centroid(candidate_features[candidate_id], state_id),
                },
                "signed_error": [actual_i[index] - target_bands[index] for index in range(4)],
                "absolute_error": [abs(actual_i[index] - target_bands[index]) for index in range(4)],
                "stage_h_distance": distance_h,
                "stage_i_distance": distance_i,
                "improvement_ratio": improvement,
                "reference_provenance": dict(target.provenance),
            }

        all_available = all(
            isinstance(row, Mapping) and row.get("availability") == "eligible"
            for row in rows.values()
        )
        mean_improvement = float(np.mean(improvements)) if improvements else None
        no_state_worse = all(value >= -0.10 for value in improvements)
        gates = {
            "all_required_states_available": all_available,
            "mean_improvement_at_least_30_percent": (
                mean_improvement is not None and mean_improvement >= 0.30
            ),
            "no_state_worse_than_10_percent": no_state_worse,
        }
        candidates[candidate_id] = {
            "states": rows,
            "mean_improvement_ratio": mean_improvement,
            "gates": gates,
            "automatic_status": (
                "PASS" if all(gates.values()) else "PARTIAL / AUTOMATED_GATE_FAIL"
            ),
        }

    return {
        "schema_version": "s12-stage-i-reference-distance-1",
        "vehicle_id": vehicle_id,
        "domain": "final_pcm",
        "bands_hz": [list(band) for band in BANDS],
        "windows_s": {name: list(bounds) for name, bounds in WINDOWS.items()},
        "candidates": candidates,
        "automatic_status": (
            "PASS"
            if all(candidate["automatic_status"] == "PASS" for candidate in candidates.values())  # type: ignore[index]
            else "PARTIAL / AUTOMATED_GATE_FAIL"
        ),
        "reference_target_sha256": target_sha,
        "provenance": (
            "B/R2 relative features; microphone/AGC dependent; "
            "synthetic candidates; uncalibrated; not OEM reproduction"
        ),
    }


def _band_shares(features: Mapping[str, object], state_id: str) -> list[float]:
    segment = _segment(features, state_id)
    values = np.asarray(segment.get("band_shares"), dtype=np.float64)
    if values.shape != (4,) or not np.all(np.isfinite(values)):
        raise ValueError(f"final-PCM {state_id!r} band shares must contain four finite values")
    return [float(value) for value in values]


def _centroid(features: Mapping[str, object], state_id: str) -> float:
    value = _segment(features, state_id).get("spectral_centroid_hz")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"final-PCM {state_id!r} spectral centroid must be finite")
    return float(value)


def _segment(features: Mapping[str, object], state_id: str) -> Mapping[str, object]:
    segments = features.get("segments")
    if not isinstance(segments, Mapping) or not isinstance(segments.get(state_id), Mapping):
        raise ValueError(f"final-PCM extractor missing state {state_id!r}")
    return segments[state_id]  # type: ignore[return-value]


def _distance(actual: list[float], target: list[float]) -> float:
    return float(math.sqrt(0.25 * sum((a - t) ** 2 for a, t in zip(actual, target, strict=True))))


def _not_available_row() -> dict[str, object]:
    return {
        "availability": "not_available",
        "target": None,
        "actual_stage_h": None,
        "actual_stage_i": None,
        "signed_error": None,
        "absolute_error": None,
        "stage_h_distance": None,
        "stage_i_distance": None,
        "improvement_ratio": None,
        "reference_provenance": None,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = (
    "BANDS",
    "CANDIDATE_IDS",
    "WINDOWS",
    "compute_stage_i_reference_distance",
)
