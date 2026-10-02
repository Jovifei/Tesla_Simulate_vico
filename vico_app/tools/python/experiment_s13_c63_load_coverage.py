"""Create isolated C63 load-edge candidates for the S13 controlled ablation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

import export_s12_android_sound_banks as exporter


VEHICLE_KEY = "c63_w204_v6"
SAMPLE_RATE_HZ = 48_000
TOTAL_FRAMES = 1_440_000
TRACE_POINTS = 1501
SOURCE_COMMIT = "29b50961d9628f835e7172b797380ccb36a7f38d"
S12_ASSET_ROOT = Path("Project/android/app/src/main/assets")
BANK_ASSET_ROOT = S12_ASSET_ROOT / "s12_v10"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def bank_sha256_inventory(bank_root: Path) -> dict[str, str]:
    return {
        path.relative_to(bank_root).as_posix(): sha256_file(path)
        for path in sorted(bank_root.rglob("*"))
        if path.is_file()
    }


def trace_load_bounds(points: list[dict]) -> tuple[float, float]:
    if len(points) != TRACE_POINTS:
        raise ValueError(f"Expected {TRACE_POINTS} trace points; got {len(points)}")
    loads = []
    for index, point in enumerate(points):
        time_s = float(point["time_s"])
        load = float(point["load"])
        if not math.isfinite(time_s) or not math.isfinite(load) or not 0.0 <= load <= 1.0:
            raise ValueError(f"Invalid C63 trace point {index}")
        if not math.isclose(time_s, index / 50.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(f"Non-canonical C63 trace time at point {index}")
        loads.append(load)
    return min(loads), max(loads)


def plan_load_variants(
    base_levels: tuple[float, ...] | list[float], minimum: float, maximum: float,
) -> dict[str, tuple[float, ...]]:
    levels = tuple(sorted({float(level) for level in base_levels}))
    if not levels or any(not math.isfinite(level) or not 0.0 <= level <= 1.0 for level in levels):
        raise ValueError("Base load levels must be finite values in [0, 1]")
    if not math.isfinite(minimum) or not math.isfinite(maximum) or minimum > maximum:
        raise ValueError("Trace load bounds are invalid")
    if not 0.0 <= minimum <= 1.0 or not 0.0 <= maximum <= 1.0:
        raise ValueError("Trace load bounds must be in [0, 1]")

    low = minimum if minimum < levels[0] else None
    high = maximum if maximum > levels[-1] else None
    variants: dict[str, tuple[float, ...]] = {"A": levels}
    if low is not None:
        variants["B-low"] = tuple(sorted((*levels, low)))
    if high is not None:
        variants["B-high"] = tuple(sorted((*levels, high)))
    if low is not None and high is not None:
        variants["B-both"] = tuple(sorted((*levels, low, high)))
    return variants


def validate_candidate_root(candidate_root: Path, production_bank_root: Path) -> Path:
    candidate = candidate_root.resolve()
    production = production_bank_root.resolve()
    if candidate == production or candidate in production.parents or production in candidate.parents:
        raise ValueError("Candidate output must be outside the production bank")
    if candidate.exists() and any(candidate.iterdir()):
        raise FileExistsError(f"Candidate output root is not empty: {candidate}")
    return candidate


def apply_fixed_gain(
    samples: np.ndarray, fixed_gain: float, peak_limit_dbfs: float = -1.5,
) -> np.ndarray:
    if not math.isfinite(fixed_gain) or fixed_gain <= 0.0:
        raise ValueError("Fixed vehicle gain must be finite and positive")
    signal = np.asarray(samples, dtype=np.float32)
    if signal.size == 0 or not np.isfinite(signal).all():
        raise ValueError("Candidate loop must be non-empty and finite")
    scaled = (signal * np.float32(fixed_gain)).astype(np.float32)
    limit = 10.0 ** (peak_limit_dbfs / 20.0)
    if float(np.max(np.abs(scaled))) > limit:
        raise ValueError("fixed vehicle gain exceeds peak limit; do not renormalize candidate")
    return scaled


def _git_value(repo_root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo_root), *args], text=True, encoding="utf-8",
    ).strip()


def _worktree_snapshot(repo_root: Path) -> dict:
    status = _git_value(repo_root, "status", "--porcelain=v1", "--untracked-files=all")
    files = []
    for line in status.splitlines():
        if len(line) < 4:
            continue
        relative = line[3:]
        path = repo_root / Path(relative.replace("/", "\\"))
        files.append({
            "status": line[:2],
            "path": relative,
            "sha256": sha256_file(path) if path.is_file() else None,
        })
    return {
        "branch": _git_value(repo_root, "branch", "--show-current"),
        "head": _git_value(repo_root, "rev-parse", "HEAD"),
        "dirty_path_count": len(files),
        "paths": files,
    }


def _event_schedule_sha256(events: list[dict]) -> str:
    fields = (
        "id", "kind", "asset_path", "asset_sha256", "source_frame",
        "crop_start_frame", "trigger_offset_frames", "samples",
    )
    canonical = "\n".join(
        "|".join(str(event[field]) for field in fields)
        for event in sorted(events, key=lambda item: int(item["crop_start_frame"]))
    )
    return sha256_bytes(canonical.encode("utf-8"))


def _source_pipeline_hashes(source_root: Path) -> dict[str, str]:
    package = source_root / "sound_sim/s12/acoustic_identity_v015"
    relative_paths = (
        "contracts.py",
        "render_realism_v10.py",
        "render_identity_v02.py",
        "synth_primitives.py",
        "sources/mercedes_v8_source.py",
        "acoustic_layers/__init__.py",
        "acoustic_layers/afterfire_model.py",
        "acoustic_layers/exhaust_rumble.py",
        "acoustic_layers/idle_dynamics.py",
        "acoustic_layers/low_frequency_body.py",
        "acoustic_layers/pre_equalization.py",
        "acoustic_layers/realism_profiles.py",
        "acoustic_layers/shift_dynamics.py",
    )
    hashes = {}
    for relative in relative_paths:
        path = package / relative
        if not path.is_file():
            raise FileNotFoundError(f"Missing frozen S12 source file: {path}")
        hashes[relative] = sha256_file(path)
    return hashes


def _validate_frozen_inputs(app_root: Path, source_root: Path) -> tuple[Path, dict, dict, dict]:
    bank_root = app_root / BANK_ASSET_ROOT / VEHICLE_KEY
    sidecar_path = app_root / S12_ASSET_ROOT / "s13_review_v1" / f"{VEHICLE_KEY}.json"
    manifest_path = bank_root / "manifest.json"
    trace_path = bank_root / "common_input_trace.json"
    if not all(path.is_file() for path in (manifest_path, trace_path, sidecar_path)):
        raise FileNotFoundError("C63 manifest, common trace, and S13 sidecar are required")

    manifest_bytes = manifest_path.read_bytes()
    trace_bytes = trace_path.read_bytes()
    sidecar_bytes = sidecar_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    trace = json.loads(trace_bytes)
    sidecar = json.loads(sidecar_bytes)

    if manifest.get("vehicle_key") != VEHICLE_KEY or sidecar.get("vehicle_key") != VEHICLE_KEY:
        raise ValueError("C63 input package has a mismatched vehicle identity")
    if manifest.get("source_commit") != SOURCE_COMMIT or sidecar.get("source_commit") != SOURCE_COMMIT:
        raise ValueError("C63 package source commit differs from the frozen S12 source")
    if exporter._source_commit(source_root) != SOURCE_COMMIT:
        raise ValueError("Current S12 source HEAD differs from the frozen bank source commit")
    if sha256_bytes(trace_bytes) != sidecar["trace"]["sha256"]:
        raise ValueError("C63 trace SHA differs from its review sidecar")
    if sha256_bytes(manifest_bytes) != sidecar["bank_manifest"]["sha256"]:
        raise ValueError("C63 manifest SHA differs from its review sidecar")
    if sha256_file(Path(exporter.__file__).resolve()) != sidecar["exporter_sha256"]:
        raise ValueError("Vico exporter SHA differs from the recorded sidecar")
    if not math.isclose(
        float(manifest["fixed_vehicle_gain"]), float(sidecar["fixed_vehicle_gain"]),
        rel_tol=0.0, abs_tol=1e-12,
    ):
        raise ValueError("C63 fixed gain differs between manifest and sidecar")
    if trace.get("schema") != "vico.s12.common_input_trace.v1":
        raise ValueError("Unexpected C63 common trace schema")

    entries = [*manifest["loops"], manifest["afterfire"], *manifest["shift_events"]]
    expected_names = {entry["file"] for entry in entries}
    if set(sidecar["bank_assets_sha256"]) != expected_names:
        raise ValueError("C63 sidecar asset inventory differs from the manifest")
    for name, expected in sidecar["bank_assets_sha256"].items():
        if sha256_file(bank_root / name) != expected:
            raise ValueError(f"C63 bank asset SHA mismatch: {name}")

    event_names = {entry["file"] for entry in [manifest["afterfire"], *manifest["shift_events"]]}
    if {Path(event["asset_path"]).name for event in sidecar["events"]} != event_names:
        raise ValueError("C63 event sidecar inventory differs from manifest")
    trace_load_bounds(trace["points"])
    return bank_root, manifest, trace, sidecar


def _write_tsv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def _write_properties(path: Path, values: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for key, value in values.items():
            if value is None:
                value = ""
            elif isinstance(value, Path):
                value = value.resolve().as_posix()
            stream.write(f"{key}={value}\n")


def _bind_digital_evidence(
    d0_path: Path | None,
    d1_path: Path | None,
    d2_path: Path | None,
    receipt_path: Path | None,
) -> dict | None:
    inputs = (d0_path, d1_path, d2_path, receipt_path)
    if all(path is None for path in inputs):
        return None
    if any(path is None for path in inputs):
        raise ValueError("D0, D1, D2 and the C63 phone receipt must be supplied together")
    d0_path, d1_path, d2_path, receipt_path = (Path(path).resolve() for path in inputs)
    receipt_bytes = receipt_path.read_bytes()
    receipt = json.loads(receipt_bytes)
    core = receipt["review_core"]
    accepted = receipt["track_accepted"]
    for capture in (core, accepted):
        if capture["input_binding"] != "MATCHED_TRACE" or not capture["full_window"]:
            raise ValueError("C63 phone PCM receipt is not a complete matched-trace capture")
        if capture["requested_frames"] != TOTAL_FRAMES or capture["accepted_frames"] != TOTAL_FRAMES:
            raise ValueError("C63 phone PCM receipt has incomplete requested/accepted frames")
    if not receipt["session_complete"] or receipt["session_error"]:
        raise ValueError("C63 phone review session did not complete cleanly")
    if not receipt["core_equals_track_accepted"] or core["sha256"] != accepted["sha256"]:
        raise ValueError("C63 D1/D2 phone PCM receipt is not byte-identical")
    mix_stats = receipt["mix_stats"]
    if mix_stats["hard_clip_frames"] or mix_stats["non_finite_frames"]:
        raise ValueError("C63 phone baseline violates pre-clip or finite-PCM integrity")

    desktop, sample_rate = sf.read(d0_path, dtype="float32", always_2d=True)
    if sample_rate != SAMPLE_RATE_HZ or desktop.shape != (TOTAL_FRAMES + 1, 1):
        raise ValueError("D0 must remain the mono 48 kHz 1,440,001-frame source reference")
    expected_bytes = TOTAL_FRAMES * 4
    d1_bytes, d2_bytes = d1_path.read_bytes(), d2_path.read_bytes()
    if len(d1_bytes) != expected_bytes or len(d2_bytes) != expected_bytes:
        raise ValueError("D1 and D2 must each contain exactly 1,440,000 float32 mono frames")
    d1_sha, d2_sha = sha256_bytes(d1_bytes), sha256_bytes(d2_bytes)
    if d1_sha != core["sha256"] or d2_sha != accepted["sha256"] or d1_bytes != d2_bytes:
        raise ValueError("D1/D2 PCM files differ from the phone receipt")
    if core["vehicle_key"] != VEHICLE_KEY or core["source_commit"] != SOURCE_COMMIT:
        raise ValueError("Phone receipt is not bound to the frozen C63 source identity")

    return {
        "D0": {"path": d0_path.as_posix(), "sha256": sha256_file(d0_path), "frames": int(desktop.shape[0])},
        "D1": {"path": d1_path.as_posix(), "sha256": d1_sha, "frames": TOTAL_FRAMES},
        "D2": {"path": d2_path.as_posix(), "sha256": d2_sha, "frames": TOTAL_FRAMES},
        "receipt": {"path": receipt_path.as_posix(), "sha256": sha256_bytes(receipt_bytes)},
        "baseline_tolerance": {"max_abs": 2e-5, "rmse": 2e-6},
    }


def generate_c63_load_candidates(
    *, app_root: Path, source_root: Path, output_root: Path,
    d0_path: Path | None = None, d1_path: Path | None = None, d2_path: Path | None = None,
    receipt_path: Path | None = None,
) -> dict:
    app_root = app_root.resolve()
    source_root = source_root.resolve()
    bank_root, manifest, trace, sidecar = _validate_frozen_inputs(app_root, source_root)
    output_root = validate_candidate_root(output_root, bank_root)
    if app_root in output_root.parents:
        raise ValueError("Candidate output must be outside the Vico repository")
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"Candidate output root is not empty: {output_root}")

    base_hashes = bank_sha256_inventory(bank_root)
    worktree = _worktree_snapshot(app_root)
    source_file_hashes = _source_pipeline_hashes(source_root)
    experiment_script_sha256 = sha256_file(Path(__file__).resolve())
    base_loads = tuple(sorted({float(loop["load"]) for loop in manifest["loops"]}))
    low, high = trace_load_bounds(trace["points"])
    variants = plan_load_variants(base_loads, low, high)
    evidence = _bind_digital_evidence(d0_path, d1_path, d2_path, receipt_path)
    if evidence is not None:
        receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
        for capture in (receipt["review_core"], receipt["track_accepted"]):
            if capture["vehicle_key"] != VEHICLE_KEY or capture["source_commit"] != SOURCE_COMMIT:
                raise ValueError("Phone PCM receipt is not bound to the frozen C63 source identity")
            if capture["trace_sha256"] != sidecar["trace"]["sha256"]:
                raise ValueError("Phone PCM receipt trace SHA differs from the frozen C63 trace")
            if capture["bank_manifest_sha256"] != sidecar["bank_manifest"]["sha256"]:
                raise ValueError("Phone PCM receipt manifest SHA differs from the frozen C63 bank")
            if capture["event_schedule_sha256"] != _event_schedule_sha256(sidecar["events"]):
                raise ValueError("Phone PCM receipt event schedule differs from the frozen sidecar")
    candidate_edges = {
        edge: next(iter(set(levels) - set(base_loads)))
        for edge, levels in (("low", variants.get("B-low", base_loads)),
                             ("high", variants.get("B-high", base_loads)))
        if set(levels) != set(base_loads)
    }

    source_api = exporter._load_source_api(source_root)
    vehicle_state_trace, _, _, _, _, renderers, apply_ptr, _, render_stateful = source_api
    source_vehicle = exporter.APP_VEHICLES[VEHICLE_KEY]
    renderer = renderers[source_vehicle]
    candidate_records = []
    candidate_payloads = []
    fixed_gain = float(manifest["fixed_vehicle_gain"])
    peak_limit = float(manifest["peak_limit_dbfs"])
    rpm_levels = sorted({int(loop["rpm"]) for loop in manifest["loops"]})
    if tuple(rpm_levels) != tuple(exporter.RPM_LEVELS[VEHICLE_KEY]):
        raise ValueError("C63 manifest RPM grid differs from the existing exporter grid")

    for edge, load in candidate_edges.items():
        for rpm in rpm_levels:
            trace_state = exporter._constant_trace(vehicle_state_trace, rpm, load, 0.52)
            rendered = render_stateful(renderer, source_vehicle, trace_state)
            loop = exporter._loop(exporter._mono_48k(apply_ptr(rendered.pressure)))
            signal = apply_fixed_gain(loop, fixed_gain, peak_limit)
            if signal.size != int(0.36 * SAMPLE_RATE_HZ):
                raise ValueError("Candidate loop frame count differs from the existing 0.36-second bank")
            token = f"{load:.8g}".replace(".", "p")
            relative = Path("candidate_assets") / edge / f"rpm_{rpm:04d}_load_{token}_s13.wav"
            record = {
                "edge": edge,
                "rpm": rpm,
                "load": load,
                "path": relative.as_posix(),
                "sample_count": int(signal.size),
                "peak_dbfs": exporter._dbfs(float(np.max(np.abs(signal)))),
                "fixed_vehicle_gain": fixed_gain,
            }
            candidate_records.append(record)
            candidate_payloads.append((record, signal))

    output_root.mkdir(parents=True, exist_ok=True)
    for record, signal in candidate_payloads:
        path = output_root / record["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(path, signal, SAMPLE_RATE_HZ, subtype="FLOAT", format="WAV")
        decoded, rate = sf.read(path, dtype="float32", always_2d=True)
        if rate != SAMPLE_RATE_HZ or decoded.shape != (int(0.36 * SAMPLE_RATE_HZ), 1):
            raise ValueError(f"Candidate loop contract mismatch: {record['path']}")
        record["sha256"] = sha256_file(path)

    input_root = output_root / "inputs"
    _write_tsv(
        input_root / "trace_points.tsv",
        ["time_s", "rpm", "load", "throttle", "acceleration_mps2"],
        [[point[key] for key in ("time_s", "rpm", "load", "throttle", "acceleration_mps2")]
         for point in trace["points"]],
    )
    _write_tsv(
        input_root / "events.tsv",
        ["id", "kind", "asset_path", "asset_sha256", "trace_sha256", "source_domain",
         "source_time_s", "source_frame", "crop_start_frame", "trigger_offset_frames", "samples"],
        [[event["id"], event["kind"], event["asset_path"], event["asset_sha256"],
          sidecar["trace"]["sha256"], event["source_domain"], event["source_time_s"],
          event["source_frame"], event["crop_start_frame"], event["trigger_offset_frames"],
          event["samples"]] for event in sidecar["events"]],
    )
    _write_tsv(
        input_root / "transients.tsv",
        ["kind", "filename", "path", "sha256", "sample_count"],
        [[
            event["kind"],
            Path(event["asset_path"]).name,
            f"{BANK_ASSET_ROOT.as_posix()}/{VEHICLE_KEY}/{Path(event['asset_path']).name}",
            event["asset_sha256"],
            event["samples"],
        ] for event in sidecar["events"]],
    )
    _write_tsv(
        input_root / "powertrain.tsv",
        ["key", "value"],
        [[key, json.dumps(value, separators=(",", ":")) if isinstance(value, list) else value]
         for key, value in manifest.items()
         if key in {
             "idle_rpm", "redline_rpm", "gear_ratios", "final_drive", "wheel_radius_m",
             "launch_rpm", "shift_rpm", "shift_attack_s", "shift_hold_s", "shift_recovery_s",
             "shift_settle_s", "shift_min_torque", "shift_reengage_gain", "minimum_shift_interval_s",
             "downshift_ratio", "speed_ceiling_kmh", "afterfire_minimum_rpm",
         }],
    )

    if evidence is not None:
        _write_properties(input_root / "experiment.properties", {
            "app_root": app_root,
            "experiment_root": output_root,
            "vehicle_key": VEHICLE_KEY,
            "source_commit": manifest["source_commit"],
            "experiment_script_sha256": experiment_script_sha256,
            "source_pipeline_sha256": source_file_hashes,
            "fixed_vehicle_gain": fixed_gain,
            "sample_rate_hz": SAMPLE_RATE_HZ,
            "total_frames": TOTAL_FRAMES,
            "trace_sha256": sidecar["trace"]["sha256"],
            "manifest_sha256": sidecar["bank_manifest"]["sha256"],
            "sidecar_sha256": sha256_file(app_root / S12_ASSET_ROOT / "s13_review_v1" / f"{VEHICLE_KEY}.json"),
            "event_schedule_sha256": _event_schedule_sha256(sidecar["events"]),
            "d0_path": evidence["D0"]["path"],
            "d0_sha256": evidence["D0"]["sha256"],
            "d0_frames": evidence["D0"]["frames"],
            "d1_path": evidence["D1"]["path"],
            "d1_sha256": evidence["D1"]["sha256"],
            "d1_frames": evidence["D1"]["frames"],
            "d2_path": evidence["D2"]["path"],
            "d2_sha256": evidence["D2"]["sha256"],
            "d2_frames": evidence["D2"]["frames"],
            "d1_max_abs_tolerance": evidence["baseline_tolerance"]["max_abs"],
            "d1_rmse_tolerance": evidence["baseline_tolerance"]["rmse"],
        })

    base_loop_records = [
        {"source": "app", "path": f"{BANK_ASSET_ROOT.as_posix()}/{VEHICLE_KEY}/{entry['file']}",
         "rpm": int(entry["rpm"]), "load": float(entry["load"]),
         "sha256": sidecar["bank_assets_sha256"][entry["file"]]}
        for entry in manifest["loops"]
    ]
    variant_inventory = {}
    for variant, levels in variants.items():
        records = list(base_loop_records)
        if variant in {"B-low", "B-both"}:
            records.extend({"source": "experiment", **record} for record in candidate_records if record["edge"] == "low")
        if variant in {"B-high", "B-both"}:
            records.extend({"source": "experiment", **record} for record in candidate_records if record["edge"] == "high")
        variant_root = output_root / "variants" / variant
        _write_tsv(
            variant_root / "loops.tsv",
            ["source", "path", "rpm", "load", "sha256"],
            [[record[key] for key in ("source", "path", "rpm", "load", "sha256")] for record in records],
        )
        inventory = {
            "schema": "vico.s13.c63_load_ablation.v1",
            "variant": variant,
            "vehicle_key": VEHICLE_KEY,
            "source_commit": manifest["source_commit"],
            "parent_manifest_sha256": sha256_file(bank_root / "manifest.json"),
            "parent_sidecar_sha256": sha256_file(app_root / S12_ASSET_ROOT / "s13_review_v1" / f"{VEHICLE_KEY}.json"),
            "trace_sha256": sidecar["trace"]["sha256"],
            "event_schedule_sha256": _event_schedule_sha256(sidecar["events"]),
            "fixed_vehicle_gain": fixed_gain,
            "base_load_levels": list(base_loads),
            "variant_load_levels": list(levels),
            "bank_asset_sha256": sidecar["bank_assets_sha256"],
            "candidate_assets": [record for record in candidate_records if record["path"] in {r["path"] for r in records if r["source"] == "experiment"}],
        }
        inventory_path = variant_root / "inventory.json"
        inventory_path.parent.mkdir(parents=True, exist_ok=True)
        inventory_path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
        inventory_sha = sha256_file(inventory_path)
        _write_properties(variant_root / "variant.properties", {
            "variant": variant,
            "bank_manifest_sha256": (
                sidecar["bank_manifest"]["sha256"] if variant == "A" else inventory_sha
            ),
            "variant_inventory_sha256": inventory_sha,
        })
        variant_inventory[variant] = {
            "load_levels": list(levels),
            "inventory_path": inventory_path.relative_to(output_root).as_posix(),
            "inventory_sha256": inventory_sha,
        }

    d0_d1_d2 = evidence or {"D0": None, "D1": None, "D2": None, "receipt": None}

    snapshot_after = _worktree_snapshot(app_root)
    current_bank_hashes = bank_sha256_inventory(bank_root)
    if current_bank_hashes != base_hashes:
        raise RuntimeError("Production C63 bank changed while candidates were generated")
    if snapshot_after != worktree:
        raise RuntimeError("Vico working tree changed during candidate generation")

    snapshot_path = output_root / "worktree_snapshot.json"
    snapshot_path.write_text(json.dumps(worktree, indent=2), encoding="utf-8")

    result = {
        "schema": "vico.s13.c63_load_experiment.v1",
        "status": "GENERATED_NOT_EVALUATED",
        "vehicle_key": VEHICLE_KEY,
        "vico_head": worktree["head"],
        "vico_branch": worktree["branch"],
        "vico_dirty_path_count": worktree["dirty_path_count"],
        "vico_worktree_snapshot_sha256": sha256_file(snapshot_path),
        "source_commit": manifest["source_commit"],
        "source_exporter_sha256": sidecar["exporter_sha256"],
        "vico_exporter_sha256": sha256_file(Path(exporter.__file__).resolve()),
        "experiment_script_sha256": experiment_script_sha256,
        "source_pipeline_sha256": source_file_hashes,
        "fixed_vehicle_gain": fixed_gain,
        "trace_sha256": sidecar["trace"]["sha256"],
        "bank_manifest_sha256": sidecar["bank_manifest"]["sha256"],
        "event_schedule_sha256": _event_schedule_sha256(sidecar["events"]),
        "minimum_trace_load": low,
        "maximum_trace_load": high,
        "base_load_levels": list(base_loads),
        "variants": variant_inventory,
        "base_asset_sha256": base_hashes,
        "candidate_asset_sha256": {record["path"]: record["sha256"] for record in candidate_records},
        "candidate_asset_paths": [str(output_root / record["path"]) for record in candidate_records],
        "candidate_assets": candidate_records,
        "D0_D1_D2": d0_d1_d2,
        "worktree_snapshot": worktree,
    }
    (output_root / "experiment.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def build_renderer_load_trajectory(
    points: list[dict],
    minimum: float,
    maximum: float,
    *,
    total_frames: int = TOTAL_FRAMES,
    block_frames: int = 960,
    sample_rate_hz: int = SAMPLE_RATE_HZ,
    smoothing_seconds: float = 0.035,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Reproduce the review renderer's request -> clamp -> 35 ms load smoothing."""
    trace_load_bounds(points)
    if not 0.0 <= minimum < maximum <= 1.0:
        raise ValueError("Renderer load bounds must be ordered values in [0, 1]")
    if total_frames <= 0 or block_frames <= 0 or total_frames % block_frames:
        raise ValueError("Load trajectory frame count must contain complete renderer blocks")
    if sample_rate_hz <= 0 or smoothing_seconds <= 0.0:
        raise ValueError("Invalid renderer smoothing contract")

    requested = np.empty(total_frames, dtype=np.float64)
    clamped = np.empty(total_frames, dtype=np.float64)
    smoothed = np.empty(total_frames, dtype=np.float64)
    alpha = 1.0 - math.exp(-1.0 / (sample_rate_hz * smoothing_seconds))
    smoothed_value = float(np.clip(points[0]["load"], minimum, maximum))
    frame = 0
    while frame < total_frames:
        count = min(block_frames, total_frames - frame)
        index = frame // block_frames
        first = float(points[index]["load"])
        second = float(points[index + 1]["load"])
        raw = first + (second - first) * (np.arange(count, dtype=np.float64) / block_frames)
        target = np.clip(raw, minimum, maximum)
        requested[frame:frame + count] = raw
        clamped[frame:frame + count] = target
        for offset, value in enumerate(target):
            smoothed_value += alpha * (float(value) - smoothed_value)
            smoothed[frame + offset] = smoothed_value
        frame += count
    return requested, clamped, smoothed


