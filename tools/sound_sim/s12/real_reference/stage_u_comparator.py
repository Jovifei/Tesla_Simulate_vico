"""Reference/Parent/Candidate legacy triad comparison for Stage U selection evidence."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from scipy.io import wavfile

from tools.sound_sim.s12.real_reference.professional_clip_analysis import analyze_proxy_pair
from tools.sound_sim.s12.real_reference.stage_u_features import extract_raw_feature_summary


class StageUComparatorError(ValueError):
    """Raised when a three-way comparison cannot bind the same scenario."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _signal(path: Path) -> tuple[np.ndarray, int, float]:
    sample_rate_hz, values = wavfile.read(str(path))
    signal = np.asarray(values)
    if np.issubdtype(signal.dtype, np.integer):
        info = np.iinfo(signal.dtype)
        signal = signal.astype(np.float64) / float(max(abs(info.min), info.max))
    else:
        signal = signal.astype(np.float64)
    mono = signal.mean(axis=1) if signal.ndim > 1 else signal
    if mono.size == 0 or sample_rate_hz <= 0 or not np.isfinite(mono).all():
        raise StageUComparatorError(f"invalid audio input: {path}")
    return mono, int(sample_rate_hz), float(mono.size / sample_rate_hz)


def _proxy_pair(reference: Path, candidate: Path, pair_id: str, scenario: str, vehicle_id: str) -> dict[str, Any]:
    _, _, reference_duration = _signal(reference)
    _, _, candidate_duration = _signal(candidate)
    duration = min(reference_duration, candidate_duration)
    if duration <= 0.0:
        raise StageUComparatorError("triad clip duration is zero")
    return analyze_proxy_pair({
        "pair_id": pair_id,
        "file_id": f"{pair_id}-reference-vs-candidate",
        "vehicle_id": vehicle_id,
        "scenario": scenario,
        "reference_class": "R2_OR_R3_DIAGNOSTIC",
        "reference_path": str(reference),
        "reference_sha256": _sha256(reference),
        "candidate_path": str(candidate),
        "candidate_sha256": _sha256(candidate),
        "window": {"profile": f"{duration:.3f}s_same_scenario", "duration_s": duration},
        "microphone_uncertainty": "BOUND_TO_REFERENCE_QUALITY_MATRIX",
        "order": {"status": "ORDER_COMPARISON_NOT_QUALIFIED", "reason": "no synchronized R1 RPM trace"},
    })


def compare_triad(reference_path: Path, parent_path: Path, candidate_path: Path, scenario: str, vehicle_id: str) -> dict[str, Any]:
    """Compute raw Legacy triad metrics; professional receipts bind later using the same SHA."""

    reference, parent, candidate = (Path(value).resolve() for value in (reference_path, parent_path, candidate_path))
    reference_sha = _sha256(reference)
    parent_sha = _sha256(parent)
    candidate_sha = _sha256(candidate)
    if parent_sha == candidate_sha:
        raise StageUComparatorError("Parent/Candidate SHA must differ before triad comparison")
    rp = _proxy_pair(reference, parent, "reference_parent", scenario, vehicle_id)
    rc = _proxy_pair(reference, candidate, "reference_candidate", scenario, vehicle_id)
    pc = _proxy_pair(parent, candidate, "parent_candidate", scenario, vehicle_id)
    parent_distance = float(rp["legacy_proxy"]["delta"]["spectral_distance"])
    candidate_distance = float(rc["legacy_proxy"]["delta"]["spectral_distance"])
    reference_signal, reference_fs, _ = _signal(reference)
    parent_signal, parent_fs, _ = _signal(parent)
    candidate_signal, candidate_fs, _ = _signal(candidate)
    absolute = parent_distance - candidate_distance
    return {
        "schema_version": "s12-stage-u-triad-comparison-v1",
        "status": "TRIAD_LEGACY_COMPARISON_COMPLETE",
        "vehicle_id": vehicle_id,
        "scenario": scenario,
        "reference_path": str(reference),
        "parent_path": str(parent),
        "candidate_path": str(candidate),
        "reference_sha256": reference_sha,
        "parent_sha256": parent_sha,
        "candidate_sha256": candidate_sha,
        "reference_parent": rp,
        "reference_candidate": rc,
        "parent_candidate": pc,
        "parent_distance": parent_distance,
        "candidate_distance": candidate_distance,
        "absolute_improvement": absolute,
        "relative_improvement": absolute / max(parent_distance, 1e-12),
        "raw_features": {
            "reference": extract_raw_feature_summary(reference_signal, reference_fs),
            "parent": extract_raw_feature_summary(parent_signal, parent_fs),
            "candidate": extract_raw_feature_summary(candidate_signal, candidate_fs),
        },
        "professional_bound": False,
        "order_status": "ORDER_COMPARISON_NOT_QUALIFIED",
    }


def compare_reference_parent_candidate(record: Mapping[str, Any]) -> dict[str, Any]:
    """Compare one rendered grid record while preserving its selection identity."""

    required = ("reference_id", "candidate_id", "vehicle_id", "scenario", "reference_path", "parent_path", "candidate_path")
    missing = [name for name in required if not str(record.get(name) or "")]
    if missing:
        raise StageUComparatorError(f"triad record missing required fields: {', '.join(missing)}")
    result = compare_triad(
        Path(str(record["reference_path"])),
        Path(str(record["parent_path"])),
        Path(str(record["candidate_path"])),
        str(record["scenario"]),
        str(record["vehicle_id"]),
    )
    result["reference_id"] = str(record["reference_id"])
    result["candidate_id"] = str(record["candidate_id"])
    result["hard_gates_pass"] = bool(record.get("hard_gates_pass", True))
    return result


__all__ = ["StageUComparatorError", "compare_reference_parent_candidate", "compare_triad"]
