"""Persistent 20 ms event-domain engine state for Stage-W hardening.

This remains a synthetic source-domain renderer. Frozen PTR/Radiation is an
explicit later stage and is not silently substituted here.
"""

from __future__ import annotations

from dataclasses import dataclass
import copy
from typing import Any, Mapping

import numpy as np

from ..contracts import SourceRender
from ..event_domain.chamber_event import render_event_packet
from ..event_domain.config_schema import unwrap, validate_config
from ..event_domain.crank_phase_pll import CrankPhasePLL
from ..event_domain.event_scheduler import schedule_events
from ..event_domain.exhaust_path import sound_speed_mps
from ..event_domain.forced_induction import render_forced_induction
from .frozen_ptr import FrozenPtrStereo


@dataclass(frozen=True)
class EngineAudioBlock:
    raw_pcm: np.ndarray
    monitor_pcm: np.ndarray
    diagnostics: dict[str, Any]
    post_ptr_raw: np.ndarray | None = None


class _DelayLine:
    def __init__(self, delay_samples: int, attenuation: float = 1.0) -> None:
        self.delay_samples = max(0, int(delay_samples))
        self.attenuation = float(attenuation)
        self.history = np.zeros(self.delay_samples, dtype=np.float64)

    def process(self, block: np.ndarray) -> np.ndarray:
        values = np.asarray(block, dtype=np.float64)
        if self.delay_samples == 0:
            return self.attenuation * values
        joined = np.concatenate((self.history, values))
        output = joined[: values.size]
        self.history = joined[-self.delay_samples :].copy()
        return self.attenuation * output

    def snapshot(self) -> dict[str, Any]:
        return {"delay_samples": self.delay_samples, "attenuation": self.attenuation, "history": self.history.copy()}

    def restore(self, payload: Mapping[str, Any]) -> None:
        if int(payload["delay_samples"]) != self.delay_samples:
            raise ValueError("delay-line topology differs from snapshot")
        self.history = np.asarray(payload["history"], dtype=np.float64).copy()