def classify_load_windows(
    requested_load: np.ndarray,
    smoothed_load: np.ndarray,
    events: list[dict],
    *,
    sample_rate_hz: int = SAMPLE_RATE_HZ,
    window_frames: int = 4800,
    low_boundary: float = 0.32,
    high_boundary: float = 0.92,
    transition_guard_frames: int = 9600,
    event_guard_frames: int = 9600,
    start_guard_frames: int = 9600,
    stop_guard_frames: int = 19200,
) -> list[dict]:
    """Label contiguous windows; never stitch separated low/mid/high regions."""
    requested = np.asarray(requested_load, dtype=np.float64)
    smoothed = np.asarray(smoothed_load, dtype=np.float64)
    if requested.ndim != 1 or requested.size == 0 or requested.shape != smoothed.shape:
        raise ValueError("Requested and smoothed loads must be equally sized non-empty vectors")
    if not np.isfinite(requested).all() or not np.isfinite(smoothed).all():
        raise ValueError("Load windows must be finite")
    if sample_rate_hz <= 0 or window_frames <= 0 or transition_guard_frames < 0 or event_guard_frames < 0:
        raise ValueError("Invalid window or guard size")
    if not 0.0 <= low_boundary < high_boundary <= 1.0:
        raise ValueError("Load class boundaries must be ordered in [0, 1]")

    total_frames = requested.size
    event_intervals = []
    event_guard = np.zeros(total_frames, dtype=bool)
    for event in events:
        start = int(event.get("start_frame", event.get("crop_start_frame", -1)))
        count = int(event.get("sample_count", event.get("samples", 0)))
        if start < 0 or count <= 0 or start + count > total_frames:
            raise ValueError(f"Invalid event interval: {event.get('id', '?')}")
        stop = start + count
        kind = str(event["kind"])
        event_intervals.append((start, stop, kind, str(event.get("id", kind))))
        guard_start = max(0, start - event_guard_frames)
        guard_stop = min(total_frames, stop + event_guard_frames)
        event_guard[guard_start:guard_stop] = True

    transition = np.zeros(total_frames, dtype=bool)
    crossings = []
    for boundary in (low_boundary, high_boundary):
        for index in range(1, total_frames):
            before, after = requested[index - 1], requested[index]
            if (before < boundary <= after) or (after < boundary <= before):
                crossings.append(index)
    for crossing in crossings:
        transition[max(0, crossing - transition_guard_frames):
                   min(total_frames, crossing + transition_guard_frames)] = True

    start_edge = np.zeros(total_frames, dtype=bool)
    start_edge[:min(total_frames, start_guard_frames)] = True
    if stop_guard_frames:
        start_edge[max(0, total_frames - stop_guard_frames):] = True

    windows = []
    for start in range(0, total_frames, window_frames):
        stop = min(total_frames, start + window_frames)
        exact_events = [event for event in event_intervals if event[0] < stop and event[1] > start]
        if exact_events:
            kinds = sorted({event[2] for event in exact_events})
            group = f"event_{kinds[0]}" if len(kinds) == 1 else "event_mixed"
            reason = "event"
        elif transition[start:stop].any():
            group, reason = "boundary", "load_boundary_transition"
        elif event_guard[start:stop].any():
            group, reason = "boundary", "event_guard"
        elif start_edge[start:stop].any():
            group, reason = "boundary", "start_stop_envelope"
        else:
            raw_min = float(np.min(requested[start:stop]))
            raw_max = float(np.max(requested[start:stop]))
            if raw_max < low_boundary:
                group, reason = "low", None
            elif raw_min > high_boundary:
                group, reason = "high", None
            elif raw_min >= low_boundary and raw_max <= high_boundary:
                group, reason = "in_range", None
            else:
                group, reason = "boundary", "load_boundary_crossing"

        windows.append({
            "start_frame": start,
            "end_frame_exclusive": stop,
            "frames": stop - start,
            "group": group,
            "eligible": reason is None and stop - start == window_frames,
            "exclusion_reason": reason or ("partial_window" if stop - start != window_frames else None),
            "event_ids": [event[3] for event in exact_events],
            "requested_min": float(np.min(requested[start:stop])),
            "requested_max": float(np.max(requested[start:stop])),
            "requested_mean": float(np.mean(requested[start:stop])),
            "smoothed_min": float(np.min(smoothed[start:stop])),
            "smoothed_max": float(np.max(smoothed[start:stop])),
            "smoothed_mean": float(np.mean(smoothed[start:stop])),
        })
    return windows


