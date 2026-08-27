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
from .boundary_adapter import FrozenPtrStereo
from .teacher_response import ReducedCfdTeacherResponse
from .waveguide import WaveguideNetwork
from .timbre_map import render_timbre_map


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

    def __init__(self, config: Mapping[str, Any], sample_rate_hz: int = 48000, block_size: int = 960, mode: str = "measured_rpm", ptr_enabled: bool = False, path_model: str = "delay_lpf_v1", forced_induction_model: str = "harmonic_v1") -> None:
        self.config = validate_config(config)
        self.sample_rate_hz = int(sample_rate_hz)
        self.block_size = int(block_size)
        if self.sample_rate_hz <= 0 or self.block_size <= 0:
            raise ValueError("sample_rate_hz and block_size must be positive")
        if mode not in {"measured_rpm", "free_dynamics"}:
            raise ValueError("mode must be measured_rpm or free_dynamics")
        self.mode = mode
        self.ptr_enabled = bool(ptr_enabled)
        if path_model not in {"delay_lpf_v1", "waveguide_v1", "reduced_cfd_teacher_v1"}:
            raise ValueError("path_model must be delay_lpf_v1, waveguide_v1 or reduced_cfd_teacher_v1")
        self.path_model = path_model
        if forced_induction_model not in {"harmonic_v1", "timbre_map_v1"}:
            raise ValueError("forced_induction_model must be harmonic_v1 or timbre_map_v1")
        self.forced_induction_model = forced_induction_model
        self.entity_count = int(unwrap(self.config, "cylinder_or_rotor_count"))
        self.bank_count = int(unwrap(self.config, "bank_count"))
        self._reset_runtime()

    def _reset_runtime(self) -> None:
        self.pll = CrankPhasePLL(self.sample_rate_hz, self.config, mode=self.mode)
        self.sample_counter = 0
        self._last_rpm = float(unwrap(self.config, "idle_target_rpm"))
        self._last_throttle = 0.18
        self._last_load = 0.18
        self._boost_state = 0.0
        self._bov_state = 0.0
        self._bov_event_count = 0
        self._blower_phase = 0.0
        self._turbo_phase = 0.0
        self._afterfire_fuel_reservoir = 0.0
        self._afterfire_temperature = 120.0
        self._afterfire_cooldown_remaining = 0
        configured_policy = str(unwrap(self.config, "afterfire.event_location"))
        if configured_policy == "collector":
            configured_policy = "bank_collector"
        if configured_policy not in {"primary", "bank_collector", "central_collector"}:
            raise ValueError("afterfire.event_location must be primary, bank_collector or central_collector")
        self.afterfire_location_policy = configured_policy
        self._event_count = 0
        self._afterfire_event_count = 0
        self._afterfire_location_counts = {"primary": 0, "collector": 0, "bank_collector": 0, "central_collector": 0}
        self._last_afterfire_route = {"route": "none", "path_id": None, "bank_id": None, "collector_pressure": 0.0, "arrival_samples": None}
        self._combustion_torque_event_count = 0
        self._omega_ripple_sum_sq = 0.0
        self._omega_ripple_sample_count = 0
        temperature = float(unwrap(self.config, "gas_temperature_model"))
        speed = float(sound_speed_mps(temperature))
        lengths = list(unwrap(self.config, "per_path_primary_length_m"))
        attenuations = list(unwrap(self.config, "per_path_attenuation"))
        self._path_lines = [_DelayLine(round(float(length) / speed * self.sample_rate_hz), float(attenuations[index])) for index, length in enumerate(lengths)]
        collector_delay = round(float(unwrap(self.config, "collector_length_m")) / speed * self.sample_rate_hz)
        collector_loss = float(unwrap(self.config, "collector_loss"))
        self._collector_lines = [_DelayLine(collector_delay, collector_loss) for _ in range(self.bank_count)]
        central_delay = round(1.35 * float(unwrap(self.config, "collector_length_m")) / speed * self.sample_rate_hz)
        self._central_collector_line = _DelayLine(central_delay, min(1.0, collector_loss * 0.98))
        self._pending_combustion_torque = np.zeros(max(self.block_size * 2, int(round(0.10 * self.sample_rate_hz)) + 2), dtype=np.float64)
        self.waveguide_network = WaveguideNetwork(lengths, list(unwrap(self.config, "bank_assignment")), self.sample_rate_hz, temperature) if self.path_model == "waveguide_v1" else None
        self.teacher_response = ReducedCfdTeacherResponse() if self.path_model == "reduced_cfd_teacher_v1" else None
        self._event_tails = [np.zeros(self._tail_length(), dtype=np.float64) for _ in range(self.entity_count)]
        self._collector_event_tails = [np.zeros(self._tail_length(), dtype=np.float64) for _ in range(self.bank_count)]
        self._central_collector_event_tail = np.zeros(self._tail_length(), dtype=np.float64)
        self._monitor_gain_db = 0.0
        self.ptr = FrozenPtrStereo(self.sample_rate_hz) if self.ptr_enabled else None

    def initialize(self) -> "PersistentEventDomainEngine":
        """Validate explicit setup before the first block without rebuilding state."""
        if self.sample_counter != 0:
            raise RuntimeError("cannot initialize an engine after processing")
        return self

    def process_block(self, vehicle_state_block: Mapping[str, np.ndarray]) -> EngineAudioBlock:
        """Process one or more state frames using the persistent block contract."""
        return self.process(vehicle_state_block)

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
        self._pending_combustion_torque.fill(0.0)

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

    def process_with_trace(self, vehicle_state_block: Mapping[str, np.ndarray]) -> EngineAudioBlock:
        """Process frames while retaining block-rate diagnostic evidence."""
        arrays = {name: np.asarray(vehicle_state_block[name], dtype=np.float64) for name in ("rpm", "load", "throttle", "acceleration_mps2")}
        if any(value.ndim != 1 for value in arrays.values()) or len({value.size for value in arrays.values()}) != 1 or arrays["rpm"].size == 0:
            raise ValueError("vehicle state block must contain equal nonempty one-dimensional arrays")
        if not all(np.all(np.isfinite(value)) for value in arrays.values()):
            raise ValueError("vehicle state block must be finite")
        outputs: list[EngineAudioBlock] = []
        trace = {"phase_rad": [], "omega_rad_s": [], "event_count": [], "afterfire_event_count": [], "combustion_torque_event_count": [], "path_state_energy": [], "monitor_gain_db": [], "sample_counter": []}
        for index in range(arrays["rpm"].size):
            outputs.append(self._process_frame({name: float(value[index]) for name, value in arrays.items()}))
            trace["phase_rad"].append(float(self.pll.phase_rad))
            trace["omega_rad_s"].append(float(self.pll.omega_rad_s))
            trace["event_count"].append(int(self._event_count))
            trace["afterfire_event_count"].append(int(self._afterfire_event_count))
            trace["combustion_torque_event_count"].append(int(self._combustion_torque_event_count))
            trace["path_state_energy"].append(self._path_state_energy())
            trace["monitor_gain_db"].append(float(self._monitor_gain_db))
            trace["sample_counter"].append(int(self.sample_counter))
        raw = np.concatenate([item.raw_pcm for item in outputs], axis=0)
        monitor = np.concatenate([item.monitor_pcm for item in outputs], axis=0)
        post_ptr = np.concatenate([item.post_ptr_raw for item in outputs if item.post_ptr_raw is not None], axis=0) if self.ptr_enabled else None
        diagnostics = self.diagnostics()
        diagnostics.update({"frames": len(outputs), "sample_count": int(raw.shape[0]), "frame_trace": trace})
        return EngineAudioBlock(raw, monitor, diagnostics, post_ptr)

    def _path_state_energy(self) -> float:
        values = [tail for tail in self._event_tails] + [tail for tail in self._collector_event_tails] + [self._central_collector_event_tail] + [line.history for line in self._path_lines] + [line.history for line in self._collector_lines] + [self._central_collector_line.history]
        if self.waveguide_network is not None:
            for guide in self.waveguide_network.guides:
                values.extend((guide._forward.history, guide._round_trip.history))
        if self.teacher_response is not None:
            values.append(self.teacher_response._state)
        return float(sum(np.sum(np.square(value)) for value in values))

    def _process_frame(self, state: Mapping[str, float]) -> EngineAudioBlock:
        n = self.block_size
        rpm = np.full(n, max(0.0, state["rpm"]), dtype=np.float64)
        load = np.full(n, np.clip(state["load"], 0.0, 1.0), dtype=np.float64)
        throttle = np.full(n, np.clip(state["throttle"], 0.0, 1.0), dtype=np.float64)
        acceleration = np.full(n, state["acceleration_mps2"], dtype=np.float64)
        torque_input = self._consume(self._pending_combustion_torque, n)
        pll_state = (self.pll.phase_rad, self.pll.omega_rad_s, self.pll.initialized, self.pll.sample_count)
        phase_preview = self.pll.process_block(rpm, load, throttle, acceleration, torque_input)
        events = schedule_events(phase_preview.phase_rad, self.config, self.sample_rate_hz)
        self._event_count += events.count
        event_torque_input = torque_input.copy()
        for event_index, entity in zip(events.sample_index, events.entity_index):
            energy = self._event_energy(float(load[event_index]), float(throttle[event_index]), int(entity), self._event_count)
            packet = render_event_packet(self.sample_rate_hz, min(0.10, max(0.035, 3.5 * float(unwrap(self.config, "combustion_event.decay_time_s")))), float(unwrap(self.config, "combustion_event.rise_time_s")), float(unwrap(self.config, "combustion_event.decay_time_s")), energy, float(unwrap(self.config, "blowdown_event")))
            self._place(self._event_tails[int(entity)], int(event_index), packet.pressure)
            end = min(n, int(event_index) + packet.torque_impulse.size)
            event_torque_input[int(event_index):end] += packet.torque_impulse[: end - int(event_index)]
            remainder = packet.torque_impulse[end - int(event_index):]
            if remainder.size:
                self._place(self._pending_combustion_torque, 0, remainder)
            self._combustion_torque_event_count += 1
        self.pll.phase_rad, self.pll.omega_rad_s, self.pll.initialized, self.pll.sample_count = pll_state
        phase_block = self.pll.process_block(rpm, load, throttle, acceleration, event_torque_input)
        omega_ripple = phase_block.omega_rad_s - rpm * 2.0 * np.pi / 60.0
        self._omega_ripple_sum_sq += float(np.sum(np.square(omega_ripple)))
        self._omega_ripple_sample_count += int(omega_ripple.size)
        self._schedule_afterfire(state, phase_block.phase_rad, n)
        banks = np.zeros((self.bank_count, n), dtype=np.float64)
        bank_assignment = list(unwrap(self.config, "bank_assignment"))
        entity_sources: list[np.ndarray] = []
        for entity, line in enumerate(self._path_lines):
            source = self._event_tails[entity][:n].copy()
            self._event_tails[entity][:-n] = self._event_tails[entity][n:]
            self._event_tails[entity][-n:] = 0.0
            entity_sources.append(source)
            if self.waveguide_network is None:
                banks[int(bank_assignment[entity])] += line.process(source)
        collector_inputs = banks
        if self.waveguide_network is not None:
            collector_inputs = self.waveguide_network.process(np.asarray(entity_sources, dtype=np.float64)).bank_audio.copy()
        for bank, tail in enumerate(self._collector_event_tails):
            collector_inputs[bank] += self._consume(tail, n)
        collector = np.zeros_like(collector_inputs)
        for bank, line in enumerate(self._collector_lines):
            collector[bank] = line.process(collector_inputs[bank])
        central = self._central_collector_line.process(self._consume(self._central_collector_event_tail, n))
        combustion_left = np.zeros(n, dtype=np.float64)
        combustion_right = np.zeros(n, dtype=np.float64)
        for bank, signal in enumerate(collector):
            pan = -0.65 if bank % 2 == 0 else 0.65
            combustion_left += signal * (1.0 - pan) * 0.5
            combustion_right += signal * (1.0 + pan) * 0.5
        if self.afterfire_location_policy == "central_collector":
            combustion_left += 0.5 * central
            combustion_right += 0.5 * central
        if self.teacher_response is not None:
            reduced = self.teacher_response.process(np.column_stack((combustion_left, combustion_right)))
            combustion_left, combustion_right = reduced[:, 0], reduced[:, 1]
        phase = phase_block.phase_rad
        forced_type = unwrap(self.config, "forced_induction.type")
        boost_target = np.clip(load * throttle * np.maximum(rpm - 900.0, 0.0) / 4800.0, 0.0, 1.0) if forced_type in {"supercharger", "turbo"} else np.zeros_like(rpm)
        boost_start = self._boost_state
        boost_state = self._advance_boost(boost_target)
        forced = render_timbre_map(phase, rpm, load, boost_state, throttle, self.config, self.sample_counter) if self.forced_induction_model == "timbre_map_v1" else render_forced_induction(phase, rpm, load, throttle, self.config, self.sample_rate_hz, boost_state=boost_state)
        self._blower_phase = float(phase[-1])
        self._turbo_phase = float(phase[-1] * max(float(unwrap(self.config, "forced_induction.ratio")), 1.0))
        if forced_type == "supercharger":
            bypass_gain = np.clip(throttle / 0.20, 0.0, 1.0)
            forced["blower"] = forced["blower"] * bypass_gain[:, None]
        forced["blowoff"] = self._render_bov(phase, boost_start, boost_state, throttle)
        if self.forced_induction_model == "timbre_map_v1":
            forced["blower"] = forced["blower"] + 0.35 * forced["sidebands"] + 0.28 * forced["broadband"] + 0.25 * forced["casing"]
            forced["turbo"] = forced["turbo"] + 0.35 * forced["sidebands"] + 0.28 * forced["broadband"] + 0.25 * forced["casing"]
            forced["intake"] = forced["intake"] + 0.20 * forced["broadband"]
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

    def _advance_boost(self, target: np.ndarray) -> np.ndarray:
        state = np.empty_like(target)
        previous = float(self._boost_state)
        rise_tau = self._optional_time_constant("primary_spool_tau", 0.08)
        fall_tau = self._optional_time_constant("secondary_spool_tau", 0.25)
        for index, value in enumerate(target):
            tau = rise_tau if value >= previous else fall_tau
            previous += (float(value) - previous) / max(tau * self.sample_rate_hz, 1.0)
            state[index] = previous
        self._boost_state = previous
        return state

    def _optional_time_constant(self, name: str, default: float) -> float:
        node = self.config.get(name)
        if isinstance(node, Mapping) and "value" in node:
            return max(float(node["value"]), 1.0e-4)
        return default

    def _optional_gain(self, name: str, default: float) -> float:
        node = self.config.get(name)
        if isinstance(node, Mapping) and "value" in node:
            return max(float(node["value"]), 0.0)
        return default

    def _render_bov(self, phase: np.ndarray, boost_start: float, boost_state: np.ndarray, throttle: np.ndarray) -> np.ndarray:
        if unwrap(self.config, "forced_induction.type") not in {"supercharger", "turbo"}:
            return np.zeros((phase.size, 2), dtype=np.float64)
        drop = max(0.0, boost_start - float(boost_state[-1]))
        closure = max(0.0, self._last_throttle - float(throttle[0]))
        gain = self._optional_gain("blow_off_gain", 0.08)
        impulse = gain * max(drop, 0.35 * closure) if float(throttle[0]) <= 0.20 else 0.0
        if impulse > 1.0e-6:
            self._bov_event_count += 1
            self._bov_state = max(self._bov_state, impulse)
        decay_s = self._optional_time_constant("blow_off_decay", 0.16)
        decay = float(np.exp(-1.0 / (decay_s * self.sample_rate_hz)))
        envelope = np.empty(phase.size, dtype=np.float64)
        current = float(self._bov_state)
        for index in range(phase.size):
            envelope[index] = current
            current *= decay
        self._bov_state = current
        carrier = envelope * (0.70 * np.sin(phase * 6.0) + 0.30 * np.sin(phase * 11.0))
        return np.column_stack((0.45 * carrier, carrier))

    @staticmethod
    def _place(target: np.ndarray, index: int, packet: np.ndarray) -> None:
        if index >= target.size:
            return
        end = min(target.size, index + packet.size)
        target[index:end] += packet[: end - index]

    @staticmethod
    def _consume(tail: np.ndarray, count: int) -> np.ndarray:
        output = tail[:count].copy()
        tail[:-count] = tail[count:]
        tail[-count:] = 0.0
        return output

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
        delay_s = float(unwrap(self.config, "afterfire.ignition_delay_s")) + 0.000001 * float(state["rpm"])
        delay_samples = min(n - 1, max(0, int(round(delay_s * self.sample_rate_hz))))
        energy = float(unwrap(self.config, "afterfire.gain")) * (0.65 + 0.35 * min(1.0, float(state["load"])))
        packet = render_event_packet(self.sample_rate_hz, 0.05, 0.002, 0.018, energy, 0.25).pressure
        if self.afterfire_location_policy == "primary":
            self._place(self._event_tails[0], delay_samples, packet)
            self._afterfire_location_counts["primary"] += 1
        elif self.afterfire_location_policy in {"collector", "bank_collector"}:
            self._place(self._collector_event_tails[0], delay_samples, packet)
            self._afterfire_location_counts["collector"] += 1
            self._afterfire_location_counts["bank_collector"] += 1
            self._last_afterfire_route = {"route": "bank_collector", "path_id": "bank_collector_0", "bank_id": 0, "collector_pressure": float(np.max(np.abs(packet))), "arrival_samples": delay_samples + self._collector_lines[0].delay_samples}
        elif self.afterfire_location_policy == "central_collector":
            self._place(self._central_collector_event_tail, delay_samples, packet)
            self._afterfire_location_counts["central_collector"] += 1
            self._last_afterfire_route = {"route": "central_collector", "path_id": "central_collector", "bank_id": None, "collector_pressure": float(np.max(np.abs(packet))), "arrival_samples": delay_samples + self._central_collector_line.delay_samples}
        else:
            raise ValueError("afterfire_location_policy must be primary, bank_collector, central_collector or collector")
        if self.afterfire_location_policy == "primary":
            path_delay = self.waveguide_network.guides[0].delay_samples if self.waveguide_network is not None else self._path_lines[0].delay_samples
            self._last_afterfire_route = {"route": "primary", "path_id": "primary_path_0", "bank_id": 0, "collector_pressure": 0.0, "arrival_samples": delay_samples + path_delay + self._collector_lines[0].delay_samples}
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
            "pending_combustion_torque": self._pending_combustion_torque.copy(),
            "last_rpm": self._last_rpm,
            "last_throttle": self._last_throttle,
            "last_load": self._last_load,
            "afterfire_fuel_reservoir": self._afterfire_fuel_reservoir,
            "afterfire_temperature": self._afterfire_temperature,
            "afterfire_cooldown_remaining": self._afterfire_cooldown_remaining,
            "event_count": self._event_count,
            "afterfire_event_count": self._afterfire_event_count,
            "afterfire_location_counts": dict(self._afterfire_location_counts),
            "afterfire_route": dict(self._last_afterfire_route),
            "combustion_torque_event_count": self._combustion_torque_event_count,
            "boost_state": self._boost_state,
            "bov_state": self._bov_state,
            "bov_event_count": self._bov_event_count,
            "blower_phase": self._blower_phase,
            "turbo_phase": self._turbo_phase,
            "omega_ripple_sum_sq": self._omega_ripple_sum_sq,
            "omega_ripple_sample_count": self._omega_ripple_sample_count,
            "event_tails": [tail.copy() for tail in self._event_tails],
            "collector_event_tails": [tail.copy() for tail in self._collector_event_tails],
            "central_collector_event_tail": self._central_collector_event_tail.copy(),
            "path_lines": [line.snapshot() for line in self._path_lines],
            "collector_lines": [line.snapshot() for line in self._collector_lines],
            "central_collector_line": self._central_collector_line.snapshot(),
            "afterfire_location_policy": self.afterfire_location_policy,
            "monitor_gain_db": self._monitor_gain_db,
            "ptr": self.ptr.snapshot() if self.ptr is not None else None,
            "waveguide": self.waveguide_network.snapshot() if self.waveguide_network is not None else None,
            "teacher_response": self.teacher_response.snapshot() if self.teacher_response is not None else None,
        }

    def restore_state(self, snapshot: Mapping[str, Any]) -> None:
        if snapshot.get("schema_version") != "s12.stage_w.persistent_engine_state.v1":
            raise ValueError("unsupported persistent engine snapshot")
        self.sample_counter = int(snapshot["sample_counter"])
        pll = snapshot["pll"]
        self.pll.phase_rad = float(pll["phase_rad"]); self.pll.omega_rad_s = float(pll["omega_rad_s"]); self.pll.initialized = bool(pll["initialized"]); self.pll.sample_count = int(pll["sample_count"])
        pending = np.asarray(snapshot["pending_combustion_torque"], dtype=np.float64)
        if pending.ndim == 0:
            migrated = np.zeros_like(self._pending_combustion_torque)
            migrated[: self.block_size] = float(pending)
            pending = migrated
        if pending.shape != self._pending_combustion_torque.shape:
            raise ValueError("pending combustion torque topology differs from snapshot")
        self._pending_combustion_torque = pending.copy(); self._last_rpm = float(snapshot["last_rpm"]); self._last_throttle = float(snapshot["last_throttle"]); self._last_load = float(snapshot["last_load"]); self._boost_state = float(snapshot.get("boost_state", 0.0)); self._bov_state = float(snapshot.get("bov_state", 0.0)); self._bov_event_count = int(snapshot.get("bov_event_count", 0)); self._blower_phase = float(snapshot.get("blower_phase", 0.0)); self._turbo_phase = float(snapshot.get("turbo_phase", 0.0)); self._afterfire_fuel_reservoir = float(snapshot["afterfire_fuel_reservoir"]); self._afterfire_temperature = float(snapshot["afterfire_temperature"]); self._afterfire_cooldown_remaining = int(snapshot["afterfire_cooldown_remaining"]); self._event_count = int(snapshot["event_count"]); self._afterfire_event_count = int(snapshot["afterfire_event_count"]); self._afterfire_location_counts = dict(snapshot.get("afterfire_location_counts", {"primary": 0, "collector": 0})); self._last_afterfire_route = dict(snapshot.get("afterfire_route", self._last_afterfire_route)); self._combustion_torque_event_count = int(snapshot["combustion_torque_event_count"]); self._omega_ripple_sum_sq = float(snapshot.get("omega_ripple_sum_sq", 0.0)); self._omega_ripple_sample_count = int(snapshot.get("omega_ripple_sample_count", 0)); self._monitor_gain_db = float(snapshot["monitor_gain_db"])
        self._event_tails = [np.asarray(tail, dtype=np.float64).copy() for tail in snapshot["event_tails"]]
        self._collector_event_tails = [np.asarray(tail, dtype=np.float64).copy() for tail in snapshot.get("collector_event_tails", self._collector_event_tails)]
        self._central_collector_event_tail = np.asarray(snapshot.get("central_collector_event_tail", self._central_collector_event_tail), dtype=np.float64).copy()
        for line, saved in zip(self._path_lines, snapshot["path_lines"]): line.restore(saved)
        for line, saved in zip(self._collector_lines, snapshot["collector_lines"]): line.restore(saved)
        if snapshot.get("central_collector_line") is not None:
            self._central_collector_line.restore(snapshot["central_collector_line"])
        self.afterfire_location_policy = str(snapshot.get("afterfire_location_policy", self.afterfire_location_policy))
        if self.ptr is not None and snapshot.get("ptr") is not None:
            self.ptr.restore(snapshot["ptr"])
        if self.waveguide_network is not None and snapshot.get("waveguide") is not None:
            self.waveguide_network.restore(snapshot["waveguide"])
        if self.teacher_response is not None and snapshot.get("teacher_response") is not None:
            self.teacher_response.restore(snapshot["teacher_response"])

    def diagnostics(self) -> dict[str, Any]:
        return {
            "source_model": "event_domain_v1_hardened_persistent",
            "mode": self.mode,
            "path_model": self.path_model,
            "forced_induction_model": self.forced_induction_model,
            "sample_counter": self.sample_counter,
            "event_count": self._event_count,
            "afterfire_event_count": self._afterfire_event_count,
            "afterfire_location_counts": dict(self._afterfire_location_counts),
            "afterfire_route": dict(self._last_afterfire_route),
            "afterfire_cooldown_remaining": self._afterfire_cooldown_remaining,
            "combustion_torque_event_count": self._combustion_torque_event_count,
            "boost_state": self._boost_state,
            "bov_state": self._bov_state,
            "bov_event_count": self._bov_event_count,
            "blower_phase": self._blower_phase,
            "turbo_phase": self._turbo_phase,
            "omega_ripple_rms": float(np.sqrt(self._omega_ripple_sum_sq / self._omega_ripple_sample_count)) if self._omega_ripple_sample_count else 0.0,
            "omega_ripple_sample_count": self._omega_ripple_sample_count,
            "state_memory_bytes": int(self._pending_combustion_torque.nbytes + sum(tail.nbytes for tail in self._event_tails) + sum(tail.nbytes for tail in self._collector_event_tails) + self._central_collector_event_tail.nbytes + sum(line.history.nbytes for line in self._path_lines) + sum(line.history.nbytes for line in self._collector_lines) + self._central_collector_line.history.nbytes),
            "ptr_status": "FROZEN_RUNTIME_PTR_ADAPTER" if self.ptr is not None else "NOT_CONNECTED",
            "ptr_provenance": self.ptr.provenance() if self.ptr is not None else None,
            "teacher_response": self.teacher_response.diagnostics() if self.teacher_response is not None else None,
            "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
        }


__all__ = ["EngineAudioBlock", "PersistentEventDomainEngine"]
