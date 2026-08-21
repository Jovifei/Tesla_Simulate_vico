"""Bounded alignment; dynamic time warping is intentionally opt-in and tiny."""
from __future__ import annotations

import numpy as np


def bounded_cross_correlation(reference: np.ndarray, candidate: np.ndarray, max_shift_samples: int = 4096) -> tuple[np.ndarray, int]:
    """Align candidate to reference with a fixed bounded lag search."""

    n = min(reference.size, candidate.size)
    if n < 8:
        raise ValueError("alignment needs at least eight samples")
    probe = min(n, 8192)
    limit = min(max_shift_samples, probe - 1)
    r = reference[:probe]
    c = candidate[:probe]
    corr = np.correlate(r, c, "full")
    lags = np.arange(-probe + 1, probe)
    allowed = (lags >= -limit) & (lags <= limit)
    shift = int(lags[allowed][np.argmax(corr[allowed])])
    return np.roll(candidate[:n], shift), shift


def bounded_dtw_alignment(reference: np.ndarray, candidate: np.ndarray, *, max_samples: int = 512, band_samples: int = 24) -> dict[str, object]:
    """Report a constrained DTW route for short excerpts only.

    Full-cycle or long-form audio is refused instead of silently warping the
    evidence.  The current comparator uses cross correlation by default; this
    helper makes the policy executable for callers that provide short excerpts.
    """

    if reference.size > max_samples or candidate.size > max_samples:
        raise ValueError("DTW is allowed only for explicitly short excerpts")
    if band_samples < 0:
        raise ValueError("DTW band must be non-negative")
    # The path is intentionally not used to resample audio: it is provenance
    # information for a caller that has separately approved a short-excerpt use.
    return {"allowed": True, "max_samples": max_samples, "band_samples": band_samples, "applied": False}
