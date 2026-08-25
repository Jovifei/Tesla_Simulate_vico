"""Deterministic fractional delay and temperature-dependent exhaust loss."""
from __future__ import annotations
import numpy as np

def sound_speed_mps(temperature_c: float | np.ndarray) -> float | np.ndarray:
    temperature_c = np.asarray(temperature_c, dtype=np.float64)
    if np.any(temperature_c < -273.0) or not np.all(np.isfinite(temperature_c)):
        raise ValueError("temperature must be finite and above absolute zero")
    result = np.sqrt(1.40 * 287.05 * (temperature_c + 273.15))
    return float(result) if result.ndim == 0 else result

def apply_fractional_delay(signal: np.ndarray, delay_s: float, sample_rate_hz: int, attenuation: float = 1.0, temperature_c: float | None = None) -> np.ndarray:
    source = np.asarray(signal, dtype=np.float64)
    if source.ndim != 1 or not np.all(np.isfinite(source)):
        raise ValueError("path signal must be a finite vector")
    if delay_s < 0.0 or sample_rate_hz <= 0 or attenuation < 0.0:
        raise ValueError("invalid path parameters")
    positions = np.arange(source.size, dtype=np.float64) - float(delay_s) * sample_rate_hz
    delayed = np.interp(positions, np.arange(source.size, dtype=np.float64), source, left=0.0, right=0.0)
    cutoff = max(900.0, min(18000.0, 17000.0 / (1.0 + 0.65 * delay_s)))
    pole = float(np.exp(-2.0 * np.pi * cutoff / sample_rate_hz))
    filtered = np.empty_like(delayed)
    filtered[0] = delayed[0]
    for i in range(1, delayed.size):
        filtered[i] = (1.0 - pole) * delayed[i] + pole * filtered[i - 1]
    return float(attenuation) * filtered
