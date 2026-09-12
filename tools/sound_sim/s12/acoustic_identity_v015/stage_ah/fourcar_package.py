"""Build and serve the four-car real-reference AH audition package."""
from __future__ import annotations

import argparse
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
from .engine import RemediationEngine
from .fourcar_pipeline import (
    FOURCAR_TARGET_PATH,
    FOURCAR_VEHICLES,
    FourCarRealReferenceEngine,
    REAL_REFERENCE_BASE_PATHS,
    REAL_REFERENCE_CHANGED_PARAMETERS,
    REAL_REFERENCE_PROFILE_PATHS,
    REAL_REFERENCE_SOURCE_VARIANTS,
    load_real_reference_profile,
)
from .output_guard import LINKED_SOFT_CEILING_V1


RUN_SCHEMA = "s12.stage_ah.fourcar.real_reference.experiment_manifest.v1"
PACKAGE_SCHEMA = "s12.stage_ah.fourcar.real_reference.package_manifest.v1"
REPORT_SCHEMA = "s12.stage_ah.fourcar.real_reference.report_manifest.v1"
BINDING_SCHEMA = "s12.stage_ah.fourcar.real_reference.binding.v1"
DEFAULT_RUN_ID = "s12-stage-ah-fourcar-real-reference-20260912-v1"
DEFAULT_OUTPUT_ROOT = Path(r"E:\Tesla_speed\review_packages")
DEFAULT_REFERENCE_ROOT = Path(
    r"E:\Tesla_speed\review_packages\s12-stage-ag-r1-identity-20260908-v1\packages"
    r"\s12-stage-ag-r1-identity-20260908-v1-identity-v1r1"
)
DEFAULT_PORT_C0 = 25380
DEFAULT_PORT_REALREF = 25480
_LOCK = threading.RLock()


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


def _reference_files(reference_root: Path, vehicle: str) -> dict[str, dict[str, str]]:
    source_dir = reference_root / _vehicle_directory(vehicle) / "web_audio"
    if not source_dir.is_dir():
        raise FileNotFoundError(f"accepted R1 reference directory missing: {source_dir}")
    files = sorted(source_dir.glob("ref_*.wav"))
    if not files:
        raise FileNotFoundError(f"accepted R1 reference WAVs missing: {source_dir}")
    return {
        path.name: {"source_path": str(path.resolve()), "sha256": sha256_file(path)}
        for path in files
    }


def _source_receipt() -> dict[str, Any]:
    receipt = dict(git_source_receipt(allow_dirty_dev=False))
    target_payload = json.loads(FOURCAR_TARGET_PATH.read_text(encoding="utf-8"))
    paths = [
        Path(__file__),
        FOURCAR_TARGET_PATH,
        Path(__file__).with_name("fourcar_pipeline.py"),
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
        }
    )
    return receipt


