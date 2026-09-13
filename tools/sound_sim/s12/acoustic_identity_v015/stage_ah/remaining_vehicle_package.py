"""Build and serve the RX-7/Aventador AH diagnostic package.

The package is deliberately a small adapter around ``RemainingVehicleEngine``
and the existing rich dashboard.  Reference media stays outside the source
tree: this module reads the files named by an external ``source_receipt.json``
and publishes only deterministic clips plus provenance metadata.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import threading
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

from ..stage_af.package_integrity import (
    REPOSITORY_ROOT,
    artifact_record,
    canonical_json_bytes,
    git_source_receipt,
    seal_payload,
    sha256_file,
    validate_artifacts,
    validate_identifier,
)
from .output_guard import LEGACY_CLIP_V1, LINKED_SOFT_CEILING_V1, OUTPUT_GUARD_RECEIPT_SCHEMA
from .remaining_vehicle_pipeline import (
    REMAINING_VEHICLES,
    SOURCE_VARIANTS,
    RemainingVehicleEngine,
    validate_source_pool,
)


# build_unified_dashboards imports engine_sim_acoustics as a top-level module.
_STAGE_AD_DIR = Path(__file__).resolve().parents[1] / "stage_ad"
sys.path.insert(0, str(_STAGE_AD_DIR))
try:
    from ..stage_ad import build_unified_dashboards as _dashboards
finally:
    sys.path.pop(0)


_SAMPLE_RATE_HZ = 48_000
RUN_SCHEMA = "s12.stage_ah.remaining_vehicles.experiment_manifest.v1"
PACKAGE_SCHEMA = "s12.stage_ah.remaining_vehicles.package_manifest.v1"
REFERENCE_SCHEMA = "s12.stage_ah.remaining_vehicles.reference_clip_receipt.v1"
CONTRACT_SCHEMA = "s12.stage_ah.remaining_vehicles.dashboard_contract.v1"
BINDING_SCHEMA = "s12.stage_ah.remaining_vehicles.binding.v1"
DEFAULT_RUN_ID = "s12-stage-ah-remaining-vehicles-20260914-v1"
DEFAULT_OUTPUT_ROOT = Path(r"E:\Tesla_speed\review_packages")
DEFAULT_PORT_B0 = 27880
DEFAULT_PORT_C0 = 28080
DEFAULT_CLIP_DURATION_S = 4.0
REFERENCE_STATUS = "R3_UNVERIFIED_UNSYNCHRONIZED"
REFERENCE_EVIDENCE_LEVEL = "R3_PUBLIC_RECORDINGS_UNVERIFIED"
SCENE_IDS = (
    "01_afterfire",
    "02_full_pull",
    "03_hot_idle",
    "04_idle_return",
    "05_lift",
    "06_shift",
    "07_steady_high",
    "08_steady_low",
    "09_steady_mid",
    "10_tip_in",
)


_VEHICLE_INFO: dict[str, dict[str, Any]] = {
    "rx7_fd": {
        "name": "Mazda RX-7 FD",
        "title": "MAZDA RX-7 FD 转子涡轮声浪试听",
        "subtitle": "Stage AH-REMAINING / 13B-REW twin-rotor turbo / R3 真实录音未核验未同步",
        "badge": "🌀 Mazda RX-7 FD (13B-REW 双转子涡轮)",
        "icon": "🌀",
        "color": "amber",
        "idle_rpm": 850.0,
        "redline_rpm": 8000.0,
        "pull_start": 2500.0,
        "pull_end": 7800.0,
        "shift_cut": 0.09,
    },
    "aventador_lp700": {
        "name": "Lamborghini Aventador LP700-4",
        "title": "LAMBORGHINI AVENTADOR V12 声浪试听",
        "subtitle": "Stage AH-REMAINING / L539 6.5L naturally aspirated V12 / R3 真实录音未核验未同步",
        "badge": "🐂 Lamborghini Aventador LP700-4 (6.5L V12)",
        "icon": "🐂",
        "color": "red",
        "idle_rpm": 850.0,
        "redline_rpm": 8500.0,
        "pull_start": 2500.0,
        "pull_end": 8300.0,
        "shift_cut": 0.07,
    },
}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _read_sealed(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    checksum_field = "manifest_sha256" if "manifest_sha256" in payload else "contract_sha256"
    checksum = payload.pop(checksum_field, None)
    if checksum is not None and checksum != _sha256_bytes(canonical_json_bytes(payload)):
        raise ValueError(f"sealed receipt mismatch: {path}")
    if checksum is not None:
        payload[checksum_field] = checksum
    return payload


def _to_float_mono(data: np.ndarray) -> np.ndarray:
    array = np.asarray(data)
    if array.ndim > 1:
        array = array[:, 0]
    if array.dtype == np.uint8:
        return (array.astype(np.float64) - 128.0) / 128.0
    if np.issubdtype(array.dtype, np.signedinteger):
        return array.astype(np.float64) / float(np.iinfo(array.dtype).max + 1)
    return array.astype(np.float64)


def _load_source_receipt(source_receipt: Path | Mapping[str, Any]) -> tuple[dict[str, Any], Path | None, str]:
    if isinstance(source_receipt, Mapping):
        payload = dict(source_receipt)
        raw = canonical_json_bytes(payload)
        return payload, None, _sha256_bytes(raw)
    path = Path(source_receipt).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    raw = path.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid source receipt: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("source receipt must be a JSON object")
    return payload, path, _sha256_bytes(raw)


def _source_path(
    source: Mapping[str, Any],
    *,
    receipt_path: Path | None,
    source_root: Path | None,
) -> Path:
    value = next(
        (source.get(key) for key in ("audio_file", "audio_path", "wav_path", "clip_path", "local_path", "path", "filename") if source.get(key)),
        None,
    )
    if value is None:
        raise ValueError(f"source {source.get('video_id', '<unknown>')} has no local audio path")
    text = str(value)
    if "://" in text:
        raise ValueError(f"source {source.get('video_id', '<unknown>')} must name a local extracted WAV")
    path = Path(text)
    if not path.is_absolute():
        path = (source_root or (receipt_path.parent if receipt_path else Path.cwd())) / path
    return path.resolve()


def _source_root(payload: Mapping[str, Any], receipt_path: Path | None) -> Path | None:
    value = payload.get("source_root")
    if not value:
        return receipt_path.parent.resolve() if receipt_path else None
    root = Path(str(value))
    if not root.is_absolute():
        root = (receipt_path.parent if receipt_path else Path.cwd()) / root
    return root.resolve()


def _lookup_window(container: Any, vehicle: str, scene_id: str) -> Any:
    if not isinstance(container, Mapping):
        return None
    if scene_id in container:
        return container[scene_id]
    nested = container.get(vehicle)
    return nested.get(scene_id) if isinstance(nested, Mapping) else None


def _select_window(
    payload: Mapping[str, Any],
    vehicle: str,
    vehicle_entry: Mapping[str, Any],
    source: Mapping[str, Any],
    source_index: int,
    scene_id: str,
    source_by_id: Mapping[str, Mapping[str, Any]],
    *,
    default_duration_s: float,
) -> tuple[Mapping[str, Any], float, float]:
    spec = None
    for key in ("reference_windows", "clip_windows", "windows"):
        spec = _lookup_window(vehicle_entry.get(key), vehicle, scene_id)
        if spec is None:
            spec = _lookup_window(payload.get(key), vehicle, scene_id)
        if spec is not None:
            break
    if spec is None:
        spec = source.get("reference_window")
    selected = source
    start_s = float(source.get("reference_start_s", source.get("clip_start_s", 0.0)))
    duration_s = float(source.get("clip_duration_s", default_duration_s))
    if isinstance(spec, Mapping):
        selector = spec.get("source_id", spec.get("video_id", spec.get("source_index", spec.get("index"))))
        if selector is not None:
            if isinstance(selector, (int, np.integer)) and not isinstance(selector, bool):
                raise ValueError("window source_index must be resolved by source list")
            selected = source_by_id.get(str(selector), source)
            if selected is source and str(selector) != str(source.get("video_id")):
                raise ValueError(f"unknown reference source: {selector}")
        start_s = float(spec.get("start_s", spec.get("start", start_s)))
        duration_s = float(spec.get("duration_s", spec.get("duration", spec.get("length_s", duration_s))))
    elif isinstance(spec, Sequence) and not isinstance(spec, (str, bytes)) and len(spec) >= 3:
        selector, start_s, duration_s = spec[0], float(spec[1]), float(spec[2])
        if isinstance(selector, (int, np.integer)) and not isinstance(selector, bool):
            raise ValueError("window source_index must be resolved by source list")
        selected = source_by_id.get(str(selector), source)
        if selected is source and str(selector) != str(source.get("video_id")):
            raise ValueError(f"unknown reference source: {selector}")
    if not np.isfinite(start_s) or not np.isfinite(duration_s) or start_s < 0.0 or duration_s <= 0.0:
        raise ValueError(f"invalid fixed window: {vehicle}/{scene_id}")
    return selected, start_s, duration_s


def build_reference_bundle(
    destination: Path,
    source_receipt: Path | Mapping[str, Any],
    *,
    clip_duration_s: float = DEFAULT_CLIP_DURATION_S,
) -> dict[str, Any]:
    """Read external source audio and write ten fixed-window clips per car."""
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError(destination)
    if not np.isfinite(float(clip_duration_s)) or float(clip_duration_s) <= 0.0:
        raise ValueError("clip_duration_s must be finite and positive")
    payload, receipt_path, receipt_sha = _load_source_receipt(source_receipt)
    source_counts = validate_source_pool(payload)
    root = _source_root(payload, receipt_path)
    destination.mkdir(parents=True)
    _write_json(destination / "source_receipt.json", payload)

    audio_cache: dict[str, np.ndarray] = {}
    source_metadata: dict[str, dict[str, Any]] = {}
    source_lists: dict[str, list[Mapping[str, Any]]] = {}
    for vehicle in REMAINING_VEHICLES:
        entry = payload["vehicles"][vehicle]
        source_rows = list(entry["selected_sources"])
        source_lists[vehicle] = source_rows
        for row in source_rows:
            video_id = str(row["video_id"])
            path = _source_path(row, receipt_path=receipt_path, source_root=root)
            if not path.is_file():
                raise FileNotFoundError(path)
            actual_sha = sha256_file(path)
            expected_sha = row.get("sha256", row.get("file_sha256", row.get("audio_sha256")))
            if expected_sha and str(expected_sha).lower() != actual_sha.lower():
                raise ValueError(f"source SHA mismatch: {video_id}")
            sample_rate, data = wavfile.read(path)
            mono = _to_float_mono(data)
            if mono.size == 0 or not np.all(np.isfinite(mono)):
                raise ValueError(f"source audio is empty/non-finite: {path}")
            original_rate = int(sample_rate)
            if original_rate != _SAMPLE_RATE_HZ:
                mono = resample_poly(mono, _SAMPLE_RATE_HZ, original_rate)
            audio_cache[video_id] = np.asarray(mono, dtype=np.float64)
            source_metadata[f"{vehicle}:{video_id}"] = {
                "vehicle": vehicle,
                "video_id": video_id,
                "source_path": str(path),
                "source_sha256": actual_sha,
                "source_sha256_verified": bool(expected_sha),
                "sample_rate_hz": original_rate,
                "normalized_sample_rate_hz": _SAMPLE_RATE_HZ,
                "resample_method": "scipy.signal.resample_poly" if original_rate != _SAMPLE_RATE_HZ else "none",
                "frames": int(mono.size),
                "duration_s": float(mono.size / _SAMPLE_RATE_HZ),
            }

    clips: dict[str, dict[str, Any]] = {}
    for vehicle in REMAINING_VEHICLES:
        vehicle_dir = destination / vehicle
        vehicle_dir.mkdir()
        entry = payload["vehicles"][vehicle]
        source_rows = source_lists[vehicle]
        source_by_id = {str(row["video_id"]): row for row in source_rows}
        for index, scene_id in enumerate(SCENE_IDS):
            source = source_rows[index % len(source_rows)]
            selected, start_s, duration_s = _select_window(
                payload,
                vehicle,
                entry,
                source,
                index,
                scene_id,
                source_by_id,
                default_duration_s=float(entry.get("clip_duration_s", clip_duration_s)),
            )
            video_id = str(selected["video_id"])
            mono = audio_cache[video_id]
            start = int(round(start_s * _SAMPLE_RATE_HZ))
            count = int(round(duration_s * _SAMPLE_RATE_HZ))
            stop = start + count
            if start < 0 or stop > mono.size:
                raise ValueError(f"reference clip window exceeds source: {vehicle}/{scene_id}")
            clip = np.column_stack((mono[start:stop], mono[start:stop]))
            clip_i16 = np.clip(np.rint(clip * 32767.0), -32768, 32767).astype(np.int16)
            filename = f"ref_{scene_id}.wav"
            clip_path = vehicle_dir / filename
            wavfile.write(clip_path, _SAMPLE_RATE_HZ, clip_i16)
            source_info = source_metadata[f"{vehicle}:{video_id}"]
            clips[f"{vehicle}/{filename}"] = {
                "vehicle": vehicle,
                "scene_id": scene_id,
                "filename": filename,
                "source_video_id": video_id,
                "source_path": source_info["source_path"],
                "source_sha256": source_info["source_sha256"],
                "start_s": start_s,
                "duration_s": duration_s,
                "start_sample": start,
                "end_sample_exclusive": stop,
                "sha256": sha256_file(clip_path),
                "sample_rate_hz": _SAMPLE_RATE_HZ,
                "evidence_level": REFERENCE_EVIDENCE_LEVEL,
                "reference_status": REFERENCE_STATUS,
                "rights_status": "UNVERIFIED_LOCAL_ASSET",
            }

    receipt = seal_payload(
        {
            "schema": REFERENCE_SCHEMA,
            "source_receipt_path": str(receipt_path) if receipt_path else "INLINE_SOURCE_RECEIPT",
            "source_receipt_sha256": receipt_sha,
            "source_counts": source_counts,
            "source_metadata": source_metadata,
            "clips": clips,
            "clip_count_total": len(clips),
            "clip_count_per_vehicle": {vehicle: 10 for vehicle in REMAINING_VEHICLES},
            "reference_evidence_level": REFERENCE_EVIDENCE_LEVEL,
            "reference_status": REFERENCE_STATUS,
            "status": "LOCAL_DIAGNOSTIC_ONLY_R3_UNVERIFIED_UNSYNCHRONIZED",
        },
        REFERENCE_SCHEMA,
    )
    _write_json(destination / "reference_clip_receipt.json", receipt)
    return receipt


def _scenes(vehicle: str, reference_prefix: str = "ref_") -> list[dict[str, Any]]:
    name = _VEHICLE_INFO[vehicle]["name"]
    titles = {
        "01_afterfire": "收油回火与爆音",
        "02_full_pull": "全负荷加速",
        "03_hot_idle": "热态怠速",
        "04_idle_return": "轰油回落怠速",
        "05_lift": "高负荷收油滑行",
        "06_shift": "换挡断火",
        "07_steady_high": "高转巡航",
        "08_steady_low": "低转跟车",
        "09_steady_mid": "中转动力巡航",
        "10_tip_in": "急踩油门瞬态",
    }
    categories = {
        "01_afterfire": "afterfire", "02_full_pull": "acceleration",
        "03_hot_idle": "idle", "04_idle_return": "idle", "05_lift": "dynamics",
        "06_shift": "dynamics", "07_steady_high": "cruise", "08_steady_low": "cruise",
        "09_steady_mid": "cruise", "10_tip_in": "dynamics",
    }
    return [
        {
            "id": scene_id,
            "index": index,
            "category": categories[scene_id],
            "candidate_file": f"{scene_id}.wav",
            "ref_file": f"{reference_prefix}{scene_id}.wav",
            "title": f"{index:02d} {titles[scene_id]} ({name})",
            "desc": f"{name} 的 {titles[scene_id]} 受控对照场景。",
            "focus": "与同场景 R3 真实录音进行相对听感比较；不代表 OEM 同步或 Human PASS。",
        }
        for index, scene_id in enumerate(SCENE_IDS, start=1)
    ]


def _config(vehicle: str, directory: Path, port: int, group: str) -> dict[str, Any]:
    info = _VEHICLE_INFO[vehicle]
    cfg = dict(info)
    cfg.update(
        {
            "dir": directory,
            "port": int(port),
            "ref_source": "External source_receipt.json / R3 unverified unsynchronized recordings",
            "scenes": _scenes(vehicle),
            "title": f"[AH-REMAINING · {group} · {'linked_soft_ceiling_v1' if group == 'C0' else 'legacy_clip_v1'}] {info['title']}",
            "subtitle": f"{info['subtitle']} · {group}",
        }
    )
    return cfg


def _reference_map(receipt: Mapping[str, Any], vehicle: str) -> dict[str, dict[str, Any]]:
    result = {}
    for key, info in receipt.get("clips", {}).items():
        if info.get("vehicle") != vehicle:
            continue
        result[str(info["filename"])] = {
            "available": True,
            "fit_required": False,
            "source_label": f"R3 source {info['source_video_id']} / {info['start_s']:.2f}-{info['start_s'] + info['duration_s']:.2f}s",
            "sha256": info["sha256"],
            "evidence_level": info["evidence_level"],
            "reference_status": info["reference_status"],
            "rights_status": info["rights_status"],
        }
    return result


def _renderer_identity(vehicle: str, engine: RemainingVehicleEngine) -> dict[str, Any]:
    pipeline_path = Path(__file__).with_name("remaining_vehicle_pipeline.py")
    identity = {
        "vehicle": vehicle,
        "renderer": "RemainingVehicleEngine + frozen_ptr + linked_soft_ceiling_v1",
        "source_variant": SOURCE_VARIANTS[vehicle],
        "pipeline_sha256": sha256_file(pipeline_path),
        "output_guard_sha256": sha256_file(Path(__file__).with_name("output_guard.py")),
        "ir_name": engine.vehicle_type and "mild_exhaust_reverb",
        "ir_volume": 0.015,
        "ir_source_path": str(engine.ir_source_path) if engine.ir_source_path else "INJECTED_TEST_IR",
        "ir_source_sha256": engine.ir_source_sha256,
        "sample_rate_hz": _SAMPLE_RATE_HZ,
    }
    if vehicle == "rx7_fd":
        candidate = Path(__file__).resolve().parents[1] / "targets" / "stage_g_candidates" / "RX7_candidate_v4.json"
        if candidate.is_file():
            identity["candidate_profile_path"] = str(candidate)
            identity["candidate_profile_sha256"] = sha256_file(candidate)
    return identity


def _build_contract(
    package_id: str,
    candidate_id: str,
    cfg: Mapping[str, Any],
    vehicle: str,
    group: str,
    engine: RemainingVehicleEngine,
    feedback: Mapping[str, Any],
    receipt: Mapping[str, Any],
    candidate_hashes: Mapping[str, str],
    reference_hashes: Mapping[str, str],
) -> dict[str, Any]:
    policy = engine.output_policy
    return seal_payload(
        {
            "schema": CONTRACT_SCHEMA,
            "stage": "AH-REMAINING",
            "package_id": package_id,
            "candidate_id": candidate_id,
            "vehicle": vehicle,
            "group": group,
            "source_variant": SOURCE_VARIANTS[vehicle],
            "output_policy": policy,
            "output_policy_config": {
                "policy_id": policy,
                "knee_linear": 0.90 if policy == LINKED_SOFT_CEILING_V1 else None,
                "ceiling_linear": 0.94,
                "stereo_link": "instantaneous_frame_peak_common_gain" if policy == LINKED_SOFT_CEILING_V1 else "legacy_renderer_path",
                "parent_denominator_policy": "fixed_parent_peak_scene_trace",
            },
            "output_guard_receipt_schema": OUTPUT_GUARD_RECEIPT_SCHEMA if policy == LINKED_SOFT_CEILING_V1 else "s12.stage_ah.output_guard_receipt.v1",
            "seed": 20260908,
            "flags": [],
            "feedback_control": dict(feedback),
            "reference_evidence_level": REFERENCE_EVIDENCE_LEVEL,
            "reference_status": REFERENCE_STATUS,
            "reference_source_count": int(receipt["source_counts"][vehicle]),
            "reference_clip_count": 10,
            "identity_mode": "remaining_source_identity_no_ag_r1_identity",
            "fit_status": "NOT_FITTED",
            "fit_metric_status": "R3_RELATIVE_CUES_ONLY",
            "measurement_status": "R3_PUBLIC_RECORDINGS_UNSYNCHRONIZED",
            "human_status": "WAITING_FOR_JOVI_FEEDBACK",
            "package_port": int(cfg["port"]),
            "nav_urls": dict(cfg.get("_nav_urls", {})),
            "renderer_identity": _renderer_identity(vehicle, engine),
            "references": _reference_map(receipt, vehicle),
            "candidate_pcm_sha256": dict(candidate_hashes),
            "reference_sha256": dict(reference_hashes),
            "source_receipt_sha256": receipt["source_receipt_sha256"],
            "reference_clip_receipt_sha256": receipt["manifest_sha256"],
            "package_gain_db": 0.0,
            "gain_policy": "fixed_parent_peak_tanh_then_optional_linked_soft_ceiling",
            "source_status": "SOURCE_CLEAN",
            "promotable": False,
            "promotion_status": "NOT_PROMOTABLE_R3_UNVERIFIED_UNSYNCHRONIZED",
        },
        CONTRACT_SCHEMA,
    )


def _artifact_paths(package_root: Path, configs: Mapping[str, Mapping[str, Any]], receipt: Mapping[str, Any]) -> list[Path]:
    paths: list[Path] = [package_root / "reference_clip_receipt.json", package_root / "source_receipt.json", package_root / "stage_ah_remaining_binding.json"]
    for vehicle, cfg in configs.items():
        root = Path(cfg["dir"])
        paths.extend((root / f"{scene['id']}.wav", root / "web_audio" / f"{scene['id']}.wav") for scene in cfg["scenes"])
        paths.extend((root / "web_audio" / f"ref_{scene['id']}.wav" for scene in cfg["scenes"]))
        paths.extend((root / "index.html", root / "index_standalone.html", root / "dashboard_contract.json"))
    return list(dict.fromkeys(paths))


def _aggregate(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    normalizations = [record["normalization"] for record in records]
    frames = sum(int(row.get("frame_count", 0)) for row in normalizations)
    active = sum(int(row.get("soft_guard_active_frames", 0)) for row in normalizations)
    return {
        "record_count": len(records),
        "legacy_ceiling_input_exceedance_samples": sum(int(row.get("legacy_ceiling_input_exceedance_samples", 0)) for row in normalizations),
        "pre_guard_peak": float(max(row["pre_guard_peak"] for row in normalizations)),
        "post_guard_peak": float(max(row["post_guard_peak"] for row in normalizations)),
        "soft_guard_active_frames": active,
        "soft_guard_active_frame_ratio": float(active / frames) if frames else 0.0,
        "soft_guard_min_gain": float(min(row.get("soft_guard_min_gain", 1.0) for row in normalizations)),
        "soft_guard_max_attenuation_db": float(max(row.get("soft_guard_max_attenuation_db", 0.0) for row in normalizations)),
        "post_guard_ceiling_exceedance_samples": sum(int(row.get("post_guard_ceiling_exceedance_samples", 0)) for row in normalizations),
        "emergency_clip_count": sum(int(row.get("emergency_clip_count", 0)) for row in normalizations),
        "identity_layer_clip_count": sum(int(record.get("identity_layer_clip_count", 0)) for record in records),
        "post_identity_clip_count": sum(int(record.get("post_identity_clip_count", 0)) for record in records),
    }


def _build_group(
    *,
    run_root: Path,
    group: str,
    source_receipt: Mapping[str, Any],
    reference_bundle: Path,
    feedback: Mapping[str, Sequence[Mapping[str, Any]]],
    parent_peaks: Mapping[str, Mapping[str, float]] | None,
    ports: Mapping[str, int],
) -> dict[str, Any]:
    policy = LEGACY_CLIP_V1 if group == "B0" else LINKED_SOFT_CEILING_V1
    package_id = validate_identifier(f"ah-remaining-{run_root.name}-{group.lower()}", "package_id")
    package_root = run_root / "packages" / package_id
    if package_root.exists():
        raise FileExistsError(package_root)
    package_root.mkdir(parents=True)
    configs: dict[str, dict[str, Any]] = {}
    for vehicle in REMAINING_VEHICLES:
        vehicle_root = package_root / vehicle
        web_dir = vehicle_root / "web_audio"
        web_dir.mkdir(parents=True)
        for clip in sorted((reference_bundle / vehicle).glob("ref_*.wav")):
            shutil.copy2(clip, web_dir / clip.name)
        cfg = _config(vehicle, vehicle_root, ports[vehicle], group)
        cfg["_nav_ports"] = dict(ports)
        cfg["_nav_vehicles"] = REMAINING_VEHICLES
        cfg["_nav_urls"] = {key: f"http://localhost:{value}/" for key, value in ports.items()}
        cfg["reference_bundle"] = reference_bundle
        configs[vehicle] = cfg
    engines: dict[str, RemainingVehicleEngine] = {}
    previous_configs = _dashboards.VEHICLE_CONFIGS
    previous_engine = _dashboards.EngineAcoustics
    previous_template = _dashboards.TEMPLATE_PATH
    _dashboards.VEHICLE_CONFIGS = configs
    _dashboards.TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "stage_ad" / "audition_dashboard_template.html"

    class Factory:
        def __new__(cls, vehicle_type: str, sr: int = _SAMPLE_RATE_HZ):
            if vehicle_type not in REMAINING_VEHICLES:
                raise ValueError(f"unexpected remaining vehicle: {vehicle_type}")
            engine = RemainingVehicleEngine(
                vehicle_type,
                sr,
                output_policy=policy,
                parent_peaks=(parent_peaks or {}).get(vehicle_type),
                seed=20260908,
                scene_ids=SCENE_IDS,
                feedback_rows=feedback.get(vehicle_type, ()),
            )
            engines[vehicle_type] = engine
            return engine

    _dashboards.EngineAcoustics = Factory
    try:
        for vehicle in REMAINING_VEHICLES:
            _dashboards.render_vehicle_audio(vehicle, configs[vehicle])
        records_by_vehicle: dict[str, list[dict[str, Any]]] = {}
        candidate_hashes_by_vehicle: dict[str, dict[str, str]] = {}
        reference_hashes_by_vehicle: dict[str, dict[str, str]] = {}
        contracts: dict[str, dict[str, Any]] = {}
        for vehicle in REMAINING_VEHICLES:
            cfg = configs[vehicle]
            root = Path(cfg["dir"])
            web_dir = root / "web_audio"
            engine = engines[vehicle]
            records = [dict(record) for record in engine.reports]
            if len(records) != len(SCENE_IDS):
                raise ValueError(f"{vehicle} did not render ten scenes")
            for scene, record in zip(cfg["scenes"], records):
                if record["scene_id"] != scene["id"]:
                    raise ValueError(f"{vehicle} scene order drift")
                record["scene"] = scene["id"]
                record["wav_file_sha256"] = sha256_file(web_dir / scene["candidate_file"])
                record["candidate_wav_sha256"] = record["wav_file_sha256"]
            candidate_hashes = {scene["candidate_file"]: sha256_file(web_dir / scene["candidate_file"]) for scene in cfg["scenes"]}
            reference_hashes = {scene["ref_file"]: sha256_file(web_dir / scene["ref_file"]) for scene in cfg["scenes"]}
            records_by_vehicle[vehicle] = records
            candidate_hashes_by_vehicle[vehicle] = candidate_hashes
            reference_hashes_by_vehicle[vehicle] = reference_hashes
            contract = _build_contract(
                package_id,
                f"AH-REMAINING-{group}-{vehicle.upper()}",
                cfg,
                vehicle,
                group,
                engine,
                engine.feedback,
                source_receipt,
                candidate_hashes,
                reference_hashes,
            )
            contracts[vehicle] = contract
            cfg["_dashboard_contract"] = contract
            cfg["_dashboard_params"] = []
            _write_json(root / "dashboard_contract.json", contract)
        for vehicle in REMAINING_VEHICLES:
            _dashboards.build_dashboard(vehicle, configs[vehicle])
            for html_path in (Path(configs[vehicle]["dir"]) / "index.html", Path(configs[vehicle]["dir"]) / "index_standalone.html"):
                html = html_path.read_text(encoding="utf-8")
                html = html.replace("B: 真车参考实录 (R3 Reference)", "B: 真车参考实录 (R3 / 未核验未同步)")
                html = html.replace("B: 真车参考实录 (R3)", "B: 真车参考实录 (R3 / 未核验未同步)")
                html_path.write_text(html, encoding="utf-8")

        shutil.copy2(reference_bundle / "reference_clip_receipt.json", package_root / "reference_clip_receipt.json")
        shutil.copy2(reference_bundle / "source_receipt.json", package_root / "source_receipt.json")
        binding = seal_payload(
            {
                "schema": BINDING_SCHEMA,
                "package_id": package_id,
                "candidate_id": f"AH-REMAINING-{group}",
                "group": group,
                "vehicles": list(REMAINING_VEHICLES),
                "source_variants": dict(SOURCE_VARIANTS),
                "output_policy": policy,
                "reference_status": REFERENCE_STATUS,
                "promotable": False,
                "feedback_control": {vehicle: dict(engines[vehicle].feedback) for vehicle in REMAINING_VEHICLES},
                "scene_trace_parent_keys": {
                    vehicle: [record["parent_peak_key"] for record in records_by_vehicle[vehicle]]
                    for vehicle in REMAINING_VEHICLES
                },
                "candidate_sha256": candidate_hashes_by_vehicle,
                "reference_sha256": reference_hashes_by_vehicle,
            },
            BINDING_SCHEMA,
        )
        _write_json(package_root / "stage_ah_remaining_binding.json", binding)
        artifacts = [
            artifact_record(path, package_root, f"remaining:{path.relative_to(package_root).as_posix()}")
            for path in _artifact_paths(package_root, configs, source_receipt)
            if path.is_file()
        ]
        manifest = seal_payload(
            {
                "schema": PACKAGE_SCHEMA,
                "stage": "AH-REMAINING",
                "package_id": package_id,
                "candidate_id": f"AH-REMAINING-{group}",
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "group": group,
                "vehicles": [
                    {
                        "vehicle": vehicle,
                        "directory": vehicle,
                        "port": int(ports[vehicle]),
                        "scenes": list(SCENE_IDS),
                        "candidate_sha256": candidate_hashes_by_vehicle[vehicle],
                        "reference_sha256": reference_hashes_by_vehicle[vehicle],
                        "parent_peak_keys": [record["parent_peak_key"] for record in records_by_vehicle[vehicle]],
                        "feedback_control": dict(engines[vehicle].feedback),
                    }
                    for vehicle in REMAINING_VEHICLES
                ],
                "source_variants": dict(SOURCE_VARIANTS),
                "output_policy": policy,
                "output_policy_config": {
                    "policy_id": policy,
                    "knee_linear": 0.90 if policy == LINKED_SOFT_CEILING_V1 else None,
                    "ceiling_linear": 0.94,
                    "stereo_link": "instantaneous_frame_peak_common_gain" if policy == LINKED_SOFT_CEILING_V1 else "legacy_renderer_path",
                },
                "reference_evidence_level": REFERENCE_EVIDENCE_LEVEL,
                "reference_status": REFERENCE_STATUS,
                "promotable": False,
                "promotion_status": "NOT_PROMOTABLE_R3_UNVERIFIED_UNSYNCHRONIZED",
                "feedback_control": {vehicle: dict(engines[vehicle].feedback) for vehicle in REMAINING_VEHICLES},
                "human_status": "WAITING_FOR_JOVI_FEEDBACK",
                "package_gain_db": 0.0,
                "source_receipt_sha256": source_receipt["source_receipt_sha256"],
                "reference_clip_receipt_sha256": source_receipt["manifest_sha256"],
                "artifacts": artifacts,
                "rules": [
                    "Only deterministic reference clips and metadata are copied; original videos/audio remain external.",
                    "Reference evidence is R3 unverified and unsynchronized; no OEM or Human PASS is claimed.",
                    "Feedback is manual, bounded, source-scoped, and never an automatic parameter search.",
                ],
            },
            PACKAGE_SCHEMA,
        )
        _write_json(package_root / "audition_manifest.json", manifest)
        validate_artifacts(artifacts, package_root)
        report_records = [record for vehicle in REMAINING_VEHICLES for record in records_by_vehicle[vehicle]]
        report = {
            "schema": "s12.stage_ah.remaining_vehicles.report.v1",
            "run_id": run_root.name,
            "package": str(package_root),
            "package_manifest_sha256": sha256_file(package_root / "audition_manifest.json"),
            "group": group,
            "output_policy": policy,
            "source_variants": dict(SOURCE_VARIANTS),
            "reference_status": REFERENCE_STATUS,
            "reference_evidence_level": REFERENCE_EVIDENCE_LEVEL,
            "promotable": False,
            "human_status": "WAITING_FOR_JOVI_FEEDBACK",
            "feedback_control": {vehicle: dict(engines[vehicle].feedback) for vehicle in REMAINING_VEHICLES},
            "vehicles": {
                vehicle: {"records": records_by_vehicle[vehicle], "aggregate": _aggregate(records_by_vehicle[vehicle])}
                for vehicle in REMAINING_VEHICLES
            },
            "records": report_records,
            "reference_gate": {
                "status": "NOT_EVALUATED_UNSYNCHRONIZED_R3",
                "rows": 0,
                "missing": 0,
                "regressions": 0,
                "reason": "R3 recordings have no synchronized RPM/microphone/AGC contract",
            },
        }
        report_path = run_root / f"{group.lower()}_report.json"
        _write_json(report_path, seal_payload(report, "s12.stage_ah.remaining_vehicles.report.v1"))
        return {
            "group": group,
            "package": str(package_root),
            "package_manifest_sha256": sha256_file(package_root / "audition_manifest.json"),
            "report": str(report_path),
            "report_sha256": sha256_file(report_path),
            "records": records_by_vehicle,
            "parent_peaks": {vehicle: dict(engines[vehicle].parent_peaks) for vehicle in REMAINING_VEHICLES},
            "candidate_hashes": candidate_hashes_by_vehicle,
            "reference_hashes": reference_hashes_by_vehicle,
            "feedback_control": {vehicle: dict(engines[vehicle].feedback) for vehicle in REMAINING_VEHICLES},
            "status": "READY_FOR_LOCAL_HUMAN_REVIEW",
        }
    finally:
        _dashboards.VEHICLE_CONFIGS = previous_configs
        _dashboards.EngineAcoustics = previous_engine
        _dashboards.TEMPLATE_PATH = previous_template


def _feedback_rows(value: Path | str | Mapping[str, Any] | None) -> dict[str, list[Mapping[str, Any]]]:
    rows: dict[str, list[Mapping[str, Any]]] = {vehicle: [] for vehicle in REMAINING_VEHICLES}
    if value is None:
        return rows
    if isinstance(value, Mapping):
        payload = dict(value)
    else:
        text = str(value)
        path = Path(text)
        if path.is_file():
            payload = _read_json(path)
        else:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError("feedback JSON must be a file or JSON object") from exc
        if not isinstance(payload, dict):
            raise ValueError("feedback JSON must be an object")
    source = payload.get("vehicles", payload)
    for vehicle in REMAINING_VEHICLES:
        entry = source.get(vehicle, []) if isinstance(source, Mapping) else []
        if isinstance(entry, Mapping):
            entry = entry.get("rows", entry.get("feedback_rows", []))
        if not isinstance(entry, list):
            raise ValueError(f"feedback rows for {vehicle} must be a list")
        rows[vehicle] = entry
    return rows


def _comparison(b0: Mapping[str, Any], c0: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    for vehicle in REMAINING_VEHICLES:
        left = b0["records"][vehicle]
        right = c0["records"][vehicle]
        if len(left) != len(right):
            raise ValueError(f"{vehicle} B0/C0 record count drift")
        for a, b in zip(left, right):
            if a["scene_id"] != b["scene_id"] or a["trace_sha256"] != b["trace_sha256"] or a["parent_peak_key"] != b["parent_peak_key"]:
                raise ValueError(f"{vehicle} B0/C0 trace/parent drift")
            if a["normalization"]["pre_guard_pcm_sha256"] != b["normalization"]["pre_guard_pcm_sha256"]:
                raise ValueError(f"{vehicle} B0/C0 pre-guard drift")
            rows.append(
                {
                    "vehicle": vehicle,
                    "scene_id": a["scene_id"],
                    "comparison_type": "OUTPUT_POLICY_ONLY",
                    "pre_guard_pcm_equal": True,
                    "pcm_equal": a["final_pcm_sha256"] == b["final_pcm_sha256"],
                    "rms_delta": float(b["final_rms"] - a["final_rms"]),
                    "peak_delta": float(b["final_peak"] - a["final_peak"]),
                }
            )
    return {
        "record_count": len(rows),
        "pre_guard_equal_count": sum(row["pre_guard_pcm_equal"] for row in rows),
        "pcm_equal_count": sum(row["pcm_equal"] for row in rows),
        "rows": rows,
    }


def build_run(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    run_id: str = DEFAULT_RUN_ID,
    source_receipt: Path | Mapping[str, Any],
    feedback_json: Path | str | Mapping[str, Any] | None = None,
    port_b0: int = DEFAULT_PORT_B0,
    port_c0: int = DEFAULT_PORT_C0,
    clip_duration_s: float = DEFAULT_CLIP_DURATION_S,
) -> Path:
    run_root = Path(output_root).resolve() / validate_identifier(run_id, "run_id")
    if run_root.exists():
        raise FileExistsError(f"run already exists: {run_root}")
    b0_ports = {"rx7_fd": int(port_b0), "aventador_lp700": int(port_b0) + 1}
    c0_ports = {"rx7_fd": int(port_c0), "aventador_lp700": int(port_c0) + 1}
    all_ports = list(b0_ports.values()) + list(c0_ports.values())
    if any(port <= 0 for port in all_ports) or len(set(all_ports)) != len(all_ports):
        raise ValueError("B0/C0 ports must be positive and unique")
    run_root.mkdir(parents=True)
    reference_bundle = run_root / "reference_bundle"
    reference_receipt = build_reference_bundle(reference_bundle, source_receipt, clip_duration_s=clip_duration_s)
    feedback = _feedback_rows(feedback_json)
    source_git = dict(git_source_receipt(allow_dirty_dev=False))
    source_git.update(
        {
            "stage": "AH-REMAINING",
            "source_variants": dict(SOURCE_VARIANTS),
            "remaining_pipeline_sha256": sha256_file(Path(__file__).with_name("remaining_vehicle_pipeline.py")),
            "source_receipt_sha256": reference_receipt["source_receipt_sha256"],
            "source_pool_counts": dict(reference_receipt["source_counts"]),
            "reference_status": REFERENCE_STATUS,
            "promotable": False,
            "promotion_status": "NOT_PROMOTABLE_R3_UNVERIFIED_UNSYNCHRONIZED",
            "feedback_control": {vehicle: feedback.get(vehicle, []) for vehicle in REMAINING_VEHICLES},
        }
    )
    # The group manifest receives the full sealed receipt so the package does not
    # trust an external path at serve time.
    b0 = _build_group(
        run_root=run_root,
        group="B0",
        source_receipt={**reference_receipt, "source_git": source_git},
        reference_bundle=reference_bundle,
        feedback=feedback,
        parent_peaks=None,
        ports=b0_ports,
    )
    c0 = _build_group(
        run_root=run_root,
        group="C0",
        source_receipt={**reference_receipt, "source_git": source_git},
        reference_bundle=reference_bundle,
        feedback=feedback,
        parent_peaks=b0["parent_peaks"],
        ports=c0_ports,
    )
    experiment = seal_payload(
        {
            "schema": RUN_SCHEMA,
            "stage": "AH-REMAINING",
            "run_id": run_id,
            "source_git": source_git,
            "source_variants": dict(SOURCE_VARIANTS),
            "reference_status": REFERENCE_STATUS,
            "reference_evidence_level": REFERENCE_EVIDENCE_LEVEL,
            "promotable": False,
            "feedback_control": {vehicle: feedback.get(vehicle, []) for vehicle in REMAINING_VEHICLES},
            "reference_clip_receipt_sha256": reference_receipt["manifest_sha256"],
            "groups": [
                {key: value for key, value in group.items() if key not in {"records", "parent_peaks", "candidate_hashes", "reference_hashes"}}
                for group in (b0, c0)
            ],
            "comparisons": {"B0_to_C0": _comparison(b0, c0)},
            "status": "DIAGNOSTIC_READY_FOR_LOCAL_HUMAN_REVIEW",
            "human_status": "WAITING_FOR_JOVI_FEEDBACK",
            "rules": [
                "R3 source recordings are unverified and unsynchronized relative cues.",
                "C0 uses linked_soft_ceiling_v1 with fixed K=0.90 and C=0.94.",
                "No automatic tuning, global gain, old package overwrite, or promotion is performed.",
            ],
        },
        RUN_SCHEMA,
    )
    experiment_path = run_root / "experiment.json"
    _write_json(experiment_path, experiment)
    return experiment_path


def _verify_package(package: Path) -> dict[str, Any]:
    manifest = _read_sealed(package / "audition_manifest.json")
    if manifest.get("schema") != PACKAGE_SCHEMA:
        raise ValueError(f"wrong remaining package schema: {package}")
    if manifest.get("promotable") is not False or manifest.get("reference_status") != REFERENCE_STATUS:
        raise ValueError(f"remaining package promotion/reference contract invalid: {package}")
    validate_artifacts(manifest.get("artifacts", []), package)
    for vehicle in manifest.get("vehicles", []):
        root = package / str(vehicle["directory"])
        if len(vehicle.get("scenes", [])) != 10:
            raise ValueError(f"remaining package must contain ten scenes: {vehicle.get('vehicle')}")
        for scene in vehicle["scenes"]:
            if not (root / "web_audio" / f"{scene}.wav").is_file():
                raise FileNotFoundError(root / "web_audio" / f"{scene}.wav")
    return manifest


def serve_run(experiment_path: Path, group: str = "C0") -> None:
    """Serve B0 plus C0, or one explicitly selected group, on manifest ports."""
    experiment = _read_sealed(Path(experiment_path).resolve())
    groups = {str(entry["group"]): entry for entry in experiment.get("groups", [])}
    selected_group = str(group).upper()
    if selected_group not in groups:
        raise ValueError(f"unknown remaining group: {group}")
    selected = [groups["B0"], groups[selected_group]] if selected_group == "C0" else [groups[selected_group]]
    servers: list[ThreadingHTTPServer] = []
    try:
        for entry in selected:
            package = Path(entry["package"]).resolve()
            manifest = _verify_package(package)
            if sha256_file(package / "audition_manifest.json") != entry["package_manifest_sha256"]:
                raise ValueError(f"package manifest drift: {package}")
            for vehicle in manifest["vehicles"]:
                root = package / str(vehicle["directory"])
                server = ThreadingHTTPServer(("127.0.0.1", int(vehicle["port"])), partial(SimpleHTTPRequestHandler, directory=str(root)))
                servers.append(server)
                print(f"{entry['group']} {vehicle['vehicle']} http://localhost:{vehicle['port']}/")
        threads = []
        for server in servers:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="build fresh RX-7/Aventador B0/C0 package")
    build.add_argument("--source-receipt", type=Path, required=True)
    build.add_argument("--feedback-json", default=None, help="feedback JSON path or inline JSON")
    build.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    build.add_argument("--run-id", default=DEFAULT_RUN_ID)
    build.add_argument("--port-b0", type=int, default=DEFAULT_PORT_B0)
    build.add_argument("--port-c0", type=int, default=DEFAULT_PORT_C0)
    build.add_argument("--clip-duration-s", type=float, default=DEFAULT_CLIP_DURATION_S)
    serve = sub.add_parser("serve", help="serve manifest-bound candidate pages")
    serve.add_argument("--experiment", type=Path, required=True)
    serve.add_argument("--group", choices=("B0", "C0"), default="C0")
    args = parser.parse_args(argv)
    if args.command == "build":
        print(build_run(output_root=args.output_root, run_id=args.run_id, source_receipt=args.source_receipt, feedback_json=args.feedback_json, port_b0=args.port_b0, port_c0=args.port_c0, clip_duration_s=args.clip_duration_s))
    else:
        serve_run(args.experiment, args.group)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "BINDING_SCHEMA",
    "CONTRACT_SCHEMA",
    "PACKAGE_SCHEMA",
    "REFERENCE_SCHEMA",
    "REFERENCE_STATUS",
    "RUN_SCHEMA",
    "build_reference_bundle",
    "build_run",
    "main",
    "serve_run",
)
