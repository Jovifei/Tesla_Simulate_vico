"""SHA-bound MATLAB audioFeatureExtractor triad distances for Stage U.

The MATLAB feature layout legitimately changes Bark/ERB bin counts at a
different sample rate.  This module therefore compares only the fixed-length
MFCC, GTCC and scalar descriptors, while retaining the complete MATLAB receipt
as provenance outside Git.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from tools.sound_sim.s12.real_reference.stage_u_features import bounded_dtw
from tools.sound_sim.s12.real_reference.stage_u_grid import _trace


_FIXED_FAMILIES = ("mfcc", "gtcc", "spectralEntropy", "spectralFlatness", "spectralFlux", "pitch", "harmonicRatio", "shortTimeEnergy")
_EXCLUDED_FAMILIES = ["barkSpectrum", "erbSpectrum"]


def _fixed_columns(receipt: Mapping[str, Any]) -> tuple[np.ndarray, list[str]]:
    values = np.asarray(receipt.get("features"), dtype=np.float64)
    info = receipt.get("feature_info")
    if values.ndim != 2 or values.size == 0 or not np.isfinite(values).all() or not isinstance(info, Mapping):
        raise ValueError("audio feature receipt requires finite non-empty features and feature_info")
    columns: list[int] = []
    labels: list[str] = []
    for family in _FIXED_FAMILIES:
        declared = info.get(family)
        if declared is None:
            continue
        entries = declared if isinstance(declared, list) else [declared]
        if not entries or any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in entries):
            raise ValueError("audio feature receipt lacks common fixed-dimension descriptors")
        for ordinal, value in enumerate(entries, start=1):
            index = int(value)
            if index < 1 or index > values.shape[1]:
                raise ValueError("audio feature receipt has an invalid fixed-dimension descriptor index")
            columns.append(index - 1)
            labels.append(f"{family}:{ordinal}")
    if not columns:
        raise ValueError("audio feature receipt lacks common fixed-dimension descriptors")
    return values[:, columns], labels


def _downsample(values: np.ndarray, maximum_frames: int) -> np.ndarray:
    if maximum_frames < 2:
        raise ValueError("maximum_frames must be at least two")
    if values.shape[0] <= maximum_frames:
        return values
    indices = np.linspace(0, values.shape[0] - 1, maximum_frames).round().astype(int)
    return values[indices]


def _reference_normalize(reference: np.ndarray, values: np.ndarray) -> np.ndarray:
    center = np.median(reference, axis=0)
    scale = np.std(reference, axis=0)
    scale = np.where(scale > 1e-9, scale, np.maximum(np.abs(center), 1.0))
    return (values - center) / scale


def compare_audio_feature_triad(
    reference_receipt: Mapping[str, Any],
    parent_receipt: Mapping[str, Any],
    candidate_receipt: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    maximum_frames: int = 360,
) -> dict[str, Any]:
    """Compute bounded reference/parent/candidate DTW from raw MATLAB frames.

    ``context`` is an inferred matching-trace scenario/RPM window, not an R1
    measured state trace.  All three clips use that same declared context.
    """

    reference, labels = _fixed_columns(reference_receipt)
    parent, parent_labels = _fixed_columns(parent_receipt)
    candidate, candidate_labels = _fixed_columns(candidate_receipt)
    if labels != parent_labels or labels != candidate_labels:
        raise ValueError("audio feature receipts have no common fixed-dimension descriptor schema")
    reference = _downsample(reference, maximum_frames)
    parent = _downsample(parent, maximum_frames)
    candidate = _downsample(candidate, maximum_frames)
    normalized_reference = _reference_normalize(reference, reference)
    normalized_parent = _reference_normalize(reference, parent)
    normalized_candidate = _reference_normalize(reference, candidate)
    parent_dtw = bounded_dtw(normalized_reference, normalized_parent, context, context)
    candidate_dtw = bounded_dtw(normalized_reference, normalized_candidate, context, context)
    pair_dtw = bounded_dtw(normalized_parent, normalized_candidate, context, context)
    parent_distance = float(parent_dtw["distance"])
    candidate_distance = float(candidate_dtw["distance"])
    return {
        "status": "AUDIO_FEATURE_TRIAD_COMPLETE",
        "tool": "MATLAB audioFeatureExtractor",
        "analysis_signal": "raw SHA-bound digital-domain clips; not loudness-matched audition copies",
        "classification": "PROFESSIONAL_ANALYSIS_NOT_R1_ORDER_GATE",
        "selected_feature_count": len(labels),
        "selected_feature_families": list(_FIXED_FAMILIES),
        "excluded_feature_families": list(_EXCLUDED_FAMILIES),
        "frame_cap": maximum_frames,
        "parent_distance": parent_distance,
        "candidate_distance": candidate_distance,
        "parent_candidate_distance": float(pair_dtw["distance"]),
        "absolute_improvement": parent_distance - candidate_distance,
        "relative_improvement": (parent_distance - candidate_distance) / max(parent_distance, 1e-12),
        "dtw": {"reference_parent": parent_dtw, "reference_candidate": candidate_dtw, "parent_candidate": pair_dtw},
        "input_sha256": {
            "reference": str(reference_receipt.get("input_sha256") or ""),
            "parent": str(parent_receipt.get("input_sha256") or ""),
            "candidate": str(candidate_receipt.get("input_sha256") or ""),
        },
    }


def _read_receipt(path: str) -> Mapping[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _receipt_input_sha256(receipt: Mapping[str, Any]) -> str:
    embedded = str(receipt.get("input_sha256") or "")
    if embedded:
        return embedded
    input_path = Path(str(receipt.get("input_path") or ""))
    if not input_path.is_file():
        raise ValueError("audio feature receipt lacks input SHA and readable input_path")
    digest = hashlib.sha256()
    with input_path.open("rb") as handle:
        for block in iter(lambda: handle.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def _state_context(vehicle_id: str, scenario: str) -> dict[str, Any]:
    trace = _trace(vehicle_id, scenario, 15.0)
    lower, upper = float(np.min(trace.rpm)), float(np.max(trace.rpm))
    policy = "MATCHING_TRACE_RANGE"
    if lower == upper:
        tolerance = max(25.0, 0.01 * lower)
        lower, upper = lower - tolerance, upper + tolerance
        policy = "CONSTANT_RPM_PLUS_MINUS_25_OR_ONE_PERCENT"
    return {
        "scenario": scenario,
        "rpm_window": [lower, upper],
        "source": "INFERRED_MATCHING_RENDER_TRACE_NOT_R1",
        "rpm_window_policy": policy,
    }


def compare_audio_feature_batch(
    legacy_results: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    batch_receipt: Mapping[str, Any],
    *,
    receipt_loader: Callable[[str], Mapping[str, Any]] = _read_receipt,
) -> dict[str, Any]:
    """Compare every Stage-U candidate triad and fail closed on any SHA gap."""

    manifest_rows = {str(row.get("clip_id")): row for row in manifest.get("clips", []) if isinstance(row, Mapping)}
    batch_rows = {str(row.get("clip_id")): row for row in batch_receipt.get("results", []) if isinstance(row, Mapping)}
    results: list[dict[str, Any]] = []
    for legacy in legacy_results:
        reference_id = str(legacy.get("reference_id") or "")
        candidate_id = str(legacy.get("candidate_id") or "")
        clip_ids = {
            "reference": f"reference::{reference_id}",
            "parent": f"parent::{reference_id}",
            "candidate": f"candidate::{reference_id}::{candidate_id}",
        }
        if not reference_id or not candidate_id or any(clip_id not in manifest_rows or clip_id not in batch_rows for clip_id in clip_ids.values()):
            raise ValueError("audio feature batch lacks a complete reference/parent/candidate triad")
        expected = {role: str(manifest_rows[clip_id].get("sha256") or "") for role, clip_id in clip_ids.items()}
        batch_sha = {role: str(batch_rows[clip_id].get("input_sha256") or "") for role, clip_id in clip_ids.items()}
        if not all(len(value) > 0 and expected[role] == value for role, value in batch_sha.items()):
            raise ValueError("audio feature batch manifest SHA binding failed")
        source_rows = {role: receipt_loader(str(batch_rows[clip_id]["feature_receipt_path"])) for role, clip_id in clip_ids.items()}
        loaded_sha = {role: _receipt_input_sha256(row) for role, row in source_rows.items()}
        if loaded_sha != expected:
            raise ValueError("audio feature receipt SHA binding failed")
        reference_row = manifest_rows[clip_ids["reference"]]
        vehicle_id = str(reference_row.get("vehicle_id") or legacy.get("vehicle_id") or "")
        scenario = str(reference_row.get("scenario") or "")
        if not vehicle_id or not scenario:
            raise ValueError("audio feature batch requires vehicle and scenario for matching-trace context")
        context = _state_context(vehicle_id, scenario)
        triad = compare_audio_feature_triad(source_rows["reference"], source_rows["parent"], source_rows["candidate"], context)
        triad.update({
            "reference_id": reference_id,
            "candidate_id": candidate_id,
            "vehicle_id": vehicle_id,
            "scenario": scenario,
            "professional_bound": True,
            "hard_gates_pass": bool(legacy.get("hard_gates_pass")),
            "state_context": context,
            "sha_binding": expected,
        })
        results.append(triad)
    return {
        "schema_version": "s12-stage-u-audio-feature-dtw-v1",
        "status": "AUDIO_FEATURE_BATCH_COMPLETE",
        "record_count": len(results),
        "results": results,
        "analysis_signal": "raw SHA-bound digital-domain clips; loudness-matched audition copies are separate",
        "classification": "PROFESSIONAL_ANALYSIS_NOT_R1_ORDER_GATE",
        "order_status": "ORDER_COMPARISON_NOT_QUALIFIED",
        "automatic_tuning_eligible": False,
    }


__all__ = ["compare_audio_feature_batch", "compare_audio_feature_triad"]