def _contract(
    *,
    group: str,
    vehicle: str,
    cfg: Mapping[str, Any],
    source_receipt: Mapping[str, Any],
    reference_sources: Mapping[str, Mapping[str, str]],
    candidate_hashes: Mapping[str, str],
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
                "name": profile_metadata["changed_source_parameter"],
                "scope": "source_before_shared_layers",
                "base_value": profile_metadata["base_value"],
                "candidate_value": profile_metadata["candidate_value"],
                "unit": "profile-defined",
                "basis": "five public recordings; primary-three median used for one bounded change",
            }
        )
    return {
        "schema": "s12.stage_af.dashboard_contract.v1",
        "package_id": f"ah-fourcar-realref-{group.lower()}",
        "candidate_id": f"AH-FOURCAR-REALREF-{group}",
        "vehicle": vehicle,
        "group": group,
        "flags": [],
        "seed": 20260912 if profile_metadata else 20260908,
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
        "candidate_pcm_sha256": dict(candidate_hashes),
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
                "post_identity_clip_count": record.get("post_identity_clip_count", 0),
            }
            for record in records
        ],
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
    parent_peaks: Mapping[str, Mapping[int, float]] | None,
) -> dict[str, Any]:
    group_root = run_root / "packages" / validate_identifier(
        f"ah-fourcar-realref-{run_root.name}-{group.lower()}", "package_id"
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
                    seed=20260908,
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
                    seed=20260912,
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
            refs = _reference_files(reference_root, vehicle)
            references_by_vehicle[vehicle] = refs
            for filename, details in refs.items():
                shutil.copy2(details["source_path"], web_dir / filename)
            dashboards.render_vehicle_audio(vehicle, cfg)
            engine = holders[vehicle]
            if profiles is None:
                records = [dict(engine.last_report, scene=scene["id"]) for scene in cfg["scenes"]]
            else:
                records = [dict(record, scene=scene["id"]) for scene, record in zip(cfg["scenes"], engine.reports)]
            records_by_vehicle[vehicle] = records
            candidate_hashes = {
                scene["candidate_file"]: sha256_file(cfg["dir"] / "web_audio" / scene["candidate_file"])
                for scene in cfg["scenes"]
            }
            contract = _contract(
                group=group,
                vehicle=vehicle,
                cfg=cfg,
                source_receipt=source_receipt,
                reference_sources=refs,
                candidate_hashes=candidate_hashes,
                records=records,
                profile_metadata=(profile_metadata or {}).get(vehicle),
            )
            cfg["_dashboard_contract"] = seal_payload(contract, "s12.stage_af.dashboard_contract.v1")
            cfg["_dashboard_params"] = contract["parameters"]
            dashboards.build_dashboard(vehicle, cfg)
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
                    "reference_sha256": {name: item["sha256"] for name, item in refs.items()},
                    "scenes": [scene["id"] for scene in cfg["scenes"]],
                }
            )
        all_artifacts = [
            artifact_record(path, group_root, f"package:{path.relative_to(group_root).as_posix()}")
            for path in sorted(group_root.rglob("*"))
            if path.is_file() and path.name != "audition_manifest.json"
        ]
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
                    else "four_vehicle_source_profiles_real_reference_v1"
                ),
                "output_policy": LINKED_SOFT_CEILING_V1,
                "output_policy_config": {
                    "policy_id": LINKED_SOFT_CEILING_V1,
                    "knee_linear": 0.90,
                    "ceiling_linear": 0.94,
                    "stereo_link": "instantaneous_frame_peak_common_gain",
                    "parent_denominator_policy": "fixed_parent_peak_from_ah_r1_control",
                },
                "output_guard_receipt_schema": "s12.stage_ah.output_guard_receipt.v2",
                "source_receipt": dict(source_receipt),
                "reference_evidence_level": "R1_PARENT_REFERENCE_COPY_PLUS_R3_RELATIVE_CUES",
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
        flat_records = [
            dict(record, vehicle=vehicle)
            for vehicle, records in records_by_vehicle.items()
            for record in records
        ]
        report = {
            "schema": REPORT_SCHEMA,
            "group": group,
            "package": str(group_root),
            "package_manifest_sha256": sha256_file(manifest_path),
            "source_receipt": dict(source_receipt),
            "reference_sources": references_by_vehicle,
            "records": flat_records,
            "status": "READY_FOR_LOCAL_HUMAN_REVIEW",
            "human_status": "WAITING_FOR_JOVI_FEEDBACK",
            "reference_gate": {
                "status": "NOT_APPLICABLE_R3_UNSYNCHRONIZED_CUES",
                "rows": 0,
                "regressions": 0,
                "missing": 0,
            },
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
                    index: float(record.get("parent_peak", record.get("normalization_denominator", 0.0)))
                    for index, record in enumerate(records_by_vehicle[vehicle])
                }
                for vehicle in FOURCAR_VEHICLES
            },
            "status": "READY_FOR_LOCAL_HUMAN_REVIEW",
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
                "control_final_pcm_sha256": left.get("candidate_pcm_sha256"),
                "candidate_final_pcm_sha256": right.get("final_pcm_sha256"),
                "rms_delta": float(right.get("final_rms", 0.0) - left.get("candidate_spectrum", {}).get("rms_digital", 0.0)),
                "peak_delta": float(right.get("final_peak", 0.0) - left.get("candidate_spectrum", {}).get("peak_digital", 0.0)),
            }
        )
    return {
        "record_count": len(rows),
        "parent_denominator_equal_count": sum(row["parent_denominator_equal"] for row in rows),
        "rows": rows,
    }


