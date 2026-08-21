"""Transparent proxy metrics; optional MoSQITo adapters may enrich these later."""
from __future__ import annotations

import numpy as np


def proxy_metrics(signal: np.ndarray, sample_rate_hz: int, centroid_hz: float) -> dict[str, float | str]:
    envelope = np.abs(signal)
    window = max(1, sample_rate_hz // 20)
    smoothed = np.convolve(envelope, np.ones(window) / window, mode="same")
    roughness = float(np.sqrt(np.mean(np.diff(envelope) ** 2)))
    fluctuation = float(np.std(smoothed))
    crest = float(np.max(envelope) / max(np.sqrt(np.mean(signal * signal)), 1e-12))
    return {
        "domain": "digital_domain_relative_only_not_absolute_SPL",
        "loudness_proxy_db": 20.0 * float(np.log10(max(np.sqrt(np.mean(signal * signal)), 1e-12))),
        "sharpness_proxy_hz": centroid_hz,
        "roughness_proxy": roughness,
        "fluctuation_proxy": fluctuation,
        "crest_factor": crest,
        "tonality_proxy": float(1.0 / max(roughness + fluctuation, 1e-12)),
    }
