"""Comparator-driven P1/P2/P2H/P3/P4/P5/P6 Hellcat bake-off."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import subprocess
import time
from typing import Any
import wave

import numpy as np

from ..contracts import VehicleStateTrace
from ..event_domain.audition_monitor import render_audition_monitor
from ..event_domain.chamber_event import render_event_packet
from ..event_domain.config_schema import load_config
from ..sources.supercharged_hemi_source import render_hellcat
from ..stage_v.comparator import compare_three_way
from ..stage_v.io import read_pcm24_wav, sha256_file, write_json, write_pcm24_wav
from .boundary_adapter import FrozenPtrStereo
from .migration import write_diagnostic_traces
from .persistent_engine import PersistentEventDomainEngine
from .click_contract import block_boundary_click_metrics

SAMPLE_RATE_HZ = 48000
BLOCK_SIZE = 960
STATE_RATE_HZ = SAMPLE_RATE_HZ // BLOCK_SIZE
OUTPUT_SCALE = 0.25
SCENES = ("hot_idle_20s", "steady_1200rpm", "steady_2000rpm", "steady_3000rpm", "throttle_tip_in", "full_load_acceleration", "gear_shift", "high_rpm_lift", "afterfire_eligible", "afterfire_ineligible", "idle_return", "complete_cycle_60s")
RENDERABLE_ARCHITECTURES = ("P1", "P2", "P2H", "P3", "P5")
SUMMARY_FILES = ("bakeoff_results.json", "parent_candidate_metrics.json", "ablation_results.json", "selected_architecture.json", "rejected_architectures.json")
STAGE_CASE_FILES = ("raw_source.wav", "post_ptr_raw.wav", "monitor.wav", "state_trace.json", "phase_trace.json", "event_trace.json", "path_trace.json", "gain_trace.json", "metrics.json", "cpu_memory_latency.json", "sha256_manifest.json")
STAGE_MANIFEST_SCHEMA = "s12.stage_w.architecture_stage_manifest.v1"
LONG_WINDOW_SCENE_DURATIONS = {"hot_idle_20s": 20.0, "complete_cycle_60s": 60.0}
PCM24_METRIC_TOLERANCE = 1.0 / (1 << 23)
PLACEHOLDER_SCOPE = "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction"
PLACEHOLDER_RECORDS = {
    "P4": {
        "status": "REFERENCE_RECORDING_RIGHTS_PENDING",
        "reason": "cycle-synchronous recorded resynthesis requires rights-bound recording",
        "scope": PLACEHOLDER_SCOPE,
        "selected_architecture": None,
        "selection_eligible": False,
    },
    "P6": {
        "status": "TEACHER_NOT_RUNTIME_CANDIDATE",
        "reason": "ENSIM4 Docker CFD ON/OFF teacher audio is externally captured but is not a fitted S12 Runtime path",
        "scope": PLACEHOLDER_SCOPE,
        "selected_architecture": None,
        "selection_eligible": False,
    },
}


def _is_safe_manifest_relative(value: Any) -> bool:
    """Accept only canonical, separator-stable relative manifest paths."""
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/"):
        return False
    if len(value) > 1 and value[0].isalpha() and value[1] == ":":
        return False
    parts = value.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        return False
    return "/".join(parts) == value


def _block_click_metrics(audio: np.ndarray) -> dict[str, Any]:
    return block_boundary_click_metrics(audio, BLOCK_SIZE)


def scene_duration_s(scene: str, duration_s: float, *, long_window: bool = False) -> float:
    if scene not in SCENES:
        raise ValueError(f"unsupported bake-off scene: {scene}")
    if not np.isfinite(duration_s) or duration_s < 0.20:
        raise ValueError("duration_s must be finite and >= 0.20")
    return LONG_WINDOW_SCENE_DURATIONS.get(scene, float(duration_s)) if long_window else float(duration_s)


def build_hellcat_bakeoff_trace(scene: str, duration_s: float = 8.0) -> VehicleStateTrace:
    if scene not in SCENES:
        raise ValueError(f"unsupported bake-off scene: {scene}")
    if not np.isfinite(duration_s) or duration_s < 0.20:
        raise ValueError("duration_s must be finite and >= 0.20")
    count = max(2, int(round(duration_s * STATE_RATE_HZ)))
    state_time_s = np.arange(count, dtype=np.float64) / STATE_RATE_HZ
    time_s = state_time_s.copy()
    phase = np.linspace(0.0, 1.0, count, dtype=np.float64)
    idle = 850.0
    redline = 6500.0
    if scene == "hot_idle_20s":
        rpm = idle + 4.0 * np.sin(2.0 * np.pi * 2.7 * state_time_s); load = np.full(count, 0.18); throttle = np.full(count, 0.18)
    elif scene.startswith("steady_"):
        target = float(scene.split("_")[1].replace("rpm", "")); rpm = np.full(count, target); load = np.full(count, 0.24 + target / 20000.0); throttle = load.copy()
    elif scene == "throttle_tip_in":
        throttle = np.where(phase < 0.35, 0.18, 0.90); load = np.where(phase < 0.35, 0.20, 0.72); rpm = np.linspace(1200.0, 4200.0, count)
    elif scene == "full_load_acceleration":
        rpm = np.linspace(1600.0, 6200.0, count); load = np.linspace(0.42, 0.96, count); throttle = np.clip(load + 0.03, 0.0, 1.0)
    elif scene == "gear_shift":
        rpm = np.linspace(2600.0, 5600.0, count); center = int(0.55 * count); width = max(1, int(0.02 * count)); rpm -= np.where(np.abs(np.arange(count) - center) < width, 1100.0, 0.0); load = np.full(count, 0.70); throttle = np.full(count, 0.75)
    elif scene in {"high_rpm_lift", "afterfire_eligible"}:
        high = 0.90 * redline; close = phase >= 0.40; late = phase >= 0.64; decline = np.clip((phase - 0.40) / 0.60, 0.0, 1.0); rpm = high + (idle - high) * decline; load = np.where(close, np.where(late, 0.12, 0.55), 0.86); throttle = np.where(close, 0.02, 0.92)
    elif scene == "afterfire_ineligible":
        high = 0.65 * redline; close = phase >= 0.40; rpm = np.where(close, np.linspace(high, idle, count), high); load = np.where(close, 0.12, 0.25); throttle = np.where(close, 0.02, 0.30)
    elif scene == "idle_return":
        rpm = np.where(phase < 0.45, 0.78 * redline, np.linspace(0.78 * redline, idle, count)); load = np.where(phase < 0.45, 0.55, 0.12); throttle = np.where(phase < 0.45, 0.62, 0.14)
    else:
        anchors = np.array([idle, 2400.0, 6200.0, 5400.0, 2200.0, idle], dtype=np.float64); anchor_x = np.linspace(0.0, 1.0, anchors.size); rpm = np.interp(phase, anchor_x, anchors); load = np.interp(phase, anchor_x, [0.18, 0.45, 0.95, 0.25, 0.30, 0.16]); throttle = np.interp(phase, anchor_x, [0.18, 0.50, 0.98, 0.03, 0.35, 0.16])
    return VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, state_time_s)).validate()


def _state_arrays(trace: VehicleStateTrace) -> dict[str, np.ndarray]:
    return {"rpm": trace.rpm, "load": trace.load, "throttle": trace.throttle, "acceleration_mps2": trace.acceleration_mps2}


def _synthetic_transient_residual(trace: VehicleStateTrace, sample_count: int) -> tuple[np.ndarray, int]:
    """Create clean-room one-shots only for a throttle lift or a gear RPM drop."""
    residual = np.zeros((sample_count, 2), dtype=np.float64)
    count = 0
    for index in range(1, trace.rpm.size):
        throttle_drop = trace.throttle[index] - trace.throttle[index - 1]
        rpm_drop = trace.rpm[index] - trace.rpm[index - 1]
        closure = throttle_drop < -0.45 and trace.rpm[index] > 2500.0
        shift = rpm_drop < -500.0 and trace.throttle[index] > 0.40
        if not (closure or shift):
            continue
        packet = render_event_packet(SAMPLE_RATE_HZ, 0.055, 0.0015, 0.018, 0.065 if closure else 0.045, 0.20).pressure
        start = index * BLOCK_SIZE
        end = min(sample_count, start + packet.size)
        if end <= start:
            continue
        pan = 0.82 if count % 2 == 0 else 0.66
        residual[start:end, 0] += packet[: end - start] * pan
        residual[start:end, 1] += packet[: end - start] * (1.48 - pan)
        count += 1
    return residual, count


def _render_architecture(architecture: str, trace: VehicleStateTrace) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    config = load_config("hellcat_v1")
    if architecture == "P1":
        source = render_hellcat(trace).pressure * OUTPUT_SCALE
        target_samples = trace.rpm.size * BLOCK_SIZE
        if source.shape[0] < target_samples:
            source = np.pad(source, ((0, target_samples - source.shape[0]), (0, 0)))
        elif source.shape[0] > target_samples:
            source = source[:target_samples]
        post_ptr = FrozenPtrStereo(SAMPLE_RATE_HZ).process(source)
        monitor = render_audition_monitor(post_ptr, SAMPLE_RATE_HZ).audio
        return source, post_ptr, monitor, {"source_model": "legacy_v015", "ptr_status": "FROZEN_RUNTIME_PTR_ADAPTER", "frame_trace": None}
    settings = {"P2": {"path_model": "delay_lpf_v1", "forced_induction_model": "harmonic_v1"}, "P2H": {"path_model": "waveguide_v1", "forced_induction_model": "harmonic_v1"}, "P3": {"path_model": "waveguide_v1", "forced_induction_model": "timbre_map_v1"}, "P5": {"path_model": "waveguide_v1", "forced_induction_model": "timbre_map_v1"}}
    setting = settings[architecture]
    transient = None
    if architecture == "P5":
        transient, transient_count = _synthetic_transient_residual(trace, trace.rpm.size * BLOCK_SIZE)
    engine = PersistentEventDomainEngine(config, SAMPLE_RATE_HZ, BLOCK_SIZE, ptr_enabled=True, **setting)
    result = engine.process_with_trace(_state_arrays(trace), external_transient=transient)
    if architecture == "P5":
        raw = result.raw_pcm * OUTPUT_SCALE
        post_ptr = result.post_ptr_raw * OUTPUT_SCALE if result.post_ptr_raw is not None else FrozenPtrStereo(SAMPLE_RATE_HZ).process(raw)
        monitor = result.monitor_pcm * OUTPUT_SCALE
    else:
        transient_count = 0
        raw = result.raw_pcm * OUTPUT_SCALE
        post_ptr = result.post_ptr_raw * OUTPUT_SCALE if result.post_ptr_raw is not None else FrozenPtrStereo(SAMPLE_RATE_HZ).process(raw)
        monitor = result.monitor_pcm * OUTPUT_SCALE
    diagnostics = dict(result.diagnostics)
    diagnostics["architecture"] = architecture
    if architecture == "P5":
        diagnostics.update({"ptr_status": "FROZEN_RUNTIME_PTR_ADAPTER", "transient_residual_source": "synthetic_one_shot_v1", "transient_residual_event_count": transient_count})
    diagnostics["monitor_source"] = "PersistentEventDomainEngine.monitor_pcm"
    return raw, post_ptr, monitor, diagnostics


def _write_case(
    root: Path,
    architecture: str,
    scene: str,
    trace: VehicleStateTrace,
    reference: np.ndarray | None = None,
    *,
    parent_post_ptr: np.ndarray | None = None,
) -> dict[str, Any]:
    case_root = root / architecture / scene
    case_root.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    raw, post_ptr, monitor, diagnostics = _render_architecture(architecture, trace)
    elapsed = time.perf_counter() - start
    if parent_post_ptr is None:
        _, parent_post, _, _ = _render_architecture("P1", trace)
    else:
        parent_post = parent_post_ptr
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
    raw_reopened, _ = read_pcm24_wav(case_root / "raw_source.wav")
    post_reopened, _ = read_pcm24_wav(case_root / "post_ptr_raw.wav")
    monitor_reopened, _ = read_pcm24_wav(case_root / "monitor.wav")
    write_json(case_root / "state_trace.json", {"sample_rate_hz": STATE_RATE_HZ, "time_s": trace.time_s.tolist(), "rpm": trace.rpm.tolist(), "load": trace.load.tolist(), "throttle": trace.throttle.tolist(), "acceleration_mps2": trace.acceleration_mps2.tolist()})
    write_diagnostic_traces(case_root, diagnostics)
    diagnostic_summary = {key: value for key, value in diagnostics.items() if key != "frame_trace"}
    click_metrics = {"raw": _block_click_metrics(raw_reopened), "post_ptr": _block_click_metrics(post_reopened), "monitor": _block_click_metrics(monitor_reopened)}
    diagnostic_summary["click_metrics"] = click_metrics["raw"]
    case_status = "REFERENCE_TARGET_MISSING" if reference is None else "R2_DIAGNOSTIC_READY"
    case_reference_status = "REFERENCE_POINTER_ONLY" if reference is None else "EXTERNAL_R2_POINTER"
    write_json(case_root / "metrics.json", {"architecture": architecture, "scene": scene, "status": case_status, "reference_status": case_reference_status, "selected_architecture": None, "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction", "raw_metrics": {"peak": float(np.max(np.abs(raw_reopened))), "rms": float(np.sqrt(np.mean(np.square(raw_reopened))) )}, "post_ptr_metrics": {"peak": float(np.max(np.abs(post_reopened))), "rms": float(np.sqrt(np.mean(np.square(post_reopened))) )}, "monitor_metrics": {"peak": float(np.max(np.abs(monitor_reopened))), "rms": float(np.sqrt(np.mean(np.square(monitor_reopened))) )}, "click_metrics": click_metrics, "comparison": comparison, "diagnostics": diagnostic_summary})
    write_json(case_root / "cpu_memory_latency.json", {"render_seconds": elapsed, "cpu_status": "measured_wall_clock", "memory_bytes": None, "latency_contract": "offline source render"})
    files = {name: sha256_file(case_root / name) for name in ("raw_source.wav", "post_ptr_raw.wav", "monitor.wav", "state_trace.json", "phase_trace.json", "event_trace.json", "path_trace.json", "gain_trace.json", "metrics.json", "cpu_memory_latency.json")}
    write_json(case_root / "sha256_manifest.json", files)
    return {"raw_sha256": sha256_file(case_root / "raw_source.wav"), "post_ptr_sha256": sha256_file(case_root / "post_ptr_raw.wav"), "monitor_sha256": sha256_file(case_root / "monitor.wav"), "comparison": comparison, "render_seconds": elapsed}


def _parent_candidate_metrics(architectures: dict[str, Any], status: str, reference_status: str) -> dict[str, Any]:
    parent = {scene: {key: architectures["P1"]["scenes"][scene][key] for key in ("raw_sha256", "post_ptr_sha256", "monitor_sha256")} for scene in SCENES}
    candidates = {
        architecture: {
            scene: {
                **{key: architectures[architecture]["scenes"][scene][key] for key in ("raw_sha256", "post_ptr_sha256", "monitor_sha256")},
                "parent_candidate_difference_rms": architectures[architecture]["scenes"][scene]["comparison"].get("parent_candidate_difference_rms"),
            }
            for scene in SCENES
        }
        for architecture in ("P2", "P2H", "P3", "P5")
    }
    return {"schema_version": "s12.stage_w.parent_candidate_metrics.v1", "status": status, "reference_status": reference_status, "selected_architecture": None, "selection_eligible": False, "parent": parent, "architectures": candidates}


def _ablation_results(architectures: dict[str, Any], status: str, reference_status: str) -> dict[str, Any]:
    pairs = {"P2_to_P2H_waveguide": ("P2", "P2H"), "P2H_to_P3_timbre_map": ("P2H", "P3"), "P3_to_P5_transient": ("P3", "P5")}
    ablations = {
        name: {
            scene: {
                "post_ptr_sha256_different": architectures[left]["scenes"][scene]["post_ptr_sha256"] != architectures[right]["scenes"][scene]["post_ptr_sha256"],
                "monitor_sha256_different": architectures[left]["scenes"][scene]["monitor_sha256"] != architectures[right]["scenes"][scene]["monitor_sha256"],
            }
            for scene in SCENES
        }
        for name, (left, right) in pairs.items()
    }
    return {"schema_version": "s12.stage_w.ablation_results.v1", "status": status, "reference_status": reference_status, "selected_architecture": None, "selection_eligible": False, "ablations": ablations}


def run_hellcat_bakeoff(output_root: str | Path, duration_s: float = 8.0, reference: np.ndarray | None = None, *, long_window: bool = False) -> dict[str, Any]:
    root = Path(output_root)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"refusing to overwrite bake-off output: {root}")
    root.mkdir(parents=True, exist_ok=True)
    architectures: dict[str, Any] = {name: dict(record) for name, record in PLACEHOLDER_RECORDS.items()}
    scene_durations = {scene: scene_duration_s(scene, duration_s, long_window=long_window) for scene in SCENES}
    for architecture in ("P1", "P2", "P2H", "P3", "P5"):
        architectures[architecture] = {"status": "RENDERED", "scenes": {}}
        for scene in SCENES:
            trace = build_hellcat_bakeoff_trace(scene, scene_durations[scene])
            architectures[architecture]["scenes"][scene] = _write_case(root, architecture, scene, trace, reference)
    block_aligned_duration_s = max(2, int(round(max(scene_durations.values()) * STATE_RATE_HZ))) / STATE_RATE_HZ
    status = "REFERENCE_TARGET_MISSING" if reference is None else "R2_DIAGNOSTIC_READY"
    reference_status = "REFERENCE_POINTER_ONLY" if reference is None else "EXTERNAL_R2_POINTER"
    result = {"schema_version": "s12.stage_w.bakeoff.v1", "status": status, "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction", "reference_status": reference_status, "requested_duration_s": float(duration_s), "long_window": bool(long_window), "scene_duration_s": scene_durations, "block_aligned_duration_s": block_aligned_duration_s, "selected_architecture": None, "architectures": architectures}
    write_json(root / "bakeoff_results.json", result)
    write_json(root / "parent_candidate_metrics.json", _parent_candidate_metrics(architectures, status, reference_status))
    write_json(root / "ablation_results.json", _ablation_results(architectures, status, reference_status))
    write_json(root / "selected_architecture.json", {"selected_architecture": None, "status": result["status"]})
    write_json(root / "rejected_architectures.json", {"status": result["status"], "reference_status": result["reference_status"], "selected_architecture": None, "rejected": ["P4", "P6"] if reference is None else []})
    files = {path.relative_to(root).as_posix(): sha256_file(path) for path in sorted(root.rglob("*")) if path.is_file() and path != root / "bakeoff_manifest.json"}
    write_json(root / "bakeoff_manifest.json", {"schema_version": "s12.stage_w.bakeoff_manifest.v1", "status": result["status"], "reference_status": result["reference_status"], "selected_architecture": None, "requested_duration_s": result["requested_duration_s"], "long_window": result["long_window"], "scene_duration_s": result["scene_duration_s"], "block_aligned_duration_s": result["block_aligned_duration_s"], "files": files})
    return result


def validate_bakeoff_manifest(root: str | Path) -> list[str]:
    """Fail closed on missing, tampered, inconsistent, or non-finite bake-off artifacts."""
    root = Path(root)
    manifest_path = root / "bakeoff_manifest.json"
    if not manifest_path.is_file():
        return ["bakeoff_manifest.json missing"]

    errors: list[str] = []
    required_state = SUMMARY_FILES
    case_files = (
        "raw_source.wav", "post_ptr_raw.wav", "monitor.wav", "state_trace.json",
        "phase_trace.json", "event_trace.json", "path_trace.json", "gain_trace.json",
        "metrics.json", "cpu_memory_latency.json", "sha256_manifest.json",
    )
    architectures = ("P1", "P2", "P2H", "P3", "P5")
    all_architectures = {"P1", "P2", "P2H", "P3", "P4", "P5", "P6"}
    candidates = {"P2", "P2H", "P3", "P5"}

    def finite(value: Any) -> bool:
        if isinstance(value, dict):
            return all(finite(item) for item in value.values())
        if isinstance(value, list):
            return all(finite(item) for item in value)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            try:
                return math.isfinite(float(value))
            except (OverflowError, TypeError, ValueError):
                return False
        return True

    def finite_number(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and finite(value)

    def load_json(path: Path, label: str) -> Any:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"invalid_json:{label}:{exc}")
            return None
        if not finite(value):
            errors.append(f"nonfinite:{label}")
        return value

    def safe_relative(value: Any) -> bool:
        return _is_safe_manifest_relative(value)

    def mapping_at(value: Any, *keys: str) -> dict[str, Any]:
        for key in keys:
            if not isinstance(value, dict):
                return {}
            value = value.get(key)
        return value if isinstance(value, dict) else {}

    def hash_matches(path: Path, expected: Any) -> bool:
        if not path.is_file() or not isinstance(expected, str):
            return False
        try:
            return sha256_file(path) == expected
        except OSError:
            return False

    def compare_values(saved: Any, expected: Any, label: str) -> None:
        if isinstance(expected, dict):
            if not isinstance(saved, dict):
                errors.append(f"metric_shape:{label}")
                return
            if set(saved) != set(expected):
                errors.append(f"metric_inventory:{label}")
                return
            for key in expected:
                compare_values(saved[key], expected[key], f"{label}/{key}")
            return
        if isinstance(expected, list):
            if not isinstance(saved, list) or len(saved) != len(expected):
                errors.append(f"metric_shape:{label}")
                return
            for index, (saved_item, expected_item) in enumerate(zip(saved, expected)):
                compare_values(saved_item, expected_item, f"{label}/{index}")
            return
        if isinstance(expected, bool) or isinstance(expected, str) or expected is None:
            if saved != expected:
                errors.append(f"metric_value:{label}")
            return
        if not isinstance(saved, (int, float)) or isinstance(saved, bool) or not finite(saved):
            errors.append(f"metric_value:{label}")
            return
        if not math.isclose(float(saved), float(expected), rel_tol=0.0, abs_tol=PCM24_METRIC_TOLERANCE):
            errors.append(f"metric_value:{label}")

    manifest = load_json(manifest_path, "bakeoff_manifest.json")
    if not isinstance(manifest, dict):
        return errors or ["bakeoff_manifest.json must be an object"]
    manifest_status = manifest.get("status")
    manifest_reference = manifest.get("reference_status")
    if (manifest_status, manifest_reference) not in {
        ("REFERENCE_TARGET_MISSING", "REFERENCE_POINTER_ONLY"),
        ("R2_DIAGNOSTIC_READY", "EXTERNAL_R2_POINTER"),
    }:
        errors.append("manifest_status_reference")
    if "selected_architecture" not in manifest:
        errors.append("selection_missing:manifest")
    elif manifest["selected_architecture"] is not None:
        errors.append("manifest_selection")

    expected_files = {
        f"{architecture}/{scene}/{filename}"
        for architecture in architectures for scene in SCENES for filename in case_files
    } | set(required_state)
    manifest_files = manifest.get("files")
    if not isinstance(manifest_files, dict):
        errors.append("manifest_files_invalid")
        manifest_files = {}
    listed_files = set(manifest_files)
    for relative in sorted(expected_files - listed_files):
        errors.append(f"missing_required:{relative}")
    for relative in sorted(listed_files - expected_files):
        errors.append(f"outer_manifest_extra:{relative}")
    actual_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*") if path.is_file() and path != manifest_path
    }
    for relative in sorted(actual_files - listed_files):
        errors.append(f"outer_unlisted:{relative}")
    for relative, expected in manifest_files.items():
        if not safe_relative(relative):
            errors.append(f"unsafe_path:{relative}")
            continue
        path = root / Path(relative)
        if not path.is_file():
            errors.append(f"missing:{relative}")
        elif not hash_matches(path, expected):
            errors.append(f"sha:{relative}")

    states: dict[str, Any] = {}
    reopened_post_ptr: dict[tuple[str, str], np.ndarray] = {}
    for name in required_state:
        path = root / name
        if not path.is_file():
            errors.append(f"missing_required:{name}")
            continue
        states[name] = load_json(path, name)

    for name, state in states.items():
        if not isinstance(state, dict):
            errors.append(f"state_shape:{name}")
            continue
        if name != "rejected_architectures" and state.get("status") != manifest_status:
            errors.append(f"status:{name}")
        elif name == "rejected_architectures" and state.get("status") != manifest_status:
            errors.append(f"status:{name}")
        if "reference_status" in state and state.get("reference_status") != manifest_reference:
            errors.append(f"reference_status:{name}")
        if "selected_architecture" not in state:
            errors.append(f"selection_missing:{name}")
        elif state["selected_architecture"] is not None:
            errors.append(f"selection:{name}")
        if name in {"parent_candidate_metrics.json", "ablation_results.json"} and state.get("selection_eligible") is not False:
            errors.append(f"selection_eligible:{name}")

    results = states.get("bakeoff_results.json")
    if not isinstance(results, dict):
        results = {}
    result_architectures = results.get("architectures", {})
    if not isinstance(result_architectures, dict) or set(result_architectures) != all_architectures:
        errors.append("nested_architecture_inventory")
        result_architectures = result_architectures if isinstance(result_architectures, dict) else {}
    for architecture, expected_placeholder in PLACEHOLDER_RECORDS.items():
        placeholder = result_architectures.get(architecture)
        if not isinstance(placeholder, dict):
            errors.append(f"placeholder_shape:{architecture}")
            continue
        if set(placeholder) != set(expected_placeholder):
            errors.append(f"placeholder_inventory:{architecture}")
        for field, expected in expected_placeholder.items():
            if placeholder.get(field) != expected:
                errors.append(f"placeholder_{field}:{architecture}")
    for architecture in architectures:
        record = result_architectures.get(architecture, {})
        scenes = record.get("scenes", {}) if isinstance(record, dict) else {}
        if not isinstance(scenes, dict) or set(scenes) != set(SCENES):
            errors.append(f"nested_scene_inventory:{architecture}")
    parent_metrics = states.get("parent_candidate_metrics.json")
    parent_metrics = parent_metrics if isinstance(parent_metrics, dict) else {}
    parent_records = parent_metrics.get("parent", {})
    candidate_records = parent_metrics.get("architectures", {})
    if not isinstance(parent_records, dict) or set(parent_records) != set(SCENES):
        errors.append("nested_parent_scene_inventory")
        parent_records = parent_records if isinstance(parent_records, dict) else {}
    if not isinstance(candidate_records, dict) or set(candidate_records) != candidates:
        errors.append("nested_parent_candidate_inventory")
        candidate_records = candidate_records if isinstance(candidate_records, dict) else {}
    for architecture in candidates:
        if not isinstance(candidate_records.get(architecture), dict) or set(candidate_records[architecture]) != set(SCENES):
            errors.append(f"nested_parent_candidate_scene_inventory:{architecture}")

    ablation_state = states.get("ablation_results.json")
    ablation_state = ablation_state if isinstance(ablation_state, dict) else {}
    ablations = ablation_state.get("ablations", {})
    ablation_pairs = {
        "P2_to_P2H_waveguide": ("P2", "P2H"),
        "P2H_to_P3_timbre_map": ("P2H", "P3"),
        "P3_to_P5_transient": ("P3", "P5"),
    }
    if not isinstance(ablations, dict) or set(ablations) != set(ablation_pairs):
        errors.append("nested_ablation_inventory")
        ablations = ablations if isinstance(ablations, dict) else {}
    for name in ablation_pairs:
        if not isinstance(ablations.get(name), dict) or set(ablations[name]) != set(SCENES):
            errors.append(f"nested_ablation_scene_inventory:{name}")

    matrix_path = Path(__file__).resolve().parents[5] / "tasks" / "reports" / "runtime" / "s12-stage-w" / "parameter_usage_matrix.json"
    try:
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        geometry = matrix["stage_w_consumed_paths"]["geometry"]
        expected_geometry = {
            "crankpin_geometry": bool(geometry["piston.crankpin_geometry"]),
            "rotor_geometry": bool(geometry.get("piston.rotor_geometry", False)),
        }
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        expected_geometry = None
        errors.append("geometry_matrix_missing")

    for architecture in architectures:
        for scene in SCENES:
            case_label = f"{architecture}/{scene}"
            case = root / architecture / scene
            for name in case_files:
                if not (case / name).is_file():
                    errors.append(f"missing_required:{case_label}/{name}")
            case_json: dict[str, Any] = {}
            for name in case_files[3:]:
                path = case / name
                if path.is_file():
                    value = load_json(path, f"{name.removesuffix('.json')}:{case_label}")
                    case_json[name] = value
            try:
                raw, raw_meta = read_pcm24_wav(case / "raw_source.wav")
                post, post_meta = read_pcm24_wav(case / "post_ptr_raw.wav")
                monitor, monitor_meta = read_pcm24_wav(case / "monitor.wav")
            except (OSError, ValueError, wave.Error, EOFError) as exc:
                errors.append(f"artifact:{case_label}:{exc}")
                continue
            reopened_post_ptr[(architecture, scene)] = post
            if max(raw_meta["clipping"], post_meta["clipping"], monitor_meta["clipping"]) != 0:
                errors.append(f"clipping:{case_label}")
            if len({raw_meta["frames"], post_meta["frames"], monitor_meta["frames"]}) != 1:
                errors.append(f"frames:{case_label}")
            if any(metadata["sample_rate_hz"] != SAMPLE_RATE_HZ for metadata in (raw_meta, post_meta, monitor_meta)):
                errors.append(f"sample_rate:{case_label}")
            if np.array_equal(raw, post) or np.array_equal(raw, monitor) or np.array_equal(post, monitor):
                errors.append(f"separation:{case_label}")

            metrics = case_json.get("metrics.json")
            if not isinstance(metrics, dict):
                continue
            latency = case_json.get("cpu_memory_latency.json")
            latency_label = f"cpu_memory_latency:{case_label}"
            if not isinstance(latency, dict):
                errors.append(f"{latency_label}:shape")
            else:
                render_seconds = latency.get("render_seconds")
                if not isinstance(render_seconds, (int, float)) or isinstance(render_seconds, bool) or not finite(render_seconds) or render_seconds < 0.0:
                    errors.append(latency_label)
                for field in ("memory_bytes", "state_rate_hz", "block_size", "latency_seconds", "cpu_seconds", "peak_memory_bytes"):
                    value = latency.get(field)
                    if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool) or not finite(value) or value < 0.0):
                        errors.append(f"{latency_label}/{field}")
            if metrics.get("architecture") != architecture or metrics.get("scene") != scene or metrics.get("status") != manifest_status or metrics.get("reference_status") != manifest_reference:
                errors.append(f"identity_gate:{case_label}")
            if "selected_architecture" not in metrics:
                errors.append(f"selection_missing:{case_label}")
            elif metrics["selected_architecture"] is not None:
                errors.append(f"selection:{case_label}")
            expected_audio = {
                "raw_metrics": {"peak": float(np.max(np.abs(raw))), "rms": float(np.sqrt(np.mean(np.square(raw))))},
                "post_ptr_metrics": {"peak": float(np.max(np.abs(post))), "rms": float(np.sqrt(np.mean(np.square(post))))},
                "monitor_metrics": {"peak": float(np.max(np.abs(monitor))), "rms": float(np.sqrt(np.mean(np.square(monitor))))},
            }
            for key, expected_audio_metrics in expected_audio.items():
                saved = metrics.get(key)
                if not isinstance(saved, dict) or not all(field in saved for field in expected_audio_metrics):
                    errors.append(f"audio_metrics_missing:{case_label}/{key}")
                else:
                    compare_values(saved, expected_audio_metrics, f"audio_metrics:{case_label}/{key}")
                    if "clipping" in saved and saved["clipping"] != 0:
                        errors.append(f"clipping_saved:{case_label}/{key}")
            recomputed_click = {"raw": _block_click_metrics(raw), "post_ptr": _block_click_metrics(post), "monitor": _block_click_metrics(monitor)}
            saved_click = metrics.get("click_metrics")
            if not isinstance(saved_click, dict):
                errors.append(f"click_saved:{case_label}")
            else:
                compare_values(saved_click, recomputed_click, f"click_saved:{case_label}")
            if any(not item["passed"] for item in recomputed_click.values()):
                errors.append(f"click_gate:{case_label}")

            event_trace = case_json.get("event_trace.json")
            if not isinstance(event_trace, dict) or "afterfire_event_count" not in event_trace:
                errors.append(f"afterfire_event_count_missing:{case_label}")
            else:
                afterfire = event_trace["afterfire_event_count"]
                if not isinstance(afterfire, list) or not afterfire or not all(isinstance(item, (int, float)) and not isinstance(item, bool) and finite(item) and item >= 0 for item in afterfire):
                    errors.append(f"afterfire_event_count_invalid:{case_label}")
                elif scene == "afterfire_ineligible" and any(item != 0 for item in afterfire):
                    errors.append(f"afterfire_wrong_condition:{case_label}")

            diagnostics = metrics.get("diagnostics", {})
            if architecture in candidates:
                consumption = diagnostics.get("parameter_consumption") if isinstance(diagnostics, dict) else None
                expected = {"collector_assignment": True, "transfer_ir": True}
                if expected_geometry is not None:
                    expected.update(expected_geometry)
                if not isinstance(consumption, dict) or any(type(consumption.get(key)) is not bool or consumption.get(key) is not value for key, value in expected.items()):
                    errors.append(f"parameter_consumption:{case_label}")

            inner = case_json.get("sha256_manifest.json")
            if not isinstance(inner, dict) or set(inner) != set(case_files[:-1]):
                errors.append(f"case_manifest_inventory:{case_label}")
            elif any(not hash_matches(case / name, inner.get(name)) for name in case_files[:-1]):
                errors.append(f"case_manifest_sha:{case_label}")

            record = mapping_at(result_architectures, architecture, "scenes", scene)
            for key, filename in (("raw_sha256", "raw_source.wav"), ("post_ptr_sha256", "post_ptr_raw.wav"), ("monitor_sha256", "monitor.wav")):
                try:
                    actual_hash = sha256_file(case / filename)
                except OSError as exc:
                    errors.append(f"hash:{case_label}/{filename}:{exc}")
                    continue
                if record.get(key) != actual_hash:
                    errors.append(f"nested_hash:{case_label}/{key}")
                if architecture == "P1":
                    expected_parent = mapping_at(parent_records, scene).get(key)
                    if expected_parent != actual_hash:
                        errors.append(f"parent_candidate_hash:{case_label}/{key}")
                else:
                    expected_candidate = mapping_at(candidate_records, architecture, scene).get(key)
                    if expected_candidate != actual_hash:
                        errors.append(f"parent_candidate_hash:{case_label}/{key}")

    for scene in SCENES:
        result_parent = mapping_at(result_architectures, "P1", "scenes", scene)
        parent = mapping_at(parent_records, scene)
        for key in ("raw_sha256", "post_ptr_sha256", "monitor_sha256"):
            if parent.get(key) != result_parent.get(key):
                errors.append(f"parent_candidate_hash:P1/{scene}/{key}")
    for architecture in candidates:
        for scene in SCENES:
            result_record = mapping_at(result_architectures, architecture, "scenes", scene)
            candidate = mapping_at(candidate_records, architecture, scene)
            for key in ("raw_sha256", "post_ptr_sha256", "monitor_sha256"):
                if candidate.get(key) != result_record.get(key):
                    errors.append(f"parent_candidate_hash:{architecture}/{scene}/{key}")
            expected_difference = mapping_at(result_record, "comparison").get("parent_candidate_difference_rms")
            if "parent_candidate_difference_rms" not in candidate:
                errors.append(f"parent_candidate_difference_missing:{architecture}/{scene}")
            elif not finite_number(expected_difference) or not finite_number(candidate["parent_candidate_difference_rms"]):
                errors.append(f"parent_candidate_difference_invalid:{architecture}/{scene}")
            else:
                compare_values(candidate["parent_candidate_difference_rms"], expected_difference, f"parent_candidate_difference:{architecture}/{scene}")
            parent_pcm = reopened_post_ptr.get(("P1", scene))
            candidate_pcm = reopened_post_ptr.get((architecture, scene))
            if parent_pcm is None or candidate_pcm is None:
                errors.append(f"parent_candidate_difference_pcm_missing:{architecture}/{scene}")
            elif parent_pcm.shape != candidate_pcm.shape:
                errors.append(f"parent_candidate_difference_pcm_frames:{architecture}/{scene}")
            else:
                recomputed_difference = float(np.sqrt(np.mean(np.square(parent_pcm - candidate_pcm))))
                result_difference = mapping_at(result_record, "comparison").get("parent_candidate_difference_rms")
                if not finite_number(result_difference) or not math.isclose(result_difference, recomputed_difference, rel_tol=0.0, abs_tol=PCM24_METRIC_TOLERANCE):
                    errors.append(f"parent_candidate_difference_pcm:{architecture}/{scene}")
                summary_difference = candidate.get("parent_candidate_difference_rms")
                if not finite_number(summary_difference) or not math.isclose(summary_difference, recomputed_difference, rel_tol=0.0, abs_tol=PCM24_METRIC_TOLERANCE):
                    errors.append(f"parent_candidate_difference_pcm_summary:{architecture}/{scene}")

    for name, (left, right) in ablation_pairs.items():
        for scene in SCENES:
            left_record = mapping_at(result_architectures, left, "scenes", scene)
            right_record = mapping_at(result_architectures, right, "scenes", scene)
            saved = mapping_at(ablations, name, scene)
            for field, key in (("post_ptr_sha256_different", "post_ptr_sha256"), ("monitor_sha256_different", "monitor_sha256")):
                expected = left_record.get(key) != right_record.get(key)
                if saved.get(field) is not expected:
                    errors.append(f"ablation_truth:{name}/{scene}/{field}")
    return errors


def _stage_canonical_path(root: Path) -> str:
    return root.resolve().as_posix()


def _stage_canonical_id(canonical_path: str) -> str:
    return hashlib.sha256(canonical_path.encode("utf-8")).hexdigest()


def _stage_source_head() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[5],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "stage_w_worktree"
    head = result.stdout.strip()
    return head if len(head) == 40 and all(character in "0123456789abcdef" for character in head.lower()) else "stage_w_worktree"


def _stage_json_finite(value: Any) -> bool:
    if isinstance(value, dict):
        return all(isinstance(key, str) and _stage_json_finite(item) for key, item in value.items())
    if isinstance(value, list):
        return all(_stage_json_finite(item) for item in value)
    if isinstance(value, float):
        return math.isfinite(value)
    return True


def _stage_load_json(path: Path, label: str, errors: list[str]) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"invalid_json:{label}:{exc}")
        return None
    if not _stage_json_finite(value):
        errors.append(f"nonfinite:{label}")
    return value


def _stage_number(value: Any, label: str, errors: list[str], *, minimum: float | None = None) -> float | None:
    """Read a finite numeric value without allowing bool/overflow to escape."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(label)
        return None
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        errors.append(label)
        return None
    if not math.isfinite(number) or (minimum is not None and number < minimum):
        errors.append(label)
        return None
    return number


