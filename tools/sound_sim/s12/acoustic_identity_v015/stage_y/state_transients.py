"""Persistent, state-triggered pre-PTR transients for Stage Y4."""
from __future__ import annotations

from numbers import Real
from typing import Any, Mapping

import numpy as np


class StateTransientMixer:
    """Create independently observable transient stems with block-continuous tails."""

    _STEMS = ("tip_in", "lift", "shift", "bov")
    _MAX_PACKET_DURATION_S = 0.120

    def __init__(self, sample_rate_hz: int = 48000) -> None:
        self.sample_rate_hz = int(sample_rate_hz)
        if self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        self._tail_length = int(round(self._MAX_PACKET_DURATION_S * self.sample_rate_hz))
        self._tip_in = False
        self._lift_latched = False
        self._shift_latched = False
        self._bov_latched = False
        self._last_throttle = 0.18
        self._last_rpm = 850.0
        self._last_boost = 0.0
        self._counts = {f"transient_{name}_count": 0 for name in self._STEMS}
        self._audio_tails = {name: np.zeros(self._tail_length, dtype=np.float64) for name in self._STEMS}
        self._mix_tails = {name: np.zeros(self._tail_length, dtype=np.float64) for name in self._STEMS}
        self._last_crossfade_mix = np.zeros(0, dtype=np.float64)
        self._last_stem_energy = {name: 0.0 for name in self._STEMS}
        self._stem_energy_total = {name: 0.0 for name in self._STEMS}
        self._crossfade_active_samples_total = 0

    def equal_power_crossfade(self, a, b, mix: float | np.ndarray) -> np.ndarray:
        first = np.asarray(a, dtype=np.float64)
        second = np.asarray(b, dtype=np.float64)
        if first.shape != second.shape:
            raise ValueError("crossfade inputs must share a shape")
        try:
            mix_array = np.asarray(mix, dtype=np.float64)
        except (TypeError, ValueError):
            raise ValueError("crossfade mix must be finite") from None
        if not np.all(np.isfinite(mix_array)):
            raise ValueError("crossfade mix must be finite")
        if mix_array.ndim == 1 and first.ndim == 2 and mix_array.shape == (first.shape[0],):
            mix_array = mix_array[:, None]
        try:
            mix_array = np.broadcast_to(np.clip(mix_array, 0.0, 1.0), first.shape)
        except ValueError:
            raise ValueError("crossfade mix is not broadcastable to inputs") from None
        if np.all(mix_array == 0.0):
            return first.copy()
        if np.all(mix_array == 1.0):
            return second.copy()
        gain_a = np.cos(mix_array * np.pi / 2.0)
        gain_b = np.sin(mix_array * np.pi / 2.0)
        return gain_a * first + gain_b * second

    def render_block(self, n: int, throttle: float, rpm: float, boost: float, dt: float) -> tuple[np.ndarray, dict[str, float | int]]:
        if not isinstance(n, int) or n <= 0:
            raise ValueError("block size must be a positive integer")
        current_throttle, current_rpm, current_boost, duration = (
            self._finite(throttle, "throttle"), self._finite(rpm, "rpm"), self._finite(boost, "boost"), self._finite(dt, "dt")
        )
        if duration <= 0.0:
            raise ValueError("dt must be positive")
        d_throttle = (current_throttle - self._last_throttle) / max(duration, 1.0 / self.sample_rate_hz)
        rpm_drop = self._last_rpm - current_rpm
        if d_throttle > 0.4 and not self._tip_in:
            self._trigger("tip_in", 180.0, 0.080, 0.060)
            self._tip_in = True
        elif d_throttle < 0.1:
            self._tip_in = False
        if d_throttle < -0.4 and not self._lift_latched:
            self._trigger("lift", 135.0, 0.065, 0.050)
            self._lift_latched = True
        elif d_throttle >= -0.1:
            self._lift_latched = False
        if rpm_drop > 800.0 and duration < 0.080 and not self._shift_latched:
            self._trigger("shift", 90.0, 0.055, 0.120)
            self._shift_latched = True
        elif rpm_drop <= 800.0:
            self._shift_latched = False
        bov_trigger = current_boost < self._last_boost - 0.05 and current_throttle < 0.20
        if bov_trigger and not self._bov_latched:
            self._trigger("bov", 420.0, 0.060, 0.070)
            self._bov_latched = True
        elif not bov_trigger:
            self._bov_latched = False
        stems = {name: self._consume(self._audio_tails[name], n) for name in self._STEMS}
        mix = np.maximum.reduce([self._consume(self._mix_tails[name], n) for name in self._STEMS])
        self._last_crossfade_mix = mix
        self._last_stem_energy = {name: float(np.sum(np.square(stem))) for name, stem in stems.items()}
        for name, energy in self._last_stem_energy.items():
            self._stem_energy_total[name] += energy
        self._crossfade_active_samples_total += int(np.count_nonzero(mix))
        residual_mono = sum(stems.values(), np.zeros(n, dtype=np.float64))
        residual = np.column_stack((residual_mono, 0.88 * residual_mono))
        self._last_throttle, self._last_rpm, self._last_boost = current_throttle, current_rpm, current_boost
        return residual, self.diagnostics()

    def crossfade_mix(self) -> np.ndarray:
        return self._last_crossfade_mix.copy()

    def diagnostics(self) -> dict[str, float | int]:
        return {**self._counts, **{f"transient_{name}_stem_energy": self._last_stem_energy[name] for name in self._STEMS}, "transient_crossfade_active_samples": int(np.count_nonzero(self._last_crossfade_mix))}

    def cumulative_diagnostics(self) -> dict[str, float | int]:
        """Return event totals for an enclosing persistent engine run."""
        return {**self._counts, **{f"transient_{name}_stem_energy": self._stem_energy_total[name] for name in self._STEMS}, "transient_crossfade_active_samples": self._crossfade_active_samples_total}

    def snapshot(self) -> dict[str, Any]:
        return {"schema_version": "s12.stage_y.state_transients.v1", "sample_rate_hz": self.sample_rate_hz, "tail_length": self._tail_length, "tip_in": self._tip_in, "lift_latched": self._lift_latched, "shift_latched": self._shift_latched, "bov_latched": self._bov_latched, "last_throttle": self._last_throttle, "last_rpm": self._last_rpm, "last_boost": self._last_boost, "counts": dict(self._counts), "stem_energy_total": dict(self._stem_energy_total), "crossfade_active_samples_total": self._crossfade_active_samples_total, "audio_tails": {name: value.copy() for name, value in self._audio_tails.items()}, "mix_tails": {name: value.copy() for name, value in self._mix_tails.items()}}

    def restore(self, payload: Mapping[str, Any]) -> None:
        state = self._validate_snapshot(payload)
        self._tip_in, self._lift_latched, self._shift_latched, self._bov_latched = state["tip_in"], state["lift_latched"], state["shift_latched"], state["bov_latched"]
        self._last_throttle, self._last_rpm, self._last_boost = state["last_throttle"], state["last_rpm"], state["last_boost"]
        self._counts, self._audio_tails, self._mix_tails = state["counts"], state["audio_tails"], state["mix_tails"]
        self._stem_energy_total, self._crossfade_active_samples_total = state["stem_energy_total"], state["crossfade_active_samples_total"]
        self._last_crossfade_mix = np.zeros(0, dtype=np.float64)
        self._last_stem_energy = {name: 0.0 for name in self._STEMS}

    def _validate_snapshot(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        required = {"schema_version", "sample_rate_hz", "tail_length", "tip_in", "lift_latched", "shift_latched", "bov_latched", "last_throttle", "last_rpm", "last_boost", "counts", "stem_energy_total", "crossfade_active_samples_total", "audio_tails", "mix_tails"}
        if not isinstance(payload, Mapping) or set(payload) != required or payload["schema_version"] != "s12.stage_y.state_transients.v1":
            raise ValueError("transient snapshot fields differ from topology")
        if type(payload["sample_rate_hz"]) is not int or payload["sample_rate_hz"] != self.sample_rate_hz or type(payload["tail_length"]) is not int or payload["tail_length"] != self._tail_length:
            raise ValueError("transient topology differs from snapshot")
        for name in ("tip_in", "lift_latched", "shift_latched", "bov_latched"):
            if type(payload[name]) is not bool:
                raise ValueError(f"transient {name} state must be boolean")
        state = {"tip_in": payload["tip_in"], "lift_latched": payload["lift_latched"], "shift_latched": payload["shift_latched"], "bov_latched": payload["bov_latched"], "last_throttle": self._finite(payload["last_throttle"], "transient last throttle"), "last_rpm": self._finite(payload["last_rpm"], "transient last rpm"), "last_boost": self._finite(payload["last_boost"], "transient last boost")}
        counts = payload["counts"]
        if not isinstance(counts, Mapping) or set(counts) != set(self._counts) or any(type(value) is not int or value < 0 for value in counts.values()):
            raise ValueError("transient count topology differs from snapshot")
        state["counts"] = dict(counts)
        energy_total = payload["stem_energy_total"]
        if not isinstance(energy_total, Mapping) or set(energy_total) != set(self._STEMS):
            raise ValueError("transient energy topology differs from snapshot")
        state["stem_energy_total"] = {name: self._finite(energy_total[name], f"transient {name} energy") for name in self._STEMS}
        if any(value < 0.0 for value in state["stem_energy_total"].values()):
            raise ValueError("transient stem energy must be non-negative")
        if type(payload["crossfade_active_samples_total"]) is not int or payload["crossfade_active_samples_total"] < 0:
            raise ValueError("transient crossfade activity must be a non-negative integer")
        state["crossfade_active_samples_total"] = payload["crossfade_active_samples_total"]
        for label in ("audio_tails", "mix_tails"):
            tails = payload[label]
            if not isinstance(tails, Mapping) or set(tails) != set(self._STEMS):
                raise ValueError(f"{label} topology differs from snapshot")
            state[label] = {name: self._tail_array(tails[name], label) for name in self._STEMS}
        return state

    def _trigger(self, name: str, frequency_hz: float, amplitude: float, duration_s: float) -> None:
        count = max(2, int(round(duration_s * self.sample_rate_hz)))
        time_s = np.arange(count, dtype=np.float64) / self.sample_rate_hz
        envelope = np.hanning(count)
        self._place(self._audio_tails[name], amplitude * envelope * np.sin(2.0 * np.pi * frequency_hz * time_s))
        self._place(self._mix_tails[name], envelope)
        self._counts[f"transient_{name}_count"] += 1

    @staticmethod
    def _place(target: np.ndarray, packet: np.ndarray) -> None:
        target[: min(target.size, packet.size)] += packet[: min(target.size, packet.size)]

    @staticmethod
    def _consume(tail: np.ndarray, count: int) -> np.ndarray:
        output = tail[:count].copy()
        tail[:-count], tail[-count:] = tail[count:], 0.0
        return output

    def _tail_array(self, value: Any, label: str) -> np.ndarray:
        try:
            array = np.asarray(value, dtype=np.float64)
        except (TypeError, ValueError):
            raise ValueError(f"{label} must contain finite arrays") from None
        if array.shape != (self._tail_length,) or not np.all(np.isfinite(array)):
            raise ValueError(f"{label} topology or values differ from snapshot")
        return array.copy()

    @staticmethod
    def _finite(value: Any, label: str) -> float:
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not np.isfinite(float(value)):
            raise ValueError(f"{label} must be finite")
        return float(value)
