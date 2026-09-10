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
from scipy.io import wavfile
from scipy.signal import resample_poly

from ..stage_af.package_integrity import (
    canonical_json_bytes, seal_payload, sha256_file, validate_artifacts, validate_identifier,
)
from ..stage_af.physical_closed_loop import fixed_reference_distance, renderer_identity
from ..stage_ag.analyze_vehicle_identity import _read_audio
from ..stage_ag.serve_r1_review_strict import (
    VEHICLES, EXPECTED_DIRS, validate_package, _make_server,
)
from ..stage_ag.vehicle_identity_r1 import IDENTITY_MODE_V1R1
from .output_guard import LEGACY_CLIP_V1, LINKED_SOFT_CEILING_V1, OUTPUT_GUARD_RECEIPT_SCHEMA
from .source_policy import VARIANTS, pcm_sha256
from .package import build_package

# Match the original 16 reference gate rows. Non-matching scene aliases (idle
# return->hot idle, lift->afterfire) must NOT become synchronized truth.
REFERENCE_SCENES = {"01_afterfire": "ref_afterfire.wav", "02_full_pull": "ref_full_pull.wav",
                    "03_hot_idle": "ref_hot_idle.wav", "09_steady_mid": "ref_steady_mid.wav"}
C1_EXPERIMENT_SCHEMA = "s12.stage_ah.c1.experiment_manifest.v1"
C1_REPORT_SCHEMA = "s12.stage_ah.c1.report_manifest.v1"
C1_GROUPS = (
    {"key": "b0", "label": "B0", "source_variant": "r1_baseline",
     "output_policy": LEGACY_CLIP_V1, "port_base": 24080},
    {"key": "c0", "label": "C0", "source_variant": "r1_baseline",
     "output_policy": LINKED_SOFT_CEILING_V1, "port_base": 24180},
    {"key": "c1", "label": "C1", "source_variant": "body_damping",
     "output_policy": LINKED_SOFT_CEILING_V1, "port_base": 24280},
    {"key": "c2", "label": "C2", "source_variant": "afterfire_pressure",
     "output_policy": LINKED_SOFT_CEILING_V1, "port_base": 24380},
    {"key": "c3", "label": "C3", "source_variant": "combined",
     "output_policy": LINKED_SOFT_CEILING_V1, "port_base": 24480},
)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_receipt(path, data, schema="s12.stage_ah.experiment_manifest.v1"):
    sealed = seal_payload(data, schema)
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


def verify_package(path: Path, expected_sha: str | None = None, variant: str | None = None,
                   source_variant: str | None = None, output_policy: str | None = None):
    validate_package(path, expected_mode=IDENTITY_MODE_V1R1,
                     expected_manifest_sha256=expected_sha)
    manifest = load(path / "audition_manifest.json")
    expected_source = source_variant or variant
    if expected_source and manifest.get("source_variant") not in (None, expected_source):
        raise ValueError("wrong AH source variant in manifest")
    if output_policy and manifest.get("output_policy") != output_policy:
        raise ValueError("wrong AH output policy in manifest")
    validate_artifacts(manifest["artifacts"], path)
    for entry in manifest["vehicles"]:
        root = path / entry["directory"]
        contract = load(root / "dashboard_contract.json")
        if expected_source and contract.get("source_remediation_variant") != expected_source:
            raise ValueError("wrong AH source intervention in dashboard")
        if output_policy and contract.get("output_policy") != output_policy:
            raise ValueError("wrong AH output policy in dashboard")
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


def estimate_true_peak_4x(pcm: np.ndarray) -> dict:
    """Estimate intersample peak for diagnosis; this is not an ITU meter."""
    values = np.asarray(pcm, dtype=np.float64) / 32767.0
    upsampled = resample_poly(
        values, 4, 1, axis=0, window=("kaiser", 5.0),
        padtype="constant", cval=0.0,
    )
    peak = float(np.max(np.abs(upsampled)))
    return {
        "estimated_true_peak_4x": peak,
        "estimator_method": "scipy.signal.resample_poly",
        "estimator_up": 4,
        "estimator_down": 1,
        "estimator_filter": "kaiser_beta_5.0",
        "estimator_edge_policy": "constant_zero_pad",
        "status": "TRUE_PEAK_REVIEW_REQUIRED" if peak > 1.0 + 1e-9
        else "DIAGNOSTIC_ONLY_NOT_ITU_CERTIFIED",
    }


