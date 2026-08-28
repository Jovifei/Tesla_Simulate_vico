"""Fail-closed Ferrari/RX-7 migration receipts for unselected Stage-W paths."""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any

import numpy as np

from ..contracts import VehicleStateTrace
from ..event_domain.audition_monitor import render_audition_monitor
from ..event_domain.config_schema import load_config
from ..sources.flat_plane_v8_source import render_ferrari_458
from ..sources.rotary_turbo_source import render_rx7_fd
from ..stage_v.io import read_pcm24_wav, sha256_file, write_json, write_pcm24_wav
from .boundary_adapter import FrozenPtrStereo
from .persistent_engine import PersistentEventDomainEngine
from .click_contract import block_boundary_click_metrics

SAMPLE_RATE_HZ = 48000
BLOCK_SIZE = 960
STATE_RATE_HZ = SAMPLE_RATE_HZ // BLOCK_SIZE
OUTPUT_SCALE = 0.05
MIGRATION_SCENES = ("hot_idle", "steady_mid", "full_pull", "lift", "complete_cycle")

_CONFIGS = {"ferrari_458": "ferrari_458_v1", "rx7_fd": "rx7_fd_v1"}
_LEGACY_RENDERERS = {"ferrari_458": render_ferrari_458, "rx7_fd": render_rx7_fd}
PARAMETER_USAGE_MATRIX_PATH = Path(__file__).resolve().parents[5] / "tasks" / "reports" / "runtime" / "s12-stage-w" / "parameter_usage_matrix.json"
_EXPECTED_GEOMETRY = {
    "piston": {"crankpin_geometry": True, "rotor_geometry": False},
    "rotary_wankel": {"crankpin_geometry": False, "rotor_geometry": True},
}
_RANGES = {
    "ferrari_458": {"hot_idle": (1050.0, 1050.0, 0.14, 0.14), "steady_mid": (3800.0, 3800.0, 0.38, 0.38), "full_pull": (3000.0, 8800.0, 0.42, 0.98), "lift": (7900.0, 5200.0, 0.90, 0.04), "complete_cycle": (1050.0, 1050.0, 0.14, 0.14)},
    "rx7_fd": {"hot_idle": (920.0, 920.0, 0.15, 0.15), "steady_mid": (3400.0, 3400.0, 0.38, 0.38), "full_pull": (2800.0, 7600.0, 0.42, 0.98), "lift": (6900.0, 4500.0, 0.90, 0.04), "complete_cycle": (920.0, 920.0, 0.15, 0.15)},
}


def build_vehicle_migration_trace(vehicle_id: str, scene: str, duration_s: float = 8.0) -> VehicleStateTrace:
    """Build a block-aligned, synthetic state trace for one migration scene."""
    if vehicle_id not in _CONFIGS:
        raise ValueError(f"unsupported migration vehicle: {vehicle_id}")
    if scene not in MIGRATION_SCENES:
        raise ValueError(f"unsupported migration scene: {scene}")
    if not np.isfinite(duration_s) or duration_s < 0.20:
        raise ValueError("duration_s must be finite and >= 0.20")
    frame_count = max(2, int(round(duration_s * STATE_RATE_HZ)))
    time_s = np.linspace(0.0, frame_count * BLOCK_SIZE / SAMPLE_RATE_HZ - 1.0 / SAMPLE_RATE_HZ, frame_count, dtype=np.float64)
    state_time_s = np.arange(frame_count, dtype=np.float64) / STATE_RATE_HZ
    phase = np.linspace(0.0, 1.0, frame_count, dtype=np.float64)
    start_rpm, end_rpm, start_load, end_load = _RANGES[vehicle_id][scene]
    rpm = np.linspace(start_rpm, end_rpm, frame_count, dtype=np.float64)
    load = np.linspace(start_load, end_load, frame_count, dtype=np.float64)
    throttle = load.copy()
    if scene == "hot_idle":
        rpm += 3.0 * np.sin(2.0 * np.pi * 2.3 * state_time_s)
    elif scene == "lift":
        close = phase >= 0.42
        late_lift = phase >= 0.70
        throttle = np.where(close, end_load, start_load)
        load = np.where(close, np.where(late_lift, np.maximum(end_load, 0.12), 0.55), start_load)
        rpm = np.where(close, np.linspace(start_rpm, end_rpm, frame_count), start_rpm)
    elif scene == "complete_cycle":
        rpm = np.interp(phase, (0.0, 0.24, 0.60, 0.78, 1.0), (start_rpm, start_rpm, 0.98 * max(_RANGES[vehicle_id]["full_pull"][:2]), 0.55 * max(_RANGES[vehicle_id]["full_pull"][:2]), end_rpm))
        throttle = np.interp(phase, (0.0, 0.24, 0.60, 0.78, 1.0), (start_load, 0.42, 0.98, 0.03, end_load))
        load = np.interp(phase, (0.0, 0.24, 0.60, 0.70, 0.86, 1.0), (start_load, 0.42, 0.96, 0.55, 0.12, end_load))
    acceleration = np.gradient(rpm / 60.0, state_time_s)
    return VehicleStateTrace(time_s, rpm, load, throttle, acceleration).validate()


