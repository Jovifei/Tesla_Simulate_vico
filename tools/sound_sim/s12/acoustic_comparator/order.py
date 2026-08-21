"""RPM/order compatibility and a dependency-free harmonicity proxy."""
from __future__ import annotations

import numpy as np


def rpm_compatible(reference_rpm: tuple[float, float], candidate_rpm: tuple[float, float]) -> bool:
    return all(abs(ref - actual) <= max(100.0, 0.10 * max(ref, 1.0)) for ref, actual in zip(reference_rpm, candidate_rpm))


def order_metrics(signal: np.ndarray, sample_rate_hz: int, rpm: tuple[float, float]) -> dict[str, float | bool]:
    mean_rpm = float(sum(rpm) / 2.0)
    if mean_rpm <= 0.0:
        return {"rpm_present": False, "mean_rpm": mean_rpm, "fundamental_hz": 0.0, "harmonic_energy_share": 0.0}
    fundamental = mean_rpm / 60.0
    spectrum = np.abs(np.fft.rfft(signal)) ** 2
    frequency = np.fft.rfftfreq(signal.size, 1.0 / sample_rate_hz)
    total = max(float(spectrum.sum()), 1e-18)
    energy = 0.0
    for order in range(1, 9):
        target = fundamental * order
        mask = np.abs(frequency - target) <= max(2.0, target * 0.03)
        energy += float(spectrum[mask].sum())
    return {"rpm_present": True, "mean_rpm": mean_rpm, "fundamental_hz": fundamental, "harmonic_energy_share": min(1.0, energy / total)}
