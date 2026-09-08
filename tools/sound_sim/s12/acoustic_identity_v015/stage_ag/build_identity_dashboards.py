"""Build immutable Stage AG vehicle-identity audition packages.

This is a thin Stage-AG adapter over the existing Stage-AD dashboard and Stage-AF-R
package-integrity machinery.  It does not create a new audio backend and it does
not fit parameters.  `vehicle_identity_v1` is always NOT_FITTED until a later
Human-approved fitting stage exists.
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..stage_af import build_existing_dashboards as af_builder
from ..stage_af.package_integrity import (
    REPOSITORY_ROOT,
    artifact_record,
    dependency_fingerprint,
    git_source_receipt,
    publish_staged_package,
    seal_contract,
    seal_payload,
    sha256_file,
    validate_artifacts,
    validate_identifier,
)
from ..stage_af.physical_closed_loop import renderer_identity
from .vehicle_identity import (
    IDENTITY_MODE_LEGACY,
    IDENTITY_MODE_V1,
    IDENTITY_MODES,
    VehicleIdentityEngine,
    vehicle_identity_signature,
)

IDENTITY_PACKAGE_SCHEMA = "s12.stage_ag.package_manifest.v1"
IDENTITY_BINDING_SCHEMA = "s12.stage_ag.binding.v1"


def identity_runtime_fingerprint() -> list[dict[str, str]]:
    path = Path(__file__).with_name("vehicle_identity.py").resolve()
    return [
        {
            "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": sha256_file(path),
        }
    ]


def stage_ag_source_receipt(*, allow_dirty_dev: bool = False) -> dict[str, Any]:
    """Extend AF-R source receipt with Stage-AG tracked audio dependencies."""
    receipt = dict(git_source_receipt(allow_dirty_dev=allow_dirty_dev))
    tracked = (
        Path(__file__).resolve(),
        Path(__file__).with_name("vehicle_identity.py").resolve(),
    )

    result = subprocess.run(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=no",
            "--",
            *(str(path.relative_to(REPOSITORY_ROOT)) for path in tracked),
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    extra_dirty = bool(result.stdout.strip())
    if extra_dirty and not allow_dirty_dev:
        raise ValueError(
            "Stage AG tracked source is dirty; use --allow-dirty-dev only for a "
            "non-promotable smoke"
        )
    if extra_dirty:
        receipt["dependency_dirty"] = True
        receipt["source_policy"] = "DEV_DIRTY_SOURCE / NOT_PROMOTABLE"
        receipt["source_status"] = "DEV_DIRTY_SOURCE"
        receipt["promotable"] = False
        receipt["promotion_status"] = "NOT_PROMOTABLE"
        dirty = list(receipt.get("dependency_dirty_paths", []))
        dirty.extend(
            line[3:].strip()
            for line in result.stdout.splitlines()
            if len(line) >= 4
        )
        receipt["dependency_dirty_paths"] = sorted(set(dirty))
    return receipt


def _package_id(requested: str | None) -> str:
    if requested:
        return validate_identifier(requested, "package_id")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return validate_identifier(
        f"s12-stage-ag-{stamp}-{uuid.uuid4().hex[:8]}",
        "package_id",
    )


def _contract(
    *,
    vehicle: str,
    cfg: Mapping[str, Any],
    package_id: str,
    candidate_id: str,
    seed: int,
    numerical_fixes: tuple[str, ...],
    identity_mode: str,
    references: Mapping[str, Mapping[str, str]],
    nav_ports: Mapping[str, int],
    selected: tuple[str, ...],
    source_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    base_identity = renderer_identity(vehicle, numerical_fixes)
    return seal_contract(
        {
            "package_id": package_id,
            "candidate_id": candidate_id,
            "vehicle": vehicle,
            "flags": sorted(set(numerical_fixes)),
            "identity_mode": identity_mode,
            "vehicle_identity_signature": (
                vehicle_identity_signature(vehicle)
                if identity_mode == IDENTITY_MODE_V1
                else None
            ),
            "identity_runtime_fingerprint": (
                identity_runtime_fingerprint()
                if identity_mode == IDENTITY_MODE_V1
                else []
            ),
            "seed": int(seed),
            "fit_status": "NOT_FITTED",
            "fit_metric_status": "NOT_MEASURED",
            "measurement_status": "NOT_MEASURED",
            "human_status": "WAITING_FOR_JOVI_FEEDBACK",
            "reference_evidence_level": "AUDITION_ONLY",
            "reference_rights_status": "UNVERIFIED_LOCAL_ASSET",
            "sample_rate_hz": 48_000,
            "package_port": int(nav_ports[vehicle]),
            "nav_urls": {
                key: f"http://localhost:{nav_ports[key]}/"
                for key in selected
            },
            "fit_baseline_distance": None,
            "fit_final_distance": None,
            "renderer_identity": base_identity,
            "references": af_builder._reference_contract(
                cfg, references, None, "AUDITION_ONLY"
            ),
            "candidate_pcm_sha256": {},
            "reference_sha256": {},
            "parameters": [],
            "package_gain_db": 0.0,
            "gain_policy": "no_additional_package_gain",
            "source_receipt": dict(source_receipt),
            "source_status": source_receipt.get("source_status"),
            "promotable": bool(source_receipt.get("promotable", False)),
            "promotion_status": source_receipt.get("promotion_status"),
            "self_contained_status": "AUDIO_SELF_CONTAINED / STYLE_NETWORK_DEPENDENCY",
        }
    )


def build_identity_package(args: argparse.Namespace) -> Path:
    if args.identity_mode not in IDENTITY_MODES:
        raise ValueError(f"unsupported identity mode: {args.identity_mode}")
    if getattr(args, "fit_root", None) is not None:
        raise ValueError("Stage AG identity packages are NOT_FITTED; fit_root is forbidden")

    source_receipt = stage_ag_source_receipt(
        allow_dirty_dev=bool(getattr(args, "allow_dirty_dev", False))
    )
    package_id = _package_id(args.package_id)
    output_root = args.output_root.resolve()
    published_root = output_root / package_id
    staging_root = output_root / ".stage_ag_staging" / package_id
    if published_root.exists() or staging_root.exists():
        raise FileExistsError(f"package id already exists: {package_id}")
    staging_root.mkdir(parents=True, exist_ok=False)

    selected = af_builder.VEHICLES if args.vehicle == "all" else (args.vehicle,)
    selected = tuple(selected)
    nav_ports = {
        vehicle: int(args.port_base) + index for index, vehicle in enumerate(selected)
    }
    flags = tuple(sorted(set(args.numerical_fixes)))
    reference_root = args.reference_root.resolve() if args.reference_root else None

    stage_ad_dir = Path(__file__).resolve().parents[1] / "stage_ad"
    sys.path.insert(0, str(stage_ad_dir))
    try:
        from ..stage_ad import build_unified_dashboards as dashboards
    finally:
        if sys.path and sys.path[0] == str(stage_ad_dir):
            sys.path.pop(0)

    previous_template = dashboards.TEMPLATE_PATH
    previous_renderer = dashboards.EngineAcoustics
    dashboards.TEMPLATE_PATH = stage_ad_dir / "audition_dashboard_template.html"

    class _Factory:
        def __new__(cls, vehicle_type: str = "ferrari_458", sr: int = 48_000):
            return VehicleIdentityEngine(
                vehicle_type,
                sr=sr,
                identity_mode=args.identity_mode,
                numerical_fixes=flags,
                seed=args.seed,
            )

    dashboards.EngineAcoustics = _Factory
    all_artifacts: list[dict[str, str]] = []
    vehicle_entries: list[dict[str, Any]] = []

    try:
        for vehicle, source_cfg in dashboards.VEHICLE_CONFIGS.items():
            if vehicle not in selected:
                continue
            cfg = copy.deepcopy(source_cfg)
            cfg["dir"] = staging_root / af_builder.DIR_NAMES[vehicle]
            cfg["dir"].mkdir(parents=True, exist_ok=False)

            references = af_builder._bind_references(
                vehicle, cfg, reference_root, expected_sources=None
            )
            contract = _contract(
                vehicle=vehicle,
                cfg=cfg,
                package_id=package_id,
                candidate_id=args.candidate_id,
                seed=args.seed,
                numerical_fixes=flags,
                identity_mode=args.identity_mode,
                references=references,
                nav_ports=nav_ports,
                selected=selected,
                source_receipt=source_receipt,
            )
            cfg["_dashboard_contract"] = contract
            cfg["_dashboard_params"] = []
            cfg["_nav_ports"] = nav_ports
            cfg["_nav_vehicles"] = selected

            dashboards.render_vehicle_audio(vehicle, cfg)
            dashboards.build_dashboard(vehicle, cfg)

            candidate_hashes, reference_hashes = af_builder._scene_hashes(cfg)
            scene_records = af_builder._scene_records(
                cfg,
                candidate_hashes,
                reference_hashes,
                None,
                contract["renderer_identity"],
            )
            contract["candidate_pcm_sha256"] = candidate_hashes
            contract["reference_sha256"] = reference_hashes
            for filename, digest in reference_hashes.items():
                if filename in contract["references"]:
                    contract["references"][filename]["available"] = True
                    contract["references"][filename]["sha256"] = digest
            contract = seal_contract(contract)
            cfg["_dashboard_contract"] = contract
            af_builder._write_json(cfg["dir"] / "dashboard_contract.json", contract)
            dashboards.build_dashboard(vehicle, cfg)

            re_candidates, re_references = af_builder._scene_hashes(cfg)
            if re_candidates != candidate_hashes or re_references != reference_hashes:
                raise RuntimeError(f"audio changed while sealing Stage AG contract: {vehicle}")

            artifacts = af_builder._vehicle_artifacts(cfg)
            binding = {
                "schema": IDENTITY_BINDING_SCHEMA,
                "package_id": package_id,
                "candidate_id": args.candidate_id,
                "vehicle": vehicle,
                "identity_mode": args.identity_mode,
                "vehicle_identity_signature": (
                    vehicle_identity_signature(vehicle)
                    if args.identity_mode == IDENTITY_MODE_V1
                    else None
                ),
                "identity_runtime_fingerprint": (
                    identity_runtime_fingerprint()
                    if args.identity_mode == IDENTITY_MODE_V1
                    else []
                ),
                "contract_sha256": contract["contract_sha256"],
                "renderer_identity": contract["renderer_identity"],
                "references": references,
                "scenes": scene_records,
                "artifacts": artifacts,
                "fit_status": "NOT_FITTED",
                "human_status": "WAITING_FOR_JOVI_FEEDBACK",
                "source_receipt": source_receipt,
            }
            af_builder._write_json(cfg["dir"] / "stage_ag_binding.json", binding)
            artifacts.append(
                artifact_record(
                    cfg["dir"] / "stage_ag_binding.json",
                    staging_root,
                    f"stage_ag_binding:{vehicle}",
                )
            )
            all_artifacts.extend(artifacts)
            vehicle_entries.append(
                {
                    "vehicle": vehicle,
                    "directory": af_builder.DIR_NAMES[vehicle],
                    "port": nav_ports[vehicle],
                    "identity_mode": args.identity_mode,
                    "contract_sha256": contract["contract_sha256"],
                    "binding_sha256": artifacts[-1]["sha256"],
                    "candidate_pcm_sha256": candidate_hashes,
                    "reference_sha256": reference_hashes,
                    "scenes": scene_records,
                }
            )

        base_fingerprints = dependency_fingerprint()
        manifest = {
            "schema": IDENTITY_PACKAGE_SCHEMA,
            "package_id": package_id,
            "candidate_id": args.candidate_id,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "identity_mode": args.identity_mode,
            "identity_runtime_fingerprint": (
                identity_runtime_fingerprint()
                if args.identity_mode == IDENTITY_MODE_V1
                else []
            ),
            "source_receipt": source_receipt,
            "human_status": "WAITING_FOR_JOVI_FEEDBACK",
            "fit_status": "NOT_FITTED",
            "reference_evidence_level": "AUDITION_ONLY",
            "package_gain_db": 0.0,
            "gain_policy": "no_additional_package_gain",
            "vehicles": vehicle_entries,
            "audio_runtime_fingerprint": base_fingerprints["audio_runtime_fingerprint"],
            "package_ui_fingerprint": base_fingerprints["package_ui_fingerprint"],
            "artifacts": all_artifacts,
            "rules": [
                "Stage AG is an opt-in source-identity hypothesis",
                "no Stage-AF fit is reused for identity_v1",
                "Hellcat identity_v1 must remain byte-identical to legacy",
                "no Human PASS/OEM/R1 claim is made",
            ],
        }
        manifest_path = staging_root / "audition_manifest.json"
        af_builder._write_json(
            manifest_path, seal_payload(manifest, IDENTITY_PACKAGE_SCHEMA)
        )
        validate_artifacts(all_artifacts, staging_root)
        return publish_staged_package(staging_root, published_root)
    except Exception:
        if staging_root.exists():
            shutil.rmtree(staging_root)
        raise
    finally:
        dashboards.TEMPLATE_PATH = previous_template
        dashboards.EngineAcoustics = previous_renderer


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Build immutable Stage AG legacy/identity audition package"
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path)
    parser.add_argument("--vehicle", choices=["all", *af_builder.VEHICLES], default="all")
    parser.add_argument("--identity-mode", choices=sorted(IDENTITY_MODES), required=True)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--numerical-fixes", nargs="*", default=[])
    parser.add_argument("--package-id")
    parser.add_argument("--candidate-id", default="candidate-stage-ag")
    parser.add_argument("--port-base", type=int, default=23080)
    parser.add_argument("--allow-dirty-dev", action="store_true")
    args = parser.parse_args(argv)
    if not 1024 <= args.port_base <= 65532:
        parser.error("--port-base must leave room for selected vehicle ports")
    published = build_identity_package(args)
    print(published)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