def _state_arrays(trace: VehicleStateTrace) -> dict[str, np.ndarray]:
    return {"rpm": trace.rpm, "load": trace.load, "throttle": trace.throttle, "acceleration_mps2": trace.acceleration_mps2}


def _render_architecture(vehicle_id: str, architecture: str, trace: VehicleStateTrace) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    if architecture == "P1":
        raw = _LEGACY_RENDERERS[vehicle_id](trace).pressure * OUTPUT_SCALE
        post_ptr = FrozenPtrStereo(SAMPLE_RATE_HZ).process(raw)
        monitor = render_audition_monitor(post_ptr, SAMPLE_RATE_HZ).audio
        return raw, post_ptr, monitor, {"source_model": "legacy_v015", "path_model": "legacy", "forced_induction_model": "legacy", "ptr_status": "FROZEN_RUNTIME_PTR_ADAPTER", "frame_trace": None}
    if architecture not in {"P2H", "P3"}:
        raise ValueError(f"unsupported migration architecture: {architecture}")
    engine = PersistentEventDomainEngine(
        load_config(_CONFIGS[vehicle_id]),
        SAMPLE_RATE_HZ,
        BLOCK_SIZE,
        ptr_enabled=True,
        path_model="waveguide_v1",
        forced_induction_model="timbre_map_v1" if architecture == "P3" else "harmonic_v1",
    )
    rendered = engine.process_with_trace(_state_arrays(trace))
    if rendered.post_ptr_raw is None:
        raise RuntimeError("P2H/P3 migration requires frozen PTR output")
    raw = rendered.raw_pcm * OUTPUT_SCALE
    post_ptr = rendered.post_ptr_raw * OUTPUT_SCALE
    monitor = rendered.monitor_pcm * OUTPUT_SCALE
    rendered.diagnostics["monitor_source"] = "PersistentEventDomainEngine.monitor_pcm"
    return raw, post_ptr, monitor, rendered.diagnostics


def _audio_metrics(audio: np.ndarray, metadata: dict[str, Any]) -> dict[str, Any]:
    return {"frames": int(metadata["frames"]), "channels": int(metadata["channels"]), "sample_rate_hz": int(metadata["sample_rate_hz"]), "clipping": int(metadata["clipping"]), "rms": float(np.sqrt(np.mean(np.square(audio)))), "peak": float(np.max(np.abs(audio)))}


