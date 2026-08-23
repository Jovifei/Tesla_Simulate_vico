"""Stage U raw-feature contracts, constrained DTW and optional research metric metadata."""
from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np
from scipy.signal import hilbert


class FeatureContractError(ValueError):
    """Raised when a feature or DTW comparison violates Stage U scope."""


def _signal(signal: np.ndarray, sample_rate_hz: int) -> np.ndarray:
    values = np.asarray(signal, dtype=np.float64).reshape(-1)
    if values.size < max(8, int(sample_rate_hz * 0.25)) or sample_rate_hz <= 0 or not np.isfinite(values).all():
        raise FeatureContractError("feature input must be finite mono audio of at least 0.25 seconds")
    return values


def extract_raw_feature_summary(signal: np.ndarray, sample_rate_hz: int) -> dict[str, float]:
    """Compute gain-aware loudness plus gain-invariant spectral/modulation descriptors."""

    values = _signal(signal, sample_rate_hz)
    spectrum = np.square(np.abs(np.fft.rfft(values * np.hanning(values.size))))
    frequencies = np.fft.rfftfreq(values.size, 1.0 / sample_rate_hz)
    total = float(np.sum(spectrum))
    if total <= 1e-30:
        raise FeatureContractError("feature input has no spectral energy")
    centroid = float(np.sum(frequencies * spectrum) / total)
    brightness = float(np.sum(spectrum[frequencies >= 2000.0]) / total)
    normalized = spectrum / total
    entropy = float(-np.sum(normalized[normalized > 0.0] * np.log(normalized[normalized > 0.0])))
    geometric = float(np.exp(np.mean(np.log(np.maximum(spectrum, 1e-30)))))
    flatness = float(geometric / max(float(np.mean(spectrum)), 1e-30))
    envelope = np.abs(hilbert(values))
    envelope -= float(np.mean(envelope))
    modulation = np.square(np.abs(np.fft.rfft(envelope * np.hanning(envelope.size))))
    modulation_frequencies = np.fft.rfftfreq(envelope.size, 1.0 / sample_rate_hz)
    band = (modulation_frequencies >= 65.0) & (modulation_frequencies <= 75.0)
    roughness_70 = float(np.sum(modulation[band]) / max(float(np.sum(modulation[modulation_frequencies >= 1.0])), 1e-30))
    rms = float(np.sqrt(np.mean(np.square(values))))
    return {
        "rms_dbfs": 20.0 * math.log10(max(rms, 1e-30)),
        "spectral_centroid_hz": centroid,
        "brightness_proxy": brightness,
        "spectral_entropy": entropy,
        "spectral_flatness": flatness,
        "roughness_70hz_proxy": roughness_70,
    }


def _context(context: Mapping[str, Any], label: str) -> tuple[str, tuple[float, float]]:
    scenario = str(context.get("scenario") or "")
    window = context.get("rpm_window")
    if not scenario or not isinstance(window, (list, tuple)) or len(window) != 2:
        raise FeatureContractError(f"{label} context requires scenario and rpm_window")
    low, high = float(window[0]), float(window[1])
    if not np.isfinite((low, high)).all() or low >= high:
        raise FeatureContractError(f"{label} rpm_window is invalid")
    return scenario, (low, high)


