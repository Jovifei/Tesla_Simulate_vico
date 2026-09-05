"""
Ferrari 458 Italia Stage AD Closed-Loop Calibration Engine.
Calibrates physical engine parameters against authentic AutoTopNL reference clips.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import qmc

import sys
sys.path.insert(0, r"E:\Tesla_speed\worktrees\s12-stage-ad-closed-loop-calibration")

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config, unwrap
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.click_contract import block_boundary_click_metrics
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.multi_reference_comparator import compare_case, aggregate_dimensions

SAMPLE_RATE_HZ = 48000
BLOCK_SIZE = 960
STATE_RATE_HZ = SAMPLE_RATE_HZ // BLOCK_SIZE

SCENE_DEFS = {
    "hot_idle": {"name": "hot_idle", "dur": 3.0, "bound_ref": "hot_idle"},
    "steady_low": {"name": "steady_low", "dur": 3.0, "bound_ref": "steady_low"},
    "steady_mid": {"name": "steady_mid", "dur": 3.0, "bound_ref": "steady_mid"},
    "steady_high": {"name": "steady_high", "dur": 3.0, "bound_ref": "steady_high"},
    "tip_in": {"name": "tip_in", "dur": 3.0, "bound_ref": None},
    "full_pull": {"name": "full_pull", "dur": 3.5, "bound_ref": "full_pull"},
    "shift": {"name": "shift", "dur": 3.0, "bound_ref": None},
    "lift": {"name": "lift", "dur": 3.5, "bound_ref": None},
    "afterfire": {"name": "afterfire", "dur": 3.5, "bound_ref": "afterfire"},
    "idle_return": {"name": "idle_return", "dur": 3.0, "bound_ref": None},
}

def build_ferrari_trace(scene: str, duration_s: float = 3.0) -> VehicleStateTrace:
    count = max(2, int(round(duration_s * STATE_RATE_HZ)))
    state_time_s = np.arange(count, dtype=np.float64) / STATE_RATE_HZ
    time_s = state_time_s.copy()
    phase = np.linspace(0.0, 1.0, count, dtype=np.float64)
    idle = 1050.0
    redline = 9000.0

    if scene == "hot_idle":
        rpm = idle + 5.0 * np.sin(2.0 * np.pi * 3.1 * state_time_s)
        load = np.full(count, 0.16)
        throttle = np.full(count, 0.16)
    elif scene == "steady_low":
        rpm = np.full(count, 1500.0)
        load = np.full(count, 0.22)
        throttle = np.full(count, 0.22)
    elif scene == "steady_mid":
        rpm = np.full(count, 3500.0)
        load = np.full(count, 0.35)
        throttle = np.full(count, 0.35)
    elif scene == "steady_high":
        rpm = np.full(count, 7200.0)
        load = np.full(count, 0.65)
        throttle = np.full(count, 0.65)
    elif scene == "tip_in":
        rpm = np.linspace(2200.0, 6500.0, count)
        throttle = np.where(phase < 0.28, 0.18, 0.95)
        load = np.where(phase < 0.28, 0.20, 0.88)
    elif scene == "full_pull":
        rpm = np.linspace(3000.0, redline, count)
        load = np.linspace(0.55, 0.98, count)
        throttle = np.full(count, 1.0)
    elif scene == "shift":
        rpm = np.linspace(4500.0, 8800.0, count)
        center = int(0.52 * count)
        width = max(1, int(0.03 * count))
        # DCT shift RPM drop
        rpm = np.where(np.abs(np.arange(count) - center) < width, rpm - 1800.0, rpm)
        load = np.full(count, 0.80)
        throttle = np.full(count, 0.85)
    elif scene == "lift":
        high = 8200.0
        close = phase >= 0.35
        rpm = np.where(close, np.linspace(high, 4800.0, count), high)
        load = np.where(close, 0.08, 0.85)
        throttle = np.where(close, 0.02, 0.90)
    elif scene == "afterfire":
        high = 8800.0
        close = phase >= 0.32
        rpm = np.where(close, np.linspace(high, 3800.0, count), high)
        load = np.where(close, 0.05, 0.90)
        throttle = np.where(close, 0.01, 0.95)
    elif scene == "idle_return":
        rpm = np.where(phase < 0.40, 5800.0, np.linspace(5800.0, idle, count))
        load = np.where(phase < 0.40, 0.45, 0.12)
        throttle = np.where(phase < 0.40, 0.50, 0.12)
    else:
        raise ValueError(f"Unknown scene: {scene}")

    return VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, state_time_s)).validate()

# Search parameters
@dataclass
class SearchParam:
    name: str
    key_path: str
    baseline: float
    min_val: float
    max_val: float
    unit: str
    family: str

FERRARI_SEARCH_PARAMETERS = [
    # Body & combustion
    SearchParam("combustion_event_energy", "combustion_event.event_energy", 0.58, 0.35, 1.10, "normalized_pressure", "body"),
    SearchParam("combustion_rise_time", "combustion_event.rise_time_s", 0.0021, 0.0016, 0.0030, "s", "body"),
    SearchParam("combustion_decay_time", "combustion_event.decay_time_s", 0.019, 0.012, 0.028, "s", "body"),
    SearchParam("load_exponent", "combustion_event.load_exponent", 0.65, 0.45, 0.85, "exponent", "body"),
    SearchParam("blowdown_event", "blowdown_event", 0.38, 0.22, 0.55, "normalized_pressure", "body"),
    SearchParam("cycle_variation", "cycle_variation", 0.038, 0.015, 0.070, "normalized", "body"),
    
    # Resonator & Exhaust & Afterfire
    SearchParam("collector_loss", "collector_loss", 0.95, 0.88, 0.99, "ratio", "exhaust"),
    SearchParam("gas_temperature", "gas_temperature_model", 830.0, 650.0, 980.0, "degC", "exhaust"),
    SearchParam("intake_mix", "intake_model", 0.22, 0.10, 0.45, "gain", "exhaust"),
    SearchParam("afterfire_gain", "afterfire.gain", 0.035, 0.015, 0.075, "gain", "afterfire"),
    SearchParam("afterfire_cooldown", "afterfire.cooldown_s", 0.070, 0.035, 0.120, "s", "afterfire"),
]

def set_config_param(cfg: dict[str, Any], path: str, val: Any) -> None:
    parts = path.split(".")
    curr = cfg
    for p in parts[:-1]:
        curr = curr[p]
    if isinstance(curr[parts[-1]], dict) and "value" in curr[parts[-1]]:
        curr[parts[-1]]["value"] = val
    else:
        curr[parts[-1]] = val

def apply_ferrari_parameters(base_cfg: dict[str, Any], overrides: dict[str, float]) -> dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)
    param_map = {p.name: p for p in FERRARI_SEARCH_PARAMETERS}
    for k, v in overrides.items():
        if k in param_map:
            set_config_param(cfg, param_map[k].key_path, float(v))
    return cfg

MASTER_SCALE = 22.0

def render_ferrari_scene(cfg: dict[str, Any], scene: str, duration_s: float) -> tuple[np.ndarray, dict[str, Any]]:
    trace = build_ferrari_trace(scene, duration_s)
    engine = PersistentEventDomainEngine(
        copy.deepcopy(cfg),
        SAMPLE_RATE_HZ,
        BLOCK_SIZE,
        ptr_enabled=True,
        path_model="waveguide_v1",
        forced_induction_model="timbre_map_v1"
    )
    rendered = engine.process_with_trace({
        "rpm": trace.rpm,
        "load": trace.load,
        "throttle": trace.throttle,
        "acceleration_mps2": trace.acceleration_mps2
    })
    post = rendered.post_ptr_raw
    if post is None:
        post = rendered.raw_pcm
    
    # Scale and soft-limit
    scaled = post * MASTER_SCALE
    # Peak clamp softly
    peak = np.max(np.abs(scaled))
    if peak > 0.98:
        scaled = scaled * (0.98 / peak)
    
    return scaled, rendered.diagnostics