def evaluate_coverage_gate(
    baseline: dict,
    candidate: dict,
    key_bands: tuple[str, ...] | list[str],
    *,
    minimum_windows: int = 5,
    minimum_median_improvement_db: float = 1.0,
) -> dict:
    if baseline.get("stable_window_count", 0) < minimum_windows or \
            candidate.get("stable_window_count", 0) < minimum_windows:
        return {"status": "INSUFFICIENT_STABLE_WINDOWS", "bands": {}}
    results = {}
    passed = True
    for band in key_bands:
        before = baseline.get("bands", {}).get(band)
        after = candidate.get("bands", {}).get(band)
        if before is None or after is None:
            return {"status": "INSUFFICIENT_STABLE_WINDOWS", "bands": results}
        improvement = float(before["absolute_error_median_db"]) - float(after["absolute_error_median_db"])
        p90_non_regression = (
            float(after["absolute_error_p90_db"]) <= float(before["absolute_error_p90_db"])
        )
        band_pass = improvement >= minimum_median_improvement_db and p90_non_regression
        results[band] = {
            "median_improvement_db": improvement,
            "p90_non_regression": p90_non_regression,
            "pass": band_pass,
        }
        passed = passed and band_pass
    return {
        "status": "PASS" if passed else "FAIL",
        "minimum_windows": minimum_windows,
        "minimum_median_improvement_db": minimum_median_improvement_db,
        "bands": results,
    }


