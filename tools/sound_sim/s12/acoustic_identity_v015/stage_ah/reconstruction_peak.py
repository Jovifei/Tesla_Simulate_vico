"""Artifact-domain multi-rate reconstructed-peak qualification.

This module never changes audio. It supplements the historical 4x diagnostic
with 4x/8x/16x evidence so a candidate cannot pass solely because one
interpolation factor happened to miss a reconstructed overshoot.

This is an engineering diagnostic, not an ITU/EBU-certified true-peak meter.
"""
from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np
from scipy import signal

RECONSTRUCTION_PEAK_SCHEMA = "s12.stage_ai.reconstruction_peak_receipt.v1"
DEFAULT_FACTORS = (4, 8, 16)
DEFAULT_THRESHOLD = 1.0


def _validate_audio(values: np.ndarray) -> np.ndarray:
    audio = np.asarray(values, dtype=np.float64)
    if audio.ndim != 2 or audio.shape[0] < 2 or audio.shape[1] not in (1, 2):
        raise ValueError("expected >=2 mono/stereo frames")
    if not np.all(np.isfinite(audio)):
        raise ValueError("reconstruction peak input must be finite")
    if float(np.max(np.abs(audio))) > 1.0 + 1e-7:
        raise ValueError("input already exceeds digital full scale")
    return audio


def _validate_factors(factors: Iterable[int]) -> tuple[int, ...]:
    result = tuple(factors)
    if not result or len(set(result)) != len(result):
        raise ValueError("factors must be a nonempty unique sequence")
    if any(isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < 2
           for value in result):
        raise ValueError("factors must contain integers >=2")
    return tuple(int(value) for value in result)


def reconstructed_peak_receipt(
    values: np.ndarray,
    *,
    sample_rate: int = 48_000,
    factors: Iterable[int] = DEFAULT_FACTORS,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, Any]:
    """Measure the final artifact-domain signal at several interpolation rates."""
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, (int, np.integer)) or sample_rate < 8_000:
        raise ValueError("invalid sample rate")
    if not math.isfinite(float(threshold)) or not 0 < float(threshold) <= 1.2:
        raise ValueError("invalid threshold")
    audio = _validate_audio(values)
    factors = _validate_factors(factors)
    threshold = float(threshold)

    rows: dict[str, dict[str, Any]] = {}
    worst_factor = None
    worst_peak = -1.0
    for factor in factors:
        reconstructed = signal.resample_poly(
            audio,
            factor,
            1,
            axis=0,
            window=("kaiser", 5.0),
            padtype="line",
        )
        absolute = np.abs(reconstructed)
        flat = int(np.argmax(absolute))
        index, channel = np.unravel_index(flat, absolute.shape)
        peak = float(absolute[index, channel])
        rows[str(factor)] = {
            "factor": factor,
            "peak": peak,
            "channel": int(channel),
            "upsampled_index": int(index),
            "time_s": float(index / (int(sample_rate) * factor)),
            "exceedance_count": int(np.count_nonzero(absolute > threshold + 1e-12)),
        }
        if peak > worst_peak:
            worst_peak = peak
            worst_factor = factor

    sample_peak = float(np.max(np.abs(audio)))
    qualified = all(row["peak"] <= threshold + 1e-12 for row in rows.values())
    return {
        "schema": RECONSTRUCTION_PEAK_SCHEMA,
        "sample_rate_hz": int(sample_rate),
        "frame_count": int(len(audio)),
        "channels": int(audio.shape[1]),
        "sample_peak": sample_peak,
        "threshold": threshold,
        "factors": rows,
        "factor_order": list(factors),
        "worst_factor": int(worst_factor),
        "worst_peak": float(worst_peak),
        "status": "PASS" if qualified else "BLOCKED_RECONSTRUCTED_PEAK",
        "method": "scipy.signal.resample_poly; kaiser beta 5; line boundary",
        "domain": "FINAL_DECODED_PCM_FLOAT",
        "standard": "ENGINEERING_DIAGNOSTIC_NOT_ITU_EBU_CERTIFIED",
        "audio_modified": False,
    }


def reconstructed_peak_ok(receipt: dict[str, Any]) -> bool:
    """Fail closed on missing factors, malformed values, or any threshold breach."""
    try:
        if receipt["schema"] != RECONSTRUCTION_PEAK_SCHEMA or receipt["status"] != "PASS":
            return False
        threshold = float(receipt["threshold"])
        order = tuple(int(value) for value in receipt["factor_order"])
        if order != DEFAULT_FACTORS or not math.isfinite(threshold) or threshold != DEFAULT_THRESHOLD:
            return False
        if set(receipt["factors"]) != {str(value) for value in DEFAULT_FACTORS}:
            return False
        for factor in DEFAULT_FACTORS:
            row = receipt["factors"][str(factor)]
            peak = float(row["peak"])
            if int(row["factor"]) != factor or not math.isfinite(peak) or peak < 0 or peak > threshold + 1e-12:
                return False
            if isinstance(row["exceedance_count"], bool) or int(row["exceedance_count"]) != 0:
                return False
        worst = float(receipt["worst_peak"])
        return math.isfinite(worst) and 0 <= worst <= threshold + 1e-12
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


__all__ = (
    "DEFAULT_FACTORS",
    "DEFAULT_THRESHOLD",
    "RECONSTRUCTION_PEAK_SCHEMA",
    "reconstructed_peak_ok",
    "reconstructed_peak_receipt",
)
