"""Regenerate the *existing* Stage-AD A/B workbench with Stage-AF fit results.

No new dashboard/backend is implemented here. The module deliberately imports
``stage_ad.build_unified_dashboards`` and replaces only its EngineAcoustics
constructor with the tuned adapter, preserving the proven UI/service workflow.

Because generated review packages are no longer committed to Git, this adapter
also copies already-existing governed ``ref_*.wav`` files into the exact
``web_audio`` locations expected by the original dashboard generator. It never
downloads or invents reference audio.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .physical_closed_loop import (
    FAMILY_PARAMETERS,
    TunableEngineAcoustics,
    renderer_identity,
    validate_fit_payload,
)
from .package_integrity import git_source_receipt, snapshot_fit_file, validate_reference_sources
from .package_integrity import (
    DASHBOARD_CONTRACT_SCHEMA,
    PACKAGE_MANIFEST_SCHEMA,
    artifact_record,
    dependency_fingerprint,
    publish_staged_package,
    seal_payload,
    seal_contract,
    sha256_file,
    validate_artifacts,
    validate_identifier,
)
from ..stage_ad.engine_sim_acoustics import NUMERICAL_FIXES

VEHICLES = ("hellcat", "ferrari_458", "lfa", "gtr_r35")
DIR_NAMES = {
    "hellcat": "s12-stage-ad-hellcat-closed-loop-v1",
    "ferrari_458": "s12-stage-ad-ferrari-458-closed-loop-v1",
    "lfa": "s12-stage-ad-lfa-closed-loop-v1",
    "gtr_r35": "s12-stage-ad-gtr-r35-closed-loop-v1",
}


def _load_fit(
    path: Path | None,
    vehicle: str,
    numerical_fixes: tuple[str, ...] = (),
    seed: int = 20260906,
) -> dict[str, float]:
    if path is None or not path.is_file():
        raise ValueError(f"requested fit missing: {path}; refusing default-config fallback")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return validate_fit_payload(payload, vehicle, numerical_fixes, seed)


def _load_fit_payload(
    path: Path | None,
    vehicle: str,
    numerical_fixes: tuple[str, ...],
    seed: int,
) -> dict[str, Any]:
    if path is None or not path.is_file():
        raise ValueError(f"requested fit missing: {path}; refusing default-config fallback")
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_fit_payload(payload, vehicle, numerical_fixes, seed)
    return payload


def _parameter_rows(payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    overrides = payload.get("overrides", {})
    if not isinstance(overrides, Mapping):
        raise ValueError("fit overrides must be an object")
    rows: list[dict[str, Any]] = []
    for family, parameters in FAMILY_PARAMETERS.items():
        for parameter in parameters:
            final = float(overrides.get(parameter.name, parameter.baseline))
            rows.append(
                {
                    "group": family,
                    "key": parameter.name,
                    "name": parameter.description,
                    "base": parameter.baseline,
                    "final": final,
                    "delta": (final / parameter.baseline - 1.0) * 100.0,
                    "desc": f"bounded {parameter.minimum:g}..{parameter.maximum:g}",
                }
            )
    return rows


def _reference_contract(
    cfg: Mapping[str, Any],
    bound: Mapping[str, Mapping[str, str]],
    expected_sources: Mapping[str, Mapping[str, Any]] | None,
    reference_level: str,
) -> dict[str, dict[str, Any]]:
    expected_by_filename = {
        str(entry.get("filename", "")): (scene, entry)
        for scene, entry in (expected_sources or {}).items()
    }
    result: dict[str, dict[str, Any]] = {}
    for scene in cfg.get("scenes", []):
        filename = str(scene.get("ref_file", ""))
        if not filename or filename in result:
            continue
        record = bound.get(filename)
        expected = expected_by_filename.get(filename)
        result[filename] = {
            "available": record is not None,
            "fit_required": expected is not None,
            "source": record.get("source") if record else None,
            "destination": record.get("destination") if record else None,
            "source_label": (
                f"local existing bytes: {Path(record['source']).name}"
                if record and record.get("source")
                else "Reference unavailable"
            ),
            "sha256": record.get("sha256") if record else None,
            "evidence_level": reference_level,
            "rights_status": "UNVERIFIED_LOCAL_ASSET",
        }
    return result


def _scene_hashes(cfg: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    candidate_hashes: dict[str, str] = {}
    reference_hashes: dict[str, str] = {}
    web_dir = Path(cfg["dir"]) / "web_audio"
    for scene in cfg.get("scenes", []):
        candidate = web_dir / str(scene["candidate_file"])
        candidate_hashes[str(scene["candidate_file"])] = sha256_file(candidate)
        filename = str(scene.get("ref_file", ""))
        if filename:
            reference = web_dir / filename
            if reference.is_file():
                reference_hashes[filename] = sha256_file(reference)
    return candidate_hashes, reference_hashes


_FIT_SCENE_IDS = {
    "hot_idle": "03_hot_idle",
    "steady_mid": "09_steady_mid",
    "full_pull": "02_full_pull",
    "afterfire": "01_afterfire",
}


def _scene_records(
    cfg: Mapping[str, Any],
    candidate_hashes: Mapping[str, str],
    reference_hashes: Mapping[str, str],
    fit_payload: Mapping[str, Any] | None,
    renderer: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Bind each rendered scene to its bytes, reference, fit scope and IR."""
    fit_inputs = (fit_payload or {}).get("scene_inputs_sha256", {})
    fit_refs = (fit_payload or {}).get("reference_sources", {})
    fit_scene_by_id = {scene_id: fit_scene for fit_scene, scene_id in _FIT_SCENE_IDS.items()}
    ir_fields = {
        "ir_source_path": renderer.get("ir_source_path"),
        "ir_source_sha256": renderer.get("ir_source_sha256"),
        "ir_effective_sha256": renderer.get("ir_effective_sha256"),
        "reference_evidence_level": (
            fit_payload.get("reference_level") if fit_payload else "AUDITION_ONLY"
        ),
        "reference_rights_status": "UNVERIFIED_LOCAL_ASSET",
    }
    records: list[dict[str, Any]] = []
    for scene in cfg.get("scenes", []):
        scene_id = str(scene["id"])
        candidate_file = str(scene["candidate_file"])
        reference_file = str(scene.get("ref_file", "")) or None
        fit_scene = fit_scene_by_id.get(scene_id)
        fit_reference = fit_refs.get(fit_scene) if fit_scene else None
        records.append(
            {
                "scene_id": scene_id,
                "category": str(scene.get("category", "")),
                "fit_scene": fit_scene,
                "input_trace_sha256": fit_inputs.get(fit_scene) if fit_scene else None,
                "candidate_file": candidate_file,
                "candidate_pcm_sha256": candidate_hashes.get(candidate_file),
                "reference_file": reference_file,
                "reference_available": bool(reference_file and reference_file in reference_hashes),
                "reference_sha256": reference_hashes.get(reference_file) if reference_file else None,
                "fit_reference_source": fit_reference,
                **ir_fields,
            }
        )
    return records