def window_feature_db(samples: np.ndarray, sample_rate_hz: int = SAMPLE_RATE_HZ) -> dict[str, float]:
    signal = np.asarray(samples, dtype=np.float64)
    if signal.ndim != 1 or signal.size < 4 or not np.isfinite(signal).all():
        raise ValueError("Spectral analysis requires a finite mono window")
    if sample_rate_hz <= 0:
        raise ValueError("Sample rate must be positive")
    rms = float(np.sqrt(np.mean(np.square(signal))))
    centered = signal - np.mean(signal)
    taper = np.hanning(signal.size)
    power = np.square(np.abs(np.fft.rfft(centered * taper))) / (
        signal.size * float(np.sum(np.square(taper)))
    )
    if signal.size % 2 == 0:
        power[1:-1] *= 2.0
    else:
        power[1:] *= 2.0
    frequency = np.fft.rfftfreq(signal.size, d=1.0 / sample_rate_hz)
    features = {"rms": 20.0 * math.log10(max(rms, 1e-12))}
    for name, lower, upper in (
        ("20-200", 20.0, 200.0),
        ("200-1000", 200.0, 1000.0),
        ("1000-4000", 1000.0, 4000.0),
        ("4000-12000", 4000.0, 12000.0),
    ):
        selected = (frequency >= lower) & (frequency < upper)
        band_power = float(np.sum(power[selected]))
        features[name] = 10.0 * math.log10(max(band_power, 1e-24))
    return features


