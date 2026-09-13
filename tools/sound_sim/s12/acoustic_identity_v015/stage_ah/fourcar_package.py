"""Build and serve the four-car real-reference AH audition package."""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import re
import shutil
import sys
import threading
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

import numpy as np
from scipy.io import wavfile

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
from ..stage_ag.vehicle_identity_r1 import IDENTITY_MODE_V1R1
from ..stage_ad.engine_sim_acoustics import EngineAcoustics
from .engine import RemediationEngine, input_sha
from .fourcar_pipeline import (
    FOURCAR_TARGET_PATH,
    FOURCAR_VEHICLES,
    FourCarRealReferenceEngine,
    REAL_REFERENCE_BASE_PATHS,
    REAL_REFERENCE_CHANGED_PARAMETERS,
    REAL_REFERENCE_PROFILE_PATHS,
    REAL_REFERENCE_SOURCE_VARIANTS,
    DEFAULT_SEED,
    scene_trace_key,
    load_real_reference_profile,
)
from .output_guard import LINKED_SOFT_CEILING_V1


RUN_SCHEMA = "s12.stage_ah.fourcar.real_reference.experiment_manifest.v2"
PACKAGE_SCHEMA = "s12.stage_ah.fourcar.real_reference.package_manifest.v2"
REPORT_SCHEMA = "s12.stage_ah.fourcar.real_reference.report_manifest.v2"
BINDING_SCHEMA = "s12.stage_ah.fourcar.real_reference.binding.v2"
DEFAULT_RUN_ID = "s12-stage-ah-fourcar-real-reference-20260912-v1"
DEFAULT_OUTPUT_ROOT = Path(r"E:\Tesla_speed\review_packages")
DEFAULT_REFERENCE_ROOT = Path(
    r"E:\Tesla_speed\review_packages\s12-stage-ag-r1-identity-20260908-v1\packages"
    r"\s12-stage-ag-r1-identity-20260908-v1-identity-v1r1"
)
DEFAULT_PORT_C0 = 25380
DEFAULT_PORT_REALREF = 25480
EXPECTED_PARENT_MANIFEST_SHA256 = "3fecb566416d498bcedcb6c1a5267f6c7b36e82e9e9a87af7c2740705f599519"
REFERENCE_GATE_STATUS = "NOT_EVALUATED_UNSYNCHRONIZED_R3"
_LOCK = threading.RLock()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _pcm_sha256(audio: np.ndarray) -> str:
    values = np.asarray(audio)
    if values.dtype != np.int16 or values.ndim != 2 or values.shape[1] != 2:
        raise ValueError("candidate audio must be int16 stereo for PCM hashing")
    return _sha256_bytes(np.ascontiguousarray(values, dtype="<i2").tobytes())


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_sealed(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    checksum = payload.pop("manifest_sha256", None)
    if checksum is None:
        checksum = payload.pop("contract_sha256", None)
        field = "contract_sha256"
    else:
        field = "manifest_sha256"
    if checksum != _sha256_bytes(canonical_json_bytes(payload)):
        raise ValueError(f"sealed receipt mismatch: {path}")
    payload[field] = checksum
    return payload


def _import_dashboards():
    stage_ad = Path(__file__).resolve().parents[1] / "stage_ad"
    sys.path.insert(0, str(stage_ad))
    try:
        from ..stage_ad import build_unified_dashboards as dashboards
    finally:
        sys.path.pop(0)
    return dashboards


def _vehicle_directory(vehicle: str) -> str:
    directory_id = {"ferrari_458": "ferrari-458", "gtr_r35": "gtr-r35"}.get(vehicle, vehicle)
    return f"s12-stage-ad-{directory_id}-closed-loop-v1"


def _reference_files(
    reference_root: Path,
    vehicle: str,
    *,
    expected_reference_sha256: Mapping[str, str] | None = None,
) -> dict[str, dict[str, str]]:
    source_dir = reference_root / _vehicle_directory(vehicle) / "web_audio"
    if not source_dir.is_dir():
        raise FileNotFoundError(f"accepted R1 reference directory missing: {source_dir}")
    files = {path.name: path for path in source_dir.glob("ref_*.wav")}
    if not files:
        raise FileNotFoundError(f"accepted R1 reference WAVs missing: {source_dir}")
    if expected_reference_sha256 is None:
        parent_manifest = _read_sealed(reference_root / "audition_manifest.json")
        entries = {
            str(entry["vehicle"]): entry for entry in parent_manifest.get("vehicles", [])
        }
        expected_reference_sha256 = entries.get(vehicle, {}).get("reference_sha256", {})
    expected = {str(name): str(value).lower() for name, value in expected_reference_sha256.items()}
    if set(files) != set(expected):
        raise ValueError(f"parent reference file set mismatch for {vehicle}")
    result = {}
    for name, path in sorted(files.items()):
        actual = sha256_file(path)
        if actual.lower() != expected[name]:
            raise ValueError(f"parent reference SHA mismatch: {vehicle}/{name}")
        result[name] = {"source_path": str(path.resolve()), "sha256": actual}
    return result


def _embedded_audio_store(path: Path) -> dict[str, bytes]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"const\s+AUDIO_STORE\s*=\s*(\{.*?\});", text, re.S)
    if match is None:
        raise ValueError(f"dashboard audio store missing: {path}")
    payload = json.loads(match.group(1))
    result = {}
    for key, data_uri in payload.items():
        if not isinstance(data_uri, str) or not data_uri.startswith("data:audio/wav;base64,"):
            raise ValueError(f"invalid embedded audio entry: {path}::{key}")
        result[str(key)] = base64.b64decode(data_uri.split(",", 1)[1], validate=True)
    return result