def build_run(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    run_id: str = DEFAULT_RUN_ID,
    reference_root: Path = DEFAULT_REFERENCE_ROOT,
    port_c0: int = DEFAULT_PORT_C0,
    port_realref: int = DEFAULT_PORT_REALREF,
) -> Path:
    run_root = output_root.resolve() / validate_identifier(run_id, "run_id")
    if run_root.exists():
        raise FileExistsError(run_root)
    run_root.mkdir(parents=True)
    source_receipt = _source_receipt()
    profiles: dict[str, Any] = {}
    profile_metadata: dict[str, Mapping[str, Any]] = {}
    for vehicle in FOURCAR_VEHICLES:
        profiles[vehicle], profile_metadata[vehicle] = load_real_reference_profile(vehicle)
    shutil.copy2(FOURCAR_TARGET_PATH, run_root / FOURCAR_TARGET_PATH.name)
    with _LOCK:
        c0 = _build_group(
            run_root=run_root,
            group="C0",
            source_receipt=source_receipt,
            reference_root=reference_root.resolve(),
            ports={vehicle: int(port_c0) + index for index, vehicle in enumerate(FOURCAR_VEHICLES)},
            profiles=None,
            profile_metadata=None,
            parent_peaks=None,
        )
        realref = _build_group(
            run_root=run_root,
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
                "path": str((run_root / FOURCAR_TARGET_PATH.name).resolve()),
                "sha256": sha256_file(run_root / FOURCAR_TARGET_PATH.name),
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
                "REALREF changes one source profile parameter per vehicle and reuses C0 parent denominators.",
                "Reference bytes are copied from the accepted AG-R1 parent without modification.",
                "Five public recordings per vehicle are diagnostic relative cues only.",
            ],
        },
        RUN_SCHEMA,
    )
    experiment_path = run_root / "experiment.json"
    _write_json(experiment_path, experiment)
    return experiment_path


def _verify_group(entry: Mapping[str, Any]) -> dict[str, Any]:
    package = Path(entry["package"])
    manifest_path = package / "audition_manifest.json"
    manifest = _read_sealed(manifest_path)
    if manifest.get("schema") != PACKAGE_SCHEMA:
        raise ValueError(f"wrong package schema: {package}")
    validate_artifacts(manifest["artifacts"], package)
    if sha256_file(manifest_path) != entry["package_manifest_sha256"]:
        raise ValueError(f"package manifest drift: {package}")
    return manifest


def serve_run(experiment_path: Path, group: str = "REALREF") -> None:
    experiment = _read_sealed(experiment_path.resolve())
    groups = {entry["group"]: entry for entry in experiment["groups"]}
    selected = groups.get(group.upper())
    if selected is None:
        raise ValueError(f"unknown group: {group}")
    manifest = _verify_group(selected)
    servers = []
    try:
        for vehicle in manifest["vehicles"]:
            package = Path(selected["package"])
            root = package / vehicle["directory"]
            handler = partial(SimpleHTTPRequestHandler, directory=str(root))
            server = ThreadingHTTPServer(("127.0.0.1", int(vehicle["port"])), handler)
            servers.append(server)
            print(f"{vehicle['vehicle']} http://localhost:{vehicle['port']}/")
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
