"""Spectrum and tonal-balance metrics with an explicit upper-band warning."""
from __future__ import annotations

import math
import numpy as np

BANDS = ((20.0, 60.0), (60.0, 120.0), (120.0, 250.0), (250.0, 400.0), (400.0, 1000.0), (1000.0, 4000.0), (4000.0, 5500.0), (5500.0, 12000.0))
BAND_NAMES = ("20_60", "60_120", "120_250", "250_400", "400_1000", "1000_4000", "4000_5500", "5500_12000")
UPPER_BAND_WARNING = "upstream perceptual compensation; outside validated radiation band; not physical radiation validation"


def spectrum_features(signal: np.ndarray, sample_rate_hz: int) -> tuple[dict[str, float], np.ndarray, np.ndarray]:
    spec = np.abs(np.fft.rfft(signal)) ** 2
    freq = np.fft.rfftfreq(signal.size, 1.0 / sample_rate_hz)
    total = max(float(spec.sum()), 1e-18)
    bands = {name: float(spec[(freq >= low) & (freq < high)].sum() / total) for name, (low, high) in zip(BAND_NAMES, BANDS)}
    centroid = float((freq * spec).sum() / total)
    rolloff = float(freq[min(len(freq) - 1, int(np.searchsorted(np.cumsum(spec), 0.85 * total)))])
    geometric = math.exp(float(np.log(spec + 1e-18).mean()))
    contrast = 10.0 * math.log10(max(float(np.quantile(spec, 0.9)), 1e-18) / max(float(np.quantile(spec, 0.1)), 1e-18))
    thirds = np.array_split(spec, 3)
    tristimulus = [float(part.sum() / total) for part in thirds]
    features = {
        "rms_db": 20.0 * math.log10(max(float(np.sqrt(np.mean(signal * signal))), 1e-12)),
        "centroid_hz": centroid,
        "rolloff_hz": rolloff,
        "spectral_flatness": float(geometric / max(float(spec.mean()), 1e-18)),
        "spectral_contrast_db": contrast,
        "tristimulus_low": tristimulus[0],
        "tristimulus_mid": tristimulus[1],
        "tristimulus_high": tristimulus[2],
        **bands,
    }
    return features, spec, freq


def band_comparison(reference: dict[str, float], candidate: dict[str, float]) -> dict[str, dict[str, float | str | None]]:
    return {
        name: {
            "reference_share": reference[name],
            "candidate_share": candidate[name],
            "delta": candidate[name] - reference[name],
            "warning": UPPER_BAND_WARNING if name == "5500_12000" else None,
        }
        for name in BAND_NAMES
    }


def normalized_log_spectral_distance(reference_spectrum: np.ndarray, candidate_spectrum: np.ndarray) -> float:
    norm = lambda value: value / max(float(np.linalg.norm(value)), 1e-18)
    return float(np.linalg.norm(norm(np.log1p(reference_spectrum)) - norm(np.log1p(candidate_spectrum))))
