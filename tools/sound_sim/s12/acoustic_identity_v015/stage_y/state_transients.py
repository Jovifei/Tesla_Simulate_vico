"""State-machine transients: tip-in hysteresis, shift one-shot, BOV."""
from __future__ import annotations

import numpy as np


class StateTransientMixer:
    def __init__(self, sample_rate_hz: int = 48000) -> None:
        self.sample_rate_hz = int(sample_rate_hz)
        self._tip_in = False
        self._last_throttle = 0.18
        self._last_rpm = 850.0
        self._last_boost = 0.0
        self._shift_count = 0
        self._tip_in_count = 0
        self._bov_count = 0

    def equal_power_crossfade(self, a, b, mix: float) -> np.ndarray:
        mix = float(np.clip(mix, 0.0, 1.0))
        gain_a = np.cos(mix * np.pi / 2.0)
        gain_b = np.sin(mix * np.pi / 2.0)
        return gain_a * a + gain_b * b

    def render_block(
        self,
        n: int,
        throttle: float,
        rpm: float,
        boost: float,
        dt: float,
    ) -> tuple[np.ndarray, dict[str, int]]:
        residual = np.zeros((n, 2), dtype=np.float64)
        d_throttle = (float(throttle) - self._last_throttle) / max(dt, 1.0 / self.sample_rate_hz)
        d_rpm = (float(rpm) - self._last_rpm) / max(dt, 1.0 / self.sample_rate_hz)
        if d_throttle > 0.4:
            self._tip_in = True
        elif d_throttle < 0.1:
            self._tip_in = False
        if self._tip_in:
            self._tip_in_count += 1
            t = np.arange(n, dtype=np.float64) / self.sample_rate_hz
            burst = 0.08 * np.hanning(n) * np.sin(2.0 * np.pi * 180.0 * t)
            residual[:, 0] += burst
            residual[:, 1] += 0.85 * burst
        rpm_drop = self._last_rpm - float(rpm)
        if rpm_drop > 800.0 and dt < 0.080:
            self._shift_count += 1
            t = np.arange(n, dtype=np.float64) / self.sample_rate_hz
            burst = 0.12 * np.hanning(n) * np.sin(2.0 * np.pi * 90.0 * t)
            residual[:, 0] += burst * 0.82
            residual[:, 1] += burst * 0.66
        if float(boost) < self._last_boost - 0.05 and float(throttle) < 0.2:
            self._bov_count += 1
            t = np.arange(n, dtype=np.float64) / self.sample_rate_hz
            burst = 0.06 * np.hanning(n) * np.sin(2.0 * np.pi * 420.0 * t)
            residual += np.column_stack((burst, 0.90 * burst))
        self._last_throttle = float(throttle)
        self._last_rpm = float(rpm)
        self._last_boost = float(boost)
        return residual, {
            "transient_shift_count": self._shift_count,
            "transient_tip_in_count": self._tip_in_count,
            "transient_bov_count": self._bov_count,
        }