def _window_feature_table(samples: np.ndarray, window_frames: int) -> dict[str, np.ndarray]:
    signal = np.asarray(samples, dtype=np.float64)
    count = signal.size // window_frames
    if count == 0:
        return {"rms": np.array([], dtype=np.float64)}
    windows = signal[:count * window_frames].reshape(count, window_frames)
    rms = np.sqrt(np.mean(np.square(windows), axis=1))
    taper = np.hanning(window_frames)
    centered = windows - np.mean(windows, axis=1, keepdims=True)
    spectrum = np.fft.rfft(centered * taper, axis=1)
    power = np.square(np.abs(spectrum)) / (window_frames * np.sum(np.square(taper)))
    if window_frames % 2 == 0:
        power[:, 1:-1] *= 2.0
    else:
        power[:, 1:] *= 2.0
    frequency = np.fft.rfftfreq(window_frames, d=1.0 / SAMPLE_RATE_HZ)
    features = {"rms": 20.0 * np.log10(np.maximum(rms, 1e-12))}
    for name, lower, upper in (
        ("20-200", 20.0, 200.0),
        ("200-1000", 200.0, 1000.0),
        ("1000-4000", 1000.0, 4000.0),
        ("4000-12000", 4000.0, 12000.0),
    ):
        selected = (frequency >= lower) & (frequency < upper)
        features[name] = 10.0 * np.log10(np.maximum(np.sum(power[:, selected], axis=1), 1e-24))
    return features


