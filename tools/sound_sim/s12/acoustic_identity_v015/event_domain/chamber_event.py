"""Reduced pressure/blowdown event packets; deliberately not a CFD solver."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class EventPacket:
    pressure: np.ndarray
    blowdown_pressure: np.ndarray
    torque_impulse: np.ndarray
    exhaust_port_flow_proxy: np.ndarray

def render_event_packet(sample_rate_hz: int, duration_s: float, rise_time_s: float, decay_time_s: float, energy: float, blowdown_gain: float = 0.35) -> EventPacket:
    if sample_rate_hz <= 0 or duration_s <= 0 or rise_time_s <= 0 or decay_time_s <= 0 or energy < 0:
        raise ValueError("invalid event packet parameters")
    count = max(2, int(round(duration_s * sample_rate_hz)))
    t = np.arange(count, dtype=np.float64) / sample_rate_hz
    pressure = float(energy) * (1.0 - np.exp(-t / rise_time_s)) * np.exp(-t / decay_time_s)
    blowdown = float(energy) * float(blowdown_gain) * np.exp(-t / max(decay_time_s * 0.55, 1.0 / sample_rate_hz))
    blowdown[0] = 0.0
    total = pressure + blowdown
    torque = 0.12 * pressure
    flow = np.maximum(total, 0.0) + 0.20 * np.maximum(np.gradient(total), 0.0)
    return EventPacket(total, blowdown, torque, flow)