def write_diagnostic_traces(case_root: Path, diagnostics: dict[str, Any]) -> None:
    trace = diagnostics.get("frame_trace")
    if trace is None:
        unavailable = {"status": "NOT_AVAILABLE_LEGACY", "reason": "legacy renderer has no persistent event-domain state"}
        write_json(case_root / "phase_trace.json", unavailable)
        # Keep the event-count contract present even for the legacy parent.
        # The parent cannot emit event-domain afterfire, so its count is an
        # explicit zero rather than an unavailable field.
        write_json(case_root / "event_trace.json", unavailable | {"afterfire_event_count": [0]})
        write_json(case_root / "path_trace.json", unavailable)
        write_json(case_root / "gain_trace.json", unavailable)
        return
    base = {"status": "PERSISTENT_ENGINE_TRACE", "sample_counter": trace["sample_counter"]}
    write_json(case_root / "phase_trace.json", base | {"phase_rad": trace["phase_rad"], "omega_rad_s": trace["omega_rad_s"]})
    write_json(case_root / "event_trace.json", base | {"event_count": trace["event_count"], "afterfire_event_count": trace["afterfire_event_count"], "combustion_torque_event_count": trace["combustion_torque_event_count"]})
    write_json(case_root / "path_trace.json", base | {"path_state_energy": trace["path_state_energy"], "afterfire_route": diagnostics.get("afterfire_route", {"route": "none"})})
    write_json(case_root / "gain_trace.json", base | {"monitor_gain_db": trace["monitor_gain_db"]})


def _write_case(root: Path, vehicle_id: str, architecture: str, scene: str, trace: VehicleStateTrace, parent_post_ptr: np.ndarray | None) -> dict[str, Any]:
    case_root = root / architecture / scene
    case_root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    raw, post_ptr, monitor, diagnostics = _render_architecture(vehicle_id, architecture, trace)
    elapsed_s = time.perf_counter() - started
    raw_receipt = write_pcm24_wav(case_root / "raw_source.wav", raw, SAMPLE_RATE_HZ)
    post_receipt = write_pcm24_wav(case_root / "post_ptr_raw.wav", post_ptr, SAMPLE_RATE_HZ)
    monitor_receipt = write_pcm24_wav(case_root / "monitor.wav", monitor, SAMPLE_RATE_HZ)
    raw_reopened, raw_metadata = read_pcm24_wav(case_root / "raw_source.wav")
    post_reopened, post_metadata = read_pcm24_wav(case_root / "post_ptr_raw.wav")
    monitor_reopened, monitor_metadata = read_pcm24_wav(case_root / "monitor.wav")
    parent_difference_rms = None
    if parent_post_ptr is not None:
        count = min(parent_post_ptr.shape[0], post_reopened.shape[0])
        parent_difference_rms = float(np.sqrt(np.mean(np.square(parent_post_ptr[:count] - post_reopened[:count]))))
    write_json(case_root / "state_trace.json", {"state_rate_hz": STATE_RATE_HZ, "time_s": trace.time_s.tolist(), "rpm": trace.rpm.tolist(), "load": trace.load.tolist(), "throttle": trace.throttle.tolist(), "acceleration_mps2": trace.acceleration_mps2.tolist()})
    write_diagnostic_traces(case_root, diagnostics)
    diagnostic_summary = {key: value for key, value in diagnostics.items() if key != "frame_trace"}
    click_metrics = {"raw": block_boundary_click_metrics(raw_reopened, BLOCK_SIZE), "post_ptr": block_boundary_click_metrics(post_reopened, BLOCK_SIZE), "monitor": block_boundary_click_metrics(monitor_reopened, BLOCK_SIZE)}
    diagnostic_summary["click_metrics"] = click_metrics["raw"]
    write_json(case_root / "metrics.json", {
        "schema_version": "s12.stage_w.vehicle_migration_metrics.v1",
        "vehicle_id": vehicle_id,
        "architecture": architecture,
        "scene": scene,
        "status": "UNSELECTED_CANDIDATE_MIGRATION",
        "reference_status": "REFERENCE_TARGET_MISSING",
        "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction; NOT_R1_QUALIFIED; NOT_PROFILE_FREEZE_READY",
        "ptr_status": diagnostics["ptr_status"],
        "publication_output_scale": OUTPUT_SCALE,
        "path_model": diagnostics["path_model"],
        "forced_induction_model": diagnostics["forced_induction_model"],
        "raw_metrics": _audio_metrics(raw_reopened, raw_metadata),
        "post_ptr_metrics": _audio_metrics(post_reopened, post_metadata),
        "monitor_metrics": _audio_metrics(monitor_reopened, monitor_metadata),
        "parent_post_ptr_difference_rms": parent_difference_rms,
        "click_metrics": click_metrics,
        "engine_diagnostics": diagnostic_summary,
    })
    write_json(case_root / "cpu_memory_latency.json", {"render_seconds": elapsed_s, "state_rate_hz": STATE_RATE_HZ, "block_size": BLOCK_SIZE, "memory_bytes": diagnostics.get("state_memory_bytes"), "latency_contract": "offline persistent source render"})
    files = {name: sha256_file(case_root / name) for name in ("raw_source.wav", "post_ptr_raw.wav", "monitor.wav", "state_trace.json", "phase_trace.json", "event_trace.json", "path_trace.json", "gain_trace.json", "metrics.json", "cpu_memory_latency.json")}
    write_json(case_root / "sha256_manifest.json", files)
    return {"raw_source_sha256": sha256_file(case_root / "raw_source.wav"), "post_ptr_sha256": sha256_file(case_root / "post_ptr_raw.wav"), "monitor_sha256": sha256_file(case_root / "monitor.wav"), "parent_post_ptr_difference_rms": parent_difference_rms}