def _summarize_window_group(
    reference_features: dict[str, np.ndarray],
    candidate_features: dict[str, np.ndarray],
    windows: list[dict],
    group: str,
) -> dict:
    chosen = [
        window for window in windows
        if window["group"] == group and (
            window["group"].startswith("event_") or window["eligible"]
        )
    ]
    indices = np.array([window["start_frame"] // 4800 for window in chosen], dtype=np.int64)
    result = {
        "window_count": int(indices.size),
        "duration_s": float(indices.size * 0.1),
        "eligible_stable_window_count": int(sum(window["eligible"] for window in chosen)),
        "stable_window_count": int(sum(window["eligible"] for window in chosen)),
    }
    if indices.size == 0:
        result["bands"] = {}
        return result
    result["requested_load_mean"] = float(np.mean([window["requested_mean"] for window in chosen]))
    result["smoothed_load_mean"] = float(np.mean([window["smoothed_mean"] for window in chosen]))
    bands = {}
    for band in ("rms", "20-200", "200-1000", "1000-4000", "4000-12000"):
        signed = candidate_features[band][indices] - reference_features[band][indices]
        absolute = np.abs(signed)
        bands[band] = {
            "signed_error_median_db": float(np.median(signed)),
            "absolute_error_median_db": float(np.median(absolute)),
            "absolute_error_p90_db": float(np.percentile(absolute, 90)),
        }
    result["bands"] = bands
    return result


def _read_tsv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def _read_f32le(path: Path) -> np.ndarray:
    raw = path.read_bytes()
    if len(raw) != TOTAL_FRAMES * 4:
        raise ValueError(f"Expected exactly {TOTAL_FRAMES} f32le frames: {path}")
    audio = np.frombuffer(raw, dtype="<f4").copy()
    if not np.isfinite(audio).all():
        raise ValueError(f"Non-finite PCM in {path}")
    return audio


def analyze_c63_load_candidates(output_root: Path, source_root: Path) -> dict:
    output_root = output_root.resolve()
    experiment_path = output_root / "experiment.json"
    properties_path = output_root / "inputs" / "experiment.properties"
    if not experiment_path.is_file() or not properties_path.is_file():
        raise FileNotFoundError("Generated C63 experiment and evidence bindings are required")
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    properties = {}
    for line in properties_path.read_text(encoding="utf-8").splitlines():
        key, value = line.split("=", 1)
        properties[key] = value

    app_root = Path(properties["app_root"])
    bank_root = app_root / BANK_ASSET_ROOT / VEHICLE_KEY
    if bank_sha256_inventory(bank_root) != experiment["base_asset_sha256"]:
        raise ValueError("Frozen C63 bank bytes changed after candidate generation")
    if _worktree_snapshot(app_root) != experiment["worktree_snapshot"]:
        raise ValueError("Vico source worktree changed after the frozen experiment snapshot")

    d0_info = experiment["D0_D1_D2"]["D0"]
    d1_info = experiment["D0_D1_D2"]["D1"]
    d2_info = experiment["D0_D1_D2"]["D2"]
    if not d0_info or not d1_info or not d2_info:
        raise ValueError("D0/D1/D2 paths were not bound when candidates were generated")
    d0_raw, d0_rate = sf.read(d0_info["path"], dtype="float32", always_2d=True)
    if d0_rate != SAMPLE_RATE_HZ or d0_raw.shape != (TOTAL_FRAMES + 1, 1):
        raise ValueError("D0 must retain the exact 1,440,001-frame mono reference")
    if sha256_file(Path(d0_info["path"])) != d0_info["sha256"]:
        raise ValueError("D0 source reference changed after generation")
    d0 = d0_raw[:TOTAL_FRAMES, 0].astype(np.float32, copy=False)
    d1 = _read_f32le(Path(d1_info["path"]))
    d2 = _read_f32le(Path(d2_info["path"]))
    if sha256_file(Path(d1_info["path"])) != d1_info["sha256"] or \
            sha256_file(Path(d2_info["path"])) != d2_info["sha256"] or \
            not np.array_equal(d1, d2):
        raise ValueError("Frozen D1/D2 PCM differs from its complete phone capture")

    points = [
        {key: float(row[key]) for key in ("time_s", "rpm", "load", "throttle", "acceleration_mps2")}
        for row in _read_tsv_dicts(output_root / "inputs" / "trace_points.tsv")
    ]
    events = [
        {"id": row["id"], "kind": row["kind"], "start_frame": int(row["crop_start_frame"]),
         "sample_count": int(row["samples"])}
        for row in _read_tsv_dicts(output_root / "inputs" / "events.tsv")
    ]
    stats_rows = {row["variant"]: row for row in _read_tsv_dicts(output_root / "renders" / "render_results.tsv")}
    expected_variants = set(experiment["variants"])
    if set(stats_rows) != expected_variants:
        raise ValueError("Rendered PCM set is incomplete or contains unexpected variants")
    control_rows = {row["variant"]: row for row in _read_tsv_dicts(
        output_root / "renders" / "in_range_control.tsv"
    )}
    if set(control_rows) != expected_variants:
        raise ValueError("In-range PCM control set is incomplete or contains unexpected variants")
    control_sha = control_rows["A"]["pcm_sha256"]
    if any(row["pcm_sha256"] != control_sha or float(row["max_abs_vs_A"]) != 0.0 or
           float(row["rmse_vs_A"]) != 0.0 for row in control_rows.values()):
        raise ValueError("Expanded bank changed PCM for the in-range control trace")

    source_api = exporter._load_source_api(source_root)
    measure_loudness = source_api[4]
    variant_pcm = {"A": _read_f32le(output_root / "renders" / "A.f32le")}
    if sha256_file(output_root / "renders" / "A.f32le") != stats_rows["A"]["pcm_sha256"] or \
            not np.array_equal(variant_pcm["A"], d1):
        raise ValueError("A renderer output differs from the frozen D1 PCM")
    reference_metrics = measure_loudness(d0, SAMPLE_RATE_HZ)

    window_frames = 4800
    baseline_bounds = tuple(experiment["base_load_levels"])
    classified_by_variant = {}
    trajectories = {}
    variant_stats = {}
    for variant, variant_info in experiment["variants"].items():
        lower, upper = min(variant_info["load_levels"]), max(variant_info["load_levels"])
        requested, clamped, smoothed = build_renderer_load_trajectory(
            points, lower, upper, total_frames=TOTAL_FRAMES,
        )
        trajectories[variant] = {
            "requested": requested,
            "clamped": clamped,
            "smoothed": smoothed,
            "low_out_of_bank_frames": int(np.count_nonzero(requested < lower)),
            "high_out_of_bank_frames": int(np.count_nonzero(requested > upper)),
        }
        mix_row = stats_rows[variant]
        measured_out = int(mix_row["load_out_of_bank_frames"])
        predicted_out = (trajectories[variant]["low_out_of_bank_frames"] +
                         trajectories[variant]["high_out_of_bank_frames"])
        if measured_out != predicted_out:
            raise ValueError(f"Renderer and trace load-overflow frame counts disagree for {variant}")
        variant_stats[variant] = {
            "evaluated_frames": int(mix_row["evaluated_frames"]),
            "pre_clip_peak": float(mix_row["pre_clip_peak"]),
            "above_contract_frames": int(mix_row["above_contract_frames"]),
            "hard_clip_frames": int(mix_row["hard_clip_frames"]),
            "non_finite_frames": int(mix_row["non_finite_frames"]),
            "load_out_of_bank_frames": measured_out,
            "low_out_of_bank_frames": trajectories[variant]["low_out_of_bank_frames"],
            "high_out_of_bank_frames": trajectories[variant]["high_out_of_bank_frames"],
            "rpm_out_of_bank_frames": int(mix_row["rpm_out_of_bank_frames"]),
            "max_abs_vs_phone_d1": float(mix_row["max_abs_vs_phone_d1"]),
            "rmse_vs_phone_d1": float(mix_row["rmse_vs_phone_d1"]),
        }
        if variant != "A":
            pcm_path = output_root / "renders" / f"{variant}.f32le"
            if sha256_file(pcm_path) != mix_row["pcm_sha256"]:
                raise ValueError(f"Rendered PCM SHA mismatch for {variant}")
            variant_pcm[variant] = _read_f32le(pcm_path)
        classified_by_variant[variant] = classify_load_windows(
            requested, smoothed, events, low_boundary=baseline_bounds[0],
            high_boundary=baseline_bounds[-1], window_frames=window_frames,
        )

    if variant_stats["A"]["max_abs_vs_phone_d1"] > float(properties["d1_max_abs_tolerance"]) or \
            variant_stats["A"]["rmse_vs_phone_d1"] > float(properties["d1_rmse_tolerance"]):
        raise ValueError("A baseline renderer no longer reproduces the frozen phone D1 within tolerance")
    if variant_stats["A"]["hard_clip_frames"] or variant_stats["A"]["non_finite_frames"]:
        raise ValueError("A baseline renderer violates finite/pre-clip integrity gates")

    full_pcm_metrics = {
        "D0": {
            "source_file_sha256": d0_info["sha256"],
            "comparison_pcm_sha256": sha256_bytes(np.asarray(d0, dtype="<f4").tobytes()),
            "source_frames": int(d0_raw.shape[0]), "comparison_frames": TOTAL_FRAMES,
        },
        "D1": {"sha256": d1_info["sha256"], "frames": TOTAL_FRAMES},
        "D2": {"sha256": d2_info["sha256"], "frames": TOTAL_FRAMES},
    }
    for label, pcm in {"D0": d0, "D1": d1, "D2": d2, **variant_pcm}.items():
        metrics = measure_loudness(pcm, SAMPLE_RATE_HZ)
        full_pcm_metrics.setdefault(label, {}).update({
            "sha256": sha256_bytes(np.asarray(pcm, dtype="<f4").tobytes()),
            "frames": int(pcm.size),
            "lufs": float(metrics.integrated_lufs),
            "rms_dbfs": float(metrics.rms_dbfs),
            "peak_dbfs": float(metrics.peak_dbfs),
        })

    feature_tables = {
        "D0": _window_feature_table(d0, window_frames),
        **{variant: _window_feature_table(pcm, window_frames) for variant, pcm in variant_pcm.items()},
    }
    groups = ("low", "in_range", "high", "event_shift", "event_afterfire")
    window_metrics = {}
    for variant, windows in classified_by_variant.items():
        window_metrics[variant] = {
            group: _summarize_window_group(feature_tables["D0"], feature_tables[variant], windows, group)
            for group in groups
        }
    window_partition = {
        variant: {
            "total_windows": len(windows),
            "groups": {group: sum(window["group"] == group for window in windows)
                       for group in sorted({window["group"] for window in windows})},
            "exclusions": {
                reason: sum(window["exclusion_reason"] == reason for window in windows)
                for reason in sorted({window["exclusion_reason"] for window in windows if window["exclusion_reason"]})
            },
        }
        for variant, windows in classified_by_variant.items()
    }

    gates = {
        "B-low": evaluate_coverage_gate(
            window_metrics["A"]["low"], window_metrics["B-low"]["low"],
            ("200-1000", "1000-4000"),
        ) if "B-low" in window_metrics else {"status": "NOT_GENERATED"},
        "B-high": evaluate_coverage_gate(
            window_metrics["A"]["high"], window_metrics["B-high"]["high"],
            ("1000-4000",),
        ) if "B-high" in window_metrics else {"status": "NOT_GENERATED"},
        "B-both-low": evaluate_coverage_gate(
            window_metrics["A"]["low"], window_metrics["B-both"]["low"],
            ("200-1000", "1000-4000"),
        ) if "B-both" in window_metrics else {"status": "NOT_GENERATED"},
        "B-both-high": evaluate_coverage_gate(
            window_metrics["A"]["high"], window_metrics["B-both"]["high"],
            ("1000-4000",),
        ) if "B-both" in window_metrics else {"status": "NOT_GENERATED"},
    }
    low_pass = gates["B-low"]["status"] == "PASS"
    high_pass = gates["B-high"]["status"] == "PASS"
    both_pass = (gates["B-both-low"]["status"] == "PASS" and
                 gates["B-both-high"]["status"] == "PASS")
    if low_pass and high_pass and both_pass:
        conclusion, selected = "DIGITAL_LOAD_COVERAGE_SUPPORTED", "B-both"
    elif low_pass:
        conclusion, selected = "DIGITAL_LOW_LOAD_COVERAGE_SUPPORTED", "B-low"
    elif high_pass:
        conclusion, selected = "DIGITAL_HIGH_LOAD_COVERAGE_SUPPORTED", "B-high"
    elif both_pass:
        conclusion, selected = "DIGITAL_COMBINED_LOAD_COVERAGE_SUPPORTED", "B-both"
    elif any(gate["status"] == "FAIL" for gate in gates.values()):
        conclusion, selected = "LOAD_COVERAGE_IS_NOT_SUFFICIENT_CAUSE", None
    else:
        conclusion, selected = "INSUFFICIENT_STABLE_WINDOWS", None

    analysis = {
        "schema": "vico.s13.c63_load_ablation_analysis.v1",
        "status": "ANALYZED_DIGITAL_ONLY",
        "conclusion": conclusion,
        "selected_variant_for_phone_replay": selected,
        "evidence_domain": "digital PCM; not speaker loopback or human/true-car similarity",
        "window_contract": {
            "window_frames": window_frames,
            "window_seconds": window_frames / SAMPLE_RATE_HZ,
            "transition_guard_seconds": 0.2,
            "event_guard_seconds": 0.2,
            "start_guard_seconds": 0.2,
            "stop_guard_seconds": 0.4,
            "stable_minimum_windows": 5,
            "bands_hz": [[20, 200], [200, 1000], [1000, 4000], [4000, 12000]],
            "no_concatenated_windows": True,
        },
        "full_window_metrics": full_pcm_metrics,
        "in_range_control": {
            "all_variants_byte_identical": True,
            "sha256": control_sha,
            "variants": {
                variant: {
                    "frames": int(row["frames"]),
                    "pcm_sha256": row["pcm_sha256"],
                    "max_abs_vs_A": float(row["max_abs_vs_A"]),
                    "rmse_vs_A": float(row["rmse_vs_A"]),
                }
                for variant, row in control_rows.items()
            },
        },
        "renderer_stats": variant_stats,
        "load_window_metrics": window_metrics,
        "window_partition": window_partition,
        "coverage_gates": gates,
        "limitations": [
            "The 0.98 C63 load interval overlaps afterfire; event windows are reported separately.",
            "The load-only experiment does not model independent throttle or alter loop-seam representation.",
            "Human audition, physical output, real-car/OEM similarity, and other-vehicle phone replay remain pending.",
        ],
    }
    metrics_path = output_root / "metrics.json"
    metrics_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    report_path = output_root / "analysis.md"
    lines = [
        "# S13 C63 load-coverage controlled ablation",
        "",
        f"- Conclusion: `{conclusion}`",
        f"- Selected for phone replay: `{selected or 'NONE'}`",
        f"- D0/D1/D2 were SHA-bound; the Kotlin A renderer reproduced D1 exactly before B variants.",
        f"- Old C63 bank files: {len(experiment['base_asset_sha256'])} SHA-bound files; unchanged at analysis time.",
        f"- Candidate loops: {len(experiment['candidate_asset_sha256'])}, generated with fixed gain `{experiment['fixed_vehicle_gain']}`.",
        "- This report covers digital PCM only, not speaker loopback, human acceptance, or true-car/OEM similarity.",
        "",
        "| Variant | Low OOB frames | High OOB frames | Hard clips | Non-finite | RMSE vs phone D1 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for variant, stats in variant_stats.items():
        lines.append(
            f"| {variant} | {stats['low_out_of_bank_frames']} | {stats['high_out_of_bank_frames']} | "
            f"{stats['hard_clip_frames']} | {stats['non_finite_frames']} | {stats['rmse_vs_phone_d1']:.8g} |"
        )
    lines.extend(["", "## Pre-registered coverage gates", ""])
    for name, gate in gates.items():
        lines.append(f"- `{name}`: `{gate['status']}`")
    lines.extend(["", "## Stable-window counts", ""])
    for variant, groups in window_metrics.items():
        low_count = groups["low"]["stable_window_count"]
        mid_count = groups["in_range"]["stable_window_count"]
        high_count = groups["high"]["stable_window_count"]
        lines.append(f"- `{variant}`: low={low_count}, in-range={mid_count}, high={high_count} 100ms windows")
    lines.extend([
        "",
        "Candidate assets remain isolated under `candidate_assets/`; production S12 WAVs, vehicle gain, EQ, reference PCM, and renderer code were not edited.",
    ])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    experiment["status"] = "ANALYZED_DIGITAL_ONLY"
    experiment["analysis_path"] = metrics_path.name
    experiment["analysis_sha256"] = sha256_file(metrics_path)
    experiment["report_path"] = report_path.name
    experiment["report_sha256"] = sha256_file(report_path)
    experiment_path = output_root / "experiment.json"
    experiment_path.write_text(json.dumps(experiment, indent=2), encoding="utf-8")
    return analysis


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--source-root", type=Path, default=Path(r"E:\Tesla_speed\prj\tools"))
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--analyze", action="store_true", help="Analyze the Kotlin-rendered PCM variants in output-root")
    parser.add_argument("--d0", type=Path)
    parser.add_argument("--d1", type=Path)
    parser.add_argument("--d2", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.analyze:
        analysis = analyze_c63_load_candidates(args.output_root, args.source_root)
        print(json.dumps({
            "status": analysis["status"],
            "conclusion": analysis["conclusion"],
            "selected_variant_for_phone_replay": analysis["selected_variant_for_phone_replay"],
            "coverage_gates": {name: result["status"] for name, result in analysis["coverage_gates"].items()},
            "analysis_path": str(args.output_root.resolve() / "metrics.json"),
        }, indent=2))
        return
    result = generate_c63_load_candidates(
        app_root=args.app_root,
        source_root=args.source_root,
        output_root=args.output_root,
        d0_path=args.d0,
        d1_path=args.d1,
        d2_path=args.d2,
        receipt_path=args.receipt,
    )
    print(json.dumps({
        "status": result["status"],
        "output_root": str(args.output_root.resolve()),
        "candidate_count": len(result["candidate_asset_paths"]),
        "trace_load_bounds": [result["minimum_trace_load"], result["maximum_trace_load"]],
        "fixed_vehicle_gain": result["fixed_vehicle_gain"],
        "dirty_path_count": result["vico_dirty_path_count"],
    }, indent=2))


if __name__ == "__main__":
    main()
