"""Analysis-only PCM preparation for the Stage-M comparator.

The helpers here deliberately have no loudness-match branch.  A presentation
copy belongs in :mod:`listening`; gate and identity calculations must use this
unaltered path only.
"""
from __future__ import annotations

import numpy as np


def to_mono_dc_free(signal: np.ndarray) -> np.ndarray:
    """Return a finite mono signal after only channel fold-down and DC removal."""

    value = np.asarray(signal, dtype=np.float64)
    if value.ndim == 2:
        value = value.mean(axis=1)
    if value.ndim != 1 or value.size < 8 or not np.isfinite(value).all():
        raise ValueError("signal must be finite mono/stereo audio with at least eight samples")
    return value - value.mean()


def linear_resample(signal: np.ndarray, input_rate_hz: int, output_rate_hz: int) -> np.ndarray:
    """Deterministically resample a signal without introducing a hidden dependency."""

    if input_rate_hz <= 0 or output_rate_hz <= 0:
        raise ValueError("sample rates must be positive")
    value = to_mono_dc_free(signal)
    if input_rate_hz == output_rate_hz:
        return value
    count = max(8, round(value.size * output_rate_hz / input_rate_hz))
    old = np.linspace(0.0, 1.0, value.size, endpoint=False)
    new = np.linspace(0.0, 1.0, count, endpoint=False)
    return np.interp(new, old, value)


def trim_window(signal: np.ndarray, start_sample: int = 0, end_sample: int | None = None) -> np.ndarray:
    """Trim only an explicitly supplied scenario window."""

    value = to_mono_dc_free(signal)
    stop = value.size if end_sample is None else end_sample
    if not (0 <= start_sample < stop <= value.size):
        raise ValueError("invalid analysis window")
    return value[start_sample:stop]