class PersistentEventDomainEngine:
    """Stateful source-domain engine with one output block per 20 ms frame."""

    def __init__(self, config: Mapping[str, Any], sample_rate_hz: int = 48000, block_size: int = 960, mode: str = "measured_rpm", ptr_enabled: bool = False) -> None:
        self.config = validate_config(config)
        self.sample_rate_hz = int(sample_rate_hz)
        self.block_size = int(block_size)
        if self.sample_rate_hz <= 0 or self.block_size <= 0:
            raise ValueError("sample_rate_hz and block_size must be positive")
        if mode not in {"measured_rpm", "free_dynamics"}:
            raise ValueError("mode must be measured_rpm or free_dynamics")
        self.mode = mode
        self.ptr_enabled = bool(ptr_enabled)
        self.entity_count = int(unwrap(self.config, "cylinder_or_rotor_count"))
        self.bank_count = int(unwrap(self.config, "bank_count"))
        self._reset_runtime()

    def _reset_runtime(self) -> None:
        self.pll = CrankPhasePLL(self.sample_rate_hz, self.config, mode=self.mode)
        self.sample_counter = 0
        self._pending_combustion_torque = 0.0
        self._last_rpm = float(unwrap(self.config, "idle_target_rpm"))
        self._last_throttle = 0.18
        self._last_load = 0.18
        self._afterfire_fuel_reservoir = 0.0
        self._afterfire_temperature = 120.0
        self._afterfire_cooldown_remaining = 0
        self.afterfire_location_policy = "primary"
        self._event_count = 0
        self._afterfire_event_count = 0
        self._combustion_torque_event_count = 0
        self._omega_ripple_values: list[float] = []
        temperature = float(unwrap(self.config, "gas_temperature_model"))
        speed = float(sound_speed_mps(temperature))
        lengths = list(unwrap(self.config, "per_path_primary_length_m"))
        attenuations = list(unwrap(self.config, "per_path_attenuation"))
        self._path_lines = [_DelayLine(round(float(length) / speed * self.sample_rate_hz), float(attenuations[index])) for index, length in enumerate(lengths)]
        collector_delay = round(float(unwrap(self.config, "collector_length_m")) / speed * self.sample_rate_hz)
        collector_loss = float(unwrap(self.config, "collector_loss"))
        self._collector_lines = [_DelayLine(collector_delay, collector_loss) for _ in range(self.bank_count)]
        self._event_tails = [np.zeros(self._tail_length(), dtype=np.float64) for _ in range(self.entity_count)]
        self._monitor_gain_db = 0.0
        self.ptr = FrozenPtrStereo(self.sample_rate_hz) if self.ptr_enabled else None

    def _tail_length(self) -> int:
        maximum_delay = max((line.delay_samples for line in getattr(self, "_path_lines", [])), default=0)
        maximum_packet = int(round(0.10 * self.sample_rate_hz))
        return max(self.block_size * 2, maximum_delay + maximum_packet + 2)

    def reset(self, reset_policy: str = "hard") -> None:
        if reset_policy not in {"hard", "phase_only"}:
            raise ValueError("reset_policy must be hard or phase_only")
        if reset_policy == "hard":
            self._reset_runtime()
            return
        self.pll.phase_rad = 0.0
        self.pll.omega_rad_s = 0.0
        self.pll.initialized = False
        self._pending_combustion_torque = 0.0

    def process(self, vehicle_state_block: Mapping[str, np.ndarray]) -> EngineAudioBlock:
        arrays = {name: np.asarray(vehicle_state_block[name], dtype=np.float64) for name in ("rpm", "load", "throttle", "acceleration_mps2")}
        if any(value.ndim != 1 for value in arrays.values()) or len({value.size for value in arrays.values()}) != 1 or arrays["rpm"].size == 0:
            raise ValueError("vehicle state block must contain equal nonempty one-dimensional arrays")
        if not all(np.all(np.isfinite(value)) for value in arrays.values()):
            raise ValueError("vehicle state block must be finite")
        outputs: list[EngineAudioBlock] = []
        for index in range(arrays["rpm"].size):
            outputs.append(self._process_frame({name: float(value[index]) for name, value in arrays.items()}))
        raw = np.concatenate([item.raw_pcm for item in outputs], axis=0)
        monitor = np.concatenate([item.monitor_pcm for item in outputs], axis=0)
        post_ptr = np.concatenate([item.post_ptr_raw for item in outputs if item.post_ptr_raw is not None], axis=0) if self.ptr_enabled else None
        diagnostics = self.diagnostics()
        diagnostics.update({"frames": len(outputs), "sample_count": int(raw.shape[0])})
        return EngineAudioBlock(raw, monitor, diagnostics, post_ptr)

    def _process_frame(self, state: Mapping[str, float]) -> EngineAudioBlock:
        n = self.block_size
        rpm = np.full(n, max(0.0, state["rpm"]), dtype=np.float64)
        load = np.full(n, np.clip(state["load"], 0.0, 1.0), dtype=np.float64)
        throttle = np.full(n, np.clip(state["throttle"], 0.0, 1.0), dtype=np.float64)
        acceleration = np.full(n, state["acceleration_mps2"], dtype=np.float64)
        torque_input = np.full(n, self._pending_combustion_torque, dtype=np.float64)
        phase_block = self.pll.process_block(rpm, load, throttle, acceleration, torque_input)
        self._omega_ripple_values.extend((phase_block.omega_rad_s - rpm * 2.0 * np.pi / 60.0).tolist())
        events = schedule_events(phase_block.phase_rad, self.config, self.sample_rate_hz)
        self._event_count += events.count
        for event_index, entity in zip(events.sample_index, events.entity_index):
            energy = self._event_energy(float(load[event_index]), float(throttle[event_index]), int(entity), self._event_count)
            packet = render_event_packet(self.sample_rate_hz, min(0.10, max(0.035, 3.5 * float(unwrap(self.config, "combustion_event.decay_time_s")))), float(unwrap(self.config, "combustion_event.rise_time_s")), float(unwrap(self.config, "combustion_event.decay_time_s")), energy, float(unwrap(self.config, "blowdown_event")))
            self._place(self._event_tails[int(entity)], int(event_index), packet.pressure)
            self._pending_combustion_torque = 0.85 * self._pending_combustion_torque + float(np.sum(packet.torque_impulse)) / max(n, 1)
            self._combustion_torque_event_count += 1
        self._schedule_afterfire(state, phase_block.phase_rad, n)
        banks = np.zeros((self.bank_count, n), dtype=np.float64)
        bank_assignment = list(unwrap(self.config, "bank_assignment"))
        for entity, line in enumerate(self._path_lines):
            source = self._event_tails[entity][:n].copy()
            self._event_tails[entity][:-n] = self._event_tails[entity][n:]
            self._event_tails[entity][-n:] = 0.0
            banks[int(bank_assignment[entity])] += line.process(source)
        collector = np.zeros_like(banks)
        for bank, line in enumerate(self._collector_lines):
            collector[bank] = line.process(banks[bank])
        combustion_left = collector[0]
        combustion_right = collector[min(1, self.bank_count - 1)]
        phase = phase_block.phase_rad
        forced = render_forced_induction(phase, rpm, load, throttle, self.config, self.sample_rate_hz)
        mechanical = 0.010 * np.sin(phase * 6.0 + 0.2) * (0.35 + 0.65 * load) + 0.003 * phase_block.torque_ripple
        raw = np.column_stack((0.55 * combustion_left + 0.72 * forced["blower"][:, 0] + 0.62 * forced["turbo"][:, 0] + 0.30 * forced["blowoff"][:, 0] + 0.54 * forced["intake"][:, 0] + 0.40 * mechanical, 0.55 * combustion_right + 0.72 * forced["blower"][:, 1] + 0.62 * forced["turbo"][:, 1] + 0.30 * forced["blowoff"][:, 1] + 0.54 * forced["intake"][:, 1] + 0.33 * mechanical))
        post_ptr = self.ptr.process(raw) if self.ptr is not None else None
        monitor = self._monitor(post_ptr if post_ptr is not None else raw)
        self.sample_counter += n
        self._last_rpm = float(state["rpm"])
        self._last_throttle = float(state["throttle"])
        self._last_load = float(state["load"])
        return EngineAudioBlock(raw, monitor, self.diagnostics(), post_ptr)

    def _event_energy(self, load: float, throttle: float, entity: int, event_number: int) -> float:
        base = float(unwrap(self.config, "combustion_event.event_energy"))
        exponent = float(unwrap(self.config, "combustion_event.load_exponent"))
        variation = float(unwrap(self.config, "cycle_variation"))
        return base * (0.28 + 0.72 * max(load, 0.0) ** exponent) * (0.70 + 0.30 * throttle) * (1.0 + variation * np.sin((entity + 1) * 1.71 + event_number * 0.37))

    @staticmethod
    def _place(target: np.ndarray, index: int, packet: np.ndarray) -> None:
        if index >= target.size:
            return
        end = min(target.size, index + packet.size)
        target[index:end] += packet[: end - index]

    def _schedule_afterfire(self, state: Mapping[str, float], phase: np.ndarray, n: int) -> None:
        dt = n / self.sample_rate_hz
        d_rpm = (float(state["rpm"]) - self._last_rpm) / max(dt, 1.0 / self.sample_rate_hz)
        d_throttle = (float(state["throttle"]) - self._last_throttle) / max(dt, 1.0 / self.sample_rate_hz)
        self._afterfire_fuel_reservoir = max(0.0, 0.995 * self._afterfire_fuel_reservoir + 0.72 * float(state["load"]))
        self._afterfire_temperature = 120.0 + 780.0 * np.clip(float(state["rpm"]) / 6500.0, 0.0, 1.0) * (0.55 + 0.45 * float(state["load"]))
        self._afterfire_cooldown_remaining = max(0, self._afterfire_cooldown_remaining - n)
        oxygen = np.clip(0.82 - 0.48 * float(state["load"]) + 0.15 * (1.0 - float(state["throttle"])), 0.0, 1.0)
        eligible = (d_throttle < -0.8) and d_rpm < -10.0 and float(state["rpm"]) >= float(unwrap(self.config, "afterfire.minimum_rpm")) and float(state["load"]) >= 0.35 and float(state["throttle"]) <= 0.18 and self._afterfire_temperature >= float(unwrap(self.config, "afterfire.minimum_temperature_c")) and self._afterfire_fuel_reservoir >= 0.2 and oxygen >= 0.15 and self._afterfire_cooldown_remaining == 0
        if not eligible:
            return
        delay_s = 0.004 + 0.000001 * float(state["rpm"])
        delay_samples = min(n - 1, max(0, int(round(delay_s * self.sample_rate_hz))))
        energy = float(unwrap(self.config, "afterfire.gain")) * (0.65 + 0.35 * min(1.0, float(state["load"])))
        packet = render_event_packet(self.sample_rate_hz, 0.05, 0.002, 0.018, energy, 0.25).pressure
        if self.afterfire_location_policy == "primary":
            self._place(self._event_tails[0], delay_samples, packet)
        else:
            bank = self._collector_lines[0]
            impulse = np.zeros(n, dtype=np.float64)
            self._place(impulse, delay_samples, packet)
            bank.history = bank.history + np.pad(impulse[: bank.history.size], (max(0, bank.history.size - impulse.size), 0))[: bank.history.size]
        self._afterfire_event_count += 1
        self._afterfire_cooldown_remaining = int(round(float(unwrap(self.config, "afterfire.cooldown_s")) * self.sample_rate_hz))

    def _monitor(self, raw: np.ndarray) -> np.ndarray:
        rms = float(np.sqrt(np.mean(np.square(raw))))
        desired = float(np.clip(20.0 * np.log10(0.08 / max(rms, 1.0e-9)), -12.0, 9.0))
        alpha = 1.0 - np.exp(-self.block_size / (0.12 * self.sample_rate_hz if desired > self._monitor_gain_db else 1.20 * self.sample_rate_hz))
        self._monitor_gain_db += alpha * (desired - self._monitor_gain_db)
        monitor = raw * 10.0 ** (self._monitor_gain_db / 20.0)
        peak = float(np.max(np.abs(monitor))) if monitor.size else 0.0
        ceiling = 10.0 ** (-1.2 / 20.0)
        if peak > ceiling:
            monitor *= ceiling / peak
        return monitor

    def snapshot_state(self) -> dict[str, Any]:
        return {
            "schema_version": "s12.stage_w.persistent_engine_state.v1",
            "sample_counter": self.sample_counter,
            "pll": {"phase_rad": self.pll.phase_rad, "omega_rad_s": self.pll.omega_rad_s, "initialized": self.pll.initialized, "sample_count": self.pll.sample_count},
            "pending_combustion_torque": self._pending_combustion_torque,
            "last_rpm": self._last_rpm,
            "last_throttle": self._last_throttle,
            "last_load": self._last_load,
            "afterfire_fuel_reservoir": self._afterfire_fuel_reservoir,
            "afterfire_temperature": self._afterfire_temperature,
            "afterfire_cooldown_remaining": self._afterfire_cooldown_remaining,
            "event_count": self._event_count,
            "afterfire_event_count": self._afterfire_event_count,
            "combustion_torque_event_count": self._combustion_torque_event_count,
            "event_tails": [tail.copy() for tail in self._event_tails],
            "path_lines": [line.snapshot() for line in self._path_lines],
            "collector_lines": [line.snapshot() for line in self._collector_lines],
            "monitor_gain_db": self._monitor_gain_db,
            "ptr": self.ptr.snapshot() if self.ptr is not None else None,
        }

    def restore_state(self, snapshot: Mapping[str, Any]) -> None:
        if snapshot.get("schema_version") != "s12.stage_w.persistent_engine_state.v1":
            raise ValueError("unsupported persistent engine snapshot")
        self.sample_counter = int(snapshot["sample_counter"])
        pll = snapshot["pll"]
        self.pll.phase_rad = float(pll["phase_rad"]); self.pll.omega_rad_s = float(pll["omega_rad_s"]); self.pll.initialized = bool(pll["initialized"]); self.pll.sample_count = int(pll["sample_count"])
        self._pending_combustion_torque = float(snapshot["pending_combustion_torque"]); self._last_rpm = float(snapshot["last_rpm"]); self._last_throttle = float(snapshot["last_throttle"]); self._last_load = float(snapshot["last_load"]); self._afterfire_fuel_reservoir = float(snapshot["afterfire_fuel_reservoir"]); self._afterfire_temperature = float(snapshot["afterfire_temperature"]); self._afterfire_cooldown_remaining = int(snapshot["afterfire_cooldown_remaining"]); self._event_count = int(snapshot["event_count"]); self._afterfire_event_count = int(snapshot["afterfire_event_count"]); self._combustion_torque_event_count = int(snapshot["combustion_torque_event_count"]); self._monitor_gain_db = float(snapshot["monitor_gain_db"])
        self._event_tails = [np.asarray(tail, dtype=np.float64).copy() for tail in snapshot["event_tails"]]
        for line, saved in zip(self._path_lines, snapshot["path_lines"]): line.restore(saved)
        for line, saved in zip(self._collector_lines, snapshot["collector_lines"]): line.restore(saved)
        if self.ptr is not None and snapshot.get("ptr") is not None:
            self.ptr.restore(snapshot["ptr"])

    def diagnostics(self) -> dict[str, Any]:
        return {
            "source_model": "event_domain_v1_hardened_persistent",
            "mode": self.mode,
            "sample_counter": self.sample_counter,
            "event_count": self._event_count,
            "afterfire_event_count": self._afterfire_event_count,
            "afterfire_cooldown_remaining": self._afterfire_cooldown_remaining,
            "combustion_torque_event_count": self._combustion_torque_event_count,
            "omega_ripple_rms": float(np.sqrt(np.mean(np.square(self._omega_ripple_values)))) if self._omega_ripple_values else 0.0,
            "state_memory_bytes": int(sum(tail.nbytes for tail in self._event_tails) + sum(line.history.nbytes for line in self._path_lines) + sum(line.history.nbytes for line in self._collector_lines)),
            "ptr_status": "FROZEN_RUNTIME_PTR_ADAPTER" if self.ptr is not None else "NOT_CONNECTED",
            "ptr_provenance": self.ptr.provenance() if self.ptr is not None else None,
            "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
        }


__all__ = ["EngineAudioBlock", "PersistentEventDomainEngine"]