def add_output_metrics(records, package: Path, manifest: dict) -> None:
    directories = {entry["vehicle"]: entry["directory"] for entry in manifest["vehicles"]}
    for record in records:
        path = package / directories[record["vehicle"]] / "web_audio" / f"{record['scene']}.wav"
        sample_rate, pcm = wavfile.read(path)
        if int(sample_rate) != 48_000:
            raise ValueError(f"unexpected sample rate: {path}")
        pcm = np.asarray(pcm, dtype=np.int16)
        record["final_pcm_sha256"] = pcm_sha256(pcm)
        record["wav_file_sha256"] = sha256_file(path)
        record["true_peak_4x"] = estimate_true_peak_4x(pcm)
        if record["final_pcm_sha256"] != record["candidate_pcm_sha256"]:
            raise RuntimeError(f"decoded PCM SHA mismatch: {path}")


def guard_totals(records):
    fields = (
        "legacy_ceiling_input_exceedance_samples",
        "post_guard_ceiling_exceedance_samples",
        "emergency_clip_count",
    )
    totals = {field: sum(int(r["normalization"].get(field, 0) or 0) for r in records)
              for field in fields}
    totals["post_identity_clip_count"] = sum(
        int(r.get("post_identity_clip_count", 0) or 0) for r in records
    )
    totals["soft_guard_active_frames"] = sum(
        int(r["normalization"].get("soft_guard_active_frames", 0) or 0)
        for r in records
    )
    totals["soft_guard_frame_count"] = sum(
        int(r["normalization"].get("frame_count", 0) or 0)
        for r in records
    )
    totals["soft_guard_active_frame_ratio"] = (
        totals["soft_guard_active_frames"] / totals["soft_guard_frame_count"]
        if totals["soft_guard_frame_count"] else 0.0
    )
    totals["soft_guard_min_gain"] = min(
        (float(r["normalization"].get("soft_guard_min_gain", 1.0)) for r in records),
        default=1.0,
    )
    totals["soft_guard_max_attenuation_db"] = max(
        (float(r["normalization"].get("soft_guard_max_attenuation_db", 0.0))
         for r in records),
        default=0.0,
    )
    return totals


def compare_records(left_records, right_records, left_group: str, right_group: str,
                    comparison_type: str) -> list[dict]:
    left = {(r["vehicle"], r["scene"]): r for r in left_records}
    right = {(r["vehicle"], r["scene"]): r for r in right_records}
    if set(left) != set(right):
        raise RuntimeError(f"comparison trace mismatch: {left_group} vs {right_group}")
    rows = []
    for key in sorted(left):
        a, b = left[key], right[key]
        ar, br = a["candidate_spectrum"], b["candidate_spectrum"]
        rows.append({
            "left_group": left_group,
            "right_group": right_group,
            "comparison_type": comparison_type,
            "vehicle": key[0],
            "scene": key[1],
            "left_pcm_sha256": a["candidate_pcm_sha256"],
            "right_pcm_sha256": b["candidate_pcm_sha256"],
            "pcm_equal": bool(a["candidate_pcm_sha256"] == b["candidate_pcm_sha256"]),
            "rms_left": ar["rms_digital"],
            "rms_right": br["rms_digital"],
            "rms_delta": br["rms_digital"] - ar["rms_digital"],
            "peak_left": ar["peak_digital"],
            "peak_right": br["peak_digital"],
            "peak_delta": br["peak_digital"] - ar["peak_digital"],
            "crest_left": ar["peak_digital"] / max(ar["rms_digital"], 1e-30),
            "crest_right": br["peak_digital"] / max(br["rms_digital"], 1e-30),
            "lf_peak_hz_left": ar["lf_peak_hz"],
            "lf_peak_hz_right": br["lf_peak_hz"],
            "lf_ratio_delta": br["lf_20_250_ratio"] - ar["lf_20_250_ratio"],
            "true_peak_left": a["true_peak_4x"]["estimated_true_peak_4x"],
            "true_peak_right": b["true_peak_4x"]["estimated_true_peak_4x"],
            "true_peak_delta": (
                b["true_peak_4x"]["estimated_true_peak_4x"]
                - a["true_peak_4x"]["estimated_true_peak_4x"]
            ),
        })
    return rows


