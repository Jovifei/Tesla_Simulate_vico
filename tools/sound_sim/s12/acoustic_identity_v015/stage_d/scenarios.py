"""Canonical Stage-D five-scene traces shared by baseline and candidates."""

from __future__ import annotations

import numpy as np

from ..acoustic_layers.realism_profiles import get_realism_profile
from ..contracts import VehicleStateTrace

SAMPLE_RATE_HZ = 48000
SCENES = ("idle", "cruise", "acceleration", "shift", "lift")


def build_stage_d_scenario_trace(vehicle_id: str, scene_id: str, duration_s: float = 8.0) -> VehicleStateTrace:
    profile = get_realism_profile(vehicle_id)
    if scene_id not in SCENES:
        raise ValueError(f"unsupported Stage-D scene_id: {scene_id!r}")
    if not np.isfinite(duration_s) or duration_s < 2.0:
        raise ValueError("duration_s must be finite and >= 2.0")
    count = int(round(duration_s * SAMPLE_RATE_HZ)) + 1
    time_s = np.linspace(0.0, duration_s, count)
    phase = time_s / duration_s
    idle_rpm = profile.idle_rpm
    redline = profile.redline_rpm
    if scene_id == "idle":
        rpm = np.full(count, idle_rpm)
        load = np.full(count, 0.14)
        throttle = np.full(count, 0.14)
    elif scene_id == "cruise":
        rpm = np.full(count, 3000.0)
        load = np.full(count, 0.35)
        throttle = np.full(count, 0.35)
    elif scene_id == "acceleration":
        rpm = np.linspace(0.30 * redline, 0.92 * redline, count)
        load = np.linspace(0.35, 0.90, count)
        throttle = load.copy()
    elif scene_id == "shift":
        rpm = np.linspace(0.42 * redline, 0.68 * redline, count)
        center = int(round(3.5 * SAMPLE_RATE_HZ))
        width = int(round(0.10 * SAMPLE_RATE_HZ))
        index = np.arange(count)
        rpm -= np.where(np.abs(index - center) < width, 0.08 * redline * (1.0 - np.abs(index - center) / width), 0.0)
        load = np.full(count, 0.78)
        throttle = np.full(count, 0.82)
    else:
        rpm = np.full(count, 0.78 * redline)
        load = np.where(phase < 0.375, 0.85, 0.12)
        throttle = np.where(phase < 0.375, 0.88, 0.03)
    return VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)).validate()
