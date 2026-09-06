"""Deterministic uniform partitioned FIR convolution reference.

Architecture is clean-room and inspired by realtime partitioned convolution patterns,
including HiFi-LoFi/FFTConvolver (MIT, pinned in Stage-AE research docs).  This Python
module is the numerical reference used to qualify the future C++/Android adapter; it
contains no copied upstream source.
"""
from __future__ import annotations

import numpy as np


class UniformPartitionedConvolver:
    """Stateful mono overlap-add partitioned convolver.

    The block size is fixed after construction.  ``process_block`` performs no
    parameter search, no normalization and no random operation, making it suitable
    for Golden-PCM equivalence tests.
    """

    def __init__(self, impulse_response: np.ndarray, partition_size: int = 960) -> None:
        ir = np.asarray(impulse_response, dtype=np.float64).reshape(-1)
        if ir.size == 0 or not np.all(np.isfinite(ir)):
            raise ValueError("impulse_response must be non-empty and finite")
        if type(partition_size) is not int or partition_size <= 0:
            raise ValueError("partition_size must be a positive integer")
        self.partition_size = partition_size
        self.fft_size = 2 * partition_size
        self.partition_count = int(np.ceil(ir.size / partition_size))
        self._h = []
        for index in range(self.partition_count):
            part = ir[index * partition_size : (index + 1) * partition_size]
            padded = np.zeros(self.fft_size, dtype=np.float64)
            padded[: part.size] = part
            self._h.append(np.fft.rfft(padded))
        bins = self._h[0].size
        self._x_history = [np.zeros(bins, dtype=np.complex128) for _ in range(self.partition_count)]
        self._overlap = np.zeros(partition_size, dtype=np.float64)

    def reset(self) -> None:
        for spectrum in self._x_history:
            spectrum.fill(0.0)
        self._overlap.fill(0.0)

    def process_block(self, block: np.ndarray) -> np.ndarray:
        values = np.asarray(block, dtype=np.float64).reshape(-1)
        if values.size != self.partition_size or not np.all(np.isfinite(values)):
            raise ValueError("block must contain exactly partition_size finite samples")
        padded = np.zeros(self.fft_size, dtype=np.float64)
        padded[: self.partition_size] = values
        current = np.fft.rfft(padded)
        self._x_history = [current] + self._x_history[:-1]
        y_spectrum = np.zeros_like(current)
        for h_part, x_part in zip(self._h, self._x_history):
            y_spectrum += h_part * x_part
        y = np.fft.irfft(y_spectrum, n=self.fft_size)
        output = y[: self.partition_size] + self._overlap
        self._overlap = y[self.partition_size :].copy()
        return output

    def process(self, signal: np.ndarray) -> np.ndarray:
        values = np.asarray(signal, dtype=np.float64).reshape(-1)
        if not np.all(np.isfinite(values)):
            raise ValueError("signal must be finite")
        if values.size == 0:
            return values.copy()
        blocks = []
        for start in range(0, values.size, self.partition_size):
            chunk = values[start : start + self.partition_size]
            valid = chunk.size
            if valid < self.partition_size:
                chunk = np.pad(chunk, (0, self.partition_size - valid))
            blocks.append(self.process_block(chunk)[:valid])
        return np.concatenate(blocks)


def convolve_stereo(signal: np.ndarray, impulse_response: np.ndarray, partition_size: int = 960) -> np.ndarray:
    """Apply the same governed IR to each channel without changing track gain."""
    values = np.asarray(signal, dtype=np.float64)
    if values.ndim == 1:
        values = np.column_stack((values, values))
    if values.ndim != 2 or values.shape[1] != 2 or not np.all(np.isfinite(values)):
        raise ValueError("signal must be finite mono/stereo audio")
    result = np.empty_like(values)
    for channel in range(2):
        result[:, channel] = UniformPartitionedConvolver(impulse_response, partition_size).process(values[:, channel])
    return result
