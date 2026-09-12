"""Build and serve a local Toyota Supra JZA80 AH audition package.

The package is intentionally separate from the four-car AH/R1 registry. It
reuses the original rich dashboard and records the SUPRA reference clips as
local, unverified diagnostic material.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import shutil
import sys
import threading
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

from ..stage_ad import engine_sim_acoustics as stage_ad_audio
from ..stage_af.package_integrity import (
    REPOSITORY_ROOT,
    artifact_record,
    canonical_json_bytes,
    git_source_receipt,
    seal_contract,
    seal_payload,
    sha256_file,
    validate_artifacts,
    validate_identifier,
)
from .supra_pipeline import (
    SUPRA_BASE_SOURCE_PATH,
    SUPRA_MULTI_REFERENCE_PATH,
    SUPRA_REFERENCE_TARGET_PATH,
    SUPRA_SOURCE_PATH,
    SupraEngine,
    SUPRA_IR_NAME,
    SUPRA_IR_VOLUME,
    SUPRA_SOURCE_VARIANT,
    SUPRA_VEHICLE,
)


_STAGE_AD_DIR = Path(__file__).resolve().parents[1] / "stage_ad"
sys.path.insert(0, str(_STAGE_AD_DIR))
try:
    from ..stage_ad import build_unified_dashboards as _dashboards
finally:
    sys.path.pop(0)
from .output_guard import (
    LEGACY_CLIP_V1,
    LINKED_SOFT_CEILING_V1,
    OUTPUT_GUARD_RECEIPT_SCHEMA,
)


SUPRA_RUN_SCHEMA = "s12.stage_ah.supra.real_reference.experiment_manifest.v1"
SUPRA_PACKAGE_SCHEMA = "s12.stage_ah.supra.real_reference.package_manifest.v1"
SUPRA_BINDING_SCHEMA = "s12.stage_ah.supra.real_reference.binding.v1"
SUPRA_REFERENCE_SCHEMA = "s12.stage_ah.supra.real_reference.reference_clip_receipt.v2"
DEFAULT_RUN_ID = "s12-stage-ah-supra-real-reference-20260912-v1"
DEFAULT_REFERENCE_ROOT = Path(r"E:\Claude_allow\Download\s12-stage-ah-supra-real-reference-20260912")
DEFAULT_OUTPUT_ROOT = Path(r"E:\Tesla_speed\review_packages")
DEFAULT_PORT_B0 = 24980
DEFAULT_PORT_C0 = 25080

REFERENCE_SOURCES = {
    "supra_01_bone_stock_dyno": {
        "filename": "supra_01.wav",
        "sha256": "e8ef231c4f4c2c46dec96d4e0ecd47bab1f9c10cfc23a0efa910052ba5e850de",
        "sample_rate_hz": 44_100,
    },
    "supra_02_mostly_stock_road": {
        "filename": "supra_02.wav",
        "sha256": "104182c07227f344c505b27d79b7501900ab5ce3b99312b64bc6492e89eb5122",
        "sample_rate_hz": 44_100,
    },
    "supra_03_stock_start_acceleration": {
        "filename": "supra_03.wav",
        "sha256": "d645f2036644b2166891d797e0a72aeea4d5427af3d37504fae8c3123a272189",
        "sample_rate_hz": 48_000,
    },
    "supra_stock_existing": {
        "filename": "supra_jza80_stock.wav",
        "sha256": "ccde31e8ec6e178eeb64019294d42a35f83c1903c8321d471eefb7f0b72e55bb",
        "sample_rate_hz": 48_000,
    },
}
REFERENCE_CLIPS = {
    "ref_afterfire.wav": ("supra_stock_existing", 12.5, 4.0),
    "ref_full_pull_dyno.wav": ("supra_01_bone_stock_dyno", 354.625, 5.0),
    "ref_hot_idle.wav": ("supra_03_stock_start_acceleration", 0.0, 5.0),
    "ref_idle_return.wav": ("supra_stock_existing", 0.0, 4.0),
    "ref_shift_road.wav": ("supra_02_mostly_stock_road", 780.375, 5.0),
    "ref_steady_high_stock.wav": ("supra_03_stock_start_acceleration", 20.625, 5.0),
    "ref_steady_low.wav": ("supra_stock_existing", 1.0, 4.0),
    "ref_steady_mid_road.wav": ("supra_02_mostly_stock_road", 780.375, 5.0),
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_sealed(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    checksum = payload.pop("manifest_sha256", None)
    checksum_field = "manifest_sha256"
    if checksum is None:
        checksum = payload.pop("contract_sha256", None)
        checksum_field = "contract_sha256"
    if checksum != _sha256_bytes(canonical_json_bytes(payload)):
        raise ValueError(f"sealed receipt mismatch: {path}")
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


def build_reference_bundle(destination: Path, source_root: Path) -> dict[str, Any]:
    """Create deterministic stereo diagnostic clips from external local media."""
    destination = destination.resolve()
    source_root = source_root.resolve()
    if destination.exists():
        raise FileExistsError(destination)
    destination.mkdir(parents=True)
    sources: dict[str, Any] = {}
    source_arrays: dict[str, np.ndarray] = {}
    for source_id, spec in REFERENCE_SOURCES.items():
        path = source_root / spec["filename"]
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual.lower() != spec["sha256"].lower():
            raise ValueError(f"reference source SHA mismatch: {path}")
        sample_rate, data = wavfile.read(path)
        if int(sample_rate) != int(spec["sample_rate_hz"]):
            raise ValueError(f"reference source sample rate mismatch: {path}")
        mono = _to_float_mono(data)
        if mono.size == 0 or not np.all(np.isfinite(mono)):
            raise ValueError(f"reference source is empty/non-finite: {path}")
        original_frames = int(mono.size)
        if int(sample_rate) != 48_000:
            mono = resample_poly(mono, 48_000, int(sample_rate))
        source_arrays[source_id] = np.asarray(mono, dtype=np.float64)
        sources[source_id] = {
            "path": str(path),
            "sha256": actual,
            "sample_rate_hz": int(sample_rate),
            "normalized_sample_rate_hz": 48_000,
            "resample_method": "scipy.signal.resample_poly" if int(sample_rate) != 48_000 else "none",
            "original_frames": original_frames,
            "frames": int(mono.size),
            "duration_s": float(mono.size / 48_000),
        }

    clips: dict[str, Any] = {}
    for filename, (source_id, start_s, duration_s) in REFERENCE_CLIPS.items():
        source = sources[source_id]
        mono = source_arrays[source_id]
        start = int(round(float(start_s) * 48_000))
        count = int(round(float(duration_s) * 48_000))
        stop = start + count
        if start < 0 or stop > mono.size:
            raise ValueError(f"reference clip window exceeds source: {filename}")
        clip = np.column_stack((mono[start:stop], mono[start:stop]))
        clip_i16 = np.clip(np.rint(clip * 32767.0), -32768, 32767).astype(np.int16)
        path = destination / filename
        wavfile.write(path, 48_000, clip_i16)
        clips[filename] = {
            "filename": filename,
            "source_id": source_id,
            "source_path": source["path"],
            "source_sha256": source["sha256"],
            "start_s": float(start_s),
            "duration_s": float(duration_s),
            "start_sample": start,
            "end_sample_exclusive": stop,
            "sha256": sha256_file(path),
            "evidence_level": "R3_PUBLIC_RECORDING_UNVERIFIED",
            "rights_status": "UNVERIFIED_LOCAL_ASSET",
        }
    receipt = {
        "schema": SUPRA_REFERENCE_SCHEMA,
        "source_root": str(source_root),
        "sources": sources,
        "clips": clips,
        "status": "LOCAL_DIAGNOSTIC_ONLY_UNSYNCHRONIZED_R3",
    }
    sealed = seal_payload(receipt, SUPRA_REFERENCE_SCHEMA)
    _write_json(destination / "reference_clip_receipt.json", sealed)
    return sealed


def _supra_config(directory: Path, port: int) -> dict[str, Any]:
    return {
        "dir": directory,
        "port": int(port),
        "name": "Toyota Supra JZA80",
        "title": "TOYOTA SUPRA JZA80 2JZ 声音仿真人耳试听",
        "subtitle": "Stage AH-SUPRA / 2JZ-GTE 3.0L inline-six twin-turbo / 三组 R3 公开录音，未核验未同步",
        "badge": "🏁 Toyota Supra JZA80 (2JZ-GTE 3.0L I6 twin-turbo)",
        "icon": "🏁",
        "color": "red",
        "idle_rpm": 800.0,
        "redline_rpm": 7000.0,
        "pull_start": 2500.0,
        "pull_end": 7000.0,
        "shift_cut": 0.08,
        "ref_source": "Three local R3 public recordings / unverified provenance and unsynchronized state",
        "scenes": [
            {"id": "01_afterfire", "index": 1, "category": "afterfire", "candidate_file": "01_afterfire.wav", "ref_file": "ref_afterfire.wav", "title": "01 收油回火与 2JZ 爆音 (Afterfire)", "desc": "高转速急收油后的直六涡轮排气回火与短促爆音。", "focus": "关注收油瞬态的脆度、涡轮泄压感与尾部衰减。"},
            {"id": "02_full_pull", "index": 2, "category": "acceleration", "candidate_file": "02_full_pull.wav", "ref_file": "ref_full_pull_dyno.wav", "title": "02 全负荷 2JZ-GTE 加速 (Full Pull)", "desc": "2JZ-GTE 双涡轮从中转速拉向红线的深沉直六咆哮。", "focus": "关注均匀直六脉冲、涡轮 spool 和中高频张力。"},
            {"id": "03_hot_idle", "index": 3, "category": "idle", "candidate_file": "03_hot_idle.wav", "ref_file": "ref_hot_idle.wav", "title": "03 热态怠速平顺直六 (Hot Idle)", "desc": "2JZ-GTE 热态低转怠速的均匀直六燃烧节奏。", "focus": "关注低频厚度、均匀脉冲和轻微机械纹理。"},
            {"id": "04_idle_return", "index": 4, "category": "idle", "candidate_file": "04_idle_return.wav", "ref_file": "ref_idle_return.wav", "title": "04 轰油回落怠速 (Idle Return)", "desc": "短暂轰油后回到稳定怠速的能量包络。", "focus": "关注回落的连续性与怠速接管。"},
            {"id": "05_lift", "index": 5, "category": "dynamics", "candidate_file": "05_lift.wav", "ref_file": "ref_afterfire.wav", "title": "05 高负荷收油与涡轮泄压 (Lift-off)", "desc": "高负荷后关闭节气门，保留排气尾部、回火和涡轮收束。", "focus": "关注闭节气门冲击、泄压尾音和回火。"},
            {"id": "06_shift", "index": 6, "category": "dynamics", "candidate_file": "06_shift.wav", "ref_file": "ref_shift_road.wav", "title": "06 6MT 换挡断火 (Shift Crack)", "desc": "六速手动换挡中的扭矩交接、短暂断火和重新接合。", "focus": "关注切断瞬间、重接合与涡轮回压。"},
            {"id": "07_steady_high", "index": 7, "category": "cruise", "candidate_file": "07_steady_high.wav", "ref_file": "ref_steady_high_stock.wav", "title": "07 高转巡航 (Steady High)", "desc": "高转速稳定负荷下的 2JZ-GTE 中高频张力。", "focus": "关注高转连续性与机械上层。"},
            {"id": "08_steady_low", "index": 8, "category": "cruise", "candidate_file": "08_steady_low.wav", "ref_file": "ref_steady_low.wav", "title": "08 低转跟车 (Steady Low)", "desc": "低负荷低转速的深沉、收束声浪。", "focus": "关注低频厚度与空腔感。"},
            {"id": "09_steady_mid", "index": 9, "category": "cruise", "candidate_file": "09_steady_mid.wav", "ref_file": "ref_steady_mid_road.wav", "title": "09 中转动力巡航 (Steady Mid)", "desc": "中转速持续负荷下的直六排气与涡轮中频张力。", "focus": "关注中频主体、涡轮连续性和均匀节奏。"},
            {"id": "10_tip_in", "index": 10, "category": "dynamics", "candidate_file": "10_tip_in.wav", "ref_file": "", "title": "10 急踩油门瞬态 (Tip-in)", "desc": "低负荷巡航到双涡轮建立增压的瞬间响应。", "focus": "关注油门踩下后的 spool 迟滞与声浪增长。"},
        ],
    }


def _reference_map(reference_receipt: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        filename: {
            "available": True,
            "fit_required": False,
            "source_label": f"local R3 public recording: {info['source_id']} [{info['start_s']:.1f}-{info['start_s'] + info['duration_s']:.1f}s]",
            "sha256": info["sha256"],
            "evidence_level": info["evidence_level"],
            "rights_status": info["rights_status"],
        }
        for filename, info in reference_receipt["clips"].items()
    }


def _renderer_identity(engine: SupraEngine) -> dict[str, Any]:
    ptr_path = SUPRA_SOURCE_PATH.parents[2] / "acoustic_demo" / "runtime_ptr_adapter.py"
    return {
        "vehicle": SUPRA_VEHICLE,
        "renderer": "render_realism_v10._render_stateful + frozen_ptr + AH-C1 output guard",
        "source_sha256": sha256_file(SUPRA_SOURCE_PATH),
        "source_path": str(SUPRA_SOURCE_PATH),
        "base_source_sha256": sha256_file(SUPRA_BASE_SOURCE_PATH),
        "base_source_path": str(SUPRA_BASE_SOURCE_PATH),
        "reference_target_sha256": sha256_file(SUPRA_REFERENCE_TARGET_PATH),
        "reference_target_path": str(SUPRA_REFERENCE_TARGET_PATH),
        "multi_reference_target_sha256": sha256_file(SUPRA_MULTI_REFERENCE_PATH),
        "multi_reference_target_path": str(SUPRA_MULTI_REFERENCE_PATH),
        "frozen_ptr_sha256": sha256_file(ptr_path),
        "ir_name": SUPRA_IR_NAME,
        "ir_volume": SUPRA_IR_VOLUME,
        "ir_source_path": str(engine.ir_source_path) if engine.ir_source_path else "INJECTED_TEST_IR",
        "ir_source_sha256": engine.ir_source_sha256,
        "sample_rate_hz": 48_000,
    }


def _true_peak(audio_path: Path) -> dict[str, Any]:
    sample_rate, data = wavfile.read(audio_path)
    if int(sample_rate) != 48_000:
        raise ValueError(f"candidate must be 48 kHz: {audio_path}")
    x = np.asarray(data, dtype=np.float64) / 32768.0
    if x.ndim == 1:
        x = x[:, None]
    up = resample_poly(x, 4, 1, axis=0, window=("kaiser", 5.0))
    return {
        "estimated_true_peak_4x": float(np.max(np.abs(up))),
        "estimator_method": "scipy.signal.resample_poly",
        "estimator_up": 4,
        "estimator_down": 1,
        "estimator_filter": "kaiser_beta_5.0",
        "estimator_edge_policy": "wav_boundary_zero_assumed",
        "status": "DIAGNOSTIC_ONLY_NOT_ITU_CERTIFIED",
    }


def _build_contract(
    package_id: str,
    candidate_id: str,
    cfg: Mapping[str, Any],
    source_receipt: Mapping[str, Any],
    reference_receipt: Mapping[str, Any],
    engine: SupraEngine,
    candidate_hashes: Mapping[str, str],
    reference_hashes: Mapping[str, str],
) -> dict[str, Any]:
    policy = engine.output_policy
    return seal_contract(
        {
            "schema": "s12.stage_ah.supra.real_reference.dashboard_contract.v1",
            "stage": "AH-SUPRA-REALREF",
            "package_id": package_id,
            "candidate_id": candidate_id,
            "vehicle": SUPRA_VEHICLE,
            "source_variant": SUPRA_SOURCE_VARIANT,
            "source_adjustment": {"edge_scale": 1.4, "hiband_scale": 3.4, "domain": "source_only"},
            "output_policy": policy,
            "output_policy_config": {
                "policy_id": policy,
                "knee_linear": 0.90 if policy == LINKED_SOFT_CEILING_V1 else None,
                "ceiling_linear": 0.94,
                "stereo_link": "instantaneous_frame_peak_common_gain" if policy == LINKED_SOFT_CEILING_V1 else "legacy_renderer_path",
                "parent_denominator_policy": "fixed_parent_peak",
            },
            "output_guard_receipt_schema": OUTPUT_GUARD_RECEIPT_SCHEMA if policy == LINKED_SOFT_CEILING_V1 else "s12.stage_ah.output_guard_receipt.v1",
            "flags": [],
            "seed": 20260908,
            "identity_mode": "stage_k_source_identity_not_ag_r1",
            "fit_status": "NOT_FITTED",
            "fit_metric_status": "NOT_MEASURED",
            "measurement_status": "NOT_MEASURED",
            "human_status": "WAITING_FOR_JOVI_FEEDBACK",
            "reference_evidence_level": "R3_PUBLIC_RECORDINGS_RELATIVE_CUES",
            "reference_rights_status": "UNVERIFIED_LOCAL_ASSET",
            "sample_rate_hz": 48_000,
            "package_port": int(cfg["port"]),
            "nav_urls": {SUPRA_VEHICLE: f"http://localhost:{int(cfg['port'])}/"},
            "renderer_identity": _renderer_identity(engine),
            "references": _reference_map(reference_receipt),
            "candidate_pcm_sha256": dict(candidate_hashes),
            "reference_sha256": dict(reference_hashes),
            "source_receipt": dict(source_receipt),
            "reference_clip_receipt_sha256": sha256_file(Path(cfg["reference_bundle"]) / "reference_clip_receipt.json"),
            "package_gain_db": 0.0,
            "gain_policy": "fixed_parent_peak_tanh_then_optional_linked_soft_ceiling",
            "source_status": "SOURCE_CLEAN",
            "promotable": False,
            "promotion_status": "NOT_PROMOTABLE_UNSYNCED_UNVERIFIED_REFERENCE",
            "self_contained_status": "AUDIO_SELF_CONTAINED / LOCAL_REFERENCE_PROVENANCE_REQUIRED",
        }
    )


def _artifact_paths(cfg: Mapping[str, Any], reference_receipt: Mapping[str, Any]) -> list[Path]:
    root = Path(cfg["dir"])
    paths: list[Path] = []
    for scene in cfg["scenes"]:
        paths.extend((root / scene["candidate_file"], root / "web_audio" / scene["candidate_file"]))
        ref = str(scene.get("ref_file", ""))
        if ref:
            paths.append(root / "web_audio" / ref)
    paths.extend((root / "index.html", root / "index_standalone.html", root / "dashboard_contract.json", root / "stage_ah_supra_binding.json"))
    paths.append(root.parent / "reference_clip_receipt.json")
    paths.append(root.parent / SUPRA_MULTI_REFERENCE_PATH.name)
    return list(dict.fromkeys(paths))


def build_group(
    *,
    run_root: Path,
    group: str,
    output_policy: str,
    source_receipt: Mapping[str, Any],
    reference_bundle: Path,
    parent_peaks: Mapping[int, float] | None,
    port: int,
) -> dict[str, Any]:
    package_id = validate_identifier(f"ah-supra-realref-{run_root.name}-{group.lower()}", "package_id")
    package_root = run_root / "packages" / package_id
    if package_root.exists():
        raise FileExistsError(package_root)
    vehicle_root = package_root / SUPRA_VEHICLE
    web_dir = vehicle_root / "web_audio"
    web_dir.mkdir(parents=True)
    for source in reference_bundle.glob("ref_*.wav"):
        shutil.copy2(source, web_dir / source.name)
    shutil.copy2(reference_bundle / "reference_clip_receipt.json", package_root / "reference_clip_receipt.json")
    shutil.copy2(SUPRA_MULTI_REFERENCE_PATH, package_root / SUPRA_MULTI_REFERENCE_PATH.name)
    cfg = _supra_config(vehicle_root, port)
    cfg["title"] = f"[AH-SUPRA-REALREF · {group} · {output_policy}] " + cfg["title"]
    cfg["subtitle"] = (
        f"Stage AH-SUPRA-REALREF / {group} / output_policy={output_policy} / "
        + cfg["subtitle"]
    )
    cfg["reference_bundle"] = reference_bundle
    cfg["_nav_ports"] = {SUPRA_VEHICLE: int(port)}
    cfg["_nav_vehicles"] = (SUPRA_VEHICLE,)
    holder: dict[str, SupraEngine] = {}
    previous_configs = _dashboards.VEHICLE_CONFIGS
    previous_engine = _dashboards.EngineAcoustics
    previous_template = _dashboards.TEMPLATE_PATH
    _dashboards.VEHICLE_CONFIGS = {SUPRA_VEHICLE: cfg}
    _dashboards.TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "stage_ad" / "audition_dashboard_template.html"

    class Factory:
        def __new__(cls, vehicle_type: str = SUPRA_VEHICLE, sr: int = 48_000):
            if vehicle_type != SUPRA_VEHICLE:
                raise ValueError(f"unexpected SUPRA vehicle: {vehicle_type}")
            engine = SupraEngine(
                vehicle_type,
                sr,
                output_policy=output_policy,
                parent_peaks=parent_peaks,
            )
            holder["engine"] = engine
            return engine

    _dashboards.EngineAcoustics = Factory
    try:
        _dashboards.render_vehicle_audio(SUPRA_VEHICLE, cfg)
        engine = holder["engine"]
        records = [dict(record, scene=scene["id"]) for scene, record in zip(cfg["scenes"], engine.reports)]
        candidate_hashes = {
            scene["candidate_file"]: sha256_file(vehicle_root / "web_audio" / scene["candidate_file"])
            for scene in cfg["scenes"]
        }
        reference_hashes = {
            filename: sha256_file(web_dir / filename)
            for filename in sorted({str(scene.get("ref_file", "")) for scene in cfg["scenes"] if scene.get("ref_file")})
        }
        reference_receipt = _read_sealed(reference_bundle / "reference_clip_receipt.json")
        contract = _build_contract(
            package_id,
            f"AH-SUPRA-REALREF-{group}",
            cfg,
            source_receipt,
            reference_receipt,
            engine,
            candidate_hashes,
            reference_hashes,
        )
        cfg["_dashboard_contract"] = contract
        cfg["_dashboard_params"] = []
        _write_json(vehicle_root / "dashboard_contract.json", contract)
        _dashboards.build_dashboard(SUPRA_VEHICLE, cfg)
        for path in (vehicle_root / "index.html", vehicle_root / "index_standalone.html"):
            text = path.read_text(encoding="utf-8")
            text = text.replace("B: 真车参考实录 (R3 Reference)", "B: 真车参考实录 (R3 / 公开录音未核验)")
            text = text.replace("B: 真车参考实录 (R3)", "B: 真车参考实录 (R3 / 公开录音未核验)")
            path.write_text(text, encoding="utf-8")

        binding = seal_payload(
            {
                "schema": SUPRA_BINDING_SCHEMA,
                "package_id": package_id,
                "candidate_id": f"AH-SUPRA-REALREF-{group}",
                "vehicle": SUPRA_VEHICLE,
                "source_variant": SUPRA_SOURCE_VARIANT,
                "output_policy": output_policy,
                "candidate_sha256": candidate_hashes,
                "reference_sha256": reference_hashes,
                "reference_clip_receipt": reference_receipt,
                "source_receipt": source_receipt,
            },
            SUPRA_BINDING_SCHEMA,
        )
        _write_json(vehicle_root / "stage_ah_supra_binding.json", binding)
        artifacts = [
            artifact_record(path, package_root, f"supra:{path.relative_to(package_root).as_posix()}")
            for path in _artifact_paths(cfg, reference_receipt)
            if path.is_file()
        ]
        manifest = seal_payload(
            {
                "schema": SUPRA_PACKAGE_SCHEMA,
                "stage": "AH-SUPRA-REALREF",
                "package_id": package_id,
                "candidate_id": f"AH-SUPRA-REALREF-{group}",
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "vehicle": SUPRA_VEHICLE,
                "source_variant": SUPRA_SOURCE_VARIANT,
                "output_policy": output_policy,
                "output_policy_config": contract["output_policy_config"],
                "output_guard_receipt_schema": contract["output_guard_receipt_schema"],
                "source_receipt": source_receipt,
                "reference_evidence_level": "R3_PUBLIC_RECORDINGS_RELATIVE_CUES",
                "reference_rights_status": "UNVERIFIED_LOCAL_ASSET",
                "human_status": "WAITING_FOR_JOVI_FEEDBACK",
                "fit_status": "NOT_FITTED",
                "package_gain_db": 0.0,
                "vehicles": [{
                    "vehicle": SUPRA_VEHICLE,
                    "directory": SUPRA_VEHICLE,
                    "port": int(port),
                    "candidate_sha256": candidate_hashes,
                    "reference_sha256": reference_hashes,
                    "scenes": [scene["id"] for scene in cfg["scenes"]],
                }],
                "artifacts": artifacts,
                "rules": [
                    "SUPRA is a separate local diagnostic package; it is not an AG-R1 parent.",
                    "Reference clips are public recordings with unverified rights and unsynchronized state.",
                    "No Human PASS, OEM reproduction, or profile freeze is claimed.",
                ],
            },
            SUPRA_PACKAGE_SCHEMA,
        )
        _write_json(package_root / "audition_manifest.json", manifest)
        validate_artifacts(artifacts, package_root)

        for scene, record in zip(cfg["scenes"], records):
            record["wav_file_sha256"] = sha256_file(vehicle_root / "web_audio" / scene["candidate_file"])
            record["candidate_wav_sha256"] = record["wav_file_sha256"]
            record["true_peak_4x"] = _true_peak(vehicle_root / "web_audio" / scene["candidate_file"])
        aggregate = {
            "legacy_ceiling_input_exceedance_samples": int(sum(r["normalization"].get("legacy_ceiling_input_exceedance_samples", 0) for r in records)),
            "pre_guard_peak": float(max(r["normalization"]["pre_guard_peak"] for r in records)),
            "post_guard_peak": float(max(r["normalization"]["post_guard_peak"] for r in records)),
            "soft_guard_active_frames": int(sum(r["normalization"].get("soft_guard_active_frames", 0) for r in records)),
            "soft_guard_active_frame_ratio": float(sum(r["normalization"].get("soft_guard_active_frames", 0) for r in records) / max(sum(r["normalization"].get("frame_count", 0) for r in records), 1)),
            "soft_guard_min_gain": float(min(r["normalization"].get("soft_guard_min_gain", 1.0) for r in records)),
            "soft_guard_max_attenuation_db": float(max(r["normalization"].get("soft_guard_max_attenuation_db", 0.0) for r in records)),
            "post_guard_ceiling_exceedance_samples": int(sum(r["normalization"].get("post_guard_ceiling_exceedance_samples", 0) for r in records)),
            "emergency_clip_count": int(sum(r["normalization"].get("emergency_clip_count", 0) for r in records)),
            "identity_layer_clip_count": 0,
            "post_identity_clip_count": 0,
        }
        report = {
            "schema": "s12.stage_ah.supra.real_reference.report_manifest.v1",
            "group": group,
            "source_variant": SUPRA_SOURCE_VARIANT,
            "output_policy": output_policy,
        "package": str(package_root),
            "package_manifest_sha256": sha256_file(package_root / "audition_manifest.json"),
            "source_receipt": source_receipt,
            "reference_clip_receipt": reference_receipt,
            "records": records,
            "aggregate": aggregate,
            "reference_gate": {"status": "NOT_APPLICABLE_UNSYNCHRONIZED_R3", "rows": 0, "regressions": 0, "missing": 0},
            "status": "READY_FOR_LOCAL_HUMAN_REVIEW",
            "human_status": "WAITING_FOR_JOVI_FEEDBACK",
        }
        report_path = run_root / f"{group.lower()}_report.json"
        _write_json(report_path, seal_payload(report, "s12.stage_ah.supra.real_reference.report_manifest.v1"))
        return {
            "group": group,
            "source_variant": SUPRA_SOURCE_VARIANT,
            "output_policy": output_policy,
            "package": str(package_root),
            "package_manifest_sha256": sha256_file(package_root / "audition_manifest.json"),
            "report": str(report_path),
            "report_sha256": sha256_file(report_path),
            "records": records,
            "parent_peaks": dict(engine.parent_peaks),
            "candidate_hashes": candidate_hashes,
            "reference_hashes": reference_hashes,
            "status": "READY_FOR_LOCAL_HUMAN_REVIEW",
        }
    finally:
        _dashboards.VEHICLE_CONFIGS = previous_configs
        _dashboards.EngineAcoustics = previous_engine
        _dashboards.TEMPLATE_PATH = previous_template


def _comparison(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    for a, b in zip(left["records"], right["records"]):
        rows.append({
            "scene": a["scene"],
            "comparison_type": "OUTPUT_POLICY_ONLY",
            "pre_guard_pcm_equal": a["normalization"]["pre_guard_pcm_sha256"] == b["normalization"]["pre_guard_pcm_sha256"],
            "pcm_equal": a["final_pcm_sha256"] == b["final_pcm_sha256"],
            "rms_delta": float(b["final_rms"] - a["final_rms"]),
            "peak_delta": float(b["final_peak"] - a["final_peak"]),
        })
    return {
        "record_count": len(rows),
        "pre_guard_equal_count": sum(r["pre_guard_pcm_equal"] for r in rows),
        "pcm_equal_count": sum(r["pcm_equal"] for r in rows),
        "mean_rms_delta": float(np.mean([r["rms_delta"] for r in rows])) if rows else 0.0,
        "mean_peak_delta": float(np.mean([r["peak_delta"] for r in rows])) if rows else 0.0,
        "max_abs_rms_delta": float(np.max(np.abs([r["rms_delta"] for r in rows]))) if rows else 0.0,
        "max_abs_peak_delta": float(np.max(np.abs([r["peak_delta"] for r in rows]))) if rows else 0.0,
        "rows": rows,
    }


def build_run(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    run_id: str = DEFAULT_RUN_ID,
    reference_root: Path = DEFAULT_REFERENCE_ROOT,
    port_b0: int = DEFAULT_PORT_B0,
    port_c0: int = DEFAULT_PORT_C0,
) -> Path:
    run_root = output_root.resolve() / validate_identifier(run_id, "run_id")
    if run_root.exists():
        raise FileExistsError(f"run already exists: {run_root}")
    run_root.mkdir(parents=True)
    reference_bundle = run_root / "reference_bundle"
    reference_receipt = build_reference_bundle(reference_bundle, reference_root)
    source_receipt = dict(git_source_receipt(allow_dirty_dev=False))
    source_receipt.update({
        "stage": "AH-SUPRA-REALREF",
        "source_variant": SUPRA_SOURCE_VARIANT,
        "source_sha256": sha256_file(SUPRA_SOURCE_PATH),
        "base_source_sha256": sha256_file(SUPRA_BASE_SOURCE_PATH),
        "multi_reference_source_adjustment": {"edge_scale": 1.4, "hiband_scale": 3.4, "domain": "source_only"},
        "reference_target_sha256": sha256_file(SUPRA_REFERENCE_TARGET_PATH),
        "reference_clip_receipt_sha256": sha256_file(reference_bundle / "reference_clip_receipt.json"),
        "multi_reference_target_sha256": sha256_file(SUPRA_MULTI_REFERENCE_PATH),
        "reference_status": "R3_PUBLIC_RECORDINGS_UNVERIFIED_UNSYNCHRONIZED",
    })
    b0 = build_group(
        run_root=run_root,
        group="B0",
        output_policy=LEGACY_CLIP_V1,
        source_receipt=source_receipt,
        reference_bundle=reference_bundle,
        parent_peaks=None,
        port=port_b0,
    )
    c0 = build_group(
        run_root=run_root,
        group="C0",
        output_policy=LINKED_SOFT_CEILING_V1,
        source_receipt=source_receipt,
        reference_bundle=reference_bundle,
        parent_peaks=b0["parent_peaks"],
        port=port_c0,
    )
    if [r["trace_sha256"] for r in b0["records"]] != [r["trace_sha256"] for r in c0["records"]]:
        raise RuntimeError("SUPRA B0/C0 trace drift")
    if [r["normalization"]["pre_guard_pcm_sha256"] for r in b0["records"]] != [r["normalization"]["pre_guard_pcm_sha256"] for r in c0["records"]]:
        raise RuntimeError("SUPRA B0/C0 pre-guard drift")
    experiment = seal_payload(
        {
            "schema": SUPRA_RUN_SCHEMA,
            "stage": "AH-SUPRA-REALREF",
            "run_id": run_id,
            "source_variant": SUPRA_SOURCE_VARIANT,
            "source_receipt": source_receipt,
            "reference_clip_receipt_sha256": sha256_file(reference_bundle / "reference_clip_receipt.json"),
            "groups": [{key: value for key, value in group.items() if key not in {"records", "parent_peaks", "candidate_hashes", "reference_hashes"}} for group in (b0, c0)],
            "comparisons": {"B0_to_C0": _comparison(b0, c0)},
            "status": "DIAGNOSTIC_READY_FOR_LOCAL_HUMAN_REVIEW",
            "human_status": "WAITING_FOR_JOVI_FEEDBACK",
            "rules": [
                "SUPRA is not an AG-R1 parent and no old package is overwritten.",
                "Reference clips are local R3 public-recording diagnostics with unsynchronized state and unverified rights.",
                "C0 output-policy effects are separated from SUPRA source behavior.",
            ],
        },
        SUPRA_RUN_SCHEMA,
    )
    experiment_path = run_root / "experiment.json"
    _write_json(experiment_path, experiment)
    return experiment_path


def _verify_package(package: Path) -> dict[str, Any]:
    manifest_path = package / "audition_manifest.json"
    manifest = _read_sealed(manifest_path)
    if manifest.get("schema") != SUPRA_PACKAGE_SCHEMA:
        raise ValueError(f"wrong SUPRA package schema: {package}")
    validate_artifacts(manifest["artifacts"], package)
    vehicle = package / SUPRA_VEHICLE
    for scene in manifest["vehicles"][0]["scenes"]:
        candidate = vehicle / f"{scene}.wav"
        if not candidate.is_file():
            raise FileNotFoundError(candidate)
    return manifest


def serve_run(experiment_path: Path, group: str = "C0") -> None:
    experiment = _read_sealed(experiment_path.resolve())
    groups = {entry["group"]: entry for entry in experiment["groups"]}
    selected = [groups["B0"], groups[group]] if group.upper() == "C0" else [groups[group]]
    servers = []
    try:
        for entry in selected:
            package = Path(entry["package"])
            manifest = _verify_package(package)
            if sha256_file(package / "audition_manifest.json") != entry["package_manifest_sha256"]:
                raise ValueError(f"package manifest drift: {package}")
            root = package / SUPRA_VEHICLE
            handler = partial(SimpleHTTPRequestHandler, directory=str(root))
            server = ThreadingHTTPServer(("127.0.0.1", int(manifest["vehicles"][0]["port"])), handler)
            servers.append(server)
            print(f"{entry['group']} http://localhost:{manifest['vehicles'][0]['port']}/")
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
    build = sub.add_parser("build")
    build.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    build.add_argument("--run-id", default=DEFAULT_RUN_ID)
    build.add_argument("--reference-root", type=Path, default=DEFAULT_REFERENCE_ROOT)
    build.add_argument("--port-b0", type=int, default=DEFAULT_PORT_B0)
    build.add_argument("--port-c0", type=int, default=DEFAULT_PORT_C0)
    serve = sub.add_parser("serve")
    serve.add_argument("--experiment", type=Path, required=True)
    serve.add_argument("--group", choices=("B0", "C0"), default="C0")
    args = parser.parse_args(argv)
    if args.command == "build":
        print(build_run(output_root=args.output_root, run_id=args.run_id, reference_root=args.reference_root, port_b0=args.port_b0, port_c0=args.port_c0))
    else:
        serve_run(args.experiment, args.group)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ("build_reference_bundle", "build_run", "serve_run")