def _parent_context(parent_path: Path, expected_sha: str):
    parent = parent_path.resolve()
    parent_manifest = verify_package(parent, expected_sha)
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
    return parent, parent_manifest, settings[0]


def _c1_policy_metadata(spec):
    linked = spec["output_policy"] == LINKED_SOFT_CEILING_V1
    return {
        "stage": "AH-C1",
        "group": spec["label"],
        "source_variant": spec["source_variant"],
        "output_policy": spec["output_policy"],
        "output_policy_config": {
            "policy_id": spec["output_policy"],
            "knee_linear": .90 if linked else None,
            "ceiling_linear": .94,
            "stereo_link": (
                "instantaneous_frame_peak_common_gain"
                if linked else "legacy_renderer_path"
            ),
            "parent_denominator_policy": "fixed_parent_peak",
        },
        "output_guard_receipt_schema": (
            OUTPUT_GUARD_RECEIPT_SCHEMA
            if linked else "s12.stage_ah.output_guard_receipt.v1"
        ),
    }


def _c1_group_status(spec, report, true_peak_review_records):
    blocked = bool(
        report["reference_regressions_gt_3pct"]
        or report["reference_missing"]
        or report["post_guard_ceiling_exceedance_samples"]
        or report["emergency_clip_count"]
        or report["post_identity_clip_count"]
        or true_peak_review_records
    )
    return "DIAGNOSTIC_GATE_BLOCKED" if blocked else "READY_FOR_HUMAN_REVIEW"


def _comparison_summary(rows):
    return {
        "record_count": len(rows),
        "pcm_equal_count": sum(row["pcm_equal"] for row in rows),
        "mean_rms_delta": float(np.mean([row["rms_delta"] for row in rows])) if rows else 0.0,
        "mean_peak_delta": float(np.mean([row["peak_delta"] for row in rows])) if rows else 0.0,
        "max_abs_rms_delta": float(max((abs(row["rms_delta"]) for row in rows), default=0.0)),
        "max_abs_peak_delta": float(max((abs(row["peak_delta"]) for row in rows), default=0.0)),
        "rows": rows,
    }


