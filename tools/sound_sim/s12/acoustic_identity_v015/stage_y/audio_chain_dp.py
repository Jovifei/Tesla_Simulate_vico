"""Clean-room DC / dP / warmup pressure chain applied before frozen PTR."""
from __future__ import annotations

from numbers import Integral, Real
from typing import Any, Mapping

import numpy as np


class PressureAudioChain:
    _SCHEMA_VERSION = "s12.stage_y.pressure_audio_chain.v1"
    _DC_DECAY = 0.995
    _DC_UPDATE = 1.0 - _DC_DECAY
    _DP_MIX = 0.35
    _DRY_MIX = 0.65
    _DELAY_MIX = 0.35

    def __init__(self, sample_rate_hz: int, delay_samples: float) -> None:
        sample_rate = self._validate_sample_rate(sample_rate_hz)
        delay = self._validate_delay(delay_samples)
        history_length = max(int(np.ceil(delay)) + 1, 2)
        self.sample_rate_hz = sample_rate
        self.delay_samples = delay
        self.history_length = history_length
        self.warmup_sample_count = max(int(0.1 * sample_rate), 1)
        self.dc = np.zeros(2, dtype=np.float64)
        self.prev = np.zeros(2, dtype=np.float64)
        self.history = np.zeros((self.history_length, 2), dtype=np.float64)
        self.warm = False
        self.sample_counter = 0

    @staticmethod
    def _validate_sample_rate(value: Any) -> int:
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or int(value) <= 0:
            raise ValueError("sample_rate_hz must be a positive integer")
        return int(value)

    @staticmethod
    def _validate_delay(value: Any) -> float:
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
            raise ValueError("delay_samples must be a finite non-negative number")
        try:
            delay = float(value)
        except (TypeError, OverflowError):
            raise ValueError("delay_samples must be a finite non-negative number") from None
        if not np.isfinite(delay) or delay < 0.0:
            raise ValueError("delay_samples must be a finite non-negative number")
        return delay

    @staticmethod
    def _validate_block(block: Any) -> np.ndarray:
        try:
            values = np.asarray(block, dtype=np.float64)
        except (TypeError, ValueError):
            raise ValueError("PressureAudioChain expects finite stereo samples") from None
        if values.ndim != 2 or values.shape[1] != 2 or not np.all(np.isfinite(values)):
            raise ValueError("PressureAudioChain expects finite stereo samples")
        return values

    def _filter(self, block: np.ndarray, *, count_samples: bool = True) -> np.ndarray:
        x = self._validate_block(block)
        if x.shape[0] == 0:
            return np.empty_like(x)
        y = np.empty_like(x)
        for index, sample in enumerate(x):
            self.dc = self._DC_DECAY * self.dc + self._DC_UPDATE * sample
            y[index] = sample - self.dc
        dp = np.diff(y, axis=0, prepend=self.prev.reshape(1, 2))
        self.prev = y[-1].copy()
        mixed = y + self._DP_MIX * dp
        joined = np.concatenate((self.history, mixed), axis=0)
        positions = self.history_length + np.arange(mixed.shape[0], dtype=np.float64) - self.delay_samples
        left = np.floor(positions).astype(np.int64)
        fraction = (positions - left).reshape(-1, 1)
        left_clipped = np.clip(left, 0, joined.shape[0] - 1)
        right_clipped = np.clip(left + 1, 0, joined.shape[0] - 1)
        delayed = joined[left_clipped] * (1.0 - fraction) + joined[right_clipped] * fraction
        self.history = joined[-self.history_length :].copy()
        if count_samples:
            self.sample_counter += int(x.shape[0])
        return self._DRY_MIX * mixed + self._DELAY_MIX * delayed

    def warmup(self, block: np.ndarray) -> None:
        values = self._validate_block(block)
        if self.warm:
            return
        if values.shape[0] == 0:
            return
        self._filter(values, count_samples=False)
        self.warm = True

    def process(self, block: np.ndarray) -> np.ndarray:
        values = self._validate_block(block)
        if values.shape[0] == 0:
            return np.empty_like(values)
        if not self.warm:
            self.warmup(np.zeros((self.warmup_sample_count, 2), dtype=np.float64))
        return self._filter(values)

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": self._SCHEMA_VERSION,
            "sample_rate_hz": self.sample_rate_hz,
            "delay_samples": self.delay_samples,
            "history_length": self.history_length,
            "warmup_sample_count": self.warmup_sample_count,
            "dc": self.dc.copy(),
            "prev": self.prev.copy(),
            "history": self.history.copy(),
            "warm": self.warm,
            "sample_counter": self.sample_counter,
        }

    @staticmethod
    def _finite_array(value: Any, shape: tuple[int, ...], label: str) -> np.ndarray:
        try:
            array = np.asarray(value, dtype=np.float64)
        except (TypeError, ValueError):
            raise ValueError(f"{label} must be a finite array") from None
        if array.shape != shape or not np.all(np.isfinite(array)):
            raise ValueError(f"{label} must be a finite array")
        return array.copy()

    def _validate_snapshot(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        required = {
            "schema_version", "sample_rate_hz", "delay_samples", "history_length", "warmup_sample_count",
            "dc", "prev", "history", "warm", "sample_counter",
        }
        if not isinstance(payload, Mapping) or set(payload) != required:
            raise ValueError("pressure audio chain snapshot fields differ from topology")
        if payload["schema_version"] != self._SCHEMA_VERSION:
            raise ValueError("unsupported pressure audio chain snapshot")
        if type(payload["sample_rate_hz"]) is not int or payload["sample_rate_hz"] != self.sample_rate_hz:
            raise ValueError("pressure audio chain sample rate differs from snapshot")
        delay = self._validate_delay(payload["delay_samples"])
        if delay != self.delay_samples:
            raise ValueError("pressure audio chain delay differs from snapshot")
        if type(payload["history_length"]) is not int or payload["history_length"] != self.history_length:
            raise ValueError("pressure audio chain history topology differs from snapshot")
        if type(payload["warmup_sample_count"]) is not int or payload["warmup_sample_count"] != self.warmup_sample_count:
            raise ValueError("pressure audio chain warmup topology differs from snapshot")
        if type(payload["warm"]) is not bool:
            raise ValueError("pressure audio chain warm state must be boolean")
        sample_counter = payload["sample_counter"]
        if isinstance(sample_counter, (bool, np.bool_)) or not isinstance(sample_counter, Integral) or int(sample_counter) < 0:
            raise ValueError("pressure audio chain sample counter must be non-negative")
        return {
            "dc": self._finite_array(payload["dc"], self.dc.shape, "pressure audio chain dc"),
            "prev": self._finite_array(payload["prev"], self.prev.shape, "pressure audio chain dP state"),
            "history": self._finite_array(payload["history"], self.history.shape, "pressure audio chain delay history"),
            "warm": payload["warm"],
            "sample_counter": int(sample_counter),
        }

    def restore(self, payload: Mapping[str, Any]) -> None:
        state = self._validate_snapshot(payload)
        self.dc = state["dc"]
        self.prev = state["prev"]
        self.history = state["history"]
        self.warm = state["warm"]
        self.sample_counter = state["sample_counter"]

    def diagnostics(self) -> dict[str, Any]:
        return {
            "sample_rate_hz": self.sample_rate_hz,
            "delay_samples": self.delay_samples,
            "warm": self.warm,
            "warmup_sample_count": self.warmup_sample_count,
            "sample_counter": self.sample_counter,
            "dc": self.dc.tolist(),
        }