def _dashboard_contract(
    vehicle: str,
    cfg: Mapping[str, Any],
    package_id: str,
    candidate_id: str,
    seed: int,
    numerical_fixes: tuple[str, ...],
    fit_payload: Mapping[str, Any] | None,
    bound: Mapping[str, Mapping[str, str]],
    nav_ports: Mapping[str, int],
    nav_vehicles: tuple[str, ...],
    source_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    identity = renderer_identity(vehicle, numerical_fixes)
    reference_level = (
        str(fit_payload.get("reference_level"))
        if fit_payload
        else "AUDITION_ONLY"
    )
    fit_metric_status = (
        "FIT_DIAGNOSTIC_DISTANCE_AVAILABLE"
        if fit_payload
        and all(
            isinstance(fit_payload.get(field), (int, float))
            and math.isfinite(float(fit_payload[field]))
            for field in ("baseline_distance", "final_distance")
        )
        else "NOT_MEASURED"
    )
    contract = {
        "schema": DASHBOARD_CONTRACT_SCHEMA,
        "package_id": package_id,
        "candidate_id": candidate_id,
        "vehicle": vehicle,
        "flags": sorted(set(numerical_fixes)),
        "seed": seed,
        "fit_status": "FITTED" if fit_payload else "NOT_FITTED",
        "fit_metric_status": fit_metric_status,
        "reference_evidence_level": reference_level,
        "reference_rights_status": "UNVERIFIED_LOCAL_ASSET",
        "measurement_status": "NOT_MEASURED",
        "human_status": "WAITING_FOR_JOVI_FEEDBACK",
        "sample_rate_hz": 48_000,
        "package_port": int(nav_ports[vehicle]),
        "nav_urls": {
            key: f"http://localhost:{port}/"
            for key, port in nav_ports.items()
            if key in nav_vehicles
        },
        "fit_baseline_distance": fit_payload.get("baseline_distance") if fit_payload else None,
        "fit_final_distance": fit_payload.get("final_distance") if fit_payload else None,
        "renderer_identity": identity,
        "references": _reference_contract(
            cfg,
            bound,
            fit_payload.get("reference_sources") if fit_payload else None,
            reference_level,
        ),
        "candidate_pcm_sha256": {},
        "reference_sha256": {},
        "parameters": _parameter_rows(fit_payload),
        "package_gain_db": 0.0,
        "gain_policy": "no_additional_package_gain",
        "source_receipt": dict(source_receipt),
        "source_status": source_receipt.get("source_status"),
        "promotable": bool(source_receipt.get("promotable", False)),
        "promotion_status": source_receipt.get("promotion_status"),
        "self_contained_status": "AUDIO_SELF_CONTAINED / STYLE_NETWORK_DEPENDENCY",
    }
    return seal_contract(contract)


def _reference_candidates(root: Path, vehicle: str, filename: str) -> tuple[Path, ...]:
    package = DIR_NAMES[vehicle]
    return (
        root / vehicle / filename,
        root / vehicle / "web_audio" / filename,
        root / package / filename,
        root / package / "web_audio" / filename,
    )


def _bind_references(
    vehicle: str,
    cfg: dict[str, Any],
    reference_root: Path | None,
    *,
    expected_sources: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, str]]:
    """Copy known reference bytes into the original dashboard's web_audio dir.

    Existing destination references are preserved. Missing references remain
    missing and the original workbench will display them as unavailable.
    """
    web_dir = Path(cfg["dir"]) / "web_audio"
    web_dir.mkdir(parents=True, exist_ok=True)
    filenames = sorted(
        {
            str(scene.get("ref_file"))
            for scene in cfg["scenes"]
            if scene.get("ref_file")
        }
    )
    bound: dict[str, dict[str, str]] = {}
    for filename in filenames:
        if Path(filename).name != filename:
            raise ValueError("reference filename must not contain a directory")
        destination = web_dir / filename
        source = None
        if reference_root is not None:
            source = next(
                (
                    candidate
                    for candidate in _reference_candidates(reference_root, vehicle, filename)
                    if candidate.is_file()
                ),
                None,
            )
        if source is None:
            if expected_sources:
                expected = next(
                    (
                        entry
                        for entry in expected_sources.values()
                        if str(entry.get("filename", "")) == filename
                    ),
                    None,
                )
                if expected is not None:
                    raise ValueError(f"fit reference missing: {filename}")
            if destination.is_file():
                raise ValueError(
                    f"reference source missing; refusing stale destination bytes: {filename}"
                )
            continue
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        expected = next(
            (
                entry
                for entry in (expected_sources or {}).values()
                if str(entry.get("filename", "")) == filename
            ),
            None,
        )
        if expected is not None and digest.lower() != str(expected.get("sha256", "")).lower():
            raise ValueError(f"fit reference SHA mismatch: {filename}")
        if destination.is_file():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise ValueError("reference collision; refusing to use stale destination bytes")
        elif source.resolve() != destination.resolve():
            shutil.copy2(source, destination)
        if destination.is_file():
            bound[filename] = {
                "source": str(source or destination),
                "destination": str(destination),
                "sha256": digest,
                "fit_required": expected is not None,
                "evidence_level": "FIT_REQUIRED" if expected is not None else "AUDITION_ONLY",
                "rights_status": "UNVERIFIED_LOCAL_ASSET",
            }
    if expected_sources:
        actual_sources = {
            scene: {
                "filename": str(entry.get("filename", "")),
                "sha256": str(entry.get("sha256", "")),
            }
            for scene, entry in expected_sources.items()
            if str(entry.get("filename", "")) in bound
        }
        validate_reference_sources(actual_sources, expected_sources)
    return bound


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _package_id(requested: str | None) -> str:
    if requested:
        return validate_identifier(requested, "package_id")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return validate_identifier(f"s12-stage-af-r-{stamp}-{uuid.uuid4().hex[:8]}", "package_id")