def _stage_expected_geometry() -> dict[str, bool] | None:
    matrix_path = Path(__file__).resolve().parents[5] / "tasks" / "reports" / "runtime" / "s12-stage-w" / "parameter_usage_matrix.json"
    try:
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        geometry = matrix["stage_w_consumed_paths"]["geometry"]
        return {
            "crankpin_geometry": bool(geometry["piston.crankpin_geometry"]),
            "rotor_geometry": bool(geometry.get("piston.rotor_geometry", False)),
        }
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError):
        return None


def _stage_expected_case_files() -> set[str]:
    return {f"{architecture}/{scene}/{filename}" for architecture in RENDERABLE_ARCHITECTURES for scene in SCENES for filename in STAGE_CASE_FILES}


def validate_hellcat_architecture_stage(
    stage_root: str | Path,
    architecture: str,
    duration_s: float,
    *,
    long_window: bool = False,
    parent_stage_root: str | Path | None = None,
) -> list[str]:
    """Strictly validate one externally staged synthetic Hellcat architecture."""
    root = Path(stage_root)
    errors: list[str] = []
    if architecture not in RENDERABLE_ARCHITECTURES:
        errors.append(f"architecture:{architecture}")
    if type(long_window) is not bool:
        errors.append("long_window")
    try:
        expected_durations = {scene: scene_duration_s(scene, duration_s, long_window=long_window) for scene in SCENES}
    except (TypeError, ValueError, OverflowError):
        expected_durations = {}
        errors.append("duration_s")

    manifest_path = root / "stage_manifest.json"
    if not root.is_dir():
        return errors + ["stage_root missing"]
    if not manifest_path.is_file():
        errors.append("stage_manifest.json missing")
        return errors

    manifest = _stage_load_json(manifest_path, "stage_manifest.json", errors)
    if not isinstance(manifest, dict):
        return errors or ["stage_manifest.json must be an object"]
    canonical_path = _stage_canonical_path(root)
    if manifest.get("schema_version") != STAGE_MANIFEST_SCHEMA:
        errors.append("schema_version")
    if manifest.get("canonical_stage_path") != canonical_path:
        errors.append("canonical_stage_path")
    if manifest.get("canonical_stage_id") != _stage_canonical_id(canonical_path):
        errors.append("canonical_stage_id")
    if manifest.get("architecture") != architecture:
        errors.append("architecture_manifest")
    if manifest.get("scenes") != list(SCENES):
        errors.append("scene_inventory")
    if manifest.get("status") != "STAGE_COMPLETE":
        errors.append("status")
    if manifest.get("reference_status") != "REFERENCE_POINTER_ONLY":
        errors.append("reference_status")
    if "selected_architecture" not in manifest:
        errors.append("selection_missing")
    elif manifest["selected_architecture"] is not None:
        errors.append("selection")
    requested_duration = _stage_number(manifest.get("requested_duration_s"), "requested_duration_s", errors, minimum=0.20)
    expected_duration = _stage_number(duration_s, "duration_s", errors, minimum=0.20)
    if requested_duration is not None and expected_duration is not None and not math.isclose(requested_duration, expected_duration, rel_tol=0.0, abs_tol=0.0):
        errors.append("requested_duration_s")
    if manifest.get("long_window") is not long_window:
        errors.append("long_window_manifest")
    if manifest.get("scene_duration_s") != expected_durations:
        errors.append("scene_duration_s")
    if manifest.get("source_head") != _stage_source_head():
        errors.append("source_head")

    parent = manifest.get("parent_stage")
    verified_parent_pcm: dict[str, np.ndarray] = {}
    if architecture != "P1" and parent_stage_root is not None:
        supplied_parent_root = Path(parent_stage_root)
        if not supplied_parent_root.is_dir():
            errors.append("parent_stage_root:missing")
        else:
            parent_errors = validate_hellcat_architecture_stage(
                supplied_parent_root,
                "P1",
                duration_s,
                long_window=long_window,
            )
            if parent_errors:
                errors.extend(f"parent_stage:{error}" for error in parent_errors)
            else:
                try:
                    actual_parent_record = {
                        "canonical_stage_path": _stage_canonical_path(supplied_parent_root),
                        "canonical_stage_id": _stage_canonical_id(_stage_canonical_path(supplied_parent_root)),
                        "architecture": "P1",
                        "status": "STAGE_COMPLETE",
                        "reference_status": "REFERENCE_POINTER_ONLY",
                        "selected_architecture": None,
                        "post_ptr_sha256": {
                            scene: sha256_file(supplied_parent_root / "P1" / scene / "post_ptr_raw.wav")
                            for scene in SCENES
                        },
                    }
                    if parent != actual_parent_record:
                        errors.append("parent_stage:binding")
                    for scene in SCENES:
                        verified_parent_pcm[scene] = read_pcm24_wav(supplied_parent_root / "P1" / scene / "post_ptr_raw.wav")[0]
                except (OSError, UnicodeError, json.JSONDecodeError, ValueError, wave.Error, EOFError) as exc:
                    errors.append(f"parent_stage:read:{exc}")

    if architecture == "P1":
        if parent is not None:
            errors.append("parent_stage:P1")
    elif not isinstance(parent, dict):
        errors.append("parent_stage:missing")
    else:
        required_parent_keys = {"canonical_stage_path", "canonical_stage_id", "architecture", "status", "reference_status", "selected_architecture", "post_ptr_sha256"}
        if set(parent) != required_parent_keys:
            errors.append("parent_stage:inventory")
        if parent.get("architecture") != "P1" or parent.get("status") != "STAGE_COMPLETE" or parent.get("reference_status") != "REFERENCE_POINTER_ONLY" or parent.get("selected_architecture") is not None:
            errors.append("parent_stage:identity")
        parent_path = parent.get("canonical_stage_path")
        parent_id = parent.get("canonical_stage_id")
        if not isinstance(parent_path, str) or not parent_path or not isinstance(parent_id, str) or parent_id != _stage_canonical_id(parent_path):
            errors.append("parent_stage:canonical_identity")
        post_hashes = parent.get("post_ptr_sha256")
        if not isinstance(post_hashes, dict) or set(post_hashes) != set(SCENES) or any(not isinstance(value, str) or len(value) != 64 or any(character not in "0123456789abcdef" for character in value) for value in (post_hashes.values() if isinstance(post_hashes, dict) else ())):
            errors.append("parent_stage:post_ptr_sha256")

    expected_files = _stage_expected_case_files()
    manifest_files = manifest.get("files")
    if not isinstance(manifest_files, dict):
        errors.append("files_inventory")
        manifest_files = {}
    elif set(manifest_files) != {relative for relative in expected_files if relative.startswith(f"{architecture}/")}:
        errors.append("files_inventory")
    actual_files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    expected_actual = {"stage_manifest.json"} | {relative for relative in expected_files if relative.startswith(f"{architecture}/")}
    actual_top_dirs = {path.name for path in root.iterdir() if path.is_dir()}
    if actual_top_dirs != {architecture}:
        errors.append("stage_directory_inventory")
    architecture_root = root / architecture
    actual_scene_dirs = {path.name for path in architecture_root.iterdir() if path.is_dir()} if architecture_root.is_dir() else set()
    if actual_scene_dirs != set(SCENES):
        errors.append("scene_directory_inventory")
    for relative in sorted(actual_files - expected_actual):
        errors.append(f"extra_file:{relative}")
    for relative in sorted(expected_actual - actual_files):
        errors.append(f"missing_file:{relative}")
    for relative, expected_hash in manifest_files.items():
        if not _is_safe_manifest_relative(relative):
            errors.append(f"unsafe_path:{relative}")
            continue
        path = root / Path(relative)
        if not path.is_file() or not isinstance(expected_hash, str) or len(expected_hash) != 64 or sha256_file(path) != expected_hash:
            errors.append(f"sha:{relative}")

    geometry = _stage_expected_geometry()
    if geometry is None:
        errors.append("geometry_matrix_missing")
    expected_case_files_without_inner = STAGE_CASE_FILES[:-1]
    candidate_post_ptr: dict[str, np.ndarray] = {}
    candidate_comparison: dict[str, float] = {}
    for scene in SCENES:
        case_label = f"{architecture}/{scene}"
        case = root / architecture / scene
        actual_case_files = {path.name for path in case.iterdir()} if case.is_dir() else set()
        if actual_case_files != set(STAGE_CASE_FILES):
            errors.append(f"case_inventory:{case_label}")
        state = _stage_load_json(case / "state_trace.json", f"state_trace:{case_label}", errors) if (case / "state_trace.json").is_file() else None
        trace_duration = expected_durations.get(scene)
        expected_trace = None
        if trace_duration is not None:
            try:
                expected_trace = build_hellcat_bakeoff_trace(scene, trace_duration)
            except (TypeError, ValueError):
                expected_trace = None
        if not isinstance(state, dict) or expected_trace is None:
            errors.append(f"state_trace:{case_label}")
        else:
            expected_state = {"sample_rate_hz": STATE_RATE_HZ, "time_s": expected_trace.time_s, "rpm": expected_trace.rpm, "load": expected_trace.load, "throttle": expected_trace.throttle, "acceleration_mps2": expected_trace.acceleration_mps2}
            if set(state) != set(expected_state):
                errors.append(f"state_trace_inventory:{case_label}")
            for key, expected_values in expected_state.items():
                saved = state.get(key)
                if key == "sample_rate_hz":
                    if saved != expected_values:
                        errors.append(f"state_trace_value:{case_label}/{key}")
                    continue
                if not isinstance(saved, list):
                    errors.append(f"state_trace_values:{case_label}/{key}")
                    continue
                numeric_values = [_stage_number(value, f"state_trace_values:{case_label}/{key}", errors) for value in saved]
                if any(value is None for value in numeric_values):
                    continue
                actual = np.asarray(numeric_values, dtype=np.float64)
                if actual.shape != expected_values.shape or not np.array_equal(actual, expected_values):
                    errors.append(f"state_trace_mismatch:{case_label}/{key}")

        audio: dict[str, np.ndarray] = {}
        metadata: dict[str, dict[str, Any]] = {}
        for name, key in (("raw_source.wav", "raw"), ("post_ptr_raw.wav", "post_ptr"), ("monitor.wav", "monitor")):
            path = case / name
            try:
                values, info = read_pcm24_wav(path)
            except (OSError, ValueError, wave.Error, EOFError) as exc:
                errors.append(f"artifact:{case_label}:{name}:{exc}")
                continue
            audio[key] = values
            metadata[key] = info
            if info.get("channels") != 2 or info.get("sample_width_bits") != 24 or info.get("sample_rate_hz") != SAMPLE_RATE_HZ or info.get("clipping") != 0:
                errors.append(f"wav_format:{case_label}/{name}")
        if len(metadata) == 3:
            frame_counts = {info["frames"] for info in metadata.values()}
            expected_frames = expected_trace.rpm.size * BLOCK_SIZE if expected_trace is not None else None
            if len(frame_counts) != 1 or expected_frames not in frame_counts:
                errors.append(f"frames:{case_label}")
            if np.array_equal(audio["raw"], audio["post_ptr"]) or np.array_equal(audio["raw"], audio["monitor"]) or np.array_equal(audio["post_ptr"], audio["monitor"]):
                errors.append(f"separation:{case_label}")
            if architecture != "P1":
                candidate_post_ptr[scene] = audio["post_ptr"]

        json_cases = {}
        for filename in ("phase_trace.json", "event_trace.json", "path_trace.json", "gain_trace.json", "metrics.json", "cpu_memory_latency.json", "sha256_manifest.json"):
            path = case / filename
            if path.is_file():
                json_cases[filename] = _stage_load_json(path, f"{filename}:{case_label}", errors)
        metrics = json_cases.get("metrics.json")
        if not isinstance(metrics, dict):
            errors.append(f"metrics:{case_label}")
        else:
            if metrics.get("architecture") != architecture or metrics.get("scene") != scene or metrics.get("status") != "REFERENCE_TARGET_MISSING" or metrics.get("reference_status") != "REFERENCE_POINTER_ONLY":
                errors.append(f"identity_gate:{case_label}")
            if "selected_architecture" not in metrics:
                errors.append(f"selection_missing:{case_label}")
            elif metrics["selected_architecture"] is not None:
                errors.append(f"selection:{case_label}")
            if len(audio) == 3:
                expected_metrics = {
                    "raw_metrics": {"peak": float(np.max(np.abs(audio["raw"]))), "rms": float(np.sqrt(np.mean(np.square(audio["raw"]))))},
                    "post_ptr_metrics": {"peak": float(np.max(np.abs(audio["post_ptr"]))), "rms": float(np.sqrt(np.mean(np.square(audio["post_ptr"]))))},
                    "monitor_metrics": {"peak": float(np.max(np.abs(audio["monitor"]))), "rms": float(np.sqrt(np.mean(np.square(audio["monitor"]))))},
                }
                for key, expected in expected_metrics.items():
                    saved = metrics.get(key)
                    if not isinstance(saved, dict) or set(saved) != set(expected):
                        errors.append(f"audio_metrics:{case_label}/{key}")
                    else:
                        for field, expected_value in expected.items():
                            value = _stage_number(saved[field], f"audio_metrics:{case_label}/{key}/{field}", errors)
                            if value is None or not math.isclose(value, expected_value, rel_tol=0.0, abs_tol=PCM24_METRIC_TOLERANCE):
                                errors.append(f"audio_metrics:{case_label}/{key}/{field}")
                expected_click = {key: _block_click_metrics(value) for key, value in audio.items()}
                saved_click = metrics.get("click_metrics")
                if not isinstance(saved_click, dict):
                    errors.append(f"click_metrics:{case_label}")
                else:
                    for output_name in expected_click:
                        gate = saved_click.get(output_name)
                        if not isinstance(gate, dict) or type(gate.get("passed")) is not bool or gate.get("passed") is not True:
                            errors.append(f"click_gate:{case_label}/{output_name}")
                    if saved_click != expected_click:
                        errors.append(f"click_metrics:{case_label}")
            diagnostics = metrics.get("diagnostics")
            if not isinstance(diagnostics, dict) or diagnostics.get("ptr_status") != "FROZEN_RUNTIME_PTR_ADAPTER" or (architecture != "P1" and not isinstance(diagnostics.get("monitor_source"), str)):
                errors.append(f"diagnostics:{case_label}")
            if architecture != "P1" and isinstance(diagnostics, dict):
                expected_consumption = {"collector_assignment": True, "transfer_ir": True}
                if geometry is not None:
                    expected_consumption.update(geometry)
                consumption = diagnostics.get("parameter_consumption")
                if not isinstance(consumption, dict) or any(type(consumption.get(key)) is not bool or consumption.get(key) is not value for key, value in expected_consumption.items()):
                    errors.append(f"parameter_consumption:{case_label}")
            comparison = metrics.get("comparison")
            if not isinstance(comparison, dict):
                errors.append(f"comparison:{case_label}")
            else:
                difference = _stage_number(comparison.get("parent_candidate_difference_rms"), f"comparison_difference:{case_label}", errors, minimum=0.0)
                if difference is None:
                    errors.append(f"comparison_difference:{case_label}")
                else:
                    candidate_comparison[scene] = difference
                    if architecture == "P1" and difference != 0.0:
                        errors.append(f"comparison_difference:{case_label}")

        latency = json_cases.get("cpu_memory_latency.json")
        if not isinstance(latency, dict):
            errors.append(f"cpu_memory_latency:{case_label}")
        elif _stage_number(latency.get("render_seconds"), f"cpu_memory_latency:{case_label}", errors, minimum=0.0) is None:
            errors.append(f"cpu_memory_latency:{case_label}")
        inner = json_cases.get("sha256_manifest.json")
        if not isinstance(inner, dict) or set(inner) != set(expected_case_files_without_inner):
            errors.append(f"case_manifest_inventory:{case_label}")
        else:
            for filename in expected_case_files_without_inner:
                path = case / filename
                expected_hash = inner.get(filename)
                if not isinstance(expected_hash, str) or len(expected_hash) != 64 or not path.is_file() or sha256_file(path) != expected_hash:
                    errors.append(f"case_manifest_sha:{case_label}/{filename}")
        event_trace = json_cases.get("event_trace.json")
        afterfire_values = event_trace.get("afterfire_event_count") if isinstance(event_trace, dict) else None
        if not isinstance(afterfire_values, list) or not afterfire_values:
            errors.append(f"afterfire_event_count:{case_label}")
        else:
            numeric_afterfire = [_stage_number(value, f"afterfire_event_count:{case_label}", errors, minimum=0.0) for value in afterfire_values]
            if any(value is None for value in numeric_afterfire):
                errors.append(f"afterfire_event_count:{case_label}")
            elif scene == "afterfire_ineligible" and any(value != 0 for value in numeric_afterfire):
                errors.append(f"afterfire_wrong_condition:{case_label}")

    if architecture != "P1" and parent_stage_root is not None and verified_parent_pcm:
        for scene in SCENES:
            parent_values = verified_parent_pcm.get(scene)
            candidate_values = candidate_post_ptr.get(scene)
            saved_difference = candidate_comparison.get(scene)
            if parent_values is None or candidate_values is None:
                errors.append(f"parent_candidate_difference_pcm_missing:{architecture}/{scene}")
                continue
            if parent_values.shape != candidate_values.shape:
                errors.append(f"parent_candidate_difference_pcm_frames:{architecture}/{scene}")
                continue
            recomputed_difference = float(np.sqrt(np.mean(np.square(parent_values - candidate_values))))
            if saved_difference is None or not math.isclose(saved_difference, recomputed_difference, rel_tol=0.0, abs_tol=PCM24_METRIC_TOLERANCE):
                errors.append(f"parent_candidate_difference_pcm:{architecture}/{scene}")

    return errors