def run_preselection_vehicle_migration(output_root: str | Path, vehicle_id: str, duration_s: float = 8.0) -> dict[str, Any]:
    """Render legacy/P2H/P3 migration evidence without selecting an architecture."""
    if vehicle_id not in _CONFIGS:
        raise ValueError(f"unsupported migration vehicle: {vehicle_id}")
    root = Path(output_root)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"refusing to overwrite migration output: {root}")
    root.mkdir(parents=True, exist_ok=True)
    rendered: dict[str, Any] = {architecture: {} for architecture in ("P1", "P2H", "P3")}
    for scene in MIGRATION_SCENES:
        trace = build_vehicle_migration_trace(vehicle_id, scene, duration_s)
        p1 = _write_case(root, vehicle_id, "P1", scene, trace, None)
        parent_post_ptr, _ = read_pcm24_wav(root / "P1" / scene / "post_ptr_raw.wav")
        rendered["P1"][scene] = p1
        for architecture in ("P2H", "P3"):
            rendered[architecture][scene] = _write_case(root, vehicle_id, architecture, scene, trace, parent_post_ptr)
    result = {"schema_version": "s12.stage_w.vehicle_migration.v1", "status": "UNSELECTED_CANDIDATE_MIGRATION", "vehicle_id": vehicle_id, "selected_architecture": None, "reference_status": "REFERENCE_TARGET_MISSING", "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction; NOT_R1_QUALIFIED; NOT_PROFILE_FREEZE_READY", "architectures": rendered}
    write_json(root / "migration_results.json", result)
    files = {path.relative_to(root).as_posix(): sha256_file(path) for path in sorted(root.rglob("*")) if path.is_file() and path.name != "migration_manifest.json"}
    write_json(root / "migration_manifest.json", {"schema_version": "s12.stage_w.vehicle_migration_manifest.v1", "status": result["status"], "vehicle_id": vehicle_id, "selected_architecture": None, "reference_status": result["reference_status"], "files": files})
    return result


def _load_geometry_contract() -> tuple[dict[str, dict[str, bool]] | None, str | None]:
    """Load and authenticate the architecture geometry contract from the live matrix."""
    try:
        matrix = json.loads(PARAMETER_USAGE_MATRIX_PATH.read_text(encoding="utf-8"))
        geometry = matrix["stage_w_consumed_paths"]["geometry"]
        if not isinstance(geometry, dict):
            return None, "geometry_matrix_invalid"
        values = {
            "piston": {
                "crankpin_geometry": geometry["piston.crankpin_geometry"],
                "rotor_geometry": geometry["piston.rotor_geometry"],
            },
            "rotary_wankel": {
                "crankpin_geometry": geometry["rotary.crankpin_geometry"],
                "rotor_geometry": geometry["rotary.rotor_geometry"],
            },
        }
        if any(type(value) is not bool for contract in values.values() for value in contract.values()):
            return None, "geometry_matrix_invalid"
        if values != _EXPECTED_GEOMETRY:
            return None, "geometry_matrix_mismatch"
        return values, None
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None, "geometry_matrix_invalid"


