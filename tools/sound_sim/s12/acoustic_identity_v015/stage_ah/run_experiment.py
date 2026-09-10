"""AH build/serve: reuse immutable R1 audio and the ORIGINAL rich A/B UI.

All candidate attempts get separate receipts; a failed acoustic gate never
silently stops the other diagnostics. Failed candidates cannot be served by this
launcher. This does not loosen the existing 3% Reference promotion guard.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import threading
from pathlib import Path

import numpy as np

from ..stage_af.package_integrity import (
    canonical_json_bytes, seal_payload, sha256_file, validate_artifacts, validate_identifier,
)
from ..stage_af.physical_closed_loop import fixed_reference_distance, renderer_identity
from ..stage_ag.analyze_vehicle_identity import _read_audio
from ..stage_ag.serve_r1_review_strict import (
    VEHICLES, EXPECTED_DIRS, validate_package, _make_server,
)
from ..stage_ag.vehicle_identity_r1 import IDENTITY_MODE_V1R1
from .source_policy import VARIANTS
from .package import build_package

# Match the original 16 reference gate rows. Non-matching scene aliases (idle
# return->hot idle, lift->afterfire) must NOT become synchronized truth.
REFERENCE_SCENES = {"01_afterfire": "ref_afterfire.wav", "02_full_pull": "ref_full_pull.wav",
                    "03_hot_idle": "ref_hot_idle.wav", "09_steady_mid": "ref_steady_mid.wav"}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_receipt(path, data):
    sealed = seal_payload(data, "s12.stage_ah.experiment_manifest.v1")
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(sealed, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    return sealed


def read_sealed(path):
    obj = load(path)
    body = dict(obj)
    recorded = body.pop("manifest_sha256", None)
    if recorded != hashlib.sha256(canonical_json_bytes(body)).hexdigest():
        raise ValueError(f"experiment receipt checksum mismatch: {path}")
    return obj


def js_json(text, name):
    match = re.search(r"\bconst\s+" + re.escape(name) + r"\s*=\s*", text)
    if not match:
        raise ValueError(f"missing embedded {name}")
    return json.JSONDecoder().raw_decode(text[match.end():])[0]


def verify_package(path: Path, expected_sha: str | None = None, variant: str | None = None):
    validate_package(path, expected_mode=IDENTITY_MODE_V1R1,
                     expected_manifest_sha256=expected_sha)
    manifest = load(path / "audition_manifest.json")
    validate_artifacts(manifest["artifacts"], path)
    for entry in manifest["vehicles"]:
        root = path / entry["directory"]
        contract = load(root / "dashboard_contract.json")
        if variant and contract.get("source_remediation_variant") != variant:
            raise ValueError("wrong AH source intervention in dashboard")
        html = (root / "index.html").read_text(encoding="utf-8")
        embedded = js_json(html, "DASHBOARD_CONTRACT")
        if embedded != contract:
            raise ValueError("HTML embeds a different dashboard contract")
        store = js_json(html, "AUDIO_STORE")
        scenes = js_json(html, "SCENES")
        if len(scenes) != 10:
            raise ValueError("original ten-scene workbench required")
        for scene in scenes:
            for role, key, hashes in (("candidate", "candidate_file", entry["candidate_pcm_sha256"]),
                                      ("ref", "ref_file", entry["reference_sha256"])):
                filename = scene.get(key)
                if filename not in hashes:
                    if role == "ref":
                        continue
                    raise ValueError("missing candidate binding")
                encoded = store.get(scene["id"] + "_" + role)
                if not isinstance(encoded, str):
                    raise ValueError("missing embedded audio")
                encoded = encoded.split(",", 1)[-1] if encoded.startswith("data:") else encoded
                actual = hashlib.sha256(base64.b64decode(encoded, validate=True)).hexdigest()
                if actual != hashes[filename]:
                    raise ValueError("embedded audio != validated on-disk WAV")
    return manifest


def reference_rows(parent: Path, candidate: Path, manifest):
    rows = []
    for entry in manifest["vehicles"]:
        directory = entry["directory"]
        for scene, filename in REFERENCE_SCENES.items():
            reference = parent / directory / "web_audio" / filename
            if not reference.is_file():
                rows.append({"vehicle": entry["vehicle"], "scene": scene,
                             "status": "REFERENCE_MISSING"})
                continue
            ref = _read_audio(reference)
            a = _read_audio(parent / directory / "web_audio" / f"{scene}.wav")
            b = _read_audio(candidate / directory / "web_audio" / f"{scene}.wav")
            before, after = fixed_reference_distance(a, ref), fixed_reference_distance(b, ref)
            regression = after > before * 1.03 + 1e-12
            rows.append({"vehicle": entry["vehicle"], "scene": scene,
                         "reference_sha256": sha256_file(reference), "parent_distance": before,
                         "candidate_distance": after,
                         "relative_change": (after-before)/before if before > 1e-12 else None,
                         "regression_gt_3pct": bool(regression),
                         "status": "REGRESSION" if regression else "WITHIN_GUARD"})
    return rows


def build(args):
    # Fail early on metadata/IR/root mistakes, BEFORE any costly audio rendering.
    parent = args.parent_package.resolve()
    parent_manifest = verify_package(parent, args.parent_manifest_sha256)
    settings = []
    for entry in parent_manifest["vehicles"]:
        contract = load(parent / entry["directory"] / "dashboard_contract.json")
        settings.append((int(contract["seed"]), tuple(contract["flags"])))
        actual_ir = renderer_identity(entry["vehicle"], contract["flags"])
        for key in ("ir_source_sha256", "ir_effective_sha256"):
            if actual_ir[key] != contract["renderer_identity"][key]:
                raise ValueError(f"parent IR drift: {entry['vehicle']}/{key}")
    if len(set(settings)) != 1:
        raise ValueError("parent vehicles use inconsistent seed/flags")
    seed, flags = settings[0]
    root = args.output_root.resolve() / validate_identifier(args.run_id, "run_id")
    if root.exists():
        raise FileExistsError("new run-id required; old evidence will not be overwritten")
    root.mkdir(parents=True)
    reports = []
    try:
        baseline_hashes = None
        for index, variant in enumerate(VARIANTS):
            records = []
            package_args = argparse.Namespace(
                output_root=root / "packages", reference_root=parent, vehicle="all",
                seed=seed, numerical_fixes=list(flags), allow_dirty_dev=False, fit_root=None,
                identity_mode=IDENTITY_MODE_V1R1,
                package_id=f"ah-{args.run_id}-b{index}", candidate_id=f"AH-B{index}-{variant}",
                port_base=args.port_base + index * 100,
            )
            path = build_package(package_args, variant, records)
            m = verify_package(path, variant=variant)
            current = {e["vehicle"]: e["candidate_pcm_sha256"] for e in m["vehicles"]}
            refs = {e["vehicle"]: e["reference_sha256"] for e in m["vehicles"]}
            if refs != {e["vehicle"]: e["reference_sha256"] for e in parent_manifest["vehicles"]}:
                raise RuntimeError("Reference byte drift in AH build")
            if index == 0:
                expected = {e["vehicle"]: e["candidate_pcm_sha256"] for e in parent_manifest["vehicles"]}
                if current != expected:
                    raise RuntimeError("AH-B0 is NOT byte-identical to accepted parent; stop")
                baseline_hashes = { (r["vehicle"], r["scene"]): r["input_sha256"] for r in records }
            elif { (r["vehicle"], r["scene"]): r["input_sha256"] for r in records } != baseline_hashes:
                raise RuntimeError("AH variants did not use identical scene traces")
            rows = reference_rows(parent, path, m)
            bad = sum(row.get("regression_gt_3pct", False) for row in rows)
            missing = sum(row["status"] == "REFERENCE_MISSING" for row in rows)
            ceilings = sum(r["normalization"]["ceiling_samples"] for r in records)
            report = {
                "variant": variant, "package": str(path),
                "package_manifest_sha256": sha256_file(path / "audition_manifest.json"),
                "port_base": package_args.port_base, "records": records, "reference_rows": rows,
                "reference_regressions_gt_3pct": int(bad), "reference_missing": int(missing),
                "ceiling_samples": int(ceilings),
                "status": "DIAGNOSTIC_GATE_BLOCKED" if (bad or missing or ceilings) else "READY_FOR_HUMAN_REVIEW",
                "human_status": "WAITING_FOR_JOVI_FEEDBACK",
            }
            report_path = root / f"b{index}_{variant}_report.json"
            write_receipt(report_path, report)
            reports.append({key: value for key, value in report.items() if key not in ("records", "reference_rows")})
            reports[-1]["report"] = str(report_path)
            reports[-1]["report_sha256"] = sha256_file(report_path)
        output = root / "experiment.json"
        write_receipt(output, {
            "stage": "AH", "parent_package": str(parent),
            "parent_manifest_sha256": sha256_file(parent / "audition_manifest.json"),
            "variants": reports, "status": "DIAGNOSTICS_COMPLETE_NOT_HUMAN_PASS",
            "rules": ["No failed candidate is automatically promoted/served", "No old package modified",
                      "Source stems and digital spectra do not establish perceptual truth"],
        })
        print(output)
        return output
    except Exception as exc:
        write_receipt(root / "failure.json", {"status": "INCOMPLETE", "error": str(exc),
                                             "completed_variants": reports})
        raise


def serve(args):
    experiment = read_sealed(args.experiment)
    rows = {row["variant"]: row for row in experiment["variants"]}
    selection = [rows["r1_baseline"], rows[args.variant]]
    if args.variant == "r1_baseline":
        selection = selection[:1]
    for row in selection:
        if row["status"] != "READY_FOR_HUMAN_REVIEW":
            raise ValueError(f"candidate guard blocked: {row['variant']}; inspect report, do not bypass")
        if sha256_file(row["report"]) != row["report_sha256"]:
            raise ValueError("diagnostic report drift")
        report = read_sealed(row["report"])
        if report["status"] != row["status"]:
            raise ValueError("inconsistent status receipts")
        verify_package(Path(row["package"]), row["package_manifest_sha256"], row["variant"])
    if args.preflight_only:
        print("AH rich-workbench preflight PASS; no sockets opened")
        return
    servers = []
    try:
        for row in selection:
            for i, vehicle in enumerate(VEHICLES):
                servers.append(_make_server(Path(row["package"]) / EXPECTED_DIRS[vehicle], row["port_base"] + i))
        threads = []
        for server in servers:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            threads.append(thread)
        for row in selection:
            print(row["variant"], [f"http://localhost:{row['port_base'] + i}/" for i in range(4)])
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        for server in servers:
            # shutdown waits on serve_forever: do not call it after partial bind
            # failures before threads were started.
            if 'threads' in locals():
                server.shutdown()
            server.server_close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("build")
    command.add_argument("--parent-package", type=Path, required=True)
    command.add_argument("--parent-manifest-sha256", required=True)
    command.add_argument("--output-root", type=Path, required=True)
    command.add_argument("--run-id", required=True)
    command.add_argument("--port-base", type=int, default=23680)
    command = sub.add_parser("serve")
    command.add_argument("--experiment", type=Path, required=True)
    command.add_argument("--variant", choices=VARIANTS, default="body_damping")
    command.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "build":
        if not 1024 <= args.port_base <= 65232:
            parser.error("port base must leave space for all four variant groups")
        build(args)
    else:
        serve(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