def render_hellcat_architecture_stage(
    stage_root: str | Path,
    architecture: str,
    duration_s: float = 8.0,
    *,
    long_window: bool = False,
    parent_stage_root: str | Path | None = None,
) -> dict[str, Any]:
    """Render one complete architecture into a new external stage root."""
    root = Path(stage_root)
    if architecture not in RENDERABLE_ARCHITECTURES:
        raise ValueError(f"unsupported stage architecture: {architecture}")
    if type(long_window) is not bool:
        raise ValueError("long_window must be a bool")
    scene_durations = {scene: scene_duration_s(scene, duration_s, long_window=long_window) for scene in SCENES}
    if root.exists():
        if not root.is_dir() or any(root.iterdir()):
            raise FileExistsError(f"refusing to overwrite architecture stage: {root}")

    parent_manifest = None
    parent_post_ptr: dict[str, np.ndarray] = {}
    if architecture != "P1":
        if parent_stage_root is None:
            raise ValueError("candidate architecture requires verified P1 stage")
        parent_root = Path(parent_stage_root)
        parent_errors = validate_hellcat_architecture_stage(parent_root, "P1", duration_s, long_window=long_window)
        if parent_errors:
            raise ValueError(f"parent stage is not a verified P1 stage: {parent_errors}")
        parent_manifest = json.loads((parent_root / "stage_manifest.json").read_text(encoding="utf-8"))
        for scene in SCENES:
            parent_post_ptr[scene] = read_pcm24_wav(parent_root / "P1" / scene / "post_ptr_raw.wav")[0]

    root.mkdir(parents=True, exist_ok=True)
    scene_records: dict[str, Any] = {}
    for scene in SCENES:
        trace = build_hellcat_bakeoff_trace(scene, scene_durations[scene])
        scene_records[scene] = _write_case(root, architecture, scene, trace, None, parent_post_ptr=parent_post_ptr.get(scene))

    canonical_path = _stage_canonical_path(root)
    files = {path.relative_to(root).as_posix(): sha256_file(path) for path in sorted(root.rglob("*")) if path.is_file()}
    parent_record = None
    if parent_manifest is not None:
        parent_record = {
            "canonical_stage_path": parent_manifest["canonical_stage_path"],
            "canonical_stage_id": parent_manifest["canonical_stage_id"],
            "architecture": "P1",
            "status": "STAGE_COMPLETE",
            "reference_status": "REFERENCE_POINTER_ONLY",
            "selected_architecture": None,
            "post_ptr_sha256": {scene: parent_manifest["files"][f"P1/{scene}/post_ptr_raw.wav"] for scene in SCENES},
        }
    manifest = {
        "schema_version": STAGE_MANIFEST_SCHEMA,
        "canonical_stage_path": canonical_path,
        "canonical_stage_id": _stage_canonical_id(canonical_path),
        "source_head": _stage_source_head(),
        "architecture": architecture,
        "scenes": list(SCENES),
        "status": "STAGE_COMPLETE",
        "reference_status": "REFERENCE_POINTER_ONLY",
        "selected_architecture": None,
        "requested_duration_s": float(duration_s),
        "long_window": bool(long_window),
        "scene_duration_s": scene_durations,
        "parent_stage": parent_record,
        "files": files,
    }
    write_json(root / "stage_manifest.json", manifest)
    validation_errors = validate_hellcat_architecture_stage(
        root,
        architecture,
        duration_s,
        long_window=long_window,
        parent_stage_root=parent_stage_root if architecture != "P1" else None,
    )
    if validation_errors:
        raise ValueError(f"rendered architecture stage failed validation: {validation_errors}")
    result = dict(manifest)
    result["stage_manifest_path"] = str(root / "stage_manifest.json")
    result["scenes"] = scene_records
    return result


