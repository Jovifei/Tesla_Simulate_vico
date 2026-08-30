"""Clean-room DC / dP / warmup pressure chain applied before frozen PTR."""
from __future__ import annotations

import numpy as np


class PressureAudioChain:
    def __init__(self, sample_rate_hz: int, delay_samples: float) -> None:
        self.sample_rate_hz = int(sample_rate_hz)
        self.dc = 0.0
        self.prev = np.zeros(2)
        self.delay_samples = float(delay_samples)
        self.history_length = max(int(np.ceil(delay_samples)) + 1, 2)
        self.history = np.zeros((self.history_length, 2), dtype=np.float64)
        self.warm = False

    def _filter(self, block: np.ndarray) -> np.ndarray:
        x = np.asarray(block, dtype=np.float64)
        if x.ndim != 2 or x.shape[1] != 2:
            raise ValueError("PressureAudioChain expects stereo")
        self.dc = 0.995 * self.dc + 0.005 * float(np.mean(x))
        y = x - self.dc
        dp = np.diff(y, axis=0, prepend=self.prev.reshape(1, 2))
        self.prev = y[-1].copy()
        mixed = y + 0.35 * dp
        joined = np.concatenate((self.history, mixed), axis=0)
        positions = self.history_length + np.arange(mixed.shape[0], dtype=np.float64) - self.delay_samples
        left = np.floor(positions).astype(np.int64)
        fraction = (positions - left).reshape(-1, 1)
        left_clipped = np.clip(left, 0, joined.shape[0] - 1)
        right_clipped = np.clip(left + 1, 0, joined.shape[0] - 1)
        delayed = joined[left_clipped] * (1.0 - fraction) + joined[right_clipped] * fraction
        self.history = joined[-self.history_length :].copy()
        return 0.65 * mixed + 0.35 * delayed

    def warmup(self, block: np.ndarray) -> None:
        self._filter(np.asarray(block, dtype=np.float64))
        self.warm = True

    def process(self, block: np.ndarray) -> np.ndarray:
        if not self.warm:
            self.warmup(np.zeros((max(int(0.1 * self.sample_rate_hz), 1), 2), dtype=np.float64))
        return self._filter(np.asarray(block, dtype=np.float64))
