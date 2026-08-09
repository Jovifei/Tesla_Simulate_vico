"""Deterministic 48 kHz K-weighted bundle loudness management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np


_K_SHELF_B = (1.53512485958697, -2.69169618940638, 1.19839281085285)
_K_SHELF_A = (1.0, -1.69065929318241, 0.73248077421585)
_K_HIGH_PASS_B = (1.0, -2.0, 1.0)
_K_HIGH_PASS_A = (1.0, -1.99004745483398, 0.99007225036621)
_LUFS_OFFSET = -0.691


@dataclass(frozen=True)
class LoudnessMetrics:
    """Measured 48 kHz loudness and sample-health values."""

    integrated_lufs: float
    rms_dbfs: float
    peak_dbfs: float
    crest_factor_db: float
    clipping_count: int


@dataclass(frozen=True)
class LoudnessManagedBundle:
    """A vehicle bundle managed with exactly one common gain."""

    segments: Mapping[str, np.ndarray]
    gain_db: float
    gain_linear: float
    headroom_limited: bool
    input_bundle_metrics: LoudnessMetrics
    bundle_metrics: LoudnessMetrics
    segment_metrics: Mapping[str, LoudnessMetrics]


def measure_loudness(audio: np.ndarray, sample_rate_hz: int = 48000) -> LoudnessMetrics:
    """Measure deterministic K-weighted gated integrated loudness at 48 kHz."""
    samples = _validate_audio(audio, sample_rate_hz)
    weighted = _biquad(_biquad(samples, _K_SHELF_B, _K_SHELF_A), _K_HIGH_PASS_B, _K_HIGH_PASS_A)
    integrated_lufs = _integrated_lufs(weighted, sample_rate_hz)
    rms = float(np.sqrt(np.mean(np.square(samples))))
    peak = float(np.max(np.abs(samples)))
    rms_dbfs = _dbfs(rms)
    peak_dbfs = _dbfs(peak)
    return LoudnessMetrics(
        integrated_lufs=integrated_lufs,
        rms_dbfs=rms_dbfs,
        peak_dbfs=peak_dbfs,
        crest_factor_db=peak_dbfs - rms_dbfs if rms else float("inf"),
        clipping_count=int(np.count_nonzero(np.abs(samples) >= 1.0)),
    )


def manage_bundle_loudness(
    segments: Mapping[str, np.ndarray],
    sample_rate_hz: int = 48000,
    target_lufs: float = -18.0,
    peak_limit_dbfs: float = -1.0,
) -> LoudnessManagedBundle:
    """Apply one deterministic gain to every supplied vehicle-state segment."""
    if not segments:
        raise ValueError("segments must not be empty")
    if not np.isfinite(target_lufs) or not np.isfinite(peak_limit_dbfs) or peak_limit_dbfs > 0.0:
        raise ValueError("target_lufs and peak_limit_dbfs must be finite; peak_limit_dbfs must be <= 0")
    validated = {name: _validate_named_audio(name, audio, sample_rate_hz) for name, audio in segments.items()}
    input_bundle_metrics = measure_loudness(np.concatenate(tuple(validated.values()), axis=0), sample_rate_hz)
    input_peak = max(float(np.max(np.abs(audio))) for audio in validated.values())
    target_gain_db = target_lufs - input_bundle_metrics.integrated_lufs if np.isfinite(input_bundle_metrics.integrated_lufs) else 0.0
    peak_gain_db = peak_limit_dbfs - _dbfs(input_peak) if input_peak else float("inf")
    gain_db = min(target_gain_db, peak_gain_db)
    gain_linear = float(10.0 ** (gain_db / 20.0))
    managed = {name: audio * gain_linear for name, audio in validated.items()}
    output_bundle = np.concatenate(tuple(managed.values()), axis=0)
    return LoudnessManagedBundle(
        segments=managed,
        gain_db=float(gain_db),
        gain_linear=gain_linear,
        headroom_limited=bool(target_gain_db > peak_gain_db),
        input_bundle_metrics=input_bundle_metrics,
        bundle_metrics=measure_loudness(output_bundle, sample_rate_hz),
        segment_metrics={name: measure_loudness(audio, sample_rate_hz) for name, audio in managed.items()},
    )


def _validate_named_audio(name: str, audio: np.ndarray, sample_rate_hz: int) -> np.ndarray:
    if not isinstance(name, str) or not name:
        raise ValueError("segments must use non-empty string names")
    return _validate_audio(audio, sample_rate_hz)


def _validate_audio(audio: np.ndarray, sample_rate_hz: int) -> np.ndarray:
    if sample_rate_hz != 48000:
        raise ValueError("sample_rate_hz must be 48000 for the K-weighted estimate")
    samples = np.asarray(audio, dtype=np.float64)
    if samples.ndim == 1:
        samples = samples[:, np.newaxis]
    if samples.ndim != 2 or samples.shape[0] == 0 or samples.shape[1] == 0:
        raise ValueError("audio must have non-empty shape [N] or [N, channels]")
    if not np.all(np.isfinite(samples)):
        raise ValueError("audio must be finite")
    return samples


def _biquad(samples: np.ndarray, numerator: tuple[float, float, float], denominator: tuple[float, float, float]) -> np.ndarray:
    output = np.zeros_like(samples)
    x1 = np.zeros(samples.shape[1], dtype=np.float64)
    x2 = np.zeros(samples.shape[1], dtype=np.float64)
    y1 = np.zeros(samples.shape[1], dtype=np.float64)
    y2 = np.zeros(samples.shape[1], dtype=np.float64)
    b0, b1, b2 = numerator
    _, a1, a2 = denominator
    for index, current in enumerate(samples):
        output[index] = b0 * current + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1 = x1, current
        y2, y1 = y1, output[index]
    return output


def _integrated_lufs(weighted: np.ndarray, sample_rate_hz: int) -> float:
    block_size = int(0.400 * sample_rate_hz)
    hop_size = int(0.100 * sample_rate_hz)
    if weighted.shape[0] < block_size:
        block_energies = np.array((float(np.sum(np.mean(np.square(weighted), axis=0))),))
    else:
        starts = range(0, weighted.shape[0] - block_size + 1, hop_size)
        block_energies = np.asarray(
            [np.sum(np.mean(np.square(weighted[start:start + block_size]), axis=0)) for start in starts]
        )
    block_lufs = np.asarray([_LUFS_OFFSET + 10.0 * np.log10(value) if value > 0.0 else -np.inf for value in block_energies])
    absolute = block_energies[block_lufs > -70.0]
    if absolute.size == 0:
        return float("-inf")
    ungated = _LUFS_OFFSET + 10.0 * np.log10(np.mean(absolute))
    relative = block_energies[block_lufs > max(-70.0, ungated - 10.0)]
    return float(_LUFS_OFFSET + 10.0 * np.log10(np.mean(relative))) if relative.size else float("-inf")


def _dbfs(value: float) -> float:
    return float(20.0 * np.log10(value)) if value > 0.0 else float("-inf")