def bounded_dtw(
    reference_features: np.ndarray,
    candidate_features: np.ndarray,
    reference_context: Mapping[str, Any],
    candidate_context: Mapping[str, Any],
    *,
    band_ratio: float = 0.20,
) -> dict[str, Any]:
    """Return constrained DTW only for the same scenario with overlapping RPM state."""

    reference = np.asarray(reference_features, dtype=np.float64)
    candidate = np.asarray(candidate_features, dtype=np.float64)
    if reference.ndim != 2 or candidate.ndim != 2 or reference.shape[1] != candidate.shape[1] or reference.size == 0 or candidate.size == 0 or not np.isfinite(reference).all() or not np.isfinite(candidate).all():
        raise FeatureContractError("DTW features must be finite non-empty matrices with matching columns")
    ref_scenario, ref_rpm = _context(reference_context, "reference")
    cand_scenario, cand_rpm = _context(candidate_context, "candidate")
    if ref_scenario != cand_scenario:
        raise FeatureContractError("DTW scenario mismatch")
    if max(ref_rpm[0], cand_rpm[0]) >= min(ref_rpm[1], cand_rpm[1]):
        raise FeatureContractError("DTW RPM windows do not overlap")
    if not 0.0 < band_ratio <= 1.0:
        raise FeatureContractError("DTW band_ratio must be in (0, 1]")
    rows, columns = reference.shape[0], candidate.shape[0]
    max_warp = max(1, int(math.ceil(max(rows, columns) * band_ratio)))
    costs = np.full((rows + 1, columns + 1), np.inf)
    lengths = np.zeros((rows + 1, columns + 1), dtype=np.int64)
    costs[0, 0] = 0.0
    for row in range(1, rows + 1):
        lower = max(1, row - max_warp)
        upper = min(columns, row + max_warp)
        for column in range(lower, upper + 1):
            previous = ((costs[row - 1, column], lengths[row - 1, column]), (costs[row, column - 1], lengths[row, column - 1]), (costs[row - 1, column - 1], lengths[row - 1, column - 1]))
            minimum_cost, minimum_length = min(previous, key=lambda item: item[0])
            if not np.isfinite(minimum_cost):
                continue
            costs[row, column] = minimum_cost + float(np.linalg.norm(reference[row - 1] - candidate[column - 1]))
            lengths[row, column] = minimum_length + 1
    if not np.isfinite(costs[rows, columns]) or lengths[rows, columns] == 0:
        raise FeatureContractError("DTW failed within the declared warp bound")
    return {
        "status": "BOUNDED_DTW_PASS",
        "scenario": ref_scenario,
        "rpm_overlap": [max(ref_rpm[0], cand_rpm[0]), min(ref_rpm[1], cand_rpm[1])],
        "max_warp_frames": max_warp,
        "path_length": int(lengths[rows, columns]),
        "distance": float(costs[rows, columns] / lengths[rows, columns]),
    }


def openl3_capability(error: str | None = None) -> dict[str, Any]:
    """Make OpenL3's optional/project-unmaintained status machine-readable."""

    available = error is None
    return {
        "name": "OpenL3",
        "classification": "OPTIONAL_RESEARCH_METRIC",
        "project_status": "PROJECT_UNMAINTAINED",
        "hard_gate": False,
        "status": "OPTIONAL_RESEARCH_METRIC_AVAILABLE" if available else "PROJECT_UNMAINTAINED_NOT_AVAILABLE",
        "reason": error,
    }


def select_common_audio_feature_columns(features: np.ndarray, feature_info: Mapping[str, Any]) -> tuple[np.ndarray, list[int]]:
    """Keep only fixed-length MATLAB descriptors for cross-sample-rate DTW.

    Bark/ERB spectrum bin counts legitimately vary with sample rate.  MFCC,
    GTCC and the scalar descriptors have stable dimensions and are therefore
    the only audioFeatureExtractor columns admitted to cross-rate DTW.
    """

    values = np.asarray(features, dtype=np.float64)
    if values.ndim != 2 or not np.isfinite(values).all():
        raise FeatureContractError("MATLAB feature matrix must be finite and two-dimensional")
    columns: list[int] = []
    for name in ("mfcc", "gtcc", "spectralFlux", "spectralFlatness", "spectralEntropy", "pitch", "harmonicRatio", "shortTimeEnergy"):
        item = feature_info.get(name)
        if isinstance(item, list):
            columns.extend(int(index) for index in item)
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            columns.append(int(item))
    if not columns or any(index < 1 or index > values.shape[1] for index in columns):
        raise FeatureContractError("MATLAB feature_info does not expose fixed cross-rate columns")
    return values[:, np.asarray(columns, dtype=int) - 1], columns


__all__ = ["FeatureContractError", "bounded_dtw", "extract_raw_feature_summary", "openl3_capability", "select_common_audio_feature_columns"]
