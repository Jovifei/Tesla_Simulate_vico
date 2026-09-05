"""Unified four-vehicle audition definitions for Stage AE."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class VehicleProfile:
    key: str
    config_id: str
    display_name: str
    idle_rpm: float
    redline_rpm: float
    pull_start_rpm: float
    pull_end_rpm: float
    shift_drop_rpm: float


VEHICLES = {
    "hellcat": VehicleProfile("hellcat", "hellcat_v1", "Dodge Challenger SRT Hellcat", 720.0, 6500.0, 1500.0, 6200.0, 1700.0),
    "ferrari_458": VehicleProfile("ferrari_458", "ferrari_458_v1", "Ferrari 458 Italia", 1050.0, 9000.0, 2500.0, 8800.0, 1900.0),
    "lfa": VehicleProfile("lfa", "lfa_v1", "Lexus LFA", 900.0, 9500.0, 2600.0, 9300.0, 2100.0),
    "gtr_r35": VehicleProfile("gtr_r35", "gtr_r35_v1", "Nissan GT-R R35", 800.0, 7200.0, 2000.0, 7000.0, 1600.0),
}

SCENES = ("afterfire", "full_pull", "hot_idle", "idle_return", "lift", "shift", "steady_high", "steady_low", "steady_mid", "tip_in")


def build_standard_trace(vehicle_key: str, scene: str, duration_s: float = 6.0, state_rate_hz: int = 50) -> dict[str, np.ndarray]:
    if vehicle_key not in VEHICLES:
        raise ValueError(f"unknown vehicle: {vehicle_key}")
    if scene not in SCENES:
        raise ValueError(f"unknown scene: {scene}")
    profile = VEHICLES[vehicle_key]
    count = max(2, int(round(duration_s * state_rate_hz)))
    t = np.arange(count, dtype=np.float64) / state_rate_hz
    phase = np.linspace(0.0, 1.0, count, dtype=np.float64)
    idle, redline = profile.idle_rpm, profile.redline_rpm
    if scene == "hot_idle":
        rpm = idle + 10.0 * np.sin(2*np.pi*0.42*t) + 5.0*np.sin(2*np.pi*0.87*t)
        throttle = np.full(count, 0.10); load = np.full(count, 0.16); accel = np.zeros(count)
    elif scene == "steady_low":
        rpm = np.full(count, idle + 800.0); throttle = np.full(count, 0.20); load = np.full(count, 0.24); accel = np.zeros(count)
    elif scene == "steady_mid":
        rpm = np.full(count, 0.46 * redline); throttle = np.full(count, 0.35); load = np.full(count, 0.42); accel = np.zeros(count)
    elif scene == "steady_high":
        rpm = np.full(count, 0.76 * redline); throttle = np.full(count, 0.55); load = np.full(count, 0.66); accel = np.zeros(count)
    elif scene == "full_pull":
        rpm = profile.pull_start_rpm + (profile.pull_end_rpm-profile.pull_start_rpm) * phase**1.10
        throttle = np.ones(count); load = 0.55 + 0.43*phase; accel = 2.0 + 3.5*phase
    elif scene == "tip_in":
        rpm = profile.pull_start_rpm + (0.82*redline-profile.pull_start_rpm) * np.maximum(phase-0.28,0.0)/0.72
        throttle = np.where(phase < 0.28, 0.16, 1.0); load = np.where(phase < 0.28, 0.22, 0.90); accel = np.where(phase < 0.28, 0.0, 4.5)
    elif scene == "shift":
        base = np.linspace(0.48*redline, 0.92*redline, count)
        center = count//2; width = max(1, int(0.05*count))
        rpm = base.copy(); rpm[center:center+width] -= profile.shift_drop_rpm
        throttle = np.ones(count)*0.92; load=np.ones(count)*0.82; accel=np.ones(count)*3.0; accel[center:center+width] = 0.3
    elif scene in {"lift", "afterfire"}:
        split = 0.32 if scene == "afterfire" else 0.38
        rpm = np.where(phase < split, 0.82*redline, idle + (0.82*redline-idle)*np.exp(-4.0*(phase-split).clip(min=0)))
        throttle=np.where(phase<split,0.88,0.02); load=np.where(phase<split,0.84,0.07); accel=np.where(phase<split,2.0,-3.2)
    elif scene == "idle_return":
        rpm = idle + (0.62*redline-idle)*np.exp(-4.2*phase)
        throttle = 0.10 + 0.55*np.exp(-5.0*phase); load=0.14+0.38*np.exp(-4.0*phase); accel=-1.8*np.exp(-2.0*phase)
    else:
        raise AssertionError(scene)
    return {"rpm": np.asarray(rpm,float), "load": np.asarray(load,float), "throttle": np.asarray(throttle,float), "acceleration_mps2": np.asarray(accel,float)}
