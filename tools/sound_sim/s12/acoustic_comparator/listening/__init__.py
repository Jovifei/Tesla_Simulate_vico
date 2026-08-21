"""Audition-only helpers and external listening-test adapters."""
from __future__ import annotations

import numpy as np


def loudness_matched_audition(signal: np.ndarray, target_rms_db: float = -23.0) -> tuple[np.ndarray, dict[str, float | str]]:
    """Create a presentation copy; callers must not route it into analysis."""

    value = np.asarray(signal, dtype=np.float64)
    rms = max(float(np.sqrt(np.mean(value * value))), 1e-12)
    gain = min(1.0 / max(float(np.max(np.abs(value))), 1e-12), 10.0 ** (target_rms_db / 20.0) / rms)
    return value * gain, {
        "domain": "loudness_matched_audition_signal",
        "target_rms_db": target_rms_db,
        "applied_gain": gain,
    }


__all__ = ("loudness_matched_audition",)
