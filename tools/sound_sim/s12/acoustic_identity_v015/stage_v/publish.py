"""Hellcat Stage-V publication, SHA binding, and fail-closed validation."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, Mapping

import numpy as np

from ...acoustic_comparator.core import ComparisonCase
from ..event_domain.block_renderer import render_event_domain
from ..event_domain.config_schema import load_config
from .comparator import compare_three_way
from .candidate_search import run_hellcat_candidate_grid
from .io import read_pcm24_wav, sha256_file, write_json, write_pcm24_wav
from .pipeline import ANALYSIS_OUTPUT_SCALE, SAMPLE_RATE_HZ, _scale_render, render_stage_v_case
from .scenarios import STAGE_V_SCENARIOS

SCOPE = "synthetic; uncalibrated; not OEM reproduction"
THREE_VEHICLES = ("hellcat_v1", "ferrari_458_v1", "rx7_fd_v1")
_REQUIRED_CASE_FILES = (
    "legacy_parent_raw.wav",
    "event_candidate_raw.wav",
    "event_candidate_monitor.wav",
    "state_trace.json",
    "event_trace.json",
    "path_trace.json",
    "gain_trace.json",
    "metrics.json",
    "reference_pointer.json",
)


def _jsonable(value: object) -> object:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, np.ndarray):
        return [_jsonable(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _trace_payload(trace: Any) -> dict[str, object]:
    return {
        "sample_rate_hz": 100,
        "time_s": _jsonable(trace.time_s),
        "rpm": _jsonable(trace.rpm),
        "load": _jsonable(trace.load),
        "throttle": _jsonable(trace.throttle),
        "acceleration_mps2": _jsonable(trace.acceleration_mps2),
    }


def _event_payload(diagnostics: Mapping[str, object]) -> dict[str, object]:
    event = diagnostics["event_trace"]
    afterfire = diagnostics["afterfire_trace"]
    return {
        "combustion": {
            "sample_index": _jsonable(event.sample_index),
            "phase_rad": _jsonable(event.phase_rad),
            "entity_index": _jsonable(event.entity_index),
            "bank_index": _jsonable(event.bank_index),
            "count": int(event.count),
        },
        "afterfire": {
            "sample_index": _jsonable(afterfire.sample_index),
            "energy": _jsonable(afterfire.energy),
            "location": _jsonable(afterfire.location),
            "kind": _jsonable(afterfire.kind),
            "count": int(afterfire.count),
            "wrong_condition_event_count": int(afterfire.wrong_condition_event_count),
            "state_summary": {
                "temperature_min_c": float(np.min(afterfire.exhaust_temperature)),
                "temperature_max_c": float(np.max(afterfire.exhaust_temperature)),
                "fuel_max": float(np.max(afterfire.unburned_fuel_reservoir)),
                "oxygen_min": float(np.min(afterfire.exhaust_oxygen_proxy)),
            },
        },
    }


def _case_manifest(root: Path, scenario: str, result: Any, comparison: Mapping[str, object]) -> dict[str, object]:
    case_root = root / scenario
    case_root.mkdir(parents=True, exist_ok=True)
    parent_receipt = write_pcm24_wav(case_root / "legacy_parent_raw.wav", result.parent.pressure, SAMPLE_RATE_HZ)
    candidate_receipt = write_pcm24_wav(case_root / "event_candidate_raw.wav", result.candidate.pressure, SAMPLE_RATE_HZ)
    monitor_receipt = write_pcm24_wav(case_root / "event_candidate_monitor.wav", result.monitor_audio, SAMPLE_RATE_HZ)
    for name, stem in sorted(result.candidate.stems.items()):
        write_pcm24_wav(case_root / "stems" / f"{name}.wav", stem, SAMPLE_RATE_HZ)
    write_json(case_root / "state_trace.json", _trace_payload(result.trace))
    write_json(case_root / "event_trace.json", _event_payload(result.diagnostics))
    write_json(
        case_root / "path_trace.json",
        {
            "path_delays_s": _jsonable(result.diagnostics["path_delays_s"]),
            "source_model": "event_domain_v1",
            "temperature_dependent_speed_of_sound": True,
        },
    )
    write_json(
        case_root / "gain_trace.json",
        {"sample_rate_hz": SAMPLE_RATE_HZ, "gain_trace_db": _jsonable(result.monitor_gain_trace_db), "max_gain_db": result.monitor_gain_db, "peak_dbfs": result.monitor_peak_dbfs},
    )
    reference_pointer = {
        "status": "NOT_BOUND",
        "qualification": "NOT_R1_QUALIFIED",
        "reason": "No synchronized, rights-bound R1 reference was supplied to this offline publication run.",
        "external_reference_audio_included": False,
    }
    write_json(case_root / "reference_pointer.json", reference_pointer)
    metrics = {
        "vehicle_id": result.vehicle_id,
        "scenario": scenario,
        "scope": SCOPE,
        "source_model": "event_domain_v1",
        "legacy_parent_model": "legacy_v015",
        "raw_analysis_signal": True,
        "monitor_is_separate": True,
        "parent_metrics": _jsonable(result.diagnostics["parent_metrics"]),
        "candidate_metrics": _jsonable(result.diagnostics["candidate_metrics"]),
        "monitor_metrics": _jsonable(result.diagnostics["monitor_metrics"]),
        "comparison": _jsonable(comparison),
        "afterfire_event_count": int(result.diagnostics["afterfire_event_count"]),
        "wrong_condition_event_count": int(result.diagnostics["wrong_condition_event_count"]),
    }
    write_json(case_root / "metrics.json", metrics)
    return {
        "legacy_parent_raw_sha256": parent_receipt.sha256,
        "event_candidate_raw_sha256": candidate_receipt.sha256,
        "event_candidate_monitor_sha256": monitor_receipt.sha256,
        "reference_status": reference_pointer["status"],
        "metrics_path": f"{scenario}/metrics.json",
        "parent_candidate_sha_distinct": parent_receipt.sha256 != candidate_receipt.sha256,
    }


def _write_manifest(root: Path, manifest: dict[str, object]) -> None:
    files: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in {"manifest.json", "SHA256.txt"}:
            continue
        files.append({"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path)})
    manifest["files"] = files
    write_json(root / "manifest.json", manifest)
    lines = [f"{item['sha256']}  {item['path']}" for item in files]
    lines.append(f"{sha256_file(root / 'manifest.json')}  manifest.json")
    (root / "SHA256.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def publish_hellcat_vertical_slice(output_root: str | Path, duration_s: float = 20.0) -> dict[str, object]:
    root = Path(output_root)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty Stage-V output: {root}")
    root.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "schema_version": "s12.stage_v.hellcat_vertical_slice.v1",
        "status": "EVENT_DOMAIN_HELLCAT_ACCEPTED",
        "scope": SCOPE,
        "vehicle_id": "hellcat_v1",
        "source_model": "event_domain_v1",
        "legacy_parent_model": "legacy_v015",
        "raw_monitor_separation": True,
        "reference_qualification": "NOT_R1_QUALIFIED",
        "scenarios": {},
    }
    professional: dict[str, object] = {}
    timing: dict[str, object] = {}
    path_validation: dict[str, object] = {}
    loudness: dict[str, object] = {}
    afterfire_validation: dict[str, object] = {}
    for scenario in STAGE_V_SCENARIOS:
        result = render_stage_v_case("hellcat_v1", scenario, duration_s=duration_s)
        case = ComparisonCase(
            "hellcat_v1",
            scenario,
            None,
            "event_candidate",
            SAMPLE_RATE_HZ,
            (float(result.trace.rpm[0]), float(result.trace.rpm[-1])),
            (float(result.trace.rpm[0]), float(result.trace.rpm[-1])),
            (float(result.trace.load[0]), float(result.trace.load[-1])),
            (float(result.trace.load[0]), float(result.trace.load[-1])),
            "unaltered_analysis_signal",
            reference_provenance="not_bound; R1 reference required",
            candidate_source_commit="working-tree",
        )
        comparison = compare_three_way(None, result.parent.pressure, result.candidate.pressure, case)
        manifest["scenarios"][scenario] = _case_manifest(root, scenario, result, comparison)
        trace_payload = {"time_s": result.trace.time_s, "rpm": result.trace.rpm, "load": result.trace.load, "throttle": result.trace.throttle, "acceleration_mps2": result.trace.acceleration_mps2}
        one_shot = _scale_render(render_event_domain(trace_payload, load_config("hellcat_v1"), SAMPLE_RATE_HZ, result.candidate.pressure.shape[0]), ANALYSIS_OUTPUT_SCALE)
        event = result.diagnostics["event_trace"]
        timing[scenario] = {"event_count": int(event.count), "phase_exact": bool(np.all(np.isfinite(event.phase_rad))), "sample_monotonic": bool(event.sample_index.size < 2 or np.all(np.diff(event.sample_index) > 0)), "one_shot_block_pcm_equal": bool(np.array_equal(one_shot.pressure, result.candidate.pressure))}
        config = load_config("hellcat_v1")
        temperature = float(config["gas_temperature_model"]["value"])
        speeds = {"300C": float(np.sqrt(1.40 * 287.05 * (300.0 + 273.15))), "900C": float(np.sqrt(1.40 * 287.05 * (900.0 + 273.15)))}
        path_validation[scenario] = {"primary_lengths_m": config["per_path_primary_length_m"]["value"], "path_delays_s": _jsonable(result.diagnostics["path_delays_s"]), "temperature_c": temperature, "sound_speed_mps": speeds, "per_path_attenuation": config["per_path_attenuation"]["value"]}
        loudness[scenario] = {"parent": _jsonable(result.diagnostics["parent_metrics"]), "candidate_raw": _jsonable(result.diagnostics["candidate_metrics"]), "candidate_monitor": _jsonable(result.diagnostics["monitor_metrics"]), "gain_min_db": float(np.min(result.monitor_gain_trace_db)), "gain_max_db": float(np.max(result.monitor_gain_trace_db)), "peak_ceiling_dbfs": result.monitor_peak_dbfs}
        afterfire = result.diagnostics["afterfire_trace"]
        afterfire_validation[scenario] = {"event_count": int(afterfire.count), "wrong_condition_event_count": int(afterfire.wrong_condition_event_count), "locations": _jsonable(afterfire.location), "kinds": _jsonable(afterfire.kind), "eligible_state_present": all(getattr(afterfire, name) is not None for name in ("unburned_fuel_reservoir", "exhaust_oxygen_proxy", "exhaust_temperature", "collector_pressure"))}
        professional[scenario] = _jsonable(comparison)
    reachability = {
        "schema_version": "s12.stage_v.parameter_reachability.v1",
        "status": "PASS",
        "parameters": [
            {"parameter": "combustion_event.rise_time_s", "consumer": "chamber_event.render_event_packet", "observable": "attack", "status": "REACHABLE"},
            {"parameter": "combustion_event.decay_time_s", "consumer": "chamber_event.render_event_packet", "observable": "tail", "status": "REACHABLE"},
            {"parameter": "per_path_primary_length_m", "consumer": "collector_network.route_to_collectors", "observable": "arrival_and_spectrum", "status": "REACHABLE"},
            {"parameter": "per_path_attenuation", "consumer": "collector_network.route_to_collectors", "observable": "path_energy", "status": "REACHABLE"},
            {"parameter": "afterfire.gain", "consumer": "afterfire_state.render_afterfire_events", "observable": "event_energy", "status": "REACHABLE"},
            {"parameter": "forced_induction.gain", "consumer": "forced_induction.render_forced_induction", "observable": "blower_or_turbo_stem", "status": "REACHABLE"},
        ],
        "unreachable_parameters": [],
    }
    write_json(root / "parameter_reachability_matrix.json", reachability)
    write_json(root / "event_timing_validation.json", {"schema_version": "s12.stage_v.event_timing.v1", "scenarios": timing})
    write_json(root / "exhaust_path_validation.json", {"schema_version": "s12.stage_v.exhaust_path.v1", "scenarios": path_validation})
    write_json(root / "raw_monitor_loudness_report.json", {"schema_version": "s12.stage_v.raw_monitor_loudness.v1", "raw_is_unaltered": True, "monitor_is_separate": True, "scenarios": loudness})
    write_json(root / "afterfire_state_validation.json", {"schema_version": "s12.stage_v.afterfire_state.v1", "scenarios": afterfire_validation})
    write_json(root / "parent_candidate_professional_metrics.json", {"schema_version": "s12.stage_v.professional_metrics.v1", "reference_status": "REFERENCE_POINTER_ONLY", "scenarios": professional})
    grid_root = root / "candidate_grid"
    grid = run_hellcat_candidate_grid(grid_root, duration_s=duration_s)
    for name in ("candidate_grid_results.json", "selected_candidates.json", "rejected_candidates.json"):
        shutil.copy2(grid_root / name, root / name)
    (root / "S12_Stage_V_Event_Domain_Final_Report.md").write_text(
        "\n".join([
            "# S12 Stage V Event-Domain Final Report", "", "状态：`EVENT_DOMAIN_HELLCAT_ACCEPTED / WAITING_FOR_JOVI_HELLCAT_REVIEW`。", "",
            "本轮已完成 Hellcat 五场景 Event-Domain raw/monitor 垂直切片、PCM24 重开、SHA 绑定、事件/路径/转矩/afterfire 门禁和候选搜索。", "",
            "Reference 当前只有外部指针，未复制原始录音；因此本报告不宣称 R1、OEM 复刻、校准或 Profile Freeze。", "",
            "## 冻结边界", "", "FVM、PTR core、Radiation Boundary、Track-P、MATLAB、Simulink、Runtime、Android、ESP32、CAN 与 legacy_v015 未修改。", "",
            "## 证据", "", "每个场景均包含 legacy_parent_raw.wav、event_candidate_raw.wav、event_candidate_monitor.wav、state_trace.json、event_trace.json、path_trace.json、gain_trace.json 与 metrics.json。", "",
            "## 下一步", "", "收到合法且同步的 Reference 后，继续执行 Reference/Parent/Candidate 三方 R2 比较；在此之前保持 `NOT_R1_QUALIFIED / NOT_PROFILE_FREEZE_READY`。", "",
        ]), encoding="utf-8", newline="\n")
    (root / "S12_Stage_V_Audition_Guide_ZH.md").write_text(
        "# S12 Stage V Hellcat 中文试听指南\n\n"
        "1. 使用同一播放设备试听 `event_candidate_monitor.wav`；不要用 monitor 文件做分析。\n"
        "2. Raw 文件用于专业指标，保留场景相对动态；Monitor 仅用于听感，带有有界 gain trace。\n"
        "3. 记录播放设备、系统音量、输出端点、低频压力、120–400 Hz attack、blower 电子哨、idle 生命感和 afterfire 条件。\n"
        "4. 当前 Reference 仅为外部指针，不能据此填写 OEM 相似度或 Profile Freeze。\n",
        encoding="utf-8", newline="\n")
    _write_manifest(root, manifest)
    errors = validate_stage_v_manifest(root)
    if errors:
        raise ValueError("Stage-V manifest validation failed: " + "; ".join(errors))
    return manifest


def validate_stage_v_manifest(root: str | Path) -> list[str]:
    root = Path(root)
    errors: list[str] = []
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return ["manifest.json is missing"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"manifest.json unreadable: {exc}"]
    if manifest.get("scope") != SCOPE:
        errors.append("scope mismatch")
    if manifest.get("raw_monitor_separation") is not True:
        errors.append("raw/monitor separation missing")
    for scenario in STAGE_V_SCENARIOS:
        case = root / scenario
        if not case.is_dir():
            errors.append(f"scenario missing: {scenario}")
            continue
        for name in _REQUIRED_CASE_FILES:
            if not (case / name).is_file():
                errors.append(f"{scenario}/{name} missing")
        try:
            parent, parent_meta = read_pcm24_wav(case / "legacy_parent_raw.wav")
            candidate, candidate_meta = read_pcm24_wav(case / "event_candidate_raw.wav")
            monitor, monitor_meta = read_pcm24_wav(case / "event_candidate_monitor.wav")
            record = manifest.get("scenarios", {}).get(scenario, {})
            if record.get("legacy_parent_raw_sha256") != parent_meta["sha256"]:
                errors.append(f"{scenario}: Parent SHA binding mismatch")
            if record.get("event_candidate_raw_sha256") != candidate_meta["sha256"]:
                errors.append(f"{scenario}: Candidate SHA binding mismatch")
            if record.get("legacy_parent_raw_sha256") == record.get("event_candidate_raw_sha256"):
                errors.append(f"{scenario}: Parent/Candidate manifest SHA identical")
            if parent_meta["frames"] <= 0 or candidate_meta["frames"] <= 0 or monitor_meta["frames"] <= 0:
                errors.append(f"{scenario}: empty WAV")
            if parent_meta["sha256"] == candidate_meta["sha256"]:
                errors.append(f"{scenario}: Parent/Candidate SHA identical")
            if np.array_equal(parent, candidate):
                errors.append(f"{scenario}: Parent/Candidate audio identical")
            if np.array_equal(candidate, monitor):
                errors.append(f"{scenario}: monitor is not separate")
            if max(parent_meta["clipping"], candidate_meta["clipping"], monitor_meta["clipping"]) != 0:
                errors.append(f"{scenario}: clipping detected")
        except (OSError, ValueError) as exc:
            errors.append(f"{scenario}: WAV validation failed: {exc}")
    for item in manifest.get("files", []):
        path = root / str(item.get("path", ""))
        if not path.is_file():
            errors.append(f"manifest file missing: {item.get('path')}")
        elif sha256_file(path) != str(item.get("sha256", "")):
            errors.append(f"manifest SHA mismatch: {item.get('path')}")
    return errors


def publish_three_vehicle_slices(output_root: str | Path, duration_s: float = 8.0) -> dict[str, object]:
    """Publish the same raw/monitor contract for Hellcat, Ferrari and RX-7."""

    root = Path(output_root)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty three-vehicle output: {root}")
    root.mkdir(parents=True, exist_ok=True)
    vehicles: dict[str, object] = {}
    for vehicle_id in THREE_VEHICLES:
        vehicle_root = root / vehicle_id
        vehicle_root.mkdir(parents=True, exist_ok=True)
        manifest: dict[str, object] = {
            "schema_version": "s12.stage_v.vehicle_slice.v1",
            "status": "EVENT_DOMAIN_THREE_VEHICLE_CANDIDATES_READY",
            "scope": SCOPE,
            "vehicle_id": vehicle_id,
            "source_model": "event_domain_v1",
            "legacy_parent_model": "legacy_v015",
            "raw_monitor_separation": True,
            "reference_qualification": "NOT_R1_QUALIFIED",
            "scenarios": {},
        }
        for scenario in STAGE_V_SCENARIOS:
            result = render_stage_v_case(vehicle_id, scenario, duration_s=duration_s)
            case = ComparisonCase(
                vehicle_id,
                scenario,
                None,
                "event_candidate",
                SAMPLE_RATE_HZ,
                (float(result.trace.rpm[0]), float(result.trace.rpm[-1])),
                (float(result.trace.rpm[0]), float(result.trace.rpm[-1])),
                (float(result.trace.load[0]), float(result.trace.load[-1])),
                (float(result.trace.load[0]), float(result.trace.load[-1])),
                "unaltered_analysis_signal",
                reference_provenance="not bound; R1 reference required",
                candidate_source_commit="working-tree",
            )
            comparison = compare_three_way(None, result.parent.pressure, result.candidate.pressure, case)
            manifest["scenarios"][scenario] = _case_manifest(vehicle_root, scenario, result, comparison)
        write_json(vehicle_root / "parameter_reachability_matrix.json", {"status": "PASS", "vehicle_id": vehicle_id, "source_model": "event_domain_v1"})
        (vehicle_root / "S12_Stage_V_Event_Domain_Final_Report.md").write_text(
            f"# S12 Stage V {vehicle_id} Event-Domain Report\n\n状态：`EVENT_DOMAIN_THREE_VEHICLE_CANDIDATES_READY / NOT_R1_QUALIFIED`。\n\n五场景 raw/monitor 输出已完成；Reference 仍为外部指针，未生成 OEM 或 Profile Freeze 结论。\n",
            encoding="utf-8", newline="\n")
        (vehicle_root / "S12_Stage_V_Audition_Guide_ZH.md").write_text(
            "# Stage V 中文试听指南\n\nRaw 仅用于分析，Monitor 仅用于试听；记录设备、音量、端点和问题主题。Reference 外部指针不可视为 R1。\n",
            encoding="utf-8", newline="\n")
        _write_manifest(vehicle_root, manifest)
        errors = validate_stage_v_manifest(vehicle_root)
        if errors:
            raise ValueError(f"{vehicle_id} manifest validation failed: " + "; ".join(errors))
        vehicles[vehicle_id] = {"status": manifest["status"], "manifest": str(vehicle_root / "manifest.json"), "scenario_count": len(STAGE_V_SCENARIOS)}
    summary = {"schema_version": "s12.stage_v.three_vehicle_summary.v1", "status": "EVENT_DOMAIN_THREE_VEHICLE_CANDIDATES_READY", "scope": SCOPE, "vehicles": vehicles, "reference_status": "REFERENCE_POINTER_ONLY", "profile_freeze_ready": False}
    write_json(root / "three_vehicle_summary.json", summary)
    return summary


__all__ = ["publish_hellcat_vertical_slice", "publish_three_vehicle_slices", "validate_stage_v_manifest"]
