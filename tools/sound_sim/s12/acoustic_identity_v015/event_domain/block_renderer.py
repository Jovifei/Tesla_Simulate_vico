"""Event-domain pressure renderer with state-preserving block boundaries."""
from __future__ import annotations
from typing import Mapping
import numpy as np
from ..contracts import SourceRender
from .afterfire_state import render_afterfire_events, schedule_afterfire
from .chamber_event import render_event_packet
from .collector_network import route_to_collectors
from .config_schema import unwrap, validate_config
from .crank_phase_pll import CrankPhasePLL
from .event_scheduler import schedule_events
from .forced_induction import render_forced_induction

def _audio_trace(trace: Mapping[str, np.ndarray], sample_rate_hz: int) -> dict[str, np.ndarray]:
    time_s = np.asarray(trace["time_s"], dtype=np.float64)
    if time_s.ndim != 1 or time_s.size < 2 or not np.all(np.diff(time_s) > 0.0):
        raise ValueError("trace time_s must be increasing")
    count = int(round((time_s[-1] - time_s[0]) * sample_rate_hz)) + 1
    target = np.arange(count, dtype=np.float64) / sample_rate_hz + time_s[0]
    result = {"time_s": target}
    for name in ("rpm", "load", "throttle", "acceleration_mps2"):
        values = np.asarray(trace[name], dtype=np.float64)
        result[name] = np.interp(target, time_s, values)
    if np.any(result["rpm"] < 0.0) or np.any(~np.isfinite(np.column_stack(tuple(result.values())))):
        raise ValueError("vehicle trace contains invalid values")
    return result

def _place(target: np.ndarray, index: int, packet: np.ndarray, scale: float) -> None:
    if index >= target.size:
        return
    end = min(target.size, index + packet.size)
    target[index:end] += packet[:end - index] * scale