def _vehicle_artifacts(cfg: Mapping[str, Any]) -> list[dict[str, str]]:
    root = Path(cfg["dir"])
    package_root = root.parent
    web_dir = root / "web_audio"
    records: list[dict[str, str]] = []
    for scene in cfg.get("scenes", []):
        scene_id = str(scene["id"])
        root_candidate = root / str(scene["candidate_file"])
        records.append(artifact_record(root_candidate, package_root, f"candidate_root:{scene_id}"))
        records.append(artifact_record(web_dir / str(scene["candidate_file"]), package_root, f"candidate:{scene_id}"))
        filename = str(scene.get("ref_file", ""))
        if filename and (web_dir / filename).is_file():
            records.append(artifact_record(web_dir / filename, package_root, f"reference:{scene_id}"))
    records.append(artifact_record(root / "index.html", package_root, "dashboard:index"))
    records.append(artifact_record(root / "index_standalone.html", package_root, "dashboard:standalone"))
    records.append(artifact_record(root / "dashboard_contract.json", package_root, "dashboard:contract"))
    fit_snapshot = root / "evidence" / "fit" / "final_fit.json"
    if fit_snapshot.is_file():
        records.append(artifact_record(fit_snapshot, package_root, "fit:snapshot"))
    return records


def _build_package(args: argparse.Namespace) -> Path:
    allow_dirty_dev = bool(getattr(args, "allow_dirty_dev", False))
    source_receipt = git_source_receipt(allow_dirty_dev=allow_dirty_dev)
    package_id = _package_id(args.package_id)
    output_root = args.output_root.resolve()
    published_root = output_root / package_id
    staging_root = output_root / ".stage_af_r_staging" / package_id
    if published_root.exists() or staging_root.exists():
        raise FileExistsError(f"package id already exists: {package_id}")
    staging_root.mkdir(parents=True, exist_ok=False)

    # Never search the publication root for references: that could silently
    # bind bytes from an older package. Callers must pass the governed source
    # root explicitly; an omitted root means audition-only candidate output.
    reference_root = args.reference_root.resolve() if args.reference_root else None
    selected = VEHICLES if args.vehicle == "all" else (args.vehicle,)
    flags = tuple(sorted(set(args.numerical_fixes)))
    nav_vehicles = tuple(selected)
    nav_ports = {
        vehicle: int(args.port_base) + index
        for index, vehicle in enumerate(nav_vehicles)
    }

    stage_ad_dir = Path(__file__).resolve().parents[1] / "stage_ad"
    sys.path.insert(0, str(stage_ad_dir))
    try:
        from ..stage_ad import build_unified_dashboards as dashboards
    finally:
        if sys.path and sys.path[0] == str(stage_ad_dir):
            sys.path.pop(0)
    previous_template_path = dashboards.TEMPLATE_PATH
    previous_engine_acoustics = dashboards.EngineAcoustics
    dashboards.TEMPLATE_PATH = stage_ad_dir / "audition_dashboard_template.html"

    fit_by_vehicle: dict[str, dict[str, float]] = {}
    fit_payloads: dict[str, dict[str, Any] | None] = {}
    fit_paths: dict[str, Path | None] = {}
    try:
        for vehicle in selected:
            path = args.fit_root / vehicle / "final_r3_diagnostic_fit.json" if args.fit_root else None
            fit_paths[vehicle] = path
            if args.baseline:
                fit_payloads[vehicle] = None
                fit_by_vehicle[vehicle] = {}
            else:
                payload = _load_fit_payload(path, vehicle, flags, args.seed)
                fit_payloads[vehicle] = payload
                fit_by_vehicle[vehicle] = validate_fit_payload(payload, vehicle, flags, args.seed)
    except Exception:
        dashboards.TEMPLATE_PATH = previous_template_path
        dashboards.EngineAcoustics = previous_engine_acoustics
        if staging_root.exists():
            shutil.rmtree(staging_root)
        raise

    class _Factory:
        def __new__(
            cls,
            vehicle_type: str = "ferrari_458",
            sr: int = 48000,
        ) -> TunableEngineAcoustics:
            return TunableEngineAcoustics(
                vehicle_type,
                sr=sr,
                overrides=fit_by_vehicle.get(vehicle_type, {}),
                seed=args.seed,
                numerical_fixes=flags,
            )

    dashboards.EngineAcoustics = _Factory
    vehicle_entries: list[dict[str, Any]] = []
    all_artifacts: list[dict[str, str]] = []
    try:
        for vehicle, source_cfg in dashboards.VEHICLE_CONFIGS.items():
            if vehicle not in selected:
                continue
            cfg = copy.deepcopy(source_cfg)
            cfg["dir"] = staging_root / DIR_NAMES[vehicle]
            cfg["dir"].mkdir(parents=True, exist_ok=False)
            fit_snapshot = None
            if fit_paths[vehicle]:
                fit_snapshot = snapshot_fit_file(
                    fit_paths[vehicle],
                    cfg["dir"] / "evidence" / "fit" / "final_fit.json",
                )
            expected_sources = (
                fit_payloads[vehicle].get("reference_sources", {})
                if fit_payloads[vehicle]
                else None
            )
            references = _bind_references(
                vehicle,
                cfg,
                reference_root,
                expected_sources=expected_sources,
            )
            contract = _dashboard_contract(
                vehicle,
                cfg,
                package_id,
                args.candidate_id,
                args.seed,
                flags,
                fit_payloads[vehicle],
                references,
                nav_ports,
                nav_vehicles,
                source_receipt,
            )
            cfg["_dashboard_contract"] = contract
            cfg["_dashboard_params"] = contract["parameters"]
            cfg["_nav_ports"] = nav_ports
            cfg["_nav_vehicles"] = nav_vehicles
            dashboards.render_vehicle_audio(vehicle, cfg)
            dashboards.build_dashboard(vehicle, cfg)

            candidate_hashes, reference_hashes = _scene_hashes(cfg)
            scene_records = _scene_records(
                cfg,
                candidate_hashes,
                reference_hashes,
                fit_payloads[vehicle],
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
            _write_json(cfg["dir"] / "dashboard_contract.json", contract)
            # Rebuild the same original page with final artifact identities embedded.
            dashboards.build_dashboard(vehicle, cfg)

            candidate_hashes, reference_hashes = _scene_hashes(cfg)
            if contract["candidate_pcm_sha256"] != candidate_hashes or contract["reference_sha256"] != reference_hashes:
                raise RuntimeError(f"audio bytes changed while sealing contract: {vehicle}")
            artifacts = _vehicle_artifacts(cfg)
            binding = {
                "schema": "s12.stage_af.binding.v5",
                "package_id": package_id,
                "candidate_id": args.candidate_id,
                "vehicle": vehicle,
                "contract_sha256": contract["contract_sha256"],
                "renderer_identity": contract["renderer_identity"],
                "fit_path": str(fit_paths[vehicle]) if fit_paths[vehicle] else None,
                "fit_file_sha256": sha256_file(fit_paths[vehicle]) if fit_paths[vehicle] else None,
                "fit_snapshot": fit_snapshot,
                "fit_identity": (
                    {
                        "schema": fit_payloads[vehicle].get("schema"),
                        "fit_sha256": fit_payloads[vehicle].get("fit_sha256"),
                        "renderer_identity": fit_payloads[vehicle].get("renderer_identity"),
                    }
                    if fit_payloads[vehicle]
                    else None
                ),
                "reference_evidence_level": contract["reference_evidence_level"],
                "reference_rights_status": contract["reference_rights_status"],
                "references": references,
                "scenes": scene_records,
                "artifacts": artifacts,
                "human_status": "WAITING_FOR_JOVI_FEEDBACK",
                "source_receipt": source_receipt,
                "source_status": source_receipt["source_status"],
                "promotable": source_receipt["promotable"],
                "promotion_status": source_receipt["promotion_status"],
            }
            _write_json(cfg["dir"] / "stage_af_binding.json", binding)
            artifacts.append(artifact_record(cfg["dir"] / "stage_af_binding.json", staging_root, f"binding:{vehicle}"))
            all_artifacts.extend(artifacts)
            vehicle_entries.append(
                {
                    "vehicle": vehicle,
                    "directory": DIR_NAMES[vehicle],
                    "port": nav_ports[vehicle],
                    "contract_sha256": contract["contract_sha256"],
                    "binding_sha256": artifacts[-1]["sha256"],
                    "candidate_pcm_sha256": candidate_hashes,
                    "reference_sha256": reference_hashes,
                    "fit_snapshot": fit_snapshot,
                    "scenes": scene_records,
                    "html": {
                        "index": f"{DIR_NAMES[vehicle]}/index.html",
                        "standalone": f"{DIR_NAMES[vehicle]}/index_standalone.html",
                    },
                }
            )

        fingerprints = dependency_fingerprint()
        manifest = {
            "schema": PACKAGE_MANIFEST_SCHEMA,
            "package_id": package_id,
            "candidate_id": args.candidate_id,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "source_receipt": source_receipt,
            "source_status": source_receipt["source_status"],
            "promotable": source_receipt["promotable"],
            "promotion_status": source_receipt["promotion_status"],
            "self_contained_status": "AUDIO_SELF_CONTAINED / STYLE_NETWORK_DEPENDENCY",
            "human_status": "WAITING_FOR_JOVI_FEEDBACK",
            "package_gain_db": 0.0,
            "gain_policy": "no_additional_package_gain",
            "vehicles": vehicle_entries,
            "audio_runtime_fingerprint": fingerprints["audio_runtime_fingerprint"],
            "fit_algorithm_fingerprint": fingerprints["fit_algorithm_fingerprint"],
            "package_ui_fingerprint": fingerprints["package_ui_fingerprint"],
            "dependency_fingerprints": fingerprints,
            "artifacts": all_artifacts,
        }
        _write_json(staging_root / "audition_manifest.json", seal_payload(manifest, PACKAGE_MANIFEST_SCHEMA))
        # Manifest itself is intentionally excluded from its artifact list to avoid a hash cycle.
        validate_artifacts(all_artifacts, staging_root)
        return publish_staged_package(staging_root, published_root)
    except Exception:
        if staging_root.exists():
            shutil.rmtree(staging_root)
        raise
    finally:
        dashboards.TEMPLATE_PATH = previous_template_path
        dashboards.EngineAcoustics = previous_engine_acoustics


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the existing 4-car A/B dashboards using Stage-AF tuned "
            "EngineAcoustics"
        )
    )
    parser.add_argument(
        "--fit-root",
        type=Path,
        help="root containing <vehicle>/final_r3_diagnostic_fit.json",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(r"E:\Tesla_speed\review_packages"),
    )
    parser.add_argument(
        "--reference-root",
        type=Path,
        help=(
            "existing governed reference root; omitted means no Reference binding. "
            "The publication root is never searched and no network download is performed"
        ),
    )
    parser.add_argument("--vehicle", choices=["all", *VEHICLES], default="all")
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="explicitly render the original baseline; required when --fit-root is absent",
    )
    parser.add_argument("--seed", type=int, default=20260906)
    parser.add_argument("--numerical-fixes", nargs="*", choices=sorted(NUMERICAL_FIXES), default=[])
    parser.add_argument("--package-id", help="fresh package id; existing ids are rejected")
    parser.add_argument("--candidate-id", default="candidate-af-r", help="candidate identity embedded in the contract")
    parser.add_argument("--port-base", type=int, default=8088, help="first loopback port used by the existing workbench")
    parser.add_argument(
        "--allow-dirty-dev",
        action="store_true",
        help="allow a development smoke from dirty tracked source; marks it DEV_DIRTY_SOURCE / NOT_PROMOTABLE",
    )
    args = parser.parse_args(argv)
    if args.fit_root is None and not args.baseline:
        parser.error("--fit-root is required unless --baseline is explicitly supplied")
    if args.fit_root is not None and args.baseline:
        parser.error("--fit-root and --baseline are mutually exclusive")
    if not 1024 <= args.port_base <= 65532:
        parser.error("--port-base must leave room for four vehicle ports")
    if not args.candidate_id:
        parser.error("--candidate-id must not be empty")
    published = _build_package(args)
    print(f"published package: {published}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