def build_c1(args):
    """Build B0/C0/C1/C2/C3 under one fixed output-policy experiment."""
    parent, parent_manifest, (seed, flags) = _parent_context(
        args.parent_package, args.parent_manifest_sha256
    )
    root = args.output_root.resolve() / validate_identifier(args.run_id, "run_id")
    if root.exists():
        raise FileExistsError("new C1 run-id required; old evidence will not be overwritten")
    root.mkdir(parents=True)
    reports = []
    group_records = {}
    baseline_inputs = None
    parent_candidates = {
        entry["vehicle"]: entry["candidate_pcm_sha256"]
        for entry in parent_manifest["vehicles"]
    }
    try:
        for index, spec in enumerate(C1_GROUPS):
            records = []
            metadata = _c1_policy_metadata(spec)
            package_args = argparse.Namespace(
                output_root=root / "packages", reference_root=parent, vehicle="all",
                seed=seed, numerical_fixes=list(flags), allow_dirty_dev=False, fit_root=None,
                identity_mode=IDENTITY_MODE_V1R1,
                package_id=f"ah-{args.run_id}-{spec['key']}",
                candidate_id=f"AH-C1-{spec['label']}-{spec['source_variant']}",
                port_base=spec["port_base"], output_policy=spec["output_policy"],
                c1_experiment=True, group_label=spec["label"], package_metadata=metadata,
            )
            path = build_package(package_args, spec["source_variant"], records)
            manifest = verify_package(
                path, source_variant=spec["source_variant"],
                output_policy=spec["output_policy"],
            )
            current = {entry["vehicle"]: entry["candidate_pcm_sha256"]
                       for entry in manifest["vehicles"]}
            refs = {entry["vehicle"]: entry["reference_sha256"]
                    for entry in manifest["vehicles"]}
            expected_refs = {entry["vehicle"]: entry["reference_sha256"]
                             for entry in parent_manifest["vehicles"]}
            if refs != expected_refs:
                raise RuntimeError(f"Reference byte drift in {spec['label']}")
            inputs = {(record["vehicle"], record["scene"]): record["input_sha256"]
                      for record in records}
            if baseline_inputs is None:
                baseline_inputs = inputs
            elif inputs != baseline_inputs:
                raise RuntimeError("C1 groups did not use identical scene traces")
            if spec["key"] == "b0" and current != parent_candidates:
                raise RuntimeError("AH-C1 B0 is not byte-identical to accepted parent")

            add_output_metrics(records, path, manifest)
            rows = reference_rows(parent, path, manifest)
            totals = guard_totals(records)
            true_peak_review_records = sum(
                record["true_peak_4x"]["status"] == "TRUE_PEAK_REVIEW_REQUIRED"
                for record in records
            )
            report = {
                "schema": C1_REPORT_SCHEMA,
                "group": spec["label"], "group_key": spec["key"],
                "variant": spec["source_variant"],
                "source_variant": spec["source_variant"],
                "output_policy": spec["output_policy"],
                "output_policy_config": metadata["output_policy_config"],
                "output_guard_receipt_schema": metadata["output_guard_receipt_schema"],
                "package": str(path),
                "package_manifest_sha256": sha256_file(path / "audition_manifest.json"),
                "port_base": spec["port_base"], "records": records, "reference_rows": rows,
                "reference_regressions_gt_3pct": int(sum(
                    row.get("regression_gt_3pct", False) for row in rows
                )),
                "reference_missing": int(sum(
                    row["status"] == "REFERENCE_MISSING" for row in rows
                )),
                # Keep the old AH meaning: this is the pre-guard count.
                "ceiling_samples": int(totals["legacy_ceiling_input_exceedance_samples"]),
                "legacy_ceiling_input_exceedance_samples": int(
                    totals["legacy_ceiling_input_exceedance_samples"]
                ),
                "post_guard_ceiling_exceedance_samples": int(
                    totals["post_guard_ceiling_exceedance_samples"]
                ),
                "emergency_clip_count": int(totals["emergency_clip_count"]),
                "post_identity_clip_count": int(totals["post_identity_clip_count"]),
                "emergency_clip_error": float(max(
                    (record["normalization"].get("emergency_clip_error", 0.0)
                     for record in records), default=0.0
                )),
                "post_identity_clip_error": float(max(
                    (record.get("post_identity_clip_error", 0.0) for record in records),
                    default=0.0
                )),
                "soft_guard_active_frames": int(totals["soft_guard_active_frames"]),
                "soft_guard_frame_count": int(totals["soft_guard_frame_count"]),
                "soft_guard_active_frame_ratio": totals["soft_guard_active_frame_ratio"],
                "soft_guard_min_gain": totals["soft_guard_min_gain"],
                "soft_guard_max_attenuation_db": totals["soft_guard_max_attenuation_db"],
                "true_peak_review_required_records": int(true_peak_review_records),
                "status": None,
                "human_status": "WAITING_FOR_JOVI_FEEDBACK",
            }
            report["status"] = _c1_group_status(spec, report, true_peak_review_records)
            report_path = root / (
                f"{spec['key']}_{spec['source_variant']}_{spec['output_policy']}_report.json"
            )
            write_receipt(report_path, report, C1_REPORT_SCHEMA)
            summary = {
                key: value for key, value in report.items()
                if key not in ("records", "reference_rows")
            }
            summary["report"] = str(report_path)
            summary["report_sha256"] = sha256_file(report_path)
            reports.append(summary)
            group_records[spec["key"]] = records

        comparisons = {
            "B0_to_C0": _comparison_summary(compare_records(
                group_records["b0"], group_records["c0"], "B0", "C0",
                "OUTPUT_POLICY_ONLY"
            )),
            "C0_to_C1": _comparison_summary(compare_records(
                group_records["c0"], group_records["c1"], "C0", "C1",
                "SOURCE_VARIANT_ONLY_BODY"
            )),
            "C0_to_C2": _comparison_summary(compare_records(
                group_records["c0"], group_records["c2"], "C0", "C2",
                "SOURCE_VARIANT_ONLY_AFTERFIRE"
            )),
            "C0_to_C3": _comparison_summary(compare_records(
                group_records["c0"], group_records["c3"], "C0", "C3",
                "SOURCE_VARIANT_ONLY_COMBINED"
            )),
        }
        output = root / "experiment.json"
        write_receipt(output, {
            "stage": "AH-C1", "experiment_schema": C1_EXPERIMENT_SCHEMA,
            "parent_package": str(parent),
            "parent_manifest_sha256": sha256_file(parent / "audition_manifest.json"),
            "source_variants": [spec["source_variant"] for spec in C1_GROUPS],
            "output_policies": [spec["output_policy"] for spec in C1_GROUPS],
            "groups": reports, "comparisons": comparisons,
            "status": "STAGE_AH_C1_OUTPUT_CONTRACT_QUALIFIED"
            if all(row["status"] == "READY_FOR_HUMAN_REVIEW" for row in reports)
            else "STAGE_AH_C1_DIAGNOSTIC_GATE_BLOCKED",
            "human_status": "WAITING_FOR_JOVI_SOURCE_AB_REVIEW",
            "rules": [
                "B0 remains the legacy output-policy control",
                "C0 isolates linked output protection from source interventions",
                "Reference bytes remain bound to the accepted R1 parent",
                "No failed group is served or promoted automatically",
            ],
        }, C1_EXPERIMENT_SCHEMA)
        print(output)
        return output
    except Exception as exc:
        write_receipt(root / "failure.json", {
            "schema": C1_REPORT_SCHEMA, "status": "INCOMPLETE",
            "error": str(exc), "completed_groups": reports,
        }, C1_REPORT_SCHEMA)
        raise


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