def render_event_domain(trace: Mapping[str, np.ndarray], config: dict, sample_rate_hz: int = 48000, block_size: int = 960) -> SourceRender:
    config = validate_config(config)
    if sample_rate_hz <= 0 or block_size <= 0:
        raise ValueError("sample_rate_hz and block_size must be positive")
    state = _audio_trace(trace, sample_rate_hz)
    count = state["time_s"].size
    pll = CrankPhasePLL(sample_rate_hz, config)
    phase_parts, omega_parts, error_parts, ripple_parts = [], [], [], []
    load_torque_parts, friction_torque_parts, governor_torque_parts, combustion_torque_parts = [], [], [], []
    for start in range(0, count, block_size):
        end = min(count, start + block_size)
        block = pll.process_block(state["rpm"][start:end], state["load"][start:end], state["throttle"][start:end], state["acceleration_mps2"][start:end])
        phase_parts.append(block.phase_rad); omega_parts.append(block.omega_rad_s); error_parts.append(block.sync_error_rad_s); ripple_parts.append(block.torque_ripple)
        load_torque_parts.append(block.load_torque); friction_torque_parts.append(block.friction_torque); governor_torque_parts.append(block.idle_governor_torque); combustion_torque_parts.append(block.combustion_torque)
    phase = np.concatenate(phase_parts); omega = np.concatenate(omega_parts); sync_error = np.concatenate(error_parts); torque_ripple = np.concatenate(ripple_parts)
    load_torque = np.concatenate(load_torque_parts); friction_torque = np.concatenate(friction_torque_parts); governor_torque = np.concatenate(governor_torque_parts); combustion_torque = np.concatenate(combustion_torque_parts)
    events = schedule_events(phase, config, sample_rate_hz)
    entity_count = int(unwrap(config, "cylinder_or_rotor_count")); paths = np.zeros((entity_count, count)); blowdown_paths = np.zeros_like(paths); torque_paths = np.zeros_like(paths); flow_paths = np.zeros_like(paths)
    variation = float(unwrap(config, "cycle_variation")); rise = float(unwrap(config, "combustion_event.rise_time_s")); decay = float(unwrap(config, "combustion_event.decay_time_s")); base_energy = float(unwrap(config, "combustion_event.event_energy")); exponent = float(unwrap(config, "combustion_event.load_exponent")); blowdown_gain = float(unwrap(config, "blowdown_event")); rotary_width_scale = float(unwrap(config, "rotary_event_width_scale")) if config["architecture"] == "rotary_wankel" else 1.0; rotary_gain_scale = float(unwrap(config, "rotary_event_gain_scale")) if config["architecture"] == "rotary_wankel" else 1.0
    for event_number, (index, entity) in enumerate(zip(events.sample_index, events.entity_index)):
        local_load = float(state["load"][index]); local_throttle = float(state["throttle"][index])
        energy = base_energy * (0.28 + 0.72 * max(local_load, 0.0) ** exponent) * (0.70 + 0.30 * local_throttle)
        energy *= rotary_gain_scale * (1.0 + variation * np.sin((int(entity) + 1) * 1.71 + event_number * 0.37))
        packet = render_event_packet(sample_rate_hz, min(0.10, max(0.035, 3.5 * decay * rotary_width_scale)), rise * rotary_width_scale, decay * rotary_width_scale, energy, blowdown_gain)
        _place(paths[int(entity)], int(index), packet.pressure, 1.0); _place(blowdown_paths[int(entity)], int(index), packet.blowdown_pressure, 1.0); _place(torque_paths[int(entity)], int(index), packet.torque_impulse, 1.0); _place(flow_paths[int(entity)], int(index), packet.exhaust_port_flow_proxy, 1.0)
    banks = list(unwrap(config, "bank_assignment")); lengths = list(unwrap(config, "per_path_primary_length_m")); attenuations = list(unwrap(config, "per_path_attenuation")); temperature = float(unwrap(config, "gas_temperature_model")); collector_length = float(unwrap(config, "collector_length_m")); collector_loss = float(unwrap(config, "collector_loss"))
    routed = route_to_collectors(paths, banks, lengths, [-0.65, 0.65], sample_rate_hz, temperature, collector_length, collector_loss, attenuations); routed_blowdown = route_to_collectors(blowdown_paths, banks, lengths, [-0.65, 0.65], sample_rate_hz, temperature, collector_length, collector_loss, attenuations); routed_torque = route_to_collectors(torque_paths, banks, lengths, [-0.65, 0.65], sample_rate_hz, temperature, collector_length, collector_loss, attenuations); routed_flow = route_to_collectors(flow_paths, banks, lengths, [-0.65, 0.65], sample_rate_hz, temperature, collector_length, collector_loss, attenuations)
    afterfire = schedule_afterfire(state["time_s"], state["rpm"], state["load"], state["throttle"], np.gradient(state["rpm"]), config, sample_rate_hz); afterfire_mono = render_afterfire_events(afterfire, count, sample_rate_hz, config); afterfire_paths = np.zeros_like(paths)
    for event_number, index in enumerate(afterfire.sample_index):
        _place(afterfire_paths[event_number % entity_count], int(index), afterfire_mono[int(index):], 1.0)
    routed_afterfire = route_to_collectors(afterfire_paths, banks, lengths, [-0.65, 0.65], sample_rate_hz, temperature, collector_length, collector_loss, attenuations)
    forced = render_forced_induction(phase, state["rpm"], state["load"], state["throttle"], config, sample_rate_hz)
    mechanical_mono = 0.010 * np.sin(phase * 6.0 + 0.2) * (0.35 + 0.65 * state["load"]) + 0.003 * torque_ripple; mechanical = np.column_stack((mechanical_mono, 0.82 * mechanical_mono))
    housing = np.zeros_like(mechanical)
    if config["architecture"] == "rotary_wankel":
        housing_gain = float(unwrap(config, "housing_gain_scale")); housing_decay = float(unwrap(config, "housing_decay_scale")); order_mix = float(unwrap(config, "housing_order_mix")); envelope = 0.75 + 0.25 * np.exp(-np.arange(count, dtype=np.float64) / max(housing_decay * sample_rate_hz, 1.0)); housing_mono = housing_gain * envelope * (0.25 + state["load"]) * (np.sin(phase * 2.0) + order_mix * np.sin(phase * 7.0)); housing = np.column_stack((housing_mono, 0.88 * housing_mono))
    combustion = np.column_stack((routed.left, routed.right)); blowdown = np.column_stack((routed_blowdown.left, routed_blowdown.right)); torque = np.column_stack((routed_torque.left, routed_torque.right)); flow = np.column_stack((routed_flow.left, routed_flow.right)); afterfire_stereo = np.column_stack((routed_afterfire.left, routed_afterfire.right))
    pressure = 0.55 * combustion + 0.72 * forced["blower"] + 0.62 * forced["turbo"] + 0.30 * forced["blowoff"] + 0.54 * forced["intake"] + 0.40 * mechanical + 0.55 * housing + 0.95 * afterfire_stereo
    zero = np.zeros_like(pressure); left_bank = np.column_stack((routed.banks[0], routed.banks[0])) if routed.banks.size else zero; right_bank = np.column_stack((routed.banks[1], routed.banks[1])) if routed.banks.shape[0] > 1 else zero
    stems = {"combustion_pressure": combustion, "blowdown_pressure": blowdown, "torque_impulse": torque, "exhaust_port_flow_proxy": flow, "exhaust_left_bank": left_bank, "exhaust_right_bank": right_bank, "afterfire": afterfire_stereo, "blower": forced["blower"], "turbo": forced["turbo"], "blowoff": forced["blowoff"], "intake": forced["intake"], "mechanical": mechanical, "housing": housing}
    diagnostics = {"vehicle_id": config["vehicle_id"], "source_model": "event_domain_v1", "scope": "synthetic; uncalibrated; offline; not OEM reproduction", "event_count": events.count, "afterfire_event_count": afterfire.count, "wrong_condition_event_count": afterfire.wrong_condition_event_count, "event_trace": events, "afterfire_trace": afterfire, "path_delays_s": routed.path_delays_s, "phase_rad": phase, "omega_rad_s": omega, "sync_error_rad_s": sync_error, "torque_ripple": torque_ripple, "load_torque": load_torque, "friction_torque": friction_torque, "idle_governor_torque": governor_torque, "combustion_torque": combustion_torque}
    return SourceRender(pressure=pressure, stems=stems, diagnostics=diagnostics).validate()