def _validate_parent_package(reference_root: Path) -> dict[str, Any]:
    """Validate the locked parent bytes before any new copy is adopted."""
    reference_root = reference_root.resolve()
    manifest_path = reference_root / "audition_manifest.json"
    manifest = _read_sealed(manifest_path)
    if sha256_file(manifest_path).lower() != EXPECTED_PARENT_MANIFEST_SHA256:
        raise ValueError("accepted R1 parent manifest SHA drift")
    validate_artifacts(manifest.get("artifacts", []), reference_root)
    entries = {str(entry["vehicle"]): entry for entry in manifest.get("vehicles", [])}
    if set(entries) != set(FOURCAR_VEHICLES):
        raise ValueError("accepted R1 parent must contain exactly four vehicles")
    for vehicle in FOURCAR_VEHICLES:
        entry = entries[vehicle]
        root = reference_root / str(entry["directory"])
        refs = _reference_files(reference_root, vehicle, expected_reference_sha256=entry["reference_sha256"])
        for name, details in refs.items():
            if sha256_file(root / "web_audio" / name) != details["sha256"]:
                raise ValueError(f"parent Reference binding drift: {vehicle}/{name}")
        contract_path = root / "dashboard_contract.json"
        binding_path = root / "stage_ag_binding.json"
        contract = _read_sealed(contract_path)
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
        if binding.get("contract_sha256") != contract.get("contract_sha256"):
            raise ValueError(f"parent binding contract drift: {vehicle}")
        identity = contract.get("renderer_identity", {})
        ir_path = Path(str(identity.get("ir_source_path", "")))
        ir_sha = str(identity.get("ir_source_sha256", "")).lower()
        if not ir_path.is_file() or sha256_file(ir_path).lower() != ir_sha:
            raise ValueError(f"parent IR source binding drift: {vehicle}")
        effective = _sha256_bytes(
            np.ascontiguousarray(
                EngineAcoustics(vehicle_type=vehicle, sr=48_000).ir,
                dtype="<f8",
            ).tobytes()
        )
        if effective != str(identity.get("ir_effective_sha256", "")).lower():
            raise ValueError(f"parent effective IR binding drift: {vehicle}")
        audio_store = _embedded_audio_store(root / "index.html")
        for scene in entry.get("scenes", []):
            filename = str(scene["candidate_file"])
            key = str(scene["scene_id"]) + "_candidate"
            candidate_path = root / "web_audio" / filename
            if key not in audio_store or audio_store[key] != candidate_path.read_bytes():
                raise ValueError(f"parent embedded candidate bytes drift: {vehicle}/{filename}")
            ref_name = scene.get("reference_file")
            if ref_name:
                ref_key = str(scene["scene_id"]) + "_ref"
                ref_path = root / "web_audio" / str(ref_name)
                if ref_key not in audio_store or audio_store[ref_key] != ref_path.read_bytes():
                    raise ValueError(f"parent embedded Reference bytes drift: {vehicle}/{ref_name}")
    return manifest


def _source_receipt() -> dict[str, Any]:
    receipt = dict(git_source_receipt(allow_dirty_dev=False))
    target_payload = json.loads(FOURCAR_TARGET_PATH.read_text(encoding="utf-8"))
    paths = [
        Path(__file__),
        FOURCAR_TARGET_PATH,
        Path(__file__).with_name("fourcar_pipeline.py"),
        Path(__file__).with_name("engine.py"),
        Path(__file__).with_name("source_policy.py"),
        Path(__file__).resolve().parents[1] / "render_identity_v02.py",
        Path(__file__).resolve().parents[1] / "stage_ad" / "build_unified_dashboards.py",
        Path(__file__).resolve().parents[1] / "stage_ad" / "audition_dashboard_template.html",
        Path(__file__).resolve().parents[1] / "stage_ag" / "vehicle_identity_r1.py",
        Path(__file__).resolve().parents[1] / "stage_ag" / "vehicle_identity.py",
        *REAL_REFERENCE_PROFILE_PATHS.values(),
        *REAL_REFERENCE_BASE_PATHS.values(),
        Path(__file__).resolve().parents[1] / "stage_g" / "render_candidate.py",
        Path(__file__).resolve().parents[1] / "stage_k" / "render_candidate.py",
    ]
    receipt["fourcar_real_reference_fingerprint"] = [
        {
            "path": path.resolve().relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": sha256_file(path),
        }
        for path in sorted(set(paths))
    ]
    receipt.update(
        {
            "stage": "AH-FOURCAR-REALREF",
            "identity_mode": IDENTITY_MODE_V1R1,
            "output_policy": LINKED_SOFT_CEILING_V1,
            "seed": DEFAULT_SEED,
            "flags": [],
            "source_recipe_schema": "s12.stage_ah.fourcar.source_recipe.v2",
            "source_status": "SOURCE_CLEAN",
            "promotable": False,
            "promotion_status": "NOT_PROMOTABLE_R3_UNSYNCED_PUBLIC_RECORDINGS",
            "reference_target_sha256": sha256_file(FOURCAR_TARGET_PATH),
            "real_reference_sources": {
                vehicle: [
                    {
                        "id": source["id"],
                        "source_url": source["source_url"],
                        "wav_sha256": source["wav_sha256"],
                        "role": source["role"],
                        "evidence_level": source["evidence_level"],
                        "rights_status": source["rights_status"],
                        "synchronization": source["synchronization"],
                    }
                    for source in target_payload["vehicles"][vehicle]["sources"]
                ]
                for vehicle in FOURCAR_VEHICLES
            },
            "real_reference_target_metrics": {
                vehicle: target_payload["vehicles"][vehicle]["target_metrics"]
                for vehicle in FOURCAR_VEHICLES
            },
        }
    )
    return receipt


