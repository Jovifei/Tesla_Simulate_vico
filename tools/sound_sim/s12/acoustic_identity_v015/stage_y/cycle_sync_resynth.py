"""Cycle-synchronous fixture grain resampler for Hellcat P4."""
from __future__ import annotations

import numpy as np


class CycleSyncResampler:
    def __init__(self, bank: dict, sample_rate_hz: int = 48000) -> None:
        self.sample_rate_hz = int(sample_rate_hz)
        self.rpms = np.array(sorted(bank["cycles"].keys()), dtype=np.float64)
        self.cycles = [np.asarray(bank["cycles"][float(rpm)], dtype=np.float64) for rpm in self.rpms]

    def render(self, phase: np.ndarray, rpm: np.ndarray) -> np.ndarray:
        phase = np.asarray(phase, dtype=np.float64)
        rpm = np.asarray(rpm, dtype=np.float64)
        lo = np.searchsorted(self.rpms, rpm, side="right") - 1
        lo = np.clip(lo, 0, self.rpms.size - 1)
        hi = np.clip(lo + 1, 0, self.rpms.size - 1)
        span = np.maximum(self.rpms[hi] - self.rpms[lo], 1e-9)
        mix = np.where(lo == hi, 0.0, np.clip((rpm - self.rpms[lo]) / span, 0.0, 1.0))
        gain_lo = np.cos(mix * np.pi / 2.0)
        gain_hi = np.sin(mix * np.pi / 2.0)
        sample_lo = self._sample_indexed(lo, phase)
        sample_hi = self._sample_indexed(hi, phase)
        return gain_lo[:, None] * sample_lo + gain_hi[:, None] * sample_hi

    def _sample_indexed(self, cycle_indices: np.ndarray, phase: np.ndarray) -> np.ndarray:
        out = np.zeros((phase.size, 2), dtype=np.float64)
        for table_index, cycle in enumerate(self.cycles):
            mask = cycle_indices == table_index
            if np.any(mask):
                out[mask] = self._sample(cycle, phase[mask])
        return out

    def _sample(self, cycle: np.ndarray, phase_rad: np.ndarray) -> np.ndarray:
        n = cycle.shape[0]
        # The fixture spans one four-stroke engine cycle: 720 crank degrees.
        # `phase_rad` comes directly from the production PLL's absolute crank
        # clock, so 2π addresses its second revolution rather than a reset.
        position = (np.asarray(phase_rad, dtype=np.float64) / (4.0 * np.pi)) * n
        wrapped = np.mod(position, n)
        left = np.floor(wrapped).astype(np.int64) % n
        right = (left + 1) % n
        fraction = (wrapped - np.floor(wrapped))[:, None]
        return (1.0 - fraction) * cycle[left] + fraction * cycle[right]