def publish_bakeoff_summaries(source_root: str | Path, output_root: str | Path, *, overwrite: bool = False) -> dict[str, Any]:
    source = Path(source_root)
    errors = validate_bakeoff_manifest(source)
    manifest = json.loads((source / "bakeoff_manifest.json").read_text(encoding="utf-8")) if not errors else {}
    for name in SUMMARY_FILES:
        path = source / name
        expected = manifest.get("files", {}).get(name)
        if expected is None:
            errors.append(f"summary_manifest:{name}")
        elif not path.is_file():
            errors.append(f"summary_missing:{name}")
        elif sha256_file(path) != expected:
            errors.append(f"summary_sha:{name}")
        else:
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                errors.append(f"summary_json:{name}")
    if errors:
        raise ValueError(f"invalid bake-off source: {errors}")
    output = Path(output_root)
    targets = [output / name for name in SUMMARY_FILES]
    if any(target.exists() for target in targets) and not overwrite:
        raise FileExistsError(f"refusing to overwrite bake-off summaries: {output}")
    output.mkdir(parents=True, exist_ok=True)
    for name, target in zip(SUMMARY_FILES, targets):
        target.write_bytes((source / name).read_bytes())
    result = json.loads((source / "bakeoff_results.json").read_text(encoding="utf-8"))
    return {"schema_version": "s12.stage_w.bakeoff_summary_receipt.v1", "status": result["status"], "reference_status": result["reference_status"], "selection_eligible": result["selected_architecture"] is not None, "files": {name: sha256_file(output / name) for name in SUMMARY_FILES}}


__all__ = [
    "SCENES", "STAGE_CASE_FILES", "build_hellcat_bakeoff_trace",
    "publish_bakeoff_summaries", "render_hellcat_architecture_stage",
    "run_hellcat_bakeoff", "scene_duration_s", "validate_bakeoff_manifest",
    "validate_hellcat_architecture_stage",
]
