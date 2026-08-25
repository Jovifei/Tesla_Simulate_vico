"""Comparator-driven P1/P2/P2H/P3/P4/P5/P6 Hellcat bake-off."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
from typing import Any

import numpy as np

from ..contracts import VehicleStateTrace
from ..event_domain.audition_monitor import render_audition_monitor
from ..event_domain.config_schema import load_config
from ..sources.supercharged_hemi_source import render_hellcat
from ..stage_v.comparator import compare_three_way
from ..stage_v.io import read_pcm24_wav, sha256_file, write_json, write_pcm24_wav
from .frozen_ptr import FrozenPtrStereo
from .persistent_engine import PersistentEventDomainEngine

STATE_RATE_HZ = 100
SAMPLE_RATE_HZ = 48000
OUTPUT_SCALE = 0.25
SCENES = ("hot_idle_20s", "steady_1200rpm", "steady_2000rpm", "steady_3000rpm", "throttle_tip_in", "full_load_acceleration", "gear_shift", "high_rpm_lift", "afterfire_eligible", "afterfire_ineligible", "idle_return", "complete_cycle_60s")


def build_hellcat_bakeoff_trace(scene: str, duration_s: float = 8.0) -> VehicleStateTrace:
    if scene not in SCENES:
        raise ValueError(f"unsupported bake-off scene: {scene}")
    if not np.isfinite(duration_s) or duration_s < 0.20:
        raise ValueError("duration_s must be finite and >= 0.20")
    count = max(2, int(round(duration_s * STATE_RATE_HZ)) + 1)
    time_s = np.linspace(0.0, duration_s, count, dtype=np.float64)
    phase = time_s / duration_s
    idle = 850.0
    redline = 6500.0
    if scene == "hot_idle_20s":
        rpm = idle + 4.0 * np.sin(2.0 * np.pi * 2.7 * time_s); load = np.full(count, 0.18); throttle = np.full(count, 0.18)
    elif scene.startswith("steady_"):
        target = float(scene.split("_")[1].replace("rpm", "")); rpm = np.full(count, target); load = np.full(count, 0.24 + target / 20000.0); throttle = load.copy()
    elif scene == "throttle_tip_in":
        throttle = np.where(phase < 0.35, 0.18, 0.90); load = np.where(phase < 0.35, 0.20, 0.72); rpm = np.linspace(1200.0, 4200.0, count)
    elif scene == "full_load_acceleration":
        rpm = np.linspace(1600.0, 6200.0, count); load = np.linspace(0.42, 0.96, count); throttle = np.clip(load + 0.03, 0.0, 1.0)
    elif scene == "gear_shift":
        rpm = np.linspace(2600.0, 5600.0, count); center = int(0.55 * count); width = max(1, int(0.02 * count)); rpm -= np.where(np.abs(np.arange(count) - center) < width, 1100.0, 0.0); load = np.full(count, 0.70); throttle = np.full(count, 0.75)
    elif scene in {"high_rpm_lift", "afterfire_eligible"}:
        high = 0.90 * redline; close = phase >= 0.40; late = phase >= 0.64; rpm = np.where(close, np.linspace(high, idle, count), high); load = np.where(close, np.where(late, 0.12, 0.55), 0.86); throttle = np.where(close, 0.02, 0.92)
    elif scene == "afterfire_ineligible":
        high = 0.65 * redline; close = phase >= 0.40; rpm = np.where(close, np.linspace(high, idle, count), high); load = np.where(close, 0.12, 0.25); throttle = np.where(close, 0.02, 0.30)
    elif scene == "idle_return":
        rpm = np.where(phase < 0.45, 0.78 * redline, np.linspace(0.78 * redline, idle, count)); load = np.where(phase < 0.45, 0.55, 0.12); throttle = np.where(phase < 0.45, 0.62, 0.14)
    else:
        anchors = np.array([idle, 2400.0, 6200.0, 5400.0, 2200.0, idle], dtype=np.float64); anchor_x = np.linspace(0.0, 1.0, anchors.size); rpm = np.interp(phase, anchor_x, anchors); load = np.interp(phase, anchor_x, [0.18, 0.45, 0.95, 0.25, 0.30, 0.16]); throttle = np.interp(phase, anchor_x, [0.18, 0.50, 0.98, 0.03, 0.35, 0.16])
    return VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)).validate()


def _state_arrays(trace: VehicleStateTrace) -> dict[str, np.ndarray]:
    return {"rpm": trace.rpm, "load": trace.load, "throttle": trace.throttle, "acceleration_mps2": trace.acceleration_mps2}


def _render_architecture(architecture: str, trace: VehicleStateTrace) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    config = load_config("hellcat_v1")
    if architecture == "P1":
        source = render_hellcat(trace).pressure * OUTPUT_SCALE
        post_ptr = FrozenPtrStereo(SAMPLE_RATE_HZ).process(source)
        monitor = render_audition_monitor(post_ptr, SAMPLE_RATE_HZ).audio
        return source, post_ptr, {"source_model": "legacy_v015", "ptr_status": "FROZEN_RUNTIME_PTR_ADAPTER"}
    settings = {"P2": {"path_model": "delay_lpf_v1", "forced_induction_model": "harmonic_v1"}, "P2H": {"path_model": "waveguide_v1", "forced_induction_model": "harmonic_v1"}, "P3": {"path_model": "waveguide_v1", "forced_induction_model": "timbre_map_v1"}}
    setting = settings[architecture]
    engine = PersistentEventDomainEngine(config, SAMPLE_RATE_HZ, 960, ptr_enabled=True, **setting)
    result = engine.process(_state_arrays(trace))
    raw = result.raw_pcm * OUTPUT_SCALE
    post_ptr = result.post_ptr_raw * OUTPUT_SCALE if result.post_ptr_raw is not None else FrozenPtrStereo(SAMPLE_RATE_HZ).process(raw)
    monitor = render_audition_monitor(post_ptr, SAMPLE_RATE_HZ).audio
    return raw, post_ptr, {"source_model": architecture, "ptr_status": result.diagnostics["ptr_status"], "engine_state": result.diagnostics}


def _write_case(root: Path, architecture: str, scene: str, trace: VehicleStateTrace, reference: np.ndarray | None = None) -> dict[str, Any]:
    case_root = root / architecture / scene
    case_root.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    raw, post_ptr, diagnostics = _render_architecture(architecture, trace)
    monitor = render_audition_monitor(post_ptr, SAMPLE_RATE_HZ).audio
    elapsed = time.perf_counter() - start
    parent_raw, parent_post, _ = _render_architecture("P1", trace)
    case = {
        "vehicle_id": "hellcat",
        "scenario": scene,
        "reference_id": None,
        "candidate_id": architecture,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "reference_rpm": (float(trace.rpm[0]), float(trace.rpm[-1])),
        "candidate_rpm": (float(trace.rpm[0]), float(trace.rpm[-1])),
        "reference_load": (float(trace.load[0]), float(trace.load[-1])),
        "candidate_load": (float(trace.load[0]), float(trace.load[-1])),
        "analysis_domain": "unaltered_analysis_signal",
        "reference_kind": "synthetic_parent",
        "reference_provenance": "REFERENCE_POINTER_ONLY",
        "candidate_source_commit": "stage_w_worktree",
    }
    from ...acoustic_comparator.core import ComparisonCase
    compare_length = min(parent_post.shape[0], post_ptr.shape[0])
    comparison_parent = parent_post[:compare_length]
    comparison_candidate = post_ptr[:compare_length]
    if architecture == "P1":
        comparison = {"schema": "s12.stage_w.baseline_comparison.v1", "status": "BASELINE_ONLY", "reference_available": reference is not None, "pairs": {"reference_parent": {"uncertainty": {"reference_missing": reference is None}}, "reference_candidate": {"uncertainty": {"reference_missing": reference is None}}, "parent_candidate": {"difference_rms": 0.0}}, "parent_candidate_difference_rms": 0.0}
    else:
        comparison = compare_three_way(reference, comparison_parent, comparison_candidate, ComparisonCase(**case))
    raw_receipt = write_pcm24_wav(case_root / "raw_source.wav", raw, SAMPLE_RATE_HZ)
    post_receipt = write_pcm24_wav(case_root / "post_ptr_raw.wav", post_ptr, SAMPLE_RATE_HZ)
    monitor_receipt = write_pcm24_wav(case_root / "monitor.wav", monitor, SAMPLE_RATE_HZ)
    write_json(case_root / "state_trace.json", {"sample_rate_hz": STATE_RATE_HZ, "time_s": trace.time_s.tolist(), "rpm": trace.rpm.tolist(), "load": trace.load.tolist(), "throttle": trace.throttle.tolist(), "acceleration_mps2": trace.acceleration_mps2.tolist()})
    write_json(case_root / "metrics.json", {"architecture": architecture, "scene": scene, "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction", "raw_metrics": {"peak": float(np.max(np.abs(raw))), "rms": float(np.sqrt(np.mean(np.square(raw))))}, "post_ptr_metrics": {"peak": float(np.max(np.abs(post_ptr))), "rms": float(np.sqrt(np.mean(np.square(post_ptr))))}, "comparison": comparison, "diagnostics": diagnostics})
    write_json(case_root / "cpu_memory_latency.json", {"render_seconds": elapsed, "cpu_status": "measured_wall_clock", "memory_bytes": None, "latency_contract": "offline source render"})
    files = {name: sha256_file(case_root / name) for name in ("raw_source.wav", "post_ptr_raw.wav", "monitor.wav", "state_trace.json", "metrics.json", "cpu_memory_latency.json")}
    write_json(case_root / "sha256_manifest.json", files)
    return {"raw_sha256": raw_receipt.sha256, "post_ptr_sha256": post_receipt.sha256, "monitor_sha256": monitor_receipt.sha256, "comparison": comparison, "render_seconds": elapsed}


def run_hellcat_bakeoff(output_root: str | Path, duration_s: float = 8.0, reference: np.ndarray | None = None) -> dict[str, Any]:
    root = Path(output_root)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"refusing to overwrite bake-off output: {root}")
    root.mkdir(parents=True, exist_ok=True)
    architectures: dict[str, Any] = {
        "P4": {"status": "REFERENCE_RECORDING_RIGHTS_PENDING", "reason": "cycle-synchronous recorded resynthesis requires rights-bound recording"},
        "P5": {"status": "HYBRID_TRANSIENT_PENDING", "reason": "requires separately qualified granular/one-shot source"},
        "P6": {"status": "BLOCKED_TOOLCHAIN_NO_CLANG_MAKE", "reason": "ENSIM4 teacher checkout cannot build on current host"},
    }
    for architecture in ("P1", "P2", "P2H", "P3"):
        architectures[architecture] = {"status": "RENDERED", "scenes": {}}
        for scene in SCENES:
            trace = build_hellcat_bakeoff_trace(scene, duration_s)
            architectures[architecture]["scenes"][scene] = _write_case(root, architecture, scene, trace, reference)
    result = {"schema_version": "s12.stage_w.bakeoff.v1", "status": "REFERENCE_TARGET_MISSING" if reference is None else "R2_DIAGNOSTIC_READY", "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction", "reference_status": "REFERENCE_POINTER_ONLY" if reference is None else "EXTERNAL_R2_POINTER", "selected_architecture": None, "architectures": architectures}
    write_json(root / "bakeoff_results.json", result)
    write_json(root / "selected_architecture.json", {"selected_architecture": None, "status": result["status"]})
    write_json(root / "rejected_architectures.json", {"status": result["status"], "rejected": ["P4", "P5", "P6"] if reference is None else []})
    files = {path.relative_to(root).as_posix(): sha256_file(path) for path in sorted(root.rglob("*")) if path.is_file() and path.name != "bakeoff_manifest.json"}
    write_json(root / "bakeoff_manifest.json", {"schema_version": "s12.stage_w.bakeoff_manifest.v1", "status": result["status"], "reference_status": result["reference_status"], "files": files})
    return result


def validate_bakeoff_manifest(root: str | Path) -> list[str]:
    root = Path(root)
    errors: list[str] = []
    manifest_path = root / "bakeoff_manifest.json"
    if not manifest_path.is_file():
        return ["bakeoff_manifest.json missing"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for relative, expected in manifest.get("files", {}).items():
        path = root / relative
        if not path.is_file():
            errors.append(f"missing:{relative}")
        elif sha256_file(path) != expected:
            errors.append(f"sha:{relative}")
    for architecture in ("P1", "P2", "P2H", "P3"):
        for scene in SCENES:
            case = root / architecture / scene
            for name in ("raw_source.wav", "post_ptr_raw.wav", "monitor.wav", "metrics.json", "sha256_manifest.json"):
                if not (case / name).is_file(): errors.append(f"missing:{architecture}/{scene}/{name}")
            try:
                raw, raw_meta = read_pcm24_wav(case / "raw_source.wav")
                post, post_meta = read_pcm24_wav(case / "post_ptr_raw.wav")
                monitor, monitor_meta = read_pcm24_wav(case / "monitor.wav")
                if max(raw_meta["clipping"], post_meta["clipping"], monitor_meta["clipping"]) != 0: errors.append(f"clipping:{architecture}/{scene}")
                if raw_meta["frames"] != post_meta["frames"] or post_meta["frames"] != monitor_meta["frames"]: errors.append(f"frames:{architecture}/{scene}")
            except (OSError, ValueError) as exc: errors.append(f"wav:{architecture}/{scene}:{exc}")
    return errors


__all__ = ["SCENES", "build_hellcat_bakeoff_trace", "run_hellcat_bakeoff", "validate_bakeoff_manifest"]
