"""Stateful clean-room waveguide_v1 and bank/collector network."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
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
    arrival_samples_exact: np.ndarray | None = None


class _FractionalDelay:
    """Bounded, streaming-safe linear-interpolated fractional delay."""

    def __init__(self, delay_samples: float) -> None:
        if not np.isfinite(delay_samples) or delay_samples < 0.0:
            raise ValueError("delay must be finite and non-negative")
        self.delay_samples_exact = float(delay_samples)
        # A causal interpolator has no output before ceil(delay).  Keep one
        # extra sample so both interpolation taps remain available at a block
        # boundary, including the zero-delay case.
        self.samples = int(np.ceil(self.delay_samples_exact))
        self.history_length = max(1, self.samples + 1)
        self.history = np.zeros(self.history_length, dtype=np.float64)
        self.sample_counter = 0

    def process(self, values: np.ndarray) -> np.ndarray:
        values = np.asarray(values, dtype=np.float64)
        joined = np.concatenate((self.history, values))
        positions = self.history_length + np.arange(values.size, dtype=np.float64) - self.delay_samples_exact
        left = np.floor(positions).astype(np.int64)
        fraction = positions - left
        left_clipped = np.clip(left, 0, joined.size - 1)
        right_clipped = np.clip(left + 1, 0, joined.size - 1)
        output = joined[left_clipped] * (1.0 - fraction) + joined[right_clipped] * fraction
        output[self.sample_counter + np.arange(values.size) < self.samples] = 0.0
        self.history = joined[-self.history_length :].copy()
        self.sample_counter += values.size
        return output

    def snapshot(self) -> dict[str, Any]:
        return {"samples": self.samples, "delay_samples": self.delay_samples_exact, "history": self.history.copy(), "sample_counter": self.sample_counter}

    def restore(self, payload: Mapping[str, Any]) -> None:
        history, sample_counter = self._validate(payload)
        self.history = history
        self.sample_counter = sample_counter

    def _validate(self, payload: Mapping[str, Any]) -> tuple[np.ndarray, int]:
        if not isinstance(payload, Mapping):
            raise ValueError("waveguide delay topology differs from snapshot")
        if set(payload) != {"samples", "delay_samples", "history", "sample_counter"}:
            raise ValueError("waveguide delay fields differ from snapshot")
        try:
            samples = payload["samples"]
            if isinstance(payload["delay_samples"], (bool, np.bool_)) or not isinstance(payload["delay_samples"], Real):
                raise ValueError
            delay_samples = float(payload["delay_samples"])
            history = np.asarray(payload["history"], dtype=np.float64)
            sample_counter = payload["sample_counter"]
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ValueError("waveguide delay topology differs from snapshot") from None
        if type(samples) is not int or type(sample_counter) is not int:
            raise ValueError("waveguide delay topology differs from snapshot")
        if samples != self.samples or delay_samples != self.delay_samples_exact:
            raise ValueError("waveguide delay topology differs from snapshot")
        if history.shape != self.history.shape:
            raise ValueError("waveguide delay history topology differs from snapshot")
        if not np.all(np.isfinite(history)) or sample_counter < 0:
            raise ValueError("waveguide delay history topology differs from snapshot")
        return history.copy(), sample_counter

    def reset(self) -> None:
        self.history.fill(0.0)
        self.sample_counter = 0


_Delay = _FractionalDelay


class _FrequencyLoss:
    """Stable one-pole low-pass representing distributed viscothermal loss."""

    def __init__(self, cutoff_hz: float, sample_rate_hz: int) -> None:
        if not np.isfinite(cutoff_hz) or cutoff_hz <= 0.0 or sample_rate_hz <= 0:
            raise ValueError("frequency-loss cutoff and sample rate must be positive")
        self.cutoff_hz = float(cutoff_hz)
        self.sample_rate_hz = int(sample_rate_hz)
        self.alpha = float(1.0 - np.exp(-2.0 * np.pi * self.cutoff_hz / self.sample_rate_hz))
        self.state = 0.0

    def process(self, values: np.ndarray) -> np.ndarray:
        output = np.empty_like(np.asarray(values, dtype=np.float64))
        state = self.state
        for index, value in enumerate(output):
            state += self.alpha * (float(values[index]) - state)
            output[index] = state
        self.state = state
        return output

    def snapshot(self) -> dict[str, Any]:
        return {"cutoff_hz": self.cutoff_hz, "sample_rate_hz": self.sample_rate_hz, "state": self.state}

    def restore(self, payload: Mapping[str, Any]) -> None:
        state = self._validate(payload)
        self.state = state

    def _validate(self, payload: Mapping[str, Any]) -> float:
        if not isinstance(payload, Mapping):
            raise ValueError("waveguide frequency-loss topology differs from snapshot")
        if set(payload) != {"cutoff_hz", "sample_rate_hz", "state"}:
            raise ValueError("waveguide frequency-loss fields differ from snapshot")
        try:
            if isinstance(payload["cutoff_hz"], (bool, np.bool_)) or not isinstance(payload["cutoff_hz"], Real):
                raise ValueError
            cutoff_hz = float(payload["cutoff_hz"])
            sample_rate_hz = payload["sample_rate_hz"]
            if isinstance(payload["state"], (bool, np.bool_)) or not isinstance(payload["state"], Real):
                raise ValueError
            state = float(payload["state"])
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ValueError("waveguide frequency-loss topology differs from snapshot") from None
        if type(sample_rate_hz) is not int:
            raise ValueError("waveguide frequency-loss topology differs from snapshot")
        if cutoff_hz != self.cutoff_hz or sample_rate_hz != self.sample_rate_hz:
            raise ValueError("waveguide frequency-loss topology differs from snapshot")
        if not np.isfinite(state):
            raise ValueError("waveguide frequency-loss topology differs from snapshot")
        return state


class StatefulWaveguide:
    def __init__(self, config: WaveguideConfig) -> None:
        if not all(np.isfinite(float(value)) for value in (config.length_m, config.area_ratio, config.temperature_c, config.loss_per_meter)) or config.length_m <= 0.0 or config.area_ratio <= 0.0 or config.sample_rate_hz <= 0 or config.temperature_c <= 0.0 or config.loss_per_meter < 0.0:
            raise ValueError("invalid waveguide geometry or sample rate")
        if config.reflection_mode not in {"open", "closed"}:
            raise ValueError("reflection_mode must be open or closed")
        self.config = config
        delay = float(config.length_m) / float(sound_speed_mps(config.temperature_c)) * config.sample_rate_hz
        self.delay_samples_exact = max(0.0, delay)
        self.delay_samples = int(np.ceil(self.delay_samples_exact))
        self._round_trip = _Delay(2.0 * self.delay_samples_exact)
        self._forward = _Delay(self.delay_samples_exact)
        self._loss = float(np.exp(-config.loss_per_meter * config.length_m))
        impedance_reflection = (1.0 - config.area_ratio) / (1.0 + config.area_ratio)
        self._reflection = -abs(impedance_reflection) if config.reflection_mode == "open" else abs(impedance_reflection)
        # Longer paths and cooler gas have lower acoustic cut-offs.  This is a
        # bounded source-domain loss model; it does not alter the frozen PTR.
        cutoff = 2600.0 * np.sqrt(max(config.temperature_c, 20.0) / 700.0) / (1.0 + 1.6 * config.length_m)
        self._frequency_loss = _FrequencyLoss(cutoff, config.sample_rate_hz)
        self.sample_counter = 0

    def process(self, signal: np.ndarray) -> np.ndarray:
        values = np.asarray(signal, dtype=np.float64)
        if values.ndim != 1 or not np.all(np.isfinite(values)):
            raise ValueError("waveguide input must be finite mono")
        filtered = self._frequency_loss.process(values)
        forward = self._forward.process(filtered) * self._loss
        reflected = self._round_trip.process(filtered * self._reflection) * self._loss
        output = forward + reflected
        self.sample_counter += values.size
        return output

    def snapshot(self) -> dict[str, Any]:
        return {"sample_counter": self.sample_counter, "forward": self._forward.snapshot(), "round_trip": self._round_trip.snapshot(), "frequency_loss": self._frequency_loss.snapshot()}

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        validated = self._validate_snapshot(snapshot)
        self._forward.history, self._forward.sample_counter = validated["forward"]
        self._round_trip.history, self._round_trip.sample_counter = validated["round_trip"]
        self._frequency_loss.state = validated["frequency_loss"]
        self.sample_counter = validated["sample_counter"]

    def reset(self) -> None:
        self._forward.reset()
        self._round_trip.reset()
        self._frequency_loss.state = 0.0
        self.sample_counter = 0

    def _validate_snapshot(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(snapshot, Mapping):
            raise ValueError("waveguide topology differs from snapshot")
        if set(snapshot) != {"sample_counter", "forward", "round_trip", "frequency_loss"}:
            raise ValueError("waveguide fields differ from topology")
        try:
            forward = self._forward._validate(snapshot["forward"])
            round_trip = self._round_trip._validate(snapshot["round_trip"])
            frequency_loss = self._frequency_loss._validate(snapshot["frequency_loss"])
            sample_counter = snapshot["sample_counter"]
        except (KeyError, TypeError):
            raise ValueError("waveguide topology differs from snapshot") from None
        if type(sample_counter) is not int:
            raise ValueError("waveguide topology differs from snapshot")
        if sample_counter < 0:
            raise ValueError("waveguide topology differs from snapshot")
        return {"forward": forward, "round_trip": round_trip, "frequency_loss": frequency_loss, "sample_counter": sample_counter}


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
        arrival_exact = np.empty(len(self.guides), dtype=np.float64)
        for index, guide in enumerate(self.guides):
            bank_audio[int(self.bank_assignment[index])] += guide.process(values[index])
            arrival[index] = guide.delay_samples
            arrival_exact[index] = guide.delay_samples_exact
        left = np.zeros(values.shape[1], dtype=np.float64)
        right = np.zeros_like(left)
        for bank, signal in enumerate(bank_audio):
            pan = -0.65 if bank % 2 == 0 else 0.65
            left += signal * (1.0 - pan) * 0.5
            right += signal * (1.0 + pan) * 0.5
        return WaveguideResult(left, right, arrival, bank_audio, arrival_exact)

    def snapshot(self) -> dict[str, Any]:
        return {"bank_assignment": self.bank_assignment.tolist(), "bank_count": self.bank_count, "guides": [guide.snapshot() for guide in self.guides]}

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        validated = self._validate_snapshot(snapshot)
        for guide, state in zip(self.guides, validated):
            guide._forward.history, guide._forward.sample_counter = state["forward"]
            guide._round_trip.history, guide._round_trip.sample_counter = state["round_trip"]
            guide._frequency_loss.state = state["frequency_loss"]
            guide.sample_counter = state["sample_counter"]

    def _validate_snapshot(self, snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
        if not isinstance(snapshot, Mapping):
            raise ValueError("waveguide network topology differs from snapshot")
        if set(snapshot) != {"bank_assignment", "bank_count", "guides"}:
            raise ValueError("waveguide network fields differ from topology")
        bank_assignment = snapshot.get("bank_assignment")
        bank_count = snapshot.get("bank_count")
        if (
            not isinstance(bank_assignment, list)
            or len(bank_assignment) != len(self.guides)
            or any(type(value) is not int for value in bank_assignment)
            or bank_assignment != self.bank_assignment.tolist()
            or type(bank_count) is not int
            or bank_count != self.bank_count
        ):
            raise ValueError("waveguide network topology differs from snapshot")
        guide_states = snapshot.get("guides")
        if not isinstance(guide_states, list) or len(guide_states) != len(self.guides):
            raise ValueError("waveguide network topology differs from snapshot")
        validated = [guide._validate_snapshot(state) for guide, state in zip(self.guides, guide_states)]
        return validated

    def reset(self) -> None:
        for guide in self.guides:
            guide.reset()


__all__ = ["StatefulWaveguide", "WaveguideConfig", "WaveguideNetwork", "WaveguideResult"]
