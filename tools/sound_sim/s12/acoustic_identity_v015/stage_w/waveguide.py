"""Stateful clean-room waveguide_v1 and bank/collector network."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from ..event_domain.exhaust_path import sound_speed_mps


@dataclass(frozen=True)
class WaveguideConfig:
    length_m: float
    area_ratio: float = 0.7
    sample_rate_hz: int = 48000
    temperature_c: float = 700.0
    loss_per_meter: float = 0.08
    reflection_mode: str = "open"


@dataclass(frozen=True)
class WaveguideResult:
    left: np.ndarray
    right: np.ndarray
    arrival_samples: np.ndarray
    bank_audio: np.ndarray


class _Delay:
    def __init__(self, samples: int) -> None:
        self.samples = max(0, int(samples))
        self.history = np.zeros(self.samples, dtype=np.float64)
        self.sample_counter = 0

    def process(self, values: np.ndarray) -> np.ndarray:
        values = np.asarray(values, dtype=np.float64)
        if self.samples == 0:
            output = values.copy()
        else:
            joined = np.concatenate((self.history, values))
            output = joined[: values.size].copy()
            self.history = joined[-self.samples :].copy()
        self.sample_counter += values.size
        return output

    def snapshot(self) -> dict[str, Any]:
        return {"samples": self.samples, "history": self.history.copy(), "sample_counter": self.sample_counter}

    def restore(self, payload: Mapping[str, Any]) -> None:
        if int(payload["samples"]) != self.samples:
            raise ValueError("waveguide delay topology differs from snapshot")
        self.history = np.asarray(payload["history"], dtype=np.float64).copy()
        self.sample_counter = int(payload["sample_counter"])


class StatefulWaveguide:
    def __init__(self, config: WaveguideConfig) -> None:
        if not np.isfinite(config.length_m) or config.length_m <= 0.0 or config.area_ratio <= 0.0 or config.sample_rate_hz <= 0:
            raise ValueError("invalid waveguide geometry or sample rate")
        if config.reflection_mode not in {"open", "closed"}:
            raise ValueError("reflection_mode must be open or closed")
        self.config = config
        delay = float(config.length_m) / float(sound_speed_mps(config.temperature_c)) * config.sample_rate_hz
        self.delay_samples = max(1, int(round(delay)))
        self._round_trip = _Delay(max(1, 2 * self.delay_samples))
        self._forward = _Delay(self.delay_samples)
        self._loss = float(np.exp(-config.loss_per_meter * config.length_m))
        impedance_reflection = (1.0 - config.area_ratio) / (1.0 + config.area_ratio)
        self._reflection = -abs(impedance_reflection) if config.reflection_mode == "open" else abs(impedance_reflection)
        self.sample_counter = 0

    def process(self, signal: np.ndarray) -> np.ndarray:
        values = np.asarray(signal, dtype=np.float64)
        if values.ndim != 1 or not np.all(np.isfinite(values)):
            raise ValueError("waveguide input must be finite mono")
        forward = self._forward.process(values) * self._loss
        reflected = self._round_trip.process(values * self._reflection) * self._loss
        output = 0.20 * values + forward + reflected
        self.sample_counter += values.size
        return output

    def snapshot(self) -> dict[str, Any]:
        return {"sample_counter": self.sample_counter, "forward": self._forward.snapshot(), "round_trip": self._round_trip.snapshot()}

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        self._forward.restore(snapshot["forward"])
        self._round_trip.restore(snapshot["round_trip"])
        self.sample_counter = int(snapshot["sample_counter"])


class WaveguideNetwork:
    def __init__(self, primary_lengths_m: list[float], bank_assignment: list[int], sample_rate_hz: int = 48000, temperature_c: float = 700.0) -> None:
        if len(primary_lengths_m) != len(bank_assignment) or not primary_lengths_m:
            raise ValueError("waveguide path and bank arrays must have equal nonzero length")
        self.bank_assignment = np.asarray(bank_assignment, dtype=np.int64)
        self.guides = [StatefulWaveguide(WaveguideConfig(float(length), sample_rate_hz=sample_rate_hz, temperature_c=temperature_c)) for length in primary_lengths_m]
        self.bank_count = int(np.max(self.bank_assignment)) + 1

    def process(self, paths: np.ndarray) -> WaveguideResult:
        values = np.asarray(paths, dtype=np.float64)
        if values.ndim != 2 or values.shape[0] != len(self.guides) or not np.all(np.isfinite(values)):
            raise ValueError("waveguide network paths must be finite [entity, sample]")
        bank_audio = np.zeros((self.bank_count, values.shape[1]), dtype=np.float64)
        arrival = np.empty(len(self.guides), dtype=np.int64)
        for index, guide in enumerate(self.guides):
            bank_audio[int(self.bank_assignment[index])] += guide.process(values[index])
            arrival[index] = guide.delay_samples
        left = np.zeros(values.shape[1], dtype=np.float64)
        right = np.zeros_like(left)
        for bank, signal in enumerate(bank_audio):
            pan = -0.65 if bank % 2 == 0 else 0.65
            left += signal * (1.0 - pan) * 0.5
            right += signal * (1.0 + pan) * 0.5
        return WaveguideResult(left, right, arrival, bank_audio)

    def snapshot(self) -> dict[str, Any]:
        return {"guides": [guide.snapshot() for guide in self.guides]}

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        for guide, state in zip(self.guides, snapshot["guides"]):
            guide.restore(state)


__all__ = ["StatefulWaveguide", "WaveguideConfig", "WaveguideNetwork", "WaveguideResult"]