def _contract(
    *,
    package_id: str,
    group: str,
    vehicle: str,
    cfg: Mapping[str, Any],
    source_receipt: Mapping[str, Any],
    reference_sources: Mapping[str, Mapping[str, str]],
    candidate_hashes: Mapping[str, str],
    candidate_pcm_hashes: Mapping[str, str] | None = None,
    records: list[Mapping[str, Any]],
    profile_metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    reference_bindings = {
        filename: {
            "available": True,
            "fit_required": False,
            "source_label": "AG-R1 accepted Reference bytes",
            "sha256": details["sha256"],
            "source_path": details["source_path"],
            "evidence_level": "R1_PARENT_REFERENCE_COPY",
        }
        for filename, details in reference_sources.items()
    }

    params: list[dict[str, Any]] = []
    if profile_metadata:
        params.append(
            {
                "group": "Source",
                "key": profile_metadata["changed_source_parameter"],
                "name": "source-scoped profile adjustment",
                "base": float(profile_metadata["base_value"]),
                "final": float(profile_metadata["candidate_value"]),
                "delta": (
                    (float(profile_metadata["candidate_value"]) / float(profile_metadata["base_value"]) - 1.0)
                    * 100.0
                ),
                "desc": "One fixed source-profile value applied only to the named engine stem.",
                "scope": profile_metadata.get("active_source_stem", "UNSPECIFIED_SOURCE_STEM"),
                "unit": "profile-defined",
                "basis": "five public recordings; primary-three median used for one bounded change",
            }
        )
    return {
        "schema": "s12.stage_af.dashboard_contract.v1",
        "package_id": package_id,
        "candidate_id": f"AH-FOURCAR-REALREF-{group}",
        "vehicle": vehicle,
        "group": group,
        "flags": [],
        "seed": DEFAULT_SEED,
        "identity_mode": IDENTITY_MODE_V1R1,
        "source_variant": (
            REAL_REFERENCE_SOURCE_VARIANTS[vehicle]
            if profile_metadata
            else "r1_baseline"
        ),
        "output_policy": LINKED_SOFT_CEILING_V1,
        "output_policy_config": {
            "policy_id": LINKED_SOFT_CEILING_V1,
            "knee_linear": 0.90,
            "ceiling_linear": 0.94,
            "stereo_link": "instantaneous_frame_peak_common_gain",
            "parent_denominator_policy": "fixed_parent_peak_from_ah_r1_control",
            "quantization_order": "linked_guard_then_int16_then_identity",
        },
        "output_guard_receipt_schema": "s12.stage_ah.output_guard_receipt.v2",
        "fit_status": "NOT_FITTED",
        "fit_metric_status": "R3_RELATIVE_CUES_ONLY",
        "measurement_status": "R3_PUBLIC_RECORDINGS_UNSYNCED",
        "human_status": "WAITING_FOR_JOVI_FEEDBACK",
        "sample_rate_hz": 48_000,
        "package_port": int(cfg["port"]),
        "nav_urls": {
            item: f"http://localhost:{int(cfg.get('_nav_ports', {}).get(item, 0))}/"
            for item in FOURCAR_VEHICLES
        },
        "source_status": "SOURCE_CLEAN",
        "promotable": False,
        "promotion_status": "NOT_PROMOTABLE_R3_UNSYNCED_PUBLIC_RECORDINGS",
        "self_contained_status": "AUDIO_SELF_CONTAINED / STYLE_NETWORK_DEPENDENCY",
        "references": reference_bindings,
        "candidate_wav_sha256": dict(candidate_hashes),
        "candidate_pcm_sha256": dict(candidate_pcm_hashes or {}),
        "reference_sha256": {name: item["sha256"] for name, item in reference_sources.items()},
        "parameters": params,
        "source_receipt": dict(source_receipt),
        "records": [
            {
                "scene": record.get("scene"),
                "source_variant": record.get("source_variant"),
                "output_policy": record.get("output_policy"),
                "final_peak": record.get("final_peak"),
                "final_rms": record.get("final_rms"),
                "normalization_denominator": record.get("normalization_denominator"),
                "trace_sha256": record.get("trace_sha256"),
                "sample_rate_hz": record.get("sample_rate_hz"),
                "sample_count": record.get("sample_count"),
                "seed": record.get("seed"),
                "flags": record.get("flags", []),
                "candidate_pcm_sha256": record.get("final_pcm_sha256", record.get("candidate_pcm_sha256")),
                "wav_file_sha256": record.get("wav_file_sha256"),
                "post_identity_clip_count": record.get("post_identity_clip_count", 0),
            }
            for record in records
        ],
    }


def _reference_gate(rows: list[Mapping[str, Any]], *, evidence_level: str) -> dict[str, Any]:
    """Keep unsynchronised public cues explicit instead of treating them as zero rows."""
    if "UNSYNC" in str(evidence_level).upper() or not rows:
        return {
            "status": REFERENCE_GATE_STATUS,
            "evidence_level": str(evidence_level),
            "rows": len(rows),
            "evaluated_rows": 0,
            "regressions": None,
            "missing": 0,
            "unknown_reason": "public recordings have no shared RPM/load/microphone synchronization",
        }
    regressions = sum(
        1 for row in rows if str(row.get("guard_3pct", "")) == "REGRESSION_GT_3PCT"
    )
    return {
        "status": "EVALUATED_RELATIVE_REFERENCE",
        "evidence_level": str(evidence_level),
        "rows": len(rows),
        "evaluated_rows": len(rows),
        "regressions": regressions,
        "missing": 0,
    }


def _numeric_gate(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    failures: list[str] = []
    finite = True
    post_guard = emergency = post_identity = 0
    for record in records:
        for key in ("final_peak", "final_rms", "parent_peak", "candidate_raw_peak"):
            value = record.get(key)
            if value is None or not np.isfinite(float(value)):
                finite = False
                failures.append(f"{record.get('vehicle')}/{record.get('scene')}:nonfinite:{key}")
        normalization = record.get("normalization", {})
        post_guard += int(normalization.get("post_guard_ceiling_exceedance_samples", 0))
        emergency += int(normalization.get("emergency_clip_count", 0))
        post_identity += int(record.get("post_identity_clip_count", 0))
    if not finite:
        failures.append("nonfinite")
    if post_guard:
        failures.append("post_guard_ceiling_exceedance")
    if emergency:
        failures.append("emergency_clip")
    if post_identity:
        failures.append("post_identity_clip")
    return {
        "status": "PASS" if not failures else "FAIL",
        "finite": finite,
        "post_guard_ceiling_exceedance_samples": post_guard,
        "emergency_clip_count": emergency,
        "post_identity_clip_count": post_identity,
        "failures": failures,
    }


def _prepare_configs(dashboards, group: str, ports: Mapping[str, int], roots: Mapping[str, Path]):
    configs = copy.deepcopy(dashboards.VEHICLE_CONFIGS)
    for vehicle in FOURCAR_VEHICLES:
        cfg = configs[vehicle]
        cfg["dir"] = roots[vehicle]
        cfg["port"] = int(ports[vehicle])
        cfg["ref_source"] = "AG-R1 accepted Reference bytes; five public recordings inform candidate only"
        cfg["title"] = f"[AH-FOURCAR-REALREF · {group}] " + cfg["title"]
        cfg["subtitle"] = (
            f"AH-FOURCAR-REALREF / {group} / output_policy={LINKED_SOFT_CEILING_V1} / "
            "A=当前候选，B=AG-R1原字节Reference · " + cfg["subtitle"]
        )
        cfg["_nav_ports"] = dict(ports)
        cfg["_nav_vehicles"] = FOURCAR_VEHICLES
    return configs


def _build_group(
    *,
    run_root: Path,
    group: str,
    source_receipt: Mapping[str, Any],
    reference_root: Path,
    ports: Mapping[str, int],
    profiles: Mapping[str, Any] | None,
    profile_metadata: Mapping[str, Mapping[str, Any]] | None,
    parent_peaks: Mapping[str, Mapping[str, float]] | None,
    run_label: str | None = None,
) -> dict[str, Any]:
    group_root = run_root / "packages" / validate_identifier(
        f"ah-fourcar-realref-{run_label or run_root.name}-{group.lower()}", "package_id"
    )
    if group_root.exists():
        raise FileExistsError(group_root)
    group_root.mkdir(parents=True)
    dashboards = _import_dashboards()
    previous_configs = dashboards.VEHICLE_CONFIGS
    previous_template = dashboards.TEMPLATE_PATH
    previous_engine = dashboards.EngineAcoustics
    roots = {
        vehicle: group_root / _vehicle_directory(vehicle)
        for vehicle in FOURCAR_VEHICLES
    }
    configs = _prepare_configs(dashboards, group, ports, roots)
    dashboards.VEHICLE_CONFIGS = configs
    dashboards.TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "stage_ad" / "audition_dashboard_template.html"
    records_by_vehicle: dict[str, list[dict[str, Any]]] = {}
    pcm_hashes_by_vehicle: dict[str, dict[str, str]] = {}
    references_by_vehicle: dict[str, dict[str, dict[str, str]]] = {}
    holders: dict[str, Any] = {}
    vehicle_entries: list[dict[str, Any]] = []

    class Factory:
        def __new__(cls, vehicle_type: str = "ferrari_458", sr: int = 48_000):
            if profiles is None:
                engine = RemediationEngine(
                    vehicle_type,
                    sr=sr,
                    identity_mode=IDENTITY_MODE_V1R1,
                    seed=DEFAULT_SEED,
                    variant="r1_baseline",
                    output_policy=LINKED_SOFT_CEILING_V1,
                    collect=True,
                )
            else:
                engine = FourCarRealReferenceEngine(
                    vehicle_type,
                    profiles[vehicle_type],
                    sr=sr,
                    output_policy=LINKED_SOFT_CEILING_V1,
                    parent_peaks=(parent_peaks or {}).get(vehicle_type),
                    seed=DEFAULT_SEED,
                )
            holders[vehicle_type] = engine
            return engine

    dashboards.EngineAcoustics = Factory
    try:
        for vehicle in FOURCAR_VEHICLES:
            cfg = configs[vehicle]
            cfg["dir"].mkdir(parents=True, exist_ok=False)
            web_dir = cfg["dir"] / "web_audio"
            web_dir.mkdir(parents=True, exist_ok=False)
            parent_entries = {
                str(entry["vehicle"]): entry
                for entry in _read_sealed(reference_root / "audition_manifest.json")["vehicles"]
            }
            refs = _reference_files(
                reference_root,
                vehicle,
                expected_reference_sha256=parent_entries[vehicle]["reference_sha256"],
            )
            references_by_vehicle[vehicle] = refs
            for filename, details in refs.items():
                shutil.copy2(details["source_path"], web_dir / filename)
            records: list[dict[str, Any]] = []

            def before_render(**payload):
                engine = holders[vehicle]
                trace = input_sha(
                    payload["rpm"],
                    payload["throttle"],
                    payload["duration"],
                    [payload["shift_events"], payload["afterfire_events"], payload["bov_events"]],
                )
                setter = getattr(engine, "set_scene_context", None)
                if callable(setter):
                    setter(payload["scene_id"], trace)

            def after_render(**payload):
                engine = holders[vehicle]
                report = copy.deepcopy(payload.get("report"))
                if not isinstance(report, dict) or not report:
                    report = copy.deepcopy(getattr(engine, "last_report", None))
                if not isinstance(report, dict) or not report:
                    raise RuntimeError(f"renderer did not expose a report for {vehicle}/{payload['scene_id']}")
                trace = input_sha(
                    payload["rpm"],
                    payload["throttle"],
                    payload["duration"],
                    [payload["shift_events"], payload["afterfire_events"], payload["bov_events"]],
                )
                report.update(
                    {
                        "scene": payload["scene_id"],
                        "scene_id": payload["scene_id"],
                        "trace_sha256": trace,
                        "sample_rate_hz": int(getattr(engine, "sr", 48_000)),
                        "sample_count": int(len(payload["audio"])),
                        "seed": int(getattr(engine, "seed", DEFAULT_SEED)),
                        "flags": list(getattr(engine, "numerical_fixes", ())),
                        "candidate_pcm_sha256": _pcm_sha256(payload["audio"]),
                        "final_pcm_sha256": _pcm_sha256(payload["audio"]),
                        "final_peak": float(np.max(np.abs(payload["audio"])) / 32767.0),
                        "final_rms": float(
                            np.sqrt(np.mean((np.asarray(payload["audio"], dtype=np.float64) / 32767.0) ** 2))
                        ),
                        "wav_file_sha256": sha256_file(
                            cfg["dir"] / "web_audio" / f"{payload['scene_id']}.wav"
                        ),
                    }
                )
                runtime = getattr(engine, "base", engine)
                if hasattr(runtime, "ir"):
                    report["ir_effective_sha256"] = _sha256_bytes(
                        np.ascontiguousarray(runtime.ir, dtype="<f8").tobytes()
                    )
                records.append(report)

            cfg["_render_context_observer"] = before_render
            cfg["_render_observer"] = after_render
            dashboards.render_vehicle_audio(vehicle, cfg)
            expected_scene_ids = [scene["id"] for scene in cfg["scenes"]]
            if [record.get("scene_id") for record in records] != expected_scene_ids:
                raise RuntimeError(f"renderer report count/order mismatch for {vehicle}")
            records_by_vehicle[vehicle] = records
            candidate_hashes = {
                scene["candidate_file"]: sha256_file(cfg["dir"] / "web_audio" / scene["candidate_file"])
                for scene in cfg["scenes"]
            }
            pcm_hashes = {
                str(record["scene_id"]) + ".wav": str(record["candidate_pcm_sha256"])
                for record in records
            }
            pcm_hashes_by_vehicle[vehicle] = pcm_hashes
            contract = _contract(
                package_id=group_root.name,
                group=group,
                vehicle=vehicle,
                cfg=cfg,
                source_receipt=source_receipt,
                reference_sources=refs,
                candidate_hashes=candidate_hashes,
                candidate_pcm_hashes=pcm_hashes,
                records=records,
                profile_metadata=(profile_metadata or {}).get(vehicle),
            )
            cfg["_dashboard_contract"] = seal_payload(contract, "s12.stage_af.dashboard_contract.v1")
            cfg["_dashboard_params"] = contract["parameters"]
            dashboards.build_dashboard(vehicle, cfg)
            for page in (cfg["dir"] / "index.html", cfg["dir"] / "index_standalone.html"):
                page.write_text(
                    page.read_text(encoding="utf-8")
                    .replace("B: 真车参考实录 (R3)", "B: AG-R1 真车Reference（原字节）")
                    .replace("B: 真车参考实录 (R3 Reference)", "B: AG-R1 真车Reference（原字节）"),
                    encoding="utf-8",
                )
            _write_json(cfg["dir"] / "dashboard_contract.json", cfg["_dashboard_contract"])
            binding = seal_payload(
                {
                    "schema": BINDING_SCHEMA,
                    "package_id": group_root.name,
                    "candidate_id": f"AH-FOURCAR-REALREF-{group}",
                    "vehicle": vehicle,
                    "group": group,
                    "source_variant": contract["source_variant"],
                    "output_policy": LINKED_SOFT_CEILING_V1,
                    "identity_mode": IDENTITY_MODE_V1R1,
                    "reference_sources": refs,
                    "source_receipt": dict(source_receipt),
                    "records": records,
                },
                BINDING_SCHEMA,
            )
            _write_json(cfg["dir"] / "stage_ah_fourcar_binding.json", binding)
            artifacts = [
                artifact_record(path, group_root, f"fourcar:{vehicle}:{path.relative_to(cfg['dir']).as_posix()}")
                for path in sorted(cfg["dir"].rglob("*"))
                if path.is_file()
            ]
            vehicle_entries.append(
                {
                    "vehicle": vehicle,
                    "directory": _vehicle_directory(vehicle),
                    "port": int(cfg["port"]),
                    "source_variant": contract["source_variant"],
                    "candidate_sha256": candidate_hashes,
                    "candidate_pcm_sha256": pcm_hashes,
                    "reference_sha256": {name: item["sha256"] for name, item in refs.items()},
                    "scenes": [
                        {
                            "scene_id": scene["id"],
                            "candidate_file": scene["candidate_file"],
                            "reference_file": scene.get("ref_file") or None,
                        }
                        for scene in cfg["scenes"]
                    ],
                }
            )
        all_artifacts = [
            artifact_record(path, group_root, f"package:{path.relative_to(group_root).as_posix()}")
            for path in sorted(group_root.rglob("*"))
            if path.is_file() and path.name != "audition_manifest.json"
        ]
        flat_records = [
            dict(record, vehicle=vehicle)
            for vehicle, records in records_by_vehicle.items()
            for record in records
        ]
        numeric_gate = _numeric_gate(flat_records)
        group_status = (
            "READY_FOR_HUMAN_REVIEW_REFERENCE_NOT_EVALUATED"
            if numeric_gate["status"] == "PASS"
            else "FAILED_NUMERIC_GATE"
        )
        manifest_path = group_root / "audition_manifest.json"
        manifest = seal_payload(
            {
                "schema": PACKAGE_SCHEMA,
                "stage": "AH-FOURCAR-REALREF",
                "package_id": group_root.name,
                "candidate_id": f"AH-FOURCAR-REALREF-{group}",
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "group": group,
                "identity_mode": IDENTITY_MODE_V1R1,
                "source_variant": (
                    "r1_baseline"
                    if profiles is None
                    else "four_vehicle_source_profiles_real_reference_stem_scoped_v2"
                ),
                "output_policy": LINKED_SOFT_CEILING_V1,
                "output_policy_config": {
                    "policy_id": LINKED_SOFT_CEILING_V1,
                    "knee_linear": 0.90,
                    "ceiling_linear": 0.94,
                    "stereo_link": "instantaneous_frame_peak_common_gain",
                    "parent_denominator_policy": "fixed_parent_peak_from_ah_r1_control",
                    "quantization_order": "linked_guard_then_int16_then_identity",
                },
                "output_guard_receipt_schema": "s12.stage_ah.output_guard_receipt.v2",
                "source_receipt": dict(source_receipt),
                "reference_evidence_level": "R1_PARENT_REFERENCE_COPY_PLUS_R3_RELATIVE_CUES",
                "numeric_gate": numeric_gate,
                "human_status": "WAITING_FOR_JOVI_FEEDBACK",
                "promotable": False,
                "vehicles": vehicle_entries,
                "artifacts": all_artifacts,
                "rules": [
                    "The accepted AG-R1 Reference bytes are copied without modification.",
                    "Five public recordings remain R3 relative cues with no RPM/mic/AGC synchronization.",
                    "This package makes no Human PASS, OEM reproduction or profile-freeze claim.",
                ],
            },
            PACKAGE_SCHEMA,
        )
        _write_json(manifest_path, manifest)
        validate_artifacts(all_artifacts, group_root)
        report = {
            "schema": REPORT_SCHEMA,
            "group": group,
            "package": str(group_root),
            "package_manifest_sha256": sha256_file(manifest_path),
            "source_receipt": dict(source_receipt),
            "reference_sources": references_by_vehicle,
            "records": flat_records,
            "status": group_status,
            "human_status": "WAITING_FOR_JOVI_FEEDBACK",
            "numeric_gate": numeric_gate,
            "reference_gate": _reference_gate(
                [], evidence_level="R3_PUBLIC_RECORDINGS_UNSYNCED"
            ),
        }
        report_path = run_root / f"{group.lower()}_report.json"
        _write_json(report_path, seal_payload(report, REPORT_SCHEMA))
        return {
            "group": group,
            "package": str(group_root),
            "package_manifest_sha256": sha256_file(manifest_path),
            "report": str(report_path),
            "report_sha256": sha256_file(report_path),
            "records": flat_records,
            "parent_peaks": {
                vehicle: {
                    scene_trace_key(
                        str(record["scene_id"]),
                        str(record["trace_sha256"]),
                    ): float(record.get("parent_peak", record.get("normalization_denominator", 0.0)))
                    for record in records_by_vehicle[vehicle]
                }
                for vehicle in FOURCAR_VEHICLES
            },
            "status": group_status,
        }
    finally:
        dashboards.VEHICLE_CONFIGS = previous_configs
        dashboards.TEMPLATE_PATH = previous_template
        dashboards.EngineAcoustics = previous_engine


def _comparison(control: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    by_key = {
        (record["vehicle"], record["scene"]): record
        for record in control["records"]
    }
    rows = []
    for right in candidate["records"]:
        left = by_key[(right["vehicle"], right["scene"])]
        rows.append(
            {
                "vehicle": right["vehicle"],
                "scene": right["scene"],
                "comparison_type": "SOURCE_LOCAL_REAL_REFERENCE_ADJUSTMENT",
                "parent_denominator_equal": bool(
                    np.isclose(
                        float(left.get("parent_peak", left.get("normalization_denominator", 0.0))),
                        float(right.get("parent_peak", right.get("normalization_denominator", 0.0))),
                    )
                ),
                "trace_equal": left.get("trace_sha256") == right.get("trace_sha256"),
                "seed_equal": left.get("seed") == right.get("seed"),
                "flags_equal": left.get("flags", []) == right.get("flags", []),
                "control_final_pcm_sha256": left.get("candidate_pcm_sha256"),
                "candidate_final_pcm_sha256": right.get("final_pcm_sha256"),
                "rms_delta": float(right.get("final_rms", 0.0) - left.get("final_rms", 0.0)),
                "peak_delta": float(right.get("final_peak", 0.0) - left.get("final_peak", 0.0)),
            }
        )
    return {
        "record_count": len(rows),
        "parent_denominator_equal_count": sum(row["parent_denominator_equal"] for row in rows),
        "rows": rows,
    }


def _replace_paths(value: Any, old: str, new: str) -> Any:
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, list):
        return [_replace_paths(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: _replace_paths(item, old, new) for key, item in value.items()}
    return value


def build_run(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    run_id: str = DEFAULT_RUN_ID,
    reference_root: Path = DEFAULT_REFERENCE_ROOT,
    port_c0: int = DEFAULT_PORT_C0,
    port_realref: int = DEFAULT_PORT_REALREF,
) -> Path:
    output_root = output_root.resolve()
    final_root = output_root / validate_identifier(run_id, "run_id")
    if final_root.exists():
        raise FileExistsError(final_root)
    staging_root = output_root / ".staging" / f"{run_id}-{uuid4().hex}"
    staging_root.mkdir(parents=True)
    source_receipt = _source_receipt()
    parent_manifest = reference_root.resolve() / "audition_manifest.json"
    try:
        if not parent_manifest.is_file():
            raise FileNotFoundError(f"accepted R1 parent manifest missing: {parent_manifest}")
        parent_manifest_sha256 = sha256_file(parent_manifest)
        if parent_manifest_sha256.lower() != EXPECTED_PARENT_MANIFEST_SHA256:
            raise ValueError("accepted R1 parent manifest SHA drift")
        _validate_parent_package(reference_root.resolve())
        source_receipt["accepted_r1_parent_manifest_sha256"] = parent_manifest_sha256
        source_receipt["accepted_r1_parent_manifest_path"] = str(parent_manifest)
        profiles: dict[str, Any] = {}
        profile_metadata: dict[str, Mapping[str, Any]] = {}
        for vehicle in FOURCAR_VEHICLES:
            profiles[vehicle], profile_metadata[vehicle] = load_real_reference_profile(vehicle)
        shutil.copy2(FOURCAR_TARGET_PATH, staging_root / FOURCAR_TARGET_PATH.name)
        with _LOCK:
            c0 = _build_group(
                run_root=staging_root,
                run_label=run_id,
                group="C0",
                source_receipt=source_receipt,
                reference_root=reference_root.resolve(),
                ports={vehicle: int(port_c0) + index for index, vehicle in enumerate(FOURCAR_VEHICLES)},
                profiles=None,
                profile_metadata=None,
                parent_peaks=None,
            )
            realref = _build_group(
                run_root=staging_root,
                run_label=run_id,
                group="REALREF",
                source_receipt=source_receipt,
                reference_root=reference_root.resolve(),
                ports={vehicle: int(port_realref) + index for index, vehicle in enumerate(FOURCAR_VEHICLES)},
                profiles=profiles,
                profile_metadata=profile_metadata,
                parent_peaks=c0["parent_peaks"],
            )
        experiment = seal_payload(
            {
                "schema": RUN_SCHEMA,
                "stage": "AH-FOURCAR-REALREF",
                "run_id": run_id,
                "source_receipt": source_receipt,
                "reference_target": {
                    "path": str((staging_root / FOURCAR_TARGET_PATH.name).resolve()),
                    "sha256": sha256_file(staging_root / FOURCAR_TARGET_PATH.name),
                },
                "groups": [
                    {key: value for key, value in c0.items() if key not in {"records", "parent_peaks"}},
                    {key: value for key, value in realref.items() if key not in {"records", "parent_peaks"}},
                ],
                "comparisons": {"C0_to_REALREF": _comparison(c0, realref)},
                "status": "DIAGNOSTIC_READY_FOR_LOCAL_HUMAN_REVIEW",
                "human_status": "WAITING_FOR_JOVI_FEEDBACK",
                "rules": [
                    "C0 is the current AH/R1 linked-soft-ceiling control.",
                    "REALREF applies one fixed named source recipe per vehicle and reuses C0 parent denominators.",
                    "Reference bytes are copied from the accepted AG-R1 parent without modification.",
                    "Five public recordings per vehicle are diagnostic relative cues only.",
                ],
            },
            RUN_SCHEMA,
        )
        experiment_path = staging_root / "experiment.json"
        _write_json(experiment_path, experiment)
        for group in experiment["groups"]:
            _verify_group(group)
        staging_root.replace(final_root)
        old = str(staging_root)
        new = str(final_root)
        for report_name in ("c0_report.json", "realref_report.json"):
            report_path = final_root / report_name
            report = _replace_paths(json.loads(report_path.read_text(encoding="utf-8")), old, new)
            _write_json(report_path, seal_payload(report, REPORT_SCHEMA))
        final_experiment = _replace_paths(
            json.loads((final_root / "experiment.json").read_text(encoding="utf-8")), old, new
        )
        _write_json(final_root / "experiment.json", seal_payload(final_experiment, RUN_SCHEMA))
        for group in final_experiment["groups"]:
            _verify_group(group)
        return final_root / "experiment.json"
    except Exception as exc:
        try:
            _write_json(
                staging_root / "FAIL.json",
                {
                    "status": "FAIL",
                    "run_id": run_id,
                    "error": f"{type(exc).__name__}: {exc}",
                    "source_head": source_receipt.get("git_head"),
                },
            )
        except Exception:
            pass
        raise


def _verify_group(entry: Mapping[str, Any]) -> dict[str, Any]:
    package = Path(entry["package"])
    manifest_path = package / "audition_manifest.json"
    manifest = _read_sealed(manifest_path)
    if manifest.get("schema") != PACKAGE_SCHEMA:
        raise ValueError(f"wrong package schema: {package}")
    validate_artifacts(manifest["artifacts"], package)
    if sha256_file(manifest_path) != entry["package_manifest_sha256"]:
        raise ValueError(f"package manifest drift: {package}")
    if manifest.get("numeric_gate", {}).get("status") != "PASS":
        raise ValueError(f"numeric gate is not qualified: {package}")
    for vehicle in manifest.get("vehicles", []):
        root = package / str(vehicle["directory"])
        contract = _read_sealed(root / "dashboard_contract.json")
        binding = _read_sealed(root / "stage_ah_fourcar_binding.json")
        if contract.get("source_variant") != vehicle.get("source_variant"):
            raise ValueError(f"source variant binding mismatch: {root}")
        if binding.get("source_variant") != contract.get("source_variant"):
            raise ValueError(f"source binding mismatch: {root}")
        if contract.get("candidate_wav_sha256") != vehicle.get("candidate_sha256"):
            raise ValueError(f"candidate WAV SHA map mismatch: {root}")
        if contract.get("candidate_pcm_sha256") != vehicle.get("candidate_pcm_sha256"):
            raise ValueError(f"candidate PCM SHA map mismatch: {root}")
        audio_store = _embedded_audio_store(root / "index.html")
        for scene in vehicle.get("scenes", []):
            candidate_name = str(scene["candidate_file"])
            candidate_key = str(scene["scene_id"]) + "_candidate"
            candidate_path = root / "web_audio" / candidate_name
            if sha256_file(candidate_path) != vehicle["candidate_sha256"][candidate_name]:
                raise ValueError(f"candidate WAV SHA mismatch: {root}/{candidate_name}")
            _, candidate_pcm = wavfile.read(candidate_path)
            if _pcm_sha256(np.asarray(candidate_pcm)) != vehicle["candidate_pcm_sha256"][candidate_name]:
                raise ValueError(f"candidate PCM SHA mismatch: {root}/{candidate_name}")
            if audio_store.get(candidate_key) != candidate_path.read_bytes():
                raise ValueError(f"embedded candidate bytes mismatch: {root}/{candidate_name}")
            ref_name = scene.get("reference_file")
            if ref_name:
                ref_path = root / "web_audio" / str(ref_name)
                ref_key = str(scene["scene_id"]) + "_ref"
                if audio_store.get(ref_key) != ref_path.read_bytes():
                    raise ValueError(f"embedded Reference bytes mismatch: {root}/{ref_name}")
    return manifest


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


def serve_run(experiment_path: Path, group: str = "REALREF") -> None:
    experiment = _read_sealed(experiment_path.resolve())
    groups = {entry["group"]: entry for entry in experiment["groups"]}
    selected = groups.get(group.upper())
    if selected is None:
        raise ValueError(f"unknown group: {group}")
    manifest = _verify_group(selected)
    servers = []
    started = []
    try:
        for vehicle in manifest["vehicles"]:
            package = Path(selected["package"])
            root = package / vehicle["directory"]
            handler = partial(NoCacheHandler, directory=str(root))
            server = ThreadingHTTPServer(("127.0.0.1", int(vehicle["port"])), handler)
            servers.append(server)
            print(f"{vehicle['vehicle']} http://localhost:{vehicle['port']}/")
        threads = []
        for server in servers:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            started.append(server)
            threads.append(thread)
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        for server in started:
            server.shutdown()
        for server in servers:
            server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    build.add_argument("--run-id", default=DEFAULT_RUN_ID)
    build.add_argument("--reference-root", type=Path, default=DEFAULT_REFERENCE_ROOT)
    build.add_argument("--port-c0", type=int, default=DEFAULT_PORT_C0)
    build.add_argument("--port-realref", type=int, default=DEFAULT_PORT_REALREF)
    serve = sub.add_parser("serve")
    serve.add_argument("--experiment", type=Path, required=True)
    serve.add_argument("--group", choices=("C0", "REALREF"), default="REALREF")
    args = parser.parse_args(argv)
    if args.command == "build":
        print(
            build_run(
                output_root=args.output_root,
                run_id=args.run_id,
                reference_root=args.reference_root,
                port_c0=args.port_c0,
                port_realref=args.port_realref,
            )
        )
    else:
        serve_run(args.experiment, args.group)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ("build_run", "serve_run")
