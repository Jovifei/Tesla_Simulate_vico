"""Physics-informed synthetic afterfire eligibility and event rendering."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from .config_schema import unwrap

@dataclass(frozen=True)
class AfterfireEvents:
    sample_index: np.ndarray
    energy: np.ndarray
    location: np.ndarray
    kind: np.ndarray
    count: int
    wrong_condition_event_count: int
    unburned_fuel_reservoir: np.ndarray | None = None
    exhaust_oxygen_proxy: np.ndarray | None = None
    exhaust_temperature: np.ndarray | None = None
    throttle_closure_age: np.ndarray | None = None
    engine_speed: np.ndarray | None = None
    load_history: np.ndarray | None = None
    ignition_delay: np.ndarray | None = None
    event_location: np.ndarray | None = None
    collector_pressure: np.ndarray | None = None

def schedule_afterfire(time_s, rpm, load, throttle, d_rpm, config, sample_rate_hz: int = 48000) -> AfterfireEvents:
    time_s, rpm, load, throttle = [np.asarray(x, dtype=np.float64) for x in (time_s, rpm, load, throttle)]
    if len({time_s.size, rpm.size, load.size, throttle.size}) != 1 or time_s.size == 0:
        raise ValueError("afterfire inputs must have equal nonzero length")
    if not all(np.all(np.isfinite(x)) for x in (time_s, rpm, load, throttle)):
        raise ValueError("afterfire inputs must be finite")
    dt = np.maximum(np.diff(time_s, prepend=time_s[0]), 1.0 / sample_rate_hz)
    dthrottle = np.diff(throttle, prepend=throttle[0]) / dt
    temp = 120.0 + 780.0 * np.clip(rpm / 6500.0, 0.0, 1.0) * (0.55 + 0.45 * load)
    fuel_reservoir = np.clip(0.72 * load + 0.35 * np.maximum(-dthrottle, 0.0), 0.0, 1.0)
    oxygen_proxy = np.clip(0.82 - 0.48 * load + 0.15 * (1.0 - throttle), 0.0, 1.0)
    closure_age = np.zeros_like(time_s)
    for index in range(1, time_s.size):
        closure_age[index] = closure_age[index - 1] + dt[index] if dthrottle[index] < -0.8 else 0.0
    collector_pressure = np.clip(0.0015 * temp * (0.25 + load), 0.0, 2.0)
    hot = temp >= float(unwrap(config, "afterfire.minimum_temperature_c"))
    closure = dthrottle < -0.8
    eligible = (rpm >= float(unwrap(config, "afterfire.minimum_rpm"))) & (load >= 0.35) & (throttle <= 0.18) & hot & closure & (fuel_reservoir >= 0.2) & (oxygen_proxy >= 0.15)
    indices, energies, locations, kinds = [], [], [], []
    cooldown = max(1, int(round(float(unwrap(config, "afterfire.cooldown_s")) * sample_rate_hz)))
    last = -cooldown
    for sample in np.flatnonzero(eligible):
        if sample - last < cooldown:
            continue
        indices.append(int(sample))
        energies.append(float(unwrap(config, "afterfire.gain")) * (0.65 + 0.35 * min(1.0, load[sample])))
        locations.append("collector" if len(indices) % 2 == 0 else "primary")
        kinds.append("single_pop" if len(indices) % 3 == 1 else "crackle_cluster")
        last = int(sample)
    event_indices = np.asarray(indices, dtype=np.int64)
    return AfterfireEvents(
        event_indices,
        np.asarray(energies, dtype=np.float64),
        np.asarray(locations, dtype=object),
        np.asarray(kinds, dtype=object),
        len(indices),
        0,
        fuel_reservoir,
        oxygen_proxy,
        temp,
        closure_age,
        rpm,
        load,
        np.asarray([0.004 + 0.000001 * rpm[index] for index in event_indices], dtype=np.float64),
        np.asarray(locations, dtype=object),
        collector_pressure,
    )

def render_afterfire_events(events: AfterfireEvents, sample_count: int, sample_rate_hz: int, config: dict) -> np.ndarray:
    output = np.zeros(sample_count, dtype=np.float64)
    for index, energy, kind in zip(events.sample_index, events.energy, events.kind):
        length = min(sample_count - int(index), max(2, int(round((0.035 if kind == "single_pop" else 0.060) * sample_rate_hz))))
        if length <= 0:
            continue
        t = np.arange(length, dtype=np.float64) / sample_rate_hz
        rise = 1.0 - np.exp(-t / (0.0018 if kind == "single_pop" else 0.0035))
        decay = np.exp(-t / (0.012 if kind == "single_pop" else 0.022))
        body = float(energy) * rise * decay
        crack = 0.24 * float(energy) * np.sin(2.0 * np.pi * (1800.0 + 700.0 * (index % 5)) * t) * decay
        output[int(index):int(index) + length] += body + crack
    return output
