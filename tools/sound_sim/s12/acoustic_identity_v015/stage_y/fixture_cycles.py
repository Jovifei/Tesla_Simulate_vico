"""Deterministic synthetic Hellcat cycle bank for Stage Y fixture maps."""
from __future__ import annotations

import numpy as np

from ..event_domain.config_schema import load_config
from ..event_domain.event_scheduler import cycle_degrees, derive_event_phase_deg

_FIXTURE_RPMS = (1200.0, 2000.0, 3000.0, 4500.0)
_RNG_SEED = 20260830


def synthesize_hellcat_cycle_bank(sample_rate_hz: int = 48000) -> dict:
    """Build one stereo engine cycle per RPM from Hellcat firing order."""
    sample_rate_hz = int(sample_rate_hz)
    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be positive")
    config = load_config("hellcat_v1")
    cycle_deg = float(cycle_degrees(config))
    phases_deg = np.asarray(derive_event_phase_deg(config), dtype=np.float64)
    rng = np.random.default_rng(_RNG_SEED)
    cycles: dict[float, np.ndarray] = {}
    rpm_hz: dict[float, float] = {}
    half = max(int(0.002 * sample_rate_hz), 4)
    window = np.hanning(2 * half)
    for rpm in _FIXTURE_RPMS:
        duration_s = (cycle_deg / 360.0) / max(float(rpm) / 60.0, 1.0e-9)
        count = max(int(round(sample_rate_hz * duration_s)), 16)
        mono = np.zeros(count, dtype=np.float64)
        for entity_phase in phases_deg:
            fraction = (float(entity_phase) % cycle_deg) / cycle_deg
            center = int(round(fraction * (count - 1)))
            start = center - half
            for offset, weight in enumerate(window):
                mono[(start + offset) % count] += float(weight)
        peak = float(np.max(np.abs(mono)))
        if peak > 0.0:
            mono *= 0.35 / peak
        mono += rng.standard_normal(count) * 0.015
        cycles[float(rpm)] = np.column_stack((mono, 0.92 * mono))
        rpm_hz[float(rpm)] = float(rpm) / 60.0
    return {"rpm_hz": rpm_hz, "cycles": cycles, "sample_rate_hz": sample_rate_hz}
