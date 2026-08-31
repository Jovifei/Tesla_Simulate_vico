"""Deterministic identity metrics for the three Stage-J source models."""

from __future__ import annotations

from typing import Mapping

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace

BANDS_HZ = ((20.0, 250.0), (250.0, 1000.0), (1000.0, 4000.0), (4000.0, 12000.0))


def compute_stage_j_perceptual_metrics(
    render: SourceRender,
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48000,
) -> dict[str, object]:
    """Measure final pre-PTR source structure without interpreting it as OEM data."""
    render.validate()
    trace.validate()
    if sample_rate_hz != 48000:
        raise ValueError("Stage-J metrics require 48 kHz")
    audio = np.asarray(render.pressure, dtype=np.float64)
    mono = np.mean(audio, axis=1)
    frequencies, power = _spectrum(mono, sample_rate_hz)
    shares = [_band_share(frequencies, power, low, high) for low, high in BANDS_HZ]
    total = float(np.sum(power))
    centroid = float(np.sum(frequencies * power) / total) if total > 0.0 else 0.0
    stems = {
        name: float(np.sum(np.square(np.asarray(stem, dtype=np.float64))))
        for name, stem in sorted(render.stems.items())
    }
    result: dict[str, object] = {
        "vehicle_id": render.diagnostics.get("vehicle_id", "unknown"),
        "band_shares": shares,
        "spectral_centroid_hz": centroid,
        "stem_energy": stems,
        "pressure_rms": float(np.sqrt(np.mean(np.square(audio)))),
        "sample_rate_hz": sample_rate_hz,
        "scope": "C/synthetic; uncalibrated; not OEM reproduction",
    }
    result["identity_features"] = _identity_features(render, trace, sample_rate_hz)
    return result


def _identity_features(render: SourceRender, trace: VehicleStateTrace, sample_rate_hz: int) -> dict[str, float]:
    features: dict[str, float] = {}
    for name, stem in render.stems.items():
        mono = np.mean(np.asarray(stem, dtype=np.float64), axis=1)
        frequencies, power = _spectrum(mono, sample_rate_hz)
        total = float(np.sum(power))
        features[f"{name}.centroid_hz"] = float(np.sum(frequencies * power) / total) if total > 0 else 0.0
        features[f"{name}.energy"] = float(np.sum(np.square(mono)))
    return features


def _spectrum(mono: np.ndarray, sample_rate_hz: int) -> tuple[np.ndarray, np.ndarray]:
    window = np.hanning(mono.size) if mono.size > 1 else np.ones_like(mono)
    spectrum = np.fft.rfft(mono * window)
    return np.fft.rfftfreq(mono.size, 1.0 / sample_rate_hz), np.square(np.abs(spectrum))


def _band_share(frequencies: np.ndarray, power: np.ndarray, low_hz: float, high_hz: float) -> float:
    band = (frequencies >= low_hz) & (frequencies < high_hz)
    total = float(np.sum(power))
    return float(np.sum(power[band]) / total) if total > 0.0 else 0.0


__all__ = ("BANDS_HZ", "compute_stage_j_perceptual_metrics")