def serve_c1(args):
    """Serve B0 plus exactly one C1 group after all receipt checks pass."""
    experiment = read_sealed(args.experiment)
    rows = {row["group_key"]: row for row in experiment["groups"]}
    if args.group not in rows:
        raise ValueError(f"unknown C1 group: {args.group}")
    selection = [rows["b0"]] if args.group == "b0" else [rows["b0"], rows[args.group]]
    for row in selection:
        if row["status"] != "READY_FOR_HUMAN_REVIEW":
            raise ValueError(f"C1 group blocked: {row['group']}; do not bypass")
        if sha256_file(row["report"]) != row["report_sha256"]:
            raise ValueError("C1 report drift")
        report = read_sealed(row["report"])
        if report["status"] != row["status"]:
            raise ValueError("inconsistent C1 status receipts")
        verify_package(
            Path(row["package"]), row["package_manifest_sha256"],
            source_variant=row["source_variant"], output_policy=row["output_policy"],
        )
    if args.preflight_only:
        print("AH-C1 rich-workbench preflight PASS; no sockets opened")
        return
    servers = []
    try:
        for row in selection:
            for i, vehicle in enumerate(VEHICLES):
                servers.append(_make_server(
                    Path(row["package"]) / EXPECTED_DIRS[vehicle], row["port_base"] + i
                ))
        threads = []
        for server in servers:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            threads.append(thread)
        for row in selection:
            print(row["group"], [f"http://localhost:{row['port_base'] + i}/" for i in range(4)])
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        for server in servers:
            if "threads" in locals():
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
    command = sub.add_parser("build-c1")
    command.add_argument("--parent-package", type=Path, required=True)
    command.add_argument("--parent-manifest-sha256", required=True)
    command.add_argument("--output-root", type=Path, required=True)
    command.add_argument("--run-id", required=True)
    command = sub.add_parser("serve-c1")
    command.add_argument("--experiment", type=Path, required=True)
    command.add_argument("--group", choices=[spec["key"] for spec in C1_GROUPS], default="c0")
    command.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "build":
        if not 1024 <= args.port_base <= 65232:
            parser.error("port base must leave space for all four variant groups")
        build(args)
    elif args.command == "serve":
        serve(args)
    elif args.command == "build-c1":
        build_c1(args)
    else:
        serve_c1(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
