"""Persistent 20 ms event-domain engine state for Stage-W hardening.

This remains a synthetic source-domain renderer. Frozen PTR/Radiation is an
explicit later stage and is not silently substituted here.
"""

from __future__ import annotations

from dataclasses import dataclass
import copy
from numbers import Integral, Real
from typing import Any, Mapping

import numpy as np
from scipy.signal import lfilter

from ..contracts import SourceRender
from ..event_domain.chamber_event import render_event_packet
from ..event_domain.config_schema import unwrap, validate_config
from ..event_domain.crank_phase_pll import CrankPhasePLL
from ..event_domain.event_scheduler import cycle_degrees, derive_event_path_schedule, derive_event_phase_deg, schedule_events
from ..event_domain.exhaust_path import sound_speed_mps
from ..event_domain.forced_induction import render_forced_induction
from .boundary_adapter import FrozenPtrStereo
from .teacher_response import ReducedCfdTeacherResponse
from .waveguide import WaveguideNetwork
from .timbre_map import TimbreMap4D, render_timbre_map
from .click_contract import click_gate_contract


def _finite_scalar(value: Any, label: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{label} must be a finite number")
    try:
        result = float(value)
    except (TypeError, OverflowError):
        raise ValueError(f"{label} must be a finite number") from None
    if not np.isfinite(result):
        raise ValueError(f"{label} must be a finite number")
    return result


def _counter(value: Any, label: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or int(value) < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return int(value)


def _finite_array(value: Any, shape: tuple[int, ...], label: str) -> np.ndarray:
    try:
        source = np.asarray(value)
        if source.dtype.kind not in "fiu":
            raise ValueError
        result = np.asarray(source, dtype=np.float64)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a finite array") from None
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise ValueError(f"{label} topology or values differ from snapshot")
    return result.copy()


def _strict_numeric_array(value: Any, shape: tuple[int, ...], label: str) -> np.ndarray:
    if not isinstance(value, (list, np.ndarray)):
        raise ValueError(f"{label} must be a numeric list or array")
    try:
        source = np.asarray(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a numeric list or array") from None
    if source.shape != shape:
        raise ValueError(f"{label} topology differs from snapshot")
    for item in source.flat:
        if isinstance(item, (bool, np.bool_)) or not isinstance(item, Real):
            raise ValueError(f"{label} contains a non-numeric value")
    result = np.asarray(source, dtype=np.float64)
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{label} must be finite")
    return result.copy()


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def _timbre_map_matches_formula_default(payload: Any) -> bool:
    table = TimbreMap4D.from_config(payload if isinstance(payload, dict) else None)
    default = TimbreMap4D.default()
    return (
        np.allclose(table.rpm_axis, default.rpm_axis)
        and np.allclose(table.load_axis, default.load_axis)
        and np.allclose(table.boost_axis, default.boost_axis)
        and np.allclose(table.order_axis, default.order_axis)
        and np.allclose(table.values, default.values)
    )


@dataclass(frozen=True)
class EngineAudioBlock:
    raw_pcm: np.ndarray
    monitor_pcm: np.ndarray
    diagnostics: dict[str, Any]
    post_ptr_raw: np.ndarray | None = None


class _DelayLine:
    """Bounded persistent fractional delay used by non-waveguide paths."""

    def __init__(self, delay_samples: float, attenuation: float = 1.0) -> None:
        if not np.isfinite(delay_samples) or float(delay_samples) < 0.0:
            raise ValueError("delay must be finite and non-negative")
        self.delay_samples_exact = float(delay_samples)
        self.delay_samples = int(np.ceil(self.delay_samples_exact))
        self.attenuation = float(attenuation)
        self.history_length = max(1, self.delay_samples + 1)
        self.history = np.zeros(self.history_length, dtype=np.float64)
        self.sample_counter = 0

    def process(self, block: np.ndarray) -> np.ndarray:
        values = np.asarray(block, dtype=np.float64)
        joined = np.concatenate((self.history, values))
        positions = self.history_length + np.arange(values.size, dtype=np.float64) - self.delay_samples_exact
        left = np.floor(positions).astype(np.int64)
        fraction = positions - left
        left_clipped = np.clip(left, 0, joined.size - 1)
        right_clipped = np.clip(left + 1, 0, joined.size - 1)
        output = joined[left_clipped] * (1.0 - fraction) + joined[right_clipped] * fraction
        output[self.sample_counter + np.arange(values.size) < self.delay_samples] = 0.0
        self.history = joined[-self.history_length :].copy()
        self.sample_counter += values.size
        return self.attenuation * output

    def snapshot(self) -> dict[str, Any]:
        return {"delay_samples": self.delay_samples, "delay_samples_exact": self.delay_samples_exact, "attenuation": self.attenuation, "history": self.history.copy(), "sample_counter": self.sample_counter}

    def restore(self, payload: Mapping[str, Any]) -> None:
        history, sample_counter = self._validate(payload)
        self.history = history.copy()
        self.sample_counter = sample_counter

    def _validate(self, payload: Mapping[str, Any]) -> tuple[np.ndarray, int]:
        payload = _mapping(payload, "delay-line snapshot")
        if set(payload) != {"delay_samples", "delay_samples_exact", "attenuation", "history", "sample_counter"}:
            raise ValueError("delay-line snapshot fields differ from topology")
        if type(payload.get("delay_samples")) is not int or payload["delay_samples"] != self.delay_samples:
            raise ValueError("delay-line topology differs from snapshot")
        exact = _finite_scalar(payload.get("delay_samples_exact"), "delay_samples_exact")
        if exact != self.delay_samples_exact:
            raise ValueError("delay-line topology differs from snapshot")
        attenuation = _finite_scalar(payload.get("attenuation"), "attenuation")
        if attenuation != self.attenuation:
            raise ValueError("delay-line topology differs from snapshot")
        history = _strict_numeric_array(payload.get("history"), self.history.shape, "delay-line history")
        sample_counter = _counter(payload.get("sample_counter"), "delay-line sample_counter")
        return history, sample_counter

    def reset(self) -> None:
        self.history.fill(0.0)
        self.sample_counter = 0


class _TransferIrFilter:
    """Bounded stateful pre-PTR transfer response selected by config label."""

    def __init__(self, label: str) -> None:
        self.label = str(label)
        # Keep the clean-room IR symbolic: label deterministically selects a
        # stable pole and high-frequency blend, with no external asset bytes.
        code = sum((index + 1) * ord(char) for index, char in enumerate(self.label))
        self.alpha = 0.16 + (code % 37) / 100.0
        self.blend = 0.08 + (code % 19) / 100.0
        self.state = np.zeros(2, dtype=np.float64)

    def process(self, values: np.ndarray) -> np.ndarray:
        array = np.asarray(values, dtype=np.float64)
        result = np.empty_like(array)
        for index, row in enumerate(array):
            self.state += self.alpha * (row - self.state)
            result[index] = (1.0 - self.blend) * self.state + self.blend * row
        return result

    def snapshot(self) -> dict[str, Any]:
        return {"label": self.label, "state": self.state.copy()}

    def restore(self, payload: Mapping[str, Any]) -> None:
        payload = _mapping(payload, "transfer IR snapshot")
        if type(payload.get("label")) is not str or payload["label"] != self.label:
            raise ValueError("transfer IR topology differs from snapshot")
        self.state = self._validate_state(payload)

    def _validate_state(self, payload: Mapping[str, Any]) -> np.ndarray:
        payload = _mapping(payload, "transfer IR snapshot")
        if set(payload) != {"label", "state"}:
            raise ValueError("transfer IR snapshot fields differ from topology")
        if type(payload.get("label")) is not str or payload["label"] != self.label:
            raise ValueError("transfer IR topology differs from snapshot")
        return _finite_array(payload.get("state"), self.state.shape, "transfer IR state")


class _Band120to400:
    """Stateful bounded 120-400 Hz emphasis (one high-pass + one low-pass)."""

    def __init__(self, sample_rate_hz: int) -> None:
        self.sample_rate_hz = int(sample_rate_hz)
        self._hp_prev_in: np.ndarray | None = None
        self._hp_prev_out: np.ndarray | None = None
        self._lp_prev_in: np.ndarray | None = None
        self._lp_prev_out: np.ndarray | None = None

    def process(self, raw: np.ndarray) -> np.ndarray:
        raw = np.asarray(raw, dtype=np.float64)
        dt = 1.0 / self.sample_rate_hz
        rc_hp = 1.0 / (2.0 * np.pi * 120.0)
        alpha_hp = rc_hp / (rc_hp + dt)
        if self._hp_prev_in is None:
            self._hp_prev_in = raw[0].copy() if raw.size else np.zeros(2)
            self._hp_prev_out = np.zeros(2)
        hp_out = np.empty_like(raw)
        previous_in = self._hp_prev_in
        previous_out = self._hp_prev_out
        for index in range(raw.shape[0]):
            current = raw[index]
            previous_out = alpha_hp * (previous_out + current - previous_in)
            previous_in = current
            hp_out[index] = previous_out
        self._hp_prev_in, self._hp_prev_out = previous_in.copy(), previous_out.copy()
        rc_lp = 1.0 / (2.0 * np.pi * 400.0)
        alpha_lp = dt / (rc_lp + dt)
        if self._lp_prev_in is None:
            self._lp_prev_in = hp_out[0].copy() if hp_out.size else np.zeros(2)
            self._lp_prev_out = np.zeros(2)
        lp_out = np.empty_like(hp_out)
        previous_in = self._lp_prev_in
        previous_out = self._lp_prev_out
        for index in range(hp_out.shape[0]):
            previous_out += alpha_lp * (hp_out[index] - previous_out)
            previous_in = hp_out[index]
            lp_out[index] = previous_out
        self._lp_prev_in, self._lp_prev_out = previous_in.copy(), previous_out.copy()
        return lp_out


class PersistentEventDomainEngine:
    """Stateful source-domain engine with one output block per 20 ms frame."""

    def __init__(self, config: Mapping[str, Any], sample_rate_hz: int = 48000, block_size: int = 960, mode: str = "measured_rpm", ptr_enabled: bool = False, path_model: str = "delay_lpf_v1", forced_induction_model: str = "harmonic_v1", random_seed: int = 0, jitter_fraction: float = 0.0, cycle_sync_model: str = "off", transient_model: str = "off", audio_chain: str = "off") -> None:
        self.config = validate_config(config)
        if self.config.get("require_fitted_timbre_map"):
            payload = self.config.get("timbre_map")
            if payload is None or _timbre_map_matches_formula_default(payload):
                raise ValueError("fitted HarmonicTimbreMap required")
        self._parameter_fallbacks: dict[str, dict[str, Any]] = {}
        for name, fallback in (("transfer_ir", "identity_default"), ("collector_assignment", "identity_default")):
            if name not in self.config:
                self.config[name] = {"value": fallback, "unit": "label", "range": "explicit_default", "source_level": "C", "source": "legacy config compatibility fallback", "verification_state": "synthetic_assumption"}
                self._parameter_fallbacks[name] = {"value": fallback, "reason": "legacy config omitted accepted field", "provenance": "explicit_identity_default"}
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
        if not isinstance(random_seed, int) or isinstance(random_seed, bool):
            raise ValueError("random_seed must be a bounded integer")
        if not np.isfinite(jitter_fraction) or not 0.0 <= float(jitter_fraction) <= 0.25:
            raise ValueError("jitter_fraction must be finite and in [0, 0.25]")
        self.random_seed = int(random_seed)
        self.jitter_fraction = float(jitter_fraction)
        if cycle_sync_model not in {"off", "fixture_v1"}:
            raise ValueError("cycle_sync_model must be off or fixture_v1")
        if transient_model not in {"off", "state_v1"}:
            raise ValueError("transient_model must be off or state_v1")
        if audio_chain not in {"off", "dp_v1"}:
            raise ValueError("audio_chain must be off or dp_v1")
        self.cycle_sync_model = cycle_sync_model
        self.transient_model = transient_model
        self.audio_chain_model = audio_chain
        self.entity_count = int(unwrap(self.config, "cylinder_or_rotor_count"))
        self.bank_count = int(unwrap(self.config, "bank_count"))
        self._reset_runtime()

    def _reset_runtime(self) -> None:
        self.pll = CrankPhasePLL(self.sample_rate_hz, self.config, mode=self.mode)
        self._rng = np.random.default_rng(self.random_seed)
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
        self._afterfire_lift_remaining = 0
        self._afterfire_pending_events: list[dict[str, Any]] = []
        self._afterfire_sequence = 0
        self._afterfire_dropped_events = 0
        self._collector_pressure = 0.0
        configured_policy = str(unwrap(self.config, "afterfire.event_location"))
        if configured_policy == "collector":
            configured_policy = "bank_collector"
        if configured_policy not in {"primary", "bank_collector", "central_collector"}:
            raise ValueError("afterfire.event_location must be primary, bank_collector or central_collector")
        self.afterfire_location_policy = configured_policy
        self._event_count = 0
        self._afterfire_event_count = 0
        self._afterfire_location_counts = {"primary": 0, "collector": 0, "bank_collector": 0, "central_collector": 0}
        self._last_afterfire_route = {"route": "none", "path_id": None, "bank_id": None, "collector_pressure": 0.0, "arrival_samples": None, "arrival_sample_index": None, "arrival_samples_exact": None}
        self._combustion_torque_event_count = 0
        self._omega_ripple_sum_sq = 0.0
        self._omega_ripple_sample_count = 0
        temperature = float(unwrap(self.config, "gas_temperature_model"))
        speed = float(sound_speed_mps(temperature))
        lengths = list(unwrap(self.config, "per_path_primary_length_m"))
        attenuations = list(unwrap(self.config, "per_path_attenuation"))
        self._path_lines = [_DelayLine(float(length) / speed * self.sample_rate_hz, float(attenuations[index])) for index, length in enumerate(lengths)]
        self._path_filter_state = np.zeros(self.entity_count, dtype=np.float64)
        collector_delay = float(unwrap(self.config, "collector_length_m")) / speed * self.sample_rate_hz
        collector_loss = float(unwrap(self.config, "collector_loss"))
        self._collector_lines = [_DelayLine(collector_delay, collector_loss) for _ in range(self.bank_count)]
        central_delay = 1.35 * float(unwrap(self.config, "collector_length_m")) / speed * self.sample_rate_hz
        self._central_collector_line = _DelayLine(central_delay, min(1.0, collector_loss * 0.98))
        self._pending_combustion_torque = np.zeros(max(self.block_size * 2, int(round(0.10 * self.sample_rate_hz)) + 2), dtype=np.float64)
        waveguide_node = self.config.get("exhaust_waveguide") or {}
        def _waveguide_value(name: str, default: float) -> float:
            node = waveguide_node.get(name)
            value = node["value"] if isinstance(node, dict) and "value" in node else node
            return float(value) if value is not None else float(default)
        reflection_node = waveguide_node.get("reflection_mode")
        reflection_value = reflection_node.get("value", "open") if isinstance(reflection_node, dict) else (reflection_node or "open")
        self.waveguide_network = WaveguideNetwork(lengths, list(unwrap(self.config, "bank_assignment")), self.sample_rate_hz, temperature, loss_per_meter=_waveguide_value("loss_per_meter", 0.08), reflection_mode=str(reflection_value)) if self.path_model == "waveguide_v1" else None
        self.teacher_response = ReducedCfdTeacherResponse() if self.path_model == "reduced_cfd_teacher_v1" else None
        self._event_tails = [np.zeros(self._tail_length(), dtype=np.float64) for _ in range(self.entity_count)]
        self._collector_event_tails = [np.zeros(self._tail_length(), dtype=np.float64) for _ in range(self.bank_count)]
        self._central_collector_event_tail = np.zeros(self._tail_length(), dtype=np.float64)
        self._monitor_gain_db = 0.0
        monitor_policy = self.config.get("monitor_policy") or {}
        def _monitor_value(name: str, default: float) -> float:
            node = monitor_policy.get(name)
            value = node["value"] if isinstance(node, dict) and "value" in node else node
            return float(value) if value is not None else float(default)
        self._monitor_target_rms = _monitor_value("target_rms", 0.08)
        self._monitor_attack_s = _monitor_value("attack_s", 0.12)
        self._monitor_release_s = _monitor_value("release_s", 1.20)
        self._monitor_max_makeup_db = _monitor_value("max_makeup_db", 9.0)
        self._monitor_max_attenuation_db = _monitor_value("max_attenuation_db", -12.0)
        attack_node = self.config.get("attack_shaping") or {}
        attack_mix_node = attack_node.get("band_120_400_mix")
        attack_mix_value = attack_mix_node.get("value", 0.0) if isinstance(attack_mix_node, dict) else (attack_mix_node if attack_mix_node is not None else 0.0)
        self._attack_mix = float(np.clip(attack_mix_value, 0.0, 2.0))
        if self._attack_mix > 0.0:
            self._attack_band_state = _Band120to400(self.sample_rate_hz)
        else:
            self._attack_band_state = None
        self._last_output_sample = np.zeros(2, dtype=np.float64)
        self._click_max_boundary_jump = 0.0
        self._click_sum_sq = 0.0
        self._click_count = 0
        self._click_threshold = 0.35
        self._click_contract = click_gate_contract(self.config)
        self._click_threshold = float(self._click_contract["threshold"])
        self._timbre_inertia_state = 0.0
        transfer_label = str(unwrap(self.config, "transfer_ir"))
        self._transfer_ir = _TransferIrFilter(transfer_label)
        self._parameter_consumption = {"collector_assignment": True, "transfer_ir": True, "crankpin_geometry": self.config["architecture"] == "piston", "rotor_geometry": self.config["architecture"] == "rotary_wankel"}
        self._cycle_sync = None
        if self.cycle_sync_model == "fixture_v1":
            from ..stage_y.cycle_sync_resynth import CycleSyncResampler
            from ..stage_y.fixture_cycles import synthesize_hellcat_cycle_bank
            self._cycle_sync = CycleSyncResampler(synthesize_hellcat_cycle_bank(self.sample_rate_hz), self.sample_rate_hz)
        self._transient_mixer = None
        self._transient_counts = {"transient_shift_count": 0, "transient_tip_in_count": 0, "transient_bov_count": 0}
        if self.transient_model == "state_v1":
            from ..stage_y.state_transients import StateTransientMixer
            self._transient_mixer = StateTransientMixer(self.sample_rate_hz)
        self._audio_chain = None
        if self.audio_chain_model == "dp_v1":
            from ..stage_y.audio_chain_dp import PressureAudioChain
            self._audio_chain = PressureAudioChain(self.sample_rate_hz, delay_samples=64.0)
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

    def process(self, vehicle_state_block: Mapping[str, np.ndarray], external_transient: np.ndarray | None = None) -> EngineAudioBlock:
        arrays = {name: np.asarray(vehicle_state_block[name], dtype=np.float64) for name in ("rpm", "load", "throttle", "acceleration_mps2")}
        if any(value.ndim != 1 for value in arrays.values()) or len({value.size for value in arrays.values()}) != 1 or arrays["rpm"].size == 0:
            raise ValueError("vehicle state block must contain equal nonempty one-dimensional arrays")
        if not all(np.all(np.isfinite(value)) for value in arrays.values()):
            raise ValueError("vehicle state block must be finite")
        transient = self._validate_external_transient(external_transient, arrays["rpm"].size)
        outputs: list[EngineAudioBlock] = []
        for index in range(arrays["rpm"].size):
            segment = transient[index * self.block_size : (index + 1) * self.block_size] if transient is not None else None
            outputs.append(self._process_frame({name: float(value[index]) for name, value in arrays.items()}, segment))
        raw = np.concatenate([item.raw_pcm for item in outputs], axis=0)
        monitor = np.concatenate([item.monitor_pcm for item in outputs], axis=0)
        post_ptr = np.concatenate([item.post_ptr_raw for item in outputs if item.post_ptr_raw is not None], axis=0) if self.ptr_enabled else None
        diagnostics = self.diagnostics()
        diagnostics.update({"frames": len(outputs), "sample_count": int(raw.shape[0])})
        return EngineAudioBlock(raw, monitor, diagnostics, post_ptr)

    def process_with_trace(self, vehicle_state_block: Mapping[str, np.ndarray], external_transient: np.ndarray | None = None) -> EngineAudioBlock:
        """Process frames while retaining block-rate diagnostic evidence."""
        arrays = {name: np.asarray(vehicle_state_block[name], dtype=np.float64) for name in ("rpm", "load", "throttle", "acceleration_mps2")}
        if any(value.ndim != 1 for value in arrays.values()) or len({value.size for value in arrays.values()}) != 1 or arrays["rpm"].size == 0:
            raise ValueError("vehicle state block must contain equal nonempty one-dimensional arrays")
        if not all(np.all(np.isfinite(value)) for value in arrays.values()):
            raise ValueError("vehicle state block must be finite")
        transient = self._validate_external_transient(external_transient, arrays["rpm"].size)
        outputs: list[EngineAudioBlock] = []
        trace = {"phase_rad": [], "omega_rad_s": [], "event_count": [], "afterfire_event_count": [], "combustion_torque_event_count": [], "path_state_energy": [], "monitor_gain_db": [], "sample_counter": []}
        for index in range(arrays["rpm"].size):
            segment = transient[index * self.block_size : (index + 1) * self.block_size] if transient is not None else None
            outputs.append(self._process_frame({name: float(value[index]) for name, value in arrays.items()}, segment))
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

    def _header_attenuation_tilt(self, entity: int, source: np.ndarray, attenuation: float) -> np.ndarray:
        """One-pole tilt so per-path attenuation spread moves mid-band/roughness, not only SHA."""
        pole = float(np.clip(0.10 + 0.82 * float(attenuation), 0.05, 0.97))
        x = np.asarray(source, dtype=np.float64)
        y, zf = lfilter([pole], [1.0, pole - 1.0], x, zi=[self._path_filter_state[entity]])
        self._path_filter_state[entity] = float(zf[0])
        return y

    def _validate_external_transient(self, value: np.ndarray | None, frame_count: int) -> np.ndarray | None:
        if value is None:
            return None
        array = np.asarray(value, dtype=np.float64)
        if array.shape != (frame_count * self.block_size, 2) or not np.all(np.isfinite(array)):
            raise ValueError("external transient must be finite stereo and frame aligned")
        return array

    def _process_frame(self, state: Mapping[str, float], external_transient: np.ndarray | None = None) -> EngineAudioBlock:
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
        frame_start = self.sample_counter
        self._schedule_afterfire(state, phase_block.phase_rad, n)
        self._emit_due_afterfires(frame_start, n)
        banks = np.zeros((self.bank_count, n), dtype=np.float64)
        bank_assignment = list(unwrap(self.config, "bank_assignment"))
        entity_sources: list[np.ndarray] = []
        for entity, line in enumerate(self._path_lines):
            source = self._event_tails[entity][:n].copy()
            self._event_tails[entity][:-n] = self._event_tails[entity][n:]
            self._event_tails[entity][-n:] = 0.0
            tilted = self._header_attenuation_tilt(entity, source, float(line.attenuation))
            entity_sources.append(tilted * float(line.attenuation))
            if self.waveguide_network is None:
                banks[int(bank_assignment[entity])] += line.process(tilted)
        collector_inputs = banks
        if self.waveguide_network is not None:
            collector_inputs = self.waveguide_network.process(np.asarray(entity_sources, dtype=np.float64)).bank_audio.copy()
            if collector_inputs.shape[0] < self.bank_count:
                collector_inputs = np.pad(collector_inputs, ((0, self.bank_count - collector_inputs.shape[0]), (0, 0)))
        collector_topology = str(unwrap(self.config, "collector_assignment"))
        self._parameter_consumption["collector_assignment"] = True
        if collector_topology == "central_first":
            merged = np.sum(collector_inputs, axis=0, keepdims=True)
            collector_inputs = np.repeat(merged, self.bank_count, axis=0) * 0.5
        elif collector_topology in {"single_collector", "single_collector_then_central"}:
            merged = np.sum(collector_inputs, axis=0, keepdims=True)
            collector_inputs = np.zeros_like(collector_inputs)
            collector_inputs[0] = merged[0]
        elif collector_topology != "two_bank_then_central":
            # Explicit identity fallback for legacy labels, recorded below.
            collector_topology = "identity_default"
        for bank, tail in enumerate(self._collector_event_tails):
            collector_inputs[bank] += self._consume(tail, n)
        collector = np.zeros_like(collector_inputs)
        for bank, line in enumerate(self._collector_lines):
            collector[bank] = line.process(collector_inputs[bank])
        central = self._central_collector_line.process(self._consume(self._central_collector_event_tail, n))
        self._collector_pressure = float(np.max(np.abs(collector_inputs))) if collector_inputs.size else 0.0
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
        if self.forced_induction_model == "timbre_map_v1":
            inertia = max(float(unwrap(self.config, "crank_inertia")), 0.01)
            target_inertia = float(np.mean((load + boost_state) * 0.5))
            self._timbre_inertia_state += (target_inertia - self._timbre_inertia_state) / (1.0 + 8.0 * inertia)
            forced = render_timbre_map(phase, rpm, load, boost_state, throttle, self.config, self.sample_counter, inertia_state=self._timbre_inertia_state)
        else:
            forced = render_forced_induction(phase, rpm, load, throttle, self.config, self.sample_rate_hz, boost_state=boost_state)
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
        mechanical = (
            0.010 * np.sin(phase * 6.0 + 0.2) * (0.35 + 0.65 * load)
            + 0.003 * phase_block.torque_ripple
            + 0.045 * omega_ripple / max(float(np.mean(np.abs(rpm)) * 2.0 * np.pi / 60.0), 1.0)
        )
        raw = np.column_stack((0.55 * combustion_left + 0.72 * forced["blower"][:, 0] + 0.62 * forced["turbo"][:, 0] + 0.30 * forced["blowoff"][:, 0] + 0.54 * forced["intake"][:, 0] + 0.40 * mechanical, 0.55 * combustion_right + 0.72 * forced["blower"][:, 1] + 0.62 * forced["turbo"][:, 1] + 0.30 * forced["blowoff"][:, 1] + 0.54 * forced["intake"][:, 1] + 0.33 * mechanical))
        if self._cycle_sync is not None:
            raw = raw + 0.35 * self._cycle_sync.render(phase, rpm)
        if self._transient_mixer is not None:
            residual, counts = self._transient_mixer.render_block(n, float(state["throttle"]), float(state["rpm"]), float(boost_state[-1]) if boost_state.size else 0.0, n / self.sample_rate_hz)
            raw = raw + residual
            self._transient_counts = counts
        if external_transient is not None:
            raw += external_transient
        if self._audio_chain is not None:
            raw = self._audio_chain.process(raw)
        if self._attack_mix > 0.0:
            raw = raw + self._attack_mix * self._attack_band_state.process(raw)
        self._parameter_consumption["transfer_ir"] = True
        raw = self._transfer_ir.process(raw)
        boundary_jump = float(np.max(np.abs(raw[0] - self._last_output_sample))) if raw.size else 0.0
        self._click_max_boundary_jump = max(self._click_max_boundary_jump, boundary_jump)
        self._click_sum_sq += boundary_jump * boundary_jump
        self._click_count += 1
        self._last_output_sample = raw[-1].copy()
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
        mixes = self.config.get("timbre_mixes") or {}
        def _mix_tau(name: str) -> float | None:
            node = mixes.get(name)
            value = node["value"] if isinstance(node, dict) and "value" in node else node
            if value is None:
                return None
            seconds = float(value)
            return max(seconds, 1.0e-4) if seconds > 0.0 else None
        attack = _mix_tau("boost_attack_s")
        release = _mix_tau("boost_release_s")
        if attack is not None:
            rise_tau = attack
        if release is not None:
            fall_tau = release
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
        if d_throttle < -0.8:
            self._afterfire_lift_remaining = 5
        lift_active = (d_throttle < -0.8) or (self._afterfire_lift_remaining > 0)
        if self._afterfire_lift_remaining > 0:
            self._afterfire_lift_remaining -= 1
        reservoir_node = self.config.get("afterfire", {}).get("fuel_reservoir_rate") if isinstance(self.config.get("afterfire"), Mapping) else None
        reservoir_rate = reservoir_node.get("value", 0.72) if isinstance(reservoir_node, Mapping) else 0.72
        self._afterfire_fuel_reservoir = max(0.0, 0.995 * self._afterfire_fuel_reservoir + float(reservoir_rate) * float(state["load"]))
        self._afterfire_temperature = 120.0 + 780.0 * np.clip(float(state["rpm"]) / 6500.0, 0.0, 1.0) * (0.55 + 0.45 * float(state["load"]))
        self._afterfire_cooldown_remaining = max(0, self._afterfire_cooldown_remaining - n)
        oxygen = np.clip(0.82 - 0.48 * float(state["load"]) + 0.15 * (1.0 - float(state["throttle"])), 0.0, 1.0)
        eligible = lift_active and d_rpm < -10.0 and float(state["rpm"]) >= float(unwrap(self.config, "afterfire.minimum_rpm")) and float(state["load"]) >= 0.35 and float(state["throttle"]) <= 0.18 and self._afterfire_temperature >= float(unwrap(self.config, "afterfire.minimum_temperature_c")) and self._afterfire_fuel_reservoir >= 0.2 and oxygen >= 0.15 and self._afterfire_cooldown_remaining == 0
        if not eligible:
            return
        delay_s = float(unwrap(self.config, "afterfire.ignition_delay_s")) + 0.000001 * float(state["rpm"])
        if self.jitter_fraction:
            delay_s *= 1.0 + float(self._rng.uniform(-self.jitter_fraction, self.jitter_fraction))
        delay_samples_exact = max(0.0, delay_s * self.sample_rate_hz)
        delay_samples = int(round(delay_samples_exact))
        pressure_factor = self._pressure_to_energy(self._collector_pressure)
        energy = float(unwrap(self.config, "afterfire.gain")) * (0.65 + 0.35 * min(1.0, float(state["load"]))) * pressure_factor
        policy = self.afterfire_location_policy
        if policy == "collector":
            policy = "bank_collector"
        if policy not in {"primary", "bank_collector", "central_collector"}:
            raise ValueError("afterfire_location_policy must be primary, bank_collector, central_collector or collector")
        if len(self._afterfire_pending_events) >= 64:
            self._afterfire_dropped_events += 1
            return
        source_entity = self._afterfire_entity(phase)
        self._afterfire_sequence += 1
        scheduled_sample_exact = self.sample_counter + delay_samples_exact
        scheduled_sample = self.sample_counter + delay_samples
        path_line = self.waveguide_network.guides[source_entity] if self.waveguide_network is not None else self._path_lines[source_entity]
        path_delay = path_line.delay_samples
        path_delay_exact = path_line.delay_samples_exact
        if policy == "primary":
            path_id = f"primary_path_{source_entity}"
            bank_id = int(unwrap(self.config, "bank_assignment")[source_entity])
            collector_delay = self._collector_lines[bank_id]
            arrival_exact = scheduled_sample_exact + path_delay_exact + collector_delay.delay_samples_exact
            arrival = scheduled_sample + path_delay + collector_delay.delay_samples
        elif policy == "bank_collector":
            bank_id = int(unwrap(self.config, "bank_assignment")[source_entity])
            path_id = f"bank_collector_{bank_id}"
            collector_delay = self._collector_lines[bank_id]
            arrival_exact = scheduled_sample_exact + collector_delay.delay_samples_exact
            arrival = scheduled_sample + collector_delay.delay_samples
        else:
            path_id = "central_collector"
            bank_id = None
            arrival_exact = scheduled_sample_exact + self._central_collector_line.delay_samples_exact
            arrival = scheduled_sample + self._central_collector_line.delay_samples
        arrival_sample_index = int(np.ceil(arrival_exact))
        self._afterfire_pending_events.append({"scheduled_sample": int(scheduled_sample), "scheduled_sample_exact": float(scheduled_sample_exact), "sequence": self._afterfire_sequence, "energy": energy, "pressure_energy_factor": pressure_factor, "route": policy, "entity": source_entity, "bank_id": bank_id, "path_id": path_id, "arrival_samples": arrival_sample_index - 1, "arrival_sample_index": arrival_sample_index, "arrival_samples_exact": float(arrival_exact), "collector_pressure": float(self._collector_pressure)})
        self._afterfire_pending_events.sort(key=lambda event: (event["scheduled_sample"], event["sequence"]))
        self._afterfire_location_counts[policy] += 1
        if policy == "bank_collector":
            self._afterfire_location_counts["collector"] += 1
        self._last_afterfire_route = dict(self._afterfire_pending_events[-1])
        self._last_afterfire_route.pop("sequence", None)
        self._last_afterfire_route["route"] = policy
        if policy == "primary":
            path_delay = self.waveguide_network.guides[0].delay_samples if self.waveguide_network is not None else self._path_lines[0].delay_samples
        self._afterfire_event_count += 1
        self._afterfire_cooldown_remaining = int(round(float(unwrap(self.config, "afterfire.cooldown_s")) * self.sample_rate_hz))

    def _afterfire_entity(self, phase: np.ndarray) -> int:
        phases = np.asarray(derive_event_phase_deg(self.config), dtype=np.float64)
        cycle = cycle_degrees(self.config)
        current = float(phase[-1] * 180.0 / np.pi) % cycle
        distance = np.abs((current - phases + 0.5 * cycle) % cycle - 0.5 * cycle)
        return int(np.argmin(distance))

    @staticmethod
    def _pressure_to_energy(pressure: float) -> float:
        """Bounded synthetic pressure-to-afterfire energy map (v1)."""
        normalized = np.clip(float(pressure), 0.0, 4.0)
        return float(0.55 + 0.45 * normalized / (normalized + 0.20))

    def _emit_due_afterfires(self, frame_start: int, block_size: int) -> None:
        """Materialize queued afterfires at absolute sample positions."""
        frame_end = frame_start + block_size
        due = [event for event in self._afterfire_pending_events if event["scheduled_sample"] < frame_end]
        self._afterfire_pending_events = [event for event in self._afterfire_pending_events if event["scheduled_sample"] >= frame_end]
        for event in due:
            offset = max(0, int(event["scheduled_sample"]) - frame_start)
            packet = render_event_packet(self.sample_rate_hz, 0.05, 0.002, 0.018, float(event["energy"]), 0.25).pressure
            if event["route"] == "primary":
                self._place(self._event_tails[int(event["entity"])], offset, packet)
            elif event["route"] == "bank_collector":
                self._place(self._collector_event_tails[int(event["bank_id"] or 0)], offset, packet)
            else:
                self._place(self._central_collector_event_tail, offset, packet)
            self._last_afterfire_route = {key: value for key, value in event.items() if key != "sequence"}

    def _monitor(self, raw: np.ndarray) -> np.ndarray:
        rms = float(np.sqrt(np.mean(np.square(raw))))
        self._monitor_gain_db = float(np.clip(self._monitor_gain_db, self._monitor_max_attenuation_db, self._monitor_max_makeup_db))
        desired = float(np.clip(20.0 * np.log10(self._monitor_target_rms / max(rms, 1.0e-9)), self._monitor_max_attenuation_db, self._monitor_max_makeup_db))
        time_constant = self._monitor_attack_s if desired > self._monitor_gain_db else self._monitor_release_s
        alpha = 1.0 - np.exp(-self.block_size / (time_constant * self.sample_rate_hz)) if time_constant > 0.0 else 1.0
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
            "afterfire_lift_remaining": self._afterfire_lift_remaining,
            "afterfire_pending_events": copy.deepcopy(self._afterfire_pending_events),
            "afterfire_sequence": self._afterfire_sequence,
            "afterfire_dropped_events": self._afterfire_dropped_events,
            "collector_pressure": self._collector_pressure,
            "afterfire_pressure_energy_map": {"version": "s12.stage_w.pressure_energy.v1", "pressure_source": "measured_collector_path", "mapping": "0.55+0.45*p/(p+0.20)", "provenance": "bounded_synthetic_engineering_mapping"},
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
            "last_output_sample": self._last_output_sample.copy(),
            "click_max_boundary_jump": self._click_max_boundary_jump,
            "click_sum_sq": self._click_sum_sq,
            "click_count": self._click_count,
            "ptr": self.ptr.snapshot() if self.ptr is not None else None,
            "waveguide": self.waveguide_network.snapshot() if self.waveguide_network is not None else None,
            "teacher_response": self.teacher_response.snapshot() if self.teacher_response is not None else None,
            "transfer_ir": self._transfer_ir.snapshot(),
            "parameter_consumption": dict(self._parameter_consumption),
            "parameter_fallbacks": copy.deepcopy(self._parameter_fallbacks),
            "timbre_inertia_state": self._timbre_inertia_state,
            "click_contract": dict(self._click_contract),
            "random_seed": self.random_seed,
            "jitter_fraction": self.jitter_fraction,
            "rng_state": copy.deepcopy(self._rng.bit_generator.state),
        }

    def restore_state(self, snapshot: Mapping[str, Any]) -> None:
        state = self._validate_restore_snapshot(snapshot)
        self.sample_counter = state["sample_counter"]
        self.pll.phase_rad, self.pll.omega_rad_s, self.pll.initialized, self.pll.sample_count = state["pll"]
        self._pending_combustion_torque = state["pending_combustion_torque"]
        for name in (
            "last_rpm", "last_throttle", "last_load", "boost_state", "bov_state", "blower_phase", "turbo_phase",
            "afterfire_fuel_reservoir", "afterfire_temperature", "collector_pressure", "monitor_gain_db",
            "omega_ripple_sum_sq", "click_max_boundary_jump", "click_sum_sq", "timbre_inertia_state",
        ):
            setattr(self, f"_{name}", state[name])
        for name in ("bov_event_count", "afterfire_cooldown_remaining", "afterfire_lift_remaining", "event_count", "afterfire_event_count", "combustion_torque_event_count", "omega_ripple_sample_count", "afterfire_sequence", "afterfire_dropped_events", "click_count"):
            setattr(self, f"_{name}", state[name])
        self._afterfire_location_counts = state["afterfire_location_counts"]
        self._last_afterfire_route = state["afterfire_route"]
        self._afterfire_pending_events = state["afterfire_pending_events"]
        self._event_tails = state["event_tails"]
        self._collector_event_tails = state["collector_event_tails"]
        self._central_collector_event_tail = state["central_collector_event_tail"]
        for line, (history, counter) in zip(self._path_lines, state["path_lines"]):
            line.history, line.sample_counter = history, counter
        for line, (history, counter) in zip(self._collector_lines, state["collector_lines"]):
            line.history, line.sample_counter = history, counter
        self._central_collector_line.history, self._central_collector_line.sample_counter = state["central_collector_line"]
        self.afterfire_location_policy = state["afterfire_location_policy"]
        self._last_output_sample = state["last_output_sample"]
        self._parameter_consumption = state["parameter_consumption"]
        self._parameter_fallbacks = state["parameter_fallbacks"]
        self._click_contract = state["click_contract"]
        self._click_threshold = float(self._click_contract["threshold"])
        self._transfer_ir.state = state["transfer_ir"]
        if self.ptr is not None:
            for adapter, adapter_state, upstream, downstream in state["ptr"]:
                adapter._x0, adapter._x1 = adapter_state["x0"], adapter_state["x1"]
                adapter._upstream.clear(); adapter._upstream.extend(upstream)
                adapter._downstream.clear(); adapter._downstream.extend(downstream)
        if self.waveguide_network is not None:
            for guide, guide_state in zip(self.waveguide_network.guides, state["waveguide"]):
                guide._forward.history, guide._forward.sample_counter = guide_state["forward"]
                guide._round_trip.history, guide._round_trip.sample_counter = guide_state["round_trip"]
                guide._frequency_loss.state = guide_state["frequency_loss"]
                guide.sample_counter = guide_state["sample_counter"]
        if self.teacher_response is not None:
            self.teacher_response._state = state["teacher_response"]
        self._rng.bit_generator.state = state["rng_state"]

    def _validate_restore_snapshot(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        required = {
            "schema_version", "sample_counter", "pll", "pending_combustion_torque", "last_rpm", "last_throttle", "last_load",
            "afterfire_fuel_reservoir", "afterfire_temperature", "afterfire_cooldown_remaining", "afterfire_lift_remaining", "afterfire_pending_events",
            "afterfire_sequence", "afterfire_dropped_events", "collector_pressure", "afterfire_pressure_energy_map", "event_count",
            "afterfire_event_count", "afterfire_location_counts", "afterfire_route", "combustion_torque_event_count", "boost_state",
            "bov_state", "bov_event_count", "blower_phase", "turbo_phase", "omega_ripple_sum_sq", "omega_ripple_sample_count",
            "event_tails", "collector_event_tails", "central_collector_event_tail", "path_lines", "collector_lines", "central_collector_line",
            "afterfire_location_policy", "monitor_gain_db", "last_output_sample", "click_max_boundary_jump", "click_sum_sq", "click_count",
            "ptr", "waveguide", "teacher_response", "transfer_ir", "parameter_consumption", "parameter_fallbacks", "timbre_inertia_state",
            "click_contract", "random_seed", "jitter_fraction", "rng_state",
        }
        snapshot = _mapping(snapshot, "persistent engine snapshot")
        if set(snapshot) != required:
            raise ValueError("persistent engine snapshot fields are incomplete or unexpected")
        if snapshot["schema_version"] != "s12.stage_w.persistent_engine_state.v1":
            raise ValueError("unsupported persistent engine snapshot")
        sample_counter = _counter(snapshot["sample_counter"], "sample_counter")
        pll = _mapping(snapshot["pll"], "PLL snapshot")
        if set(pll) != {"phase_rad", "omega_rad_s", "initialized", "sample_count"}:
            raise ValueError("PLL snapshot fields differ from topology")
        phase = _finite_scalar(pll["phase_rad"], "PLL phase_rad")
        omega = _finite_scalar(pll["omega_rad_s"], "PLL omega_rad_s")
        if type(pll["initialized"]) is not bool:
            raise ValueError("PLL initialized must be boolean")
        pll_count = _counter(pll["sample_count"], "PLL sample_count")
        if pll_count != sample_counter:
            raise ValueError("PLL and engine sample counters differ")
        pending_value = snapshot["pending_combustion_torque"]
        try:
            pending_array = np.asarray(pending_value)
        except (TypeError, ValueError):
            raise ValueError("pending combustion torque must be a finite array") from None
        if pending_array.ndim == 0:
            pending_scalar = _finite_scalar(pending_value, "pending combustion torque")
            pending = np.zeros_like(self._pending_combustion_torque)
            pending[: self.block_size] = pending_scalar
        else:
            pending = _finite_array(pending_value, self._pending_combustion_torque.shape, "pending combustion torque")
        state: dict[str, Any] = {"sample_counter": sample_counter, "pll": (phase, omega, pll["initialized"], pll_count), "pending_combustion_torque": pending}
        for name in ("last_rpm", "last_throttle", "last_load", "boost_state", "bov_state", "blower_phase", "turbo_phase", "afterfire_fuel_reservoir", "afterfire_temperature", "collector_pressure", "monitor_gain_db", "omega_ripple_sum_sq", "click_max_boundary_jump", "click_sum_sq", "timbre_inertia_state"):
            state[name] = _finite_scalar(snapshot[name], name)
        for name in ("bov_event_count", "afterfire_cooldown_remaining", "afterfire_lift_remaining", "event_count", "afterfire_event_count", "combustion_torque_event_count", "omega_ripple_sample_count", "afterfire_sequence", "afterfire_dropped_events", "click_count"):
            state[name] = _counter(snapshot[name], name)
        counts = _mapping(snapshot["afterfire_location_counts"], "afterfire location counts")
        if set(counts) != {"primary", "collector", "bank_collector", "central_collector"}:
            raise ValueError("afterfire location count topology differs")
        state["afterfire_location_counts"] = {key: _counter(counts[key], f"afterfire location count {key}") for key in counts}
        state["afterfire_route"] = self._validate_afterfire_route(snapshot["afterfire_route"])
        pending_events = snapshot["afterfire_pending_events"]
        if not isinstance(pending_events, list) or len(pending_events) > 64:
            raise ValueError("afterfire queue capacity differs from topology")
        state["afterfire_pending_events"] = [self._validate_afterfire_event(event) for event in pending_events]
        sequences = [event["sequence"] for event in state["afterfire_pending_events"]]
        if any(sequence <= 0 for sequence in sequences) or len(sequences) != len(set(sequences)):
            raise ValueError("afterfire event sequences must be unique positive integers")
        if sequences and max(sequences) > state["afterfire_sequence"]:
            raise ValueError("afterfire event sequence exceeds sequence counter")
        for event in state["afterfire_pending_events"]:
            if event["scheduled_sample"] < sample_counter:
                raise ValueError("pending afterfire event is scheduled before engine counter")
            if event["scheduled_sample_exact"] < sample_counter:
                raise ValueError("pending afterfire exact schedule is before engine counter")
            if event["arrival_samples_exact"] < event["scheduled_sample_exact"]:
                raise ValueError("afterfire exact arrival precedes scheduled sample")
            if event["arrival_sample_index"] < event["scheduled_sample"] or event["arrival_samples"] + 1 < event["scheduled_sample"]:
                raise ValueError("afterfire arrival precedes scheduled sample")
        if state["afterfire_pending_events"] != sorted(state["afterfire_pending_events"], key=lambda event: (event["scheduled_sample"], event["sequence"])):
            raise ValueError("afterfire queue order differs from topology")
        pressure_map = _mapping(snapshot["afterfire_pressure_energy_map"], "afterfire pressure map")
        expected_map = {"version": "s12.stage_w.pressure_energy.v1", "pressure_source": "measured_collector_path", "mapping": "0.55+0.45*p/(p+0.20)", "provenance": "bounded_synthetic_engineering_mapping"}
        if dict(pressure_map) != expected_map:
            raise ValueError("afterfire pressure map differs from topology")
        for name, expected_count in (("event_tails", len(self._event_tails)), ("collector_event_tails", len(self._collector_event_tails))):
            tails = snapshot[name]
            if not isinstance(tails, list) or len(tails) != expected_count:
                raise ValueError(f"{name} topology differs from snapshot")
            state[name] = [_finite_array(tail, self._event_tails[0].shape, name) for tail in tails]
        state["central_collector_event_tail"] = _finite_array(snapshot["central_collector_event_tail"], self._central_collector_event_tail.shape, "central collector event tail")
        for name, lines in (("path_lines", self._path_lines), ("collector_lines", self._collector_lines)):
            saved = snapshot[name]
            if not isinstance(saved, list) or len(saved) != len(lines):
                label = "path line" if name == "path_lines" else "collector line"
                raise ValueError(f"{label} topology differs from snapshot")
            state[name] = [line._validate(item) for line, item in zip(lines, saved)]
        state["central_collector_line"] = self._central_collector_line._validate(snapshot["central_collector_line"])
        policy = snapshot["afterfire_location_policy"]
        if not isinstance(policy, str) or policy not in {"primary", "bank_collector", "central_collector"}:
            raise ValueError("afterfire location policy differs from topology")
        state["afterfire_location_policy"] = policy
        state["last_output_sample"] = _finite_array(snapshot["last_output_sample"], (2,), "last output sample")
        state["ptr"] = self._validate_optional_component(snapshot["ptr"], self.ptr, "ptr")
        state["waveguide"] = self._validate_optional_component(snapshot["waveguide"], self.waveguide_network, "waveguide")
        state["teacher_response"] = self._validate_optional_component(snapshot["teacher_response"], self.teacher_response, "teacher response")
        state["transfer_ir"] = self._transfer_ir._validate_state(snapshot["transfer_ir"])
        consumption = _mapping(snapshot["parameter_consumption"], "parameter consumption")
        if set(consumption) != {"collector_assignment", "transfer_ir", "crankpin_geometry", "rotor_geometry"} or any(type(value) is not bool for value in consumption.values()) or dict(consumption) != self._parameter_consumption:
            raise ValueError("parameter consumption differs from topology")
        state["parameter_consumption"] = dict(consumption)
        fallbacks = _mapping(snapshot["parameter_fallbacks"], "parameter fallbacks")
        if set(fallbacks) != set(self._parameter_fallbacks):
            raise ValueError("parameter fallback topology differs")
        for key, fallback in fallbacks.items():
            fallback = _mapping(fallback, f"parameter fallback {key}")
            if set(fallback) != {"value", "reason", "provenance"} or not isinstance(fallback["value"], str) or not isinstance(fallback["reason"], str) or not isinstance(fallback["provenance"], str):
                raise ValueError("parameter fallback fields differ from topology")
        if dict(fallbacks) != self._parameter_fallbacks:
            raise ValueError("parameter fallback values differ from topology")
        state["parameter_fallbacks"] = copy.deepcopy(dict(fallbacks))
        contract = _mapping(snapshot["click_contract"], "click contract")
        if set(contract) != set(self._click_contract) or any(contract[key] != self._click_contract[key] for key in contract if key != "threshold") or _finite_scalar(contract["threshold"], "click threshold") != self._click_threshold:
            raise ValueError("click contract differs from topology")
        state["click_contract"] = dict(contract)
        if type(snapshot["random_seed"]) is not int or snapshot["random_seed"] != self.random_seed:
            raise ValueError("random seed differs from topology")
        jitter = _finite_scalar(snapshot["jitter_fraction"], "jitter_fraction")
        if not 0.0 <= jitter <= 0.25 or jitter != self.jitter_fraction:
            raise ValueError("jitter fraction differs from topology")
        rng = np.random.default_rng(self.random_seed)
        try:
            rng.bit_generator.state = copy.deepcopy(snapshot["rng_state"])
        except (TypeError, ValueError, KeyError, OverflowError):
            raise ValueError("RNG state differs from topology") from None
        state["rng_state"] = copy.deepcopy(rng.bit_generator.state)
        return state

    def _validate_optional_component(self, snapshot: Any, component: Any, name: str) -> Any:
        if component is None:
            if snapshot is not None:
                raise ValueError(f"unexpected {name} component state")
            return None
        if snapshot is None:
            raise ValueError(f"missing active {name} component state")
        if name == "ptr":
            return self.ptr._validate_snapshot(snapshot)
        if name == "waveguide":
            return self.waveguide_network._validate_snapshot(snapshot)
        return self.teacher_response._validate(snapshot)

    def _validate_afterfire_event(self, event: Any) -> dict[str, Any]:
        event = _mapping(event, "afterfire event")
        required = {"scheduled_sample", "scheduled_sample_exact", "sequence", "energy", "pressure_energy_factor", "route", "entity", "bank_id", "path_id", "arrival_samples", "arrival_sample_index", "arrival_samples_exact", "collector_pressure"}
        if set(event) != required:
            raise ValueError("afterfire event fields differ from topology")
        result = dict(event)
        for name in ("scheduled_sample", "sequence", "entity", "arrival_samples", "arrival_sample_index"):
            result[name] = _counter(event[name], f"afterfire event {name}")
        for name in ("scheduled_sample_exact", "energy", "pressure_energy_factor", "arrival_samples_exact", "collector_pressure"):
            result[name] = _finite_scalar(event[name], f"afterfire event {name}")
        if not isinstance(event["route"], str) or event["route"] not in {"primary", "bank_collector", "central_collector"}:
            raise ValueError("afterfire event route differs from topology")
        result["route"] = event["route"]
        if result["entity"] >= self.entity_count:
            raise ValueError("afterfire event entity differs from topology")
        assignment = list(unwrap(self.config, "bank_assignment"))
        expected_bank = int(assignment[result["entity"]])
        if event["route"] == "central_collector":
            if event["bank_id"] is not None or event["path_id"] != "central_collector":
                raise ValueError("central afterfire event topology differs")
        elif event["route"] == "primary":
            if event["bank_id"] is None or event["path_id"] != f"primary_path_{result['entity']}" :
                raise ValueError("primary afterfire event topology differs")
        elif event["bank_id"] is None or event["path_id"] != f"bank_collector_{event['bank_id']}" :
            raise ValueError("bank afterfire event topology differs")
        if event["bank_id"] is not None:
            result["bank_id"] = _counter(event["bank_id"], "afterfire event bank_id")
            if result["bank_id"] >= self.bank_count:
                raise ValueError("afterfire event bank_id differs from topology")
            if result["bank_id"] != expected_bank:
                raise ValueError("afterfire event bank assignment differs from topology")
        if not isinstance(event["path_id"], str):
            raise ValueError("afterfire event path_id differs from topology")
        return result

    def _validate_afterfire_route(self, route: Any) -> dict[str, Any]:
        route = _mapping(route, "afterfire route")
        allowed = {"route", "path_id", "bank_id", "collector_pressure", "arrival_samples", "arrival_sample_index", "arrival_samples_exact", "scheduled_sample", "scheduled_sample_exact", "sequence", "energy", "pressure_energy_factor", "entity"}
        required = {"route", "path_id", "bank_id", "collector_pressure", "arrival_samples", "arrival_sample_index", "arrival_samples_exact"}
        if not set(route) <= allowed or not required <= set(route):
            raise ValueError("afterfire route fields differ from topology")
        result = dict(route)
        if not isinstance(route["route"], str) or route["route"] not in {"none", "primary", "bank_collector", "central_collector"}:
            raise ValueError("afterfire route differs from topology")
        base = {"route", "path_id", "bank_id", "collector_pressure", "arrival_samples", "arrival_sample_index", "arrival_samples_exact"}
        event_fields = base | {"scheduled_sample", "scheduled_sample_exact", "sequence", "energy", "pressure_energy_factor", "entity"}
        if set(route) != base and set(route) != event_fields - {"sequence"}:
            raise ValueError("afterfire route fields differ from topology")
        if route["route"] == "none":
            if set(route) != base or any(route[key] is not None for key in ("path_id", "bank_id", "arrival_samples", "arrival_sample_index", "arrival_samples_exact")):
                raise ValueError("empty afterfire route is malformed")
        elif any(route[key] is None for key in ("path_id", "arrival_samples", "arrival_sample_index", "arrival_samples_exact")):
            raise ValueError("afterfire route requires arrival fields")
        elif any(route.get(key) is None for key in ("scheduled_sample", "scheduled_sample_exact", "energy", "pressure_energy_factor")):
            raise ValueError("afterfire route requires complete schedule and energy fields")
        result["collector_pressure"] = _finite_scalar(route["collector_pressure"], "afterfire route collector_pressure")
        for name in ("arrival_samples_exact", "scheduled_sample_exact", "energy", "pressure_energy_factor"):
            if name in route and route[name] is not None:
                result[name] = _finite_scalar(route[name], f"afterfire route {name}")
        for name in ("arrival_samples", "arrival_sample_index", "scheduled_sample", "sequence", "entity"):
            if name in route and route[name] is not None:
                result[name] = _counter(route[name], f"afterfire route {name}")
        if route.get("path_id") is not None and not isinstance(route["path_id"], str):
            raise ValueError("afterfire route path_id differs from topology")
        if route.get("bank_id") is not None:
            result["bank_id"] = _counter(route["bank_id"], "afterfire route bank_id")
            if result["bank_id"] >= self.bank_count:
                raise ValueError("afterfire route bank_id differs from topology")
        if route["route"] != "none":
            entity = route.get("entity")
            if entity is None:
                raise ValueError("afterfire route requires entity")
            entity = _counter(entity, "afterfire route entity")
            result["entity"] = entity
            if entity >= self.entity_count:
                raise ValueError("afterfire route entity differs from topology")
            expected_bank = int(list(unwrap(self.config, "bank_assignment"))[entity])
            if route["route"] == "central_collector":
                if route["bank_id"] is not None or route["path_id"] != "central_collector":
                    raise ValueError("central afterfire route topology differs")
            elif route["bank_id"] != expected_bank:
                raise ValueError("afterfire route bank assignment differs from topology")
            expected_path = f"primary_path_{entity}" if route["route"] == "primary" else f"bank_collector_{route['bank_id']}"
            if route["route"] != "central_collector" and route["path_id"] != expected_path:
                raise ValueError("afterfire route path differs from topology")
            if route["arrival_sample_index"] < route["scheduled_sample"] or route["arrival_samples"] + 1 < route["scheduled_sample"] or route["arrival_samples_exact"] < route["scheduled_sample_exact"]:
                raise ValueError("afterfire route arrival precedes scheduled sample")
        return result

    def diagnostics(self) -> dict[str, Any]:
        return {
            "source_model": "event_domain_v1_hardened_persistent",
            "mode": self.mode,
            "path_model": self.path_model,
            "forced_induction_model": self.forced_induction_model,
            "cycle_sync_model": self.cycle_sync_model,
            "transient_model": self.transient_model,
            "audio_chain": self.audio_chain_model,
            "transient_shift_count": int(self._transient_counts.get("transient_shift_count", 0)),
            "transient_tip_in_count": int(self._transient_counts.get("transient_tip_in_count", 0)),
            "sample_counter": self.sample_counter,
            "event_count": self._event_count,
            "afterfire_event_count": self._afterfire_event_count,
            "afterfire_location_counts": dict(self._afterfire_location_counts),
            "afterfire_route": dict(self._last_afterfire_route),
            "afterfire_cooldown_remaining": self._afterfire_cooldown_remaining,
            "afterfire_pending_events": [
                {key: value for key, value in event.items() if key != "energy"}
                | {"energy": float(event["energy"])} for event in self._afterfire_pending_events
            ],
            "afterfire_dropped_events": self._afterfire_dropped_events,
            "collector_pressure": self._collector_pressure,
            "afterfire_pressure_energy_map": {"version": "s12.stage_w.pressure_energy.v1", "pressure_source": "measured_collector_path", "mapping": "0.55+0.45*p/(p+0.20)", "provenance": "bounded_synthetic_engineering_mapping"},
            "combustion_torque_event_count": self._combustion_torque_event_count,
            "boost_state": self._boost_state,
            "bov_state": self._bov_state,
            "bov_event_count": self._bov_event_count,
            "blower_phase": self._blower_phase,
            "turbo_phase": self._turbo_phase,
            "omega_ripple_rms": float(np.sqrt(self._omega_ripple_sum_sq / self._omega_ripple_sample_count)) if self._omega_ripple_sample_count else 0.0,
            "omega_ripple_sample_count": self._omega_ripple_sample_count,
            "click_metrics": {
                "max_boundary_jump": self._click_max_boundary_jump,
                "normalized_rms_boundary": float(np.sqrt(self._click_sum_sq / self._click_count)) if self._click_count else 0.0,
                "threshold": self._click_threshold,
                "passed": self._click_max_boundary_jump <= self._click_threshold,
                "definition": self._click_contract["definition"],
                "contract_version": self._click_contract["contract_version"],
                "provenance": self._click_contract["provenance"],
            },
            "state_memory_bytes": int(self._pending_combustion_torque.nbytes + sum(tail.nbytes for tail in self._event_tails) + sum(tail.nbytes for tail in self._collector_event_tails) + self._central_collector_event_tail.nbytes + sum(line.history.nbytes for line in self._path_lines) + sum(line.history.nbytes for line in self._collector_lines) + self._central_collector_line.history.nbytes),
            "ptr_status": "FROZEN_RUNTIME_PTR_ADAPTER" if self.ptr is not None else "NOT_CONNECTED",
            "ptr_provenance": self.ptr.provenance() if self.ptr is not None else None,
            "teacher_response": self.teacher_response.diagnostics() if self.teacher_response is not None else None,
            "parameter_consumption": dict(self._parameter_consumption),
            "parameter_fallbacks": copy.deepcopy(self._parameter_fallbacks),
            "timbre_inertia_state": self._timbre_inertia_state,
            "click_contract": dict(self._click_contract),
            "random_state": {"seed": self.random_seed, "jitter_fraction": self.jitter_fraction, "provenance": "bounded_local_pcg64_only"},
            "path_schedule": derive_event_path_schedule(self.config),
            "monitor_source": "PersistentEventDomainEngine.monitor_pcm",
            "collector_assignment": str(unwrap(self.config, "collector_assignment")),
            "transfer_ir": str(unwrap(self.config, "transfer_ir")),
            "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
        }


__all__ = ["EngineAudioBlock", "PersistentEventDomainEngine"]
