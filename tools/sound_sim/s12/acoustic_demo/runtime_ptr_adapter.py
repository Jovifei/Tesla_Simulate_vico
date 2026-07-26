"""Stateful runtime adapter for the immutable accepted PTR/radiation package.

This module preserves the existing delay/loss and Tustin recurrence exactly; it
only retains their state across PCM blocks.  It does not modify PTR or radiation
mathematics.
"""

from __future__ import annotations

from collections import deque
import math
from typing import Sequence

from s12_ptr_network import PtrNetworkConfig, load_radiation_package


class RuntimePtrAdapter:
    """Apply the frozen PTR/radiation recurrence to consecutive sample blocks."""

    def __init__(self, config: PtrNetworkConfig = PtrNetworkConfig(), sample_rate_hz: int = 48000) -> None:
        if sample_rate_hz <= 0:
            raise ValueError("runtime PTR requires a positive sample rate")
        self.config = config
        self.sample_rate_hz = sample_rate_hz
        self.package = load_radiation_package(config.package_path)
        self._dt = 1.0 / sample_rate_hz
        (self._a00, self._a01), (self._a10, self._a11) = self.package.a
        self._determinant = (
            (1.0 - self._dt * self._a00 / 2.0) * (1.0 - self._dt * self._a11 / 2.0)
            - (self._dt * self._a01 / 2.0) * (self._dt * self._a10 / 2.0)
        )
        if not math.isfinite(self._determinant) or abs(self._determinant) < 1.0e-15:
            raise ValueError("frozen PTR Tustin update is singular")
        self._upstream = deque([0.0] * config.upstream_delay_frames)
        self._downstream = deque([0.0] * config.downstream_delay_frames)
        self._x0, self._x1 = self.package.initial_state

    @staticmethod
    def _delay_loss(delay_line: deque[float], sample: float, loss: float) -> float:
        if not delay_line:
            return loss * sample
        delayed = delay_line.popleft()
        delay_line.append(sample)
        return loss * delayed

    def _tustin(self, sample: float) -> float:
        rhs0 = (1.0 + self._dt * self._a00 / 2.0) * self._x0 + self._dt * self._a01 * self._x1 / 2.0 + self._dt * self.package.b[0] * sample
        rhs1 = self._dt * self._a10 * self._x0 / 2.0 + (1.0 + self._dt * self._a11 / 2.0) * self._x1 + self._dt * self.package.b[1] * sample
        self._x0, self._x1 = (
            ((1.0 - self._dt * self._a11 / 2.0) * rhs0 + self._dt * self._a01 * rhs1 / 2.0) / self._determinant,
            (self._dt * self._a10 * rhs0 / 2.0 + (1.0 - self._dt * self._a00 / 2.0) * rhs1) / self._determinant,
        )
        return self.package.c[0] * self._x0 + self.package.c[1] * self._x1 + self.package.d * sample

    def process(self, samples: Sequence[float]) -> list[float]:
        """Return output for one block while retaining delay and radiation state."""
        output = []
        for sample in samples:
            value = float(sample)
            if not math.isfinite(value):
                raise ValueError("runtime PTR input must be finite")
            outgoing = self._delay_loss(self._upstream, value, self.config.upstream_loss)
            outgoing = self._delay_loss(self._downstream, outgoing, self.config.downstream_loss)
            total = outgoing + self._tustin(outgoing)
            if not math.isfinite(total):
                raise ValueError("runtime PTR output became nonfinite")
            output.append(total)
        return output