def validate_vehicle_migration_manifest(root: str | Path) -> list[str]:
    """Validate the complete migration receipt and fail closed on tampering."""
    root = Path(root)
    manifest_path = root / "migration_manifest.json"
    if not manifest_path.is_file():
        return ["migration_manifest.json missing"]
    errors: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"migration_manifest.json invalid:{exc}"]
    if manifest.get("status") != "UNSELECTED_CANDIDATE_MIGRATION":
        errors.append("status")
    if manifest.get("selected_architecture") is not None:
        errors.append("selected_architecture")
    if manifest.get("reference_status") != "REFERENCE_TARGET_MISSING":
        errors.append("reference_status")
    geometry_contract, geometry_error = _load_geometry_contract()
    if geometry_error is not None:
        errors.append(geometry_error)
    for relative, expected in manifest.get("files", {}).items():
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            errors.append(f"unsafe_path:{relative}")
            continue
        path = root / relative_path
        if not path.is_file():
            errors.append(f"missing:{relative}")
        elif sha256_file(path) != expected:
            errors.append(f"sha:{relative}")

    expected_case_files = (
        "raw_source.wav",
        "post_ptr_raw.wav",
        "monitor.wav",
        "state_trace.json",
        "phase_trace.json",
        "event_trace.json",
        "path_trace.json",
        "gain_trace.json",
        "metrics.json",
        "cpu_memory_latency.json",
        "sha256_manifest.json",
    )
    expected_outer_files = {
        f"{architecture}/{scene}/{filename}"
        for architecture in ("P1", "P2H", "P3")
        for scene in MIGRATION_SCENES
        for filename in expected_case_files
    } | {"migration_results.json"}
    listed_files = set(manifest.get("files", {}))
    for relative in sorted(expected_outer_files - listed_files):
        errors.append(f"missing_required:{relative}")

    results_path = root / "migration_results.json"
    try:
        results = json.loads(results_path.read_text(encoding="utf-8"))
        for key in ("status", "vehicle_id", "selected_architecture", "reference_status"):
            if results.get(key) != manifest.get(key):
                errors.append(f"results_{key}")
        result_architectures = results.get("architectures", {})
        if set(result_architectures) != {"P1", "P2H", "P3"}:
            errors.append("results_architecture_inventory")
        for architecture in ("P1", "P2H", "P3"):
            scene_records = result_architectures.get(architecture, {})
            if set(scene_records) != set(MIGRATION_SCENES):
                errors.append(f"results_scene_inventory:{architecture}")
            for scene in MIGRATION_SCENES:
                record = scene_records.get(scene, {})
                case = root / architecture / scene
                for key, filename in (("raw_source_sha256", "raw_source.wav"), ("post_ptr_sha256", "post_ptr_raw.wav"), ("monitor_sha256", "monitor.wav")):
                    path = case / filename
                    if path.is_file() and record.get(key) != sha256_file(path):
                        errors.append(f"results_hash:{architecture}/{scene}/{key}")
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"migration_results.json invalid:{exc}")

    def finite(value: Any) -> bool:
        if isinstance(value, dict):
            return all(finite(item) for item in value.values())
        if isinstance(value, list):
            return all(finite(item) for item in value)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return bool(np.isfinite(value))
        return True

    for architecture in ("P1", "P2H", "P3"):
        for scene in MIGRATION_SCENES:
            case = root / architecture / scene
            try:
                for filename in expected_case_files:
                    if not (case / filename).is_file():
                        errors.append(f"missing_required:{architecture}/{scene}/{filename}")
                raw, raw_meta = read_pcm24_wav(case / "raw_source.wav")
                post, post_meta = read_pcm24_wav(case / "post_ptr_raw.wav")
                monitor, monitor_meta = read_pcm24_wav(case / "monitor.wav")
                if max(raw_meta["clipping"], post_meta["clipping"], monitor_meta["clipping"]) != 0:
                    errors.append(f"clipping:{architecture}/{scene}")
                if raw.shape[0] != post.shape[0] or post.shape[0] != monitor.shape[0]:
                    errors.append(f"frames:{architecture}/{scene}")
                if np.array_equal(raw, monitor):
                    errors.append(f"raw_monitor_separation:{architecture}/{scene}")
                metrics = json.loads((case / "metrics.json").read_text(encoding="utf-8"))
                if metrics.get("vehicle_id") != manifest.get("vehicle_id") or metrics.get("architecture") != architecture or metrics.get("scene") != scene:
                    errors.append(f"identity:{architecture}/{scene}")
                if metrics.get("status") != "UNSELECTED_CANDIDATE_MIGRATION" or metrics.get("reference_status") != "REFERENCE_TARGET_MISSING":
                    errors.append(f"selection_gate:{architecture}/{scene}")
                if not finite(metrics):
                    errors.append(f"nonfinite:metrics:{architecture}/{scene}")
                recomputed_click = {"raw": block_boundary_click_metrics(raw, BLOCK_SIZE), "post_ptr": block_boundary_click_metrics(post, BLOCK_SIZE), "monitor": block_boundary_click_metrics(monitor, BLOCK_SIZE)}
                click = metrics.get("click_metrics")
                if click != recomputed_click:
                    errors.append(f"click_saved:{architecture}/{scene}")
                if any(not item.get("passed", False) for item in recomputed_click.values()):
                    errors.append(f"click_gate:{architecture}/{scene}")
                diagnostics = metrics.get("engine_diagnostics", {})
                consumption = diagnostics.get("parameter_consumption", {})
                if architecture in {"P2H", "P3"} and not all(isinstance(consumption.get(key), bool) for key in ("collector_assignment", "crankpin_geometry", "rotor_geometry", "transfer_ir")):
                    errors.append(f"parameter_consumption:{architecture}/{scene}")
                if architecture in {"P2H", "P3"} and geometry_contract is not None:
                    vehicle_architecture = "rotary_wankel" if manifest.get("vehicle_id") == "rx7_fd" else "piston" if manifest.get("vehicle_id") == "ferrari_458" else None
                    expected = geometry_contract.get(vehicle_architecture) if vehicle_architecture is not None else None
                    if expected is None or any(consumption.get(key) is not value for key, value in expected.items()):
                        errors.append(f"geometry_consumption:{architecture}/{scene}")
                if scene == "lift" and architecture in {"P2H", "P3"} and diagnostics.get("afterfire_event_count", 0) <= 0:
                    errors.append(f"afterfire_missing:{architecture}/{scene}")
                if scene != "lift" and architecture in {"P2H", "P3"} and diagnostics.get("afterfire_event_count", 0) != 0:
                    errors.append(f"afterfire_wrong_condition:{architecture}/{scene}")
                latency = json.loads((case / "cpu_memory_latency.json").read_text(encoding="utf-8"))
                if not finite(latency) or not isinstance(latency.get("render_seconds"), (int, float)) or latency["render_seconds"] < 0:
                    errors.append(f"latency:{architecture}/{scene}")
                for filename in expected_case_files[:-1]:
                    payload = json.loads((case / filename).read_text(encoding="utf-8")) if filename.endswith(".json") else None
                    if payload is not None and not finite(payload):
                        errors.append(f"nonfinite:{filename}:{architecture}/{scene}")
                inner = json.loads((case / "sha256_manifest.json").read_text(encoding="utf-8"))
                inner_files = inner.get("files", inner)
                expected_inner = set(expected_case_files[:-1])
                if set(inner_files) != expected_inner:
                    errors.append(f"case_manifest_inventory:{architecture}/{scene}")
                for filename in sorted(expected_inner):
                    expected_hash = inner_files.get(filename)
                    actual_path = case / filename
                    if not actual_path.is_file() or not isinstance(expected_hash, str) or sha256_file(actual_path) != expected_hash:
                        errors.append(f"case_manifest_sha:{architecture}/{scene}/{filename}")
            except (OSError, ValueError) as exc:
                errors.append(f"wav:{architecture}/{scene}:{exc}")
            except (json.JSONDecodeError, TypeError, KeyError) as exc:
                errors.append(f"artifact:{architecture}/{scene}:{exc}")
    return errors


__all__ = ["MIGRATION_SCENES", "build_vehicle_migration_trace", "run_preselection_vehicle_migration", "validate_vehicle_migration_manifest", "write_diagnostic_traces"]
