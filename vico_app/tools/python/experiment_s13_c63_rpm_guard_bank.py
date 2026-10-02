"""Generate and analyze the bounded C63 5400/5600 RPM guard candidate."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import soundfile as sf

import experiment_s13_c63_anchor_resonance as resonance
import experiment_s13_c63_load_coverage as coverage
import export_s12_android_sound_banks as exporter


VEHICLE_KEY = "c63_w204_v6"
SAMPLE_RATE_HZ = 48_000
CONDITION_FRAMES = 4 * SAMPLE_RATE_HZ
WINDOW_FRAMES = 4_800
TOTAL_FRAMES = 1_440_000
ANCHOR_RPM = 5_500
CANDIDATE_RPMS = (5_400, 5_600)
LOADS = (0.32, 0.92)
HOLDOUT_RPMS = (5_450, 5_550)
ALLOWED_OUTPUT_ROOT = Path(r"E:\Claude_allow\Download")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def _canonical_inventory_sha(inventory: dict[str, str]) -> str:
    payload = json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(payload)


def _require_external_root(output_root: Path, app_root: Path, production_root: Path) -> Path:
    output_root = output_root.resolve()
    if output_root == app_root or app_root in output_root.parents:
        raise ValueError("Candidate output must stay outside the Vico repository")
    if output_root == production_root or production_root in output_root.parents:
        raise ValueError("Candidate output must stay outside the production bank")
    try:
        output_root.relative_to(ALLOWED_OUTPUT_ROOT.resolve())
    except ValueError as error:
        raise ValueError("Candidate output must remain under E:\\Claude_allow\\Download") from error
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"Candidate output root is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    return output_root


def _generate_loop(source_root: Path, rpm: float, load: float, fixed_gain: float) -> np.ndarray:
    (
        vehicle_state_trace, _build_drive_cycle_trace, _detect_shift_events,
        _manage_bundle_loudness, _measure_loudness, renderers, apply_ptr,
        _edge_fade, render_stateful,
    ) = exporter._load_source_api(source_root)
    trace = exporter._constant_trace(vehicle_state_trace, rpm, load, 0.52)
    rendered = render_stateful(renderers["c63_w204"], "c63_w204", trace)
    loop = exporter._loop(exporter._mono_48k(apply_ptr(rendered.pressure)))
    return coverage.apply_fixed_gain(loop, fixed_gain)


def _parent_loop_rows(r4_root: Path) -> list[dict[str, str]]:
    rows = _read_tsv(r4_root / "variants" / "A" / "loops.tsv")
    if len(rows) != 16 or {int(row["rpm"]) for row in rows} != {700, 1400, 2200, 3200, 4300, 5500, 6800, 7200}:
        raise ValueError("Frozen parent bank must contain the original eight RPM anchors")
    return rows


def prepare_candidate(resonance_root: Path, output_root: Path) -> dict:
    resonance_root = resonance_root.resolve()
    phase = json.loads((resonance_root / "phase.json").read_text(encoding="utf-8"))
    metrics = json.loads((resonance_root / "anchor_resonance_metrics.json").read_text(encoding="utf-8"))
    if metrics.get("conclusion") != "5500_STATIONARY_RESONANCE_TRANSFER_SUPPORTED":
        raise ValueError("Weighted S13.5 support gate is not satisfied; refuse candidate generation")
    support = metrics.get("support_gate", {})
    if support.get("share_fraction_ge_0p8", 0.0) < 0.6 or len(support.get("share_intervals", [])) < 2:
        raise ValueError("Weighted 5500 share gate is not satisfied in both RPM intervals")

    app_root = Path(phase["app_root"]).resolve()
    source_root = Path(phase["source_root"]).resolve()
    r4_root = Path(phase["r4_root"]).resolve()
    r3_root = Path(phase["r3_root"]).resolve()
    r4_experiment = json.loads((r4_root / "experiment.json").read_text(encoding="utf-8"))
    properties = resonance._read_properties(r4_root / "inputs" / "experiment.properties")
    fixed_gain = float(properties["fixed_vehicle_gain"])
    production_root = app_root / coverage.BANK_ASSET_ROOT / VEHICLE_KEY
    output_root = _require_external_root(output_root, app_root, production_root)
    parent_inventory = coverage.bank_sha256_inventory(production_root)
    if parent_inventory != r4_experiment["base_asset_sha256"]:
        raise ValueError("Original C63 production bank changed before candidate generation")
    parent_rows = _parent_loop_rows(r4_root)

    loop_root = output_root / "loops"
    loop_root.mkdir(parents=True, exist_ok=True)
    new_rows = []
    for rpm in CANDIDATE_RPMS:
        for load in LOADS:
            filename = f"rpm_{int(rpm):04d}_load_{int(load * 100):02d}.wav"
            path = loop_root / filename
            samples = _generate_loop(source_root, rpm, load, fixed_gain)
            sf.write(path, samples, SAMPLE_RATE_HZ, subtype="FLOAT", format="WAV")
            decoded, rate = sf.read(path, dtype="float32", always_2d=False)
            decoded = np.asarray(decoded, dtype=np.float32)
            if rate != SAMPLE_RATE_HZ or decoded.size != 17_280 or not np.isfinite(decoded).all():
                raise ValueError(f"Invalid generated candidate loop: {filename}")
            if float(np.max(np.abs(decoded))) > 10 ** (-1.5 / 20.0):
                raise ValueError(f"Candidate loop exceeds the fixed peak limit: {filename}")
            new_rows.append({
                "source": "candidate", "path": f"loops/{filename}", "rpm": str(int(rpm)),
                "load": str(load), "sha256": sha256_file(path), "frames": str(decoded.size),
            })

    loop_rows = [
        {**row, "frames": "17280"} for row in parent_rows
    ] + new_rows
    with (output_root / "loops.tsv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["source", "path", "rpm", "load", "sha256", "frames"],
                                delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(loop_rows)

    parent_manifest = production_root / "manifest.json"
    candidate_manifest = {
        "schema": "vico.s13.c63.rpm_guard_candidate.v1",
        "vehicle_key": VEHICLE_KEY,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "fixed_vehicle_gain": fixed_gain,
        "source_commit": properties["source_commit"],
        "parent_bank_manifest_sha256": sha256_file(parent_manifest),
        "parent_bank_inventory_sha256": _canonical_inventory_sha(parent_inventory),
        "parent_rpm_levels": sorted({int(row["rpm"]) for row in parent_rows}),
        "new_rpm_levels": list(CANDIDATE_RPMS),
        "loads": list(LOADS),
        "loop_manifest": "loops.tsv",
        "new_loops": new_rows,
        "candidate_status": "PREPARED_EXTERNAL_ONLY",
    }
    _write_json(output_root / "candidate_manifest.json", candidate_manifest)
    manifest_sha = sha256_file(output_root / "candidate_manifest.json")
    (output_root / "phase.properties").write_text(
        "\n".join([
            f"resonance_root={resonance_root.as_posix()}",
            f"r4_root={r4_root.as_posix()}",
            f"r3_root={r3_root.as_posix()}",
            f"app_root={app_root.as_posix()}",
            f"source_root={source_root.as_posix()}",
            f"candidate_manifest_sha256={manifest_sha}",
            f"parent_bank_manifest_sha256={candidate_manifest['parent_bank_manifest_sha256']}",
            f"parent_bank_inventory_sha256={candidate_manifest['parent_bank_inventory_sha256']}",
            f"fixed_vehicle_gain={fixed_gain}",
        ]) + "\n", encoding="utf-8",
    )
    result = {
        "schema": "vico.s13.c63.rpm_guard_bank.v1",
        "status": "CANDIDATE_PREPARED",
        "candidate_root": output_root.as_posix(),
        "candidate_manifest_sha256": manifest_sha,
        "parent_bank_manifest_sha256": candidate_manifest["parent_bank_manifest_sha256"],
        "parent_bank_inventory_sha256": candidate_manifest["parent_bank_inventory_sha256"],
        "new_loops": new_rows,
        "original_5500_loop_reproduction": resonance.reproduce_original_5500_loops(
            app_root, source_root, fixed_gain,
        ),
    }
    _write_json(output_root / "candidate_preparation.json", result)
    return result


def _read_float_file(root: Path, entry: dict) -> np.ndarray:
    raw = (root / entry["path"]).read_bytes()
    if sha256_bytes(raw) != entry["sha256"]:
        raise ValueError(f"Candidate capture SHA changed: {entry['path']}")
    return np.frombuffer(raw, dtype="<f4").astype(np.float64)


def _band_errors(reference: np.ndarray, rendered: np.ndarray, windows: list[tuple[int, int]], band: str) -> list[float]:
    return [abs(resonance.window_band_db(rendered[start:end], band) -
                resonance.window_band_db(reference[start:end], band)) for start, end in windows]


def _error_summary(values: list[float]) -> dict:
    return {
        "median_db": float(np.median(values)) if values else None,
        "p90_db": float(np.percentile(values, 90)) if values else None,
        "count": len(values),
    }


def evaluate_error_gate(
    improvements: list[float], a_errors: list[float], b_errors: list[float],
    *, minimum_median_improvement_db: float, minimum_strict_improvement_fraction: float,
) -> dict:
    if not improvements or len(improvements) != len(a_errors) or len(a_errors) != len(b_errors):
        return {"pass": False, "reason": "EMPTY_OR_MISMATCHED_WINDOW_SET"}
    strict_fraction = float(np.mean(np.asarray(improvements, dtype=np.float64) > 0.0))
    result = {
        "pass": bool(
            float(np.median(improvements)) >= minimum_median_improvement_db and
            float(np.percentile(b_errors, 90)) <= float(np.percentile(a_errors, 90)) and
            strict_fraction >= minimum_strict_improvement_fraction
        ),
        "improvement": _error_summary(improvements),
        "a_error": _error_summary(a_errors),
        "b_error": _error_summary(b_errors),
        "strict_improved_fraction": strict_fraction,
        "minimum_median_improvement_db": minimum_median_improvement_db,
        "minimum_strict_improvement_fraction": minimum_strict_improvement_fraction,
        "p90_not_worse": float(np.percentile(b_errors, 90)) <= float(np.percentile(a_errors, 90)),
    }
    return result


def evaluate_protection_gate(rows: list[dict], max_regression_db: float = 0.5) -> dict:
    if not rows:
        return {"pass": False, "reason": "NO_PROTECTION_ROWS", "rows": []}
    evaluated = []
    for row in rows:
        a, b = row["A"], row["B"]
        median_regression = float(b["median_db"]) - float(a["median_db"])
        p90_regression = float(b["p90_db"]) - float(a["p90_db"])
        evaluated.append({
            "scope": row["scope"], "band": row["band"],
            "median_regression_db": median_regression,
            "p90_regression_db": p90_regression,
            "pass": median_regression <= max_regression_db and p90_regression <= max_regression_db,
            "A": a, "B": b,
        })
    return {
        "pass": all(row["pass"] for row in evaluated),
        "max_regression_db": max_regression_db,
        "rows": evaluated,
    }


def _load_frozen_d0(r4_root: Path) -> tuple[np.ndarray, dict]:
    experiment = json.loads((r4_root / "experiment.json").read_text(encoding="utf-8"))
    identity = experiment["D0_D1_D2"]["D0"]
    path = Path(identity["path"])
    if sha256_file(path) != identity["sha256"]:
        raise ValueError("Frozen D0 SHA changed")
    samples, rate = sf.read(path, dtype="float32", always_2d=False)
    samples = np.asarray(samples, dtype=np.float64)
    if rate != SAMPLE_RATE_HZ or samples.size != int(identity["frames"]):
        raise ValueError("Frozen D0 rate or frame count changed")
    if not np.isfinite(samples).all():
        raise ValueError("Frozen D0 contains non-finite samples")
    return samples[:TOTAL_FRAMES], identity


def _source_controls(source_root: Path, trace_root: Path, fixed_gain: float) -> dict[str, np.ndarray]:
    (
        vehicle_state_trace, _build_drive_cycle_trace, _detect_shift_events,
        _manage_bundle_loudness, _measure_loudness, renderers, apply_ptr,
        _edge_fade, render_stateful,
    ) = exporter._load_source_api(source_root)
    controls = {}
    for rpm in (*HOLDOUT_RPMS, *resonance.TARGET_RPMS):
        for load in LOADS:
            trace = exporter._constant_trace(vehicle_state_trace, rpm, load, 4.0)
            rendered = render_stateful(renderers["c63_w204"], "c63_w204", trace)
            controls[f"rpm_{int(rpm)}_load_{int(load * 100)}"] = (
                exporter._mono_48k(apply_ptr(rendered.pressure))[:CONDITION_FRAMES].astype(np.float64) * fixed_gain
            )
    return controls


def analyze_candidate(output_root: Path) -> dict:
    output_root = output_root.resolve()
    properties = resonance._read_properties(output_root / "phase.properties")
    candidate = json.loads((output_root / "candidate_manifest.json").read_text(encoding="utf-8"))
    capture = json.loads((output_root / "candidate_capture_manifest.json").read_text(encoding="utf-8"))
    if capture.get("schema") != "vico.s13.c63.rpm_guard_capture.v2":
        raise ValueError("Candidate capture must use the v2 safety-bound schema")
    if capture.get("candidate_manifest_sha256") != properties["candidate_manifest_sha256"]:
        raise ValueError("Candidate capture is not bound to the prepared candidate manifest")
    app_root = Path(properties["app_root"])
    source_root = Path(properties["source_root"])
    r4_root = Path(properties["r4_root"])
    r3_root = Path(properties["r3_root"])
    r4_experiment = json.loads((r4_root / "experiment.json").read_text(encoding="utf-8"))
    d1_identity = r4_experiment["D0_D1_D2"]["D1"]
    if capture.get("frozen_d1_sha256") != d1_identity["sha256"]:
        raise ValueError("Candidate capture is not bound to frozen D1")
    controls = _source_controls(source_root, r4_root, float(properties["fixed_vehicle_gain"]))
    d0, d0_identity = _load_frozen_d0(r4_root)
    if d0_identity["frames"] < TOTAL_FRAMES:
        raise ValueError("Frozen D0 is shorter than the review interval")
    windows = resonance.stable_condition_windows(
        total_frames=CONDITION_FRAMES, sample_rate_hz=SAMPLE_RATE_HZ,
        warmup_seconds=1.0, end_guard_seconds=0.0, window_frames=WINDOW_FRAMES,
    )
    fixed = {}
    primary_b_improvement = []
    protection_rows = []
    for condition, entry in capture["fixed_conditions"].items():
        rpm = int(entry["rpm"])
        load_key = f"load_{int(float(entry['load']) * 100)}"
        reference = controls[f"rpm_{rpm}_load_{int(float(entry['load']) * 100)}"]
        a = _read_float_file(output_root, entry["a_pcm"])
        b = _read_float_file(output_root, entry["b_pcm"])
        if a.size != CONDITION_FRAMES or b.size != CONDITION_FRAMES:
            raise ValueError(f"Unexpected fixed-condition frame count: {condition}")
        a_values = _band_errors(reference, a, windows, "1000-4000")
        b_values = _band_errors(reference, b, windows, "1000-4000")
        primary_gate = evaluate_error_gate(
            [left - right for left, right in zip(a_values, b_values)], a_values, b_values,
            minimum_median_improvement_db=6.0, minimum_strict_improvement_fraction=0.6,
        )
        fixed[condition] = {
            "rpm": rpm, "load": float(entry["load"]), "load_key": load_key,
            "primary_1_4khz": {"A": _error_summary(a_values), "B": _error_summary(b_values),
                                "improvement_median_db": float(np.median(a_values) - np.median(b_values)),
                                "gate": primary_gate},
            "protected_bands": {
                band: {
                    "A": _error_summary(_band_errors(reference, a, windows, band)),
                    "B": _error_summary(_band_errors(reference, b, windows, band)),
                }
                for band in ("20-200", "200-1000", "4000-12000")
            },
        }
        for band, values in fixed[condition]["protected_bands"].items():
            protection_rows.append({"scope": f"fixed:{condition}", "band": band, **values})
        if rpm in (5200, 6100):
            primary_b_improvement.append(primary_gate["improvement"]["median_db"])

    holdout = {}
    for condition, entry in capture["holdout_conditions"].items():
        rpm = int(entry["rpm"])
        reference = controls[f"rpm_{rpm}_load_{int(float(entry['load']) * 100)}"]
        a = _read_float_file(output_root, entry["a_pcm"])
        b = _read_float_file(output_root, entry["b_pcm"])
        a_values = _band_errors(reference, a, windows, "1000-4000")
        b_values = _band_errors(reference, b, windows, "1000-4000")
        protected = {
            band: {
                "A": _error_summary(_band_errors(reference, a, windows, band)),
                "B": _error_summary(_band_errors(reference, b, windows, band)),
            }
            for band in ("20-200", "200-1000", "4000-12000")
        }
        holdout[condition] = {
            "A": _error_summary(a_values), "B": _error_summary(b_values),
            "protected_bands": protected,
            "gate": bool(_error_summary(b_values)["median_db"] <= 3.0 and
                          _error_summary(b_values)["p90_db"] <= 6.0),
        }
        for band, values in protected.items():
            protection_rows.append({"scope": f"holdout:{condition}", "band": band, **values})

    a_dynamic = _read_float_file(output_root, capture["dynamic"]["a_pcm"])
    b_dynamic = _read_float_file(output_root, capture["dynamic"]["b_pcm"])
    if capture["dynamic"].get("stats") is None:
        raise ValueError("Dynamic capture safety statistics are missing")
    dynamic_stats = capture["dynamic"]["stats"]
    safety_gate = {
        "pass": bool(
            dynamic_stats["a"]["evaluated_frames"] == TOTAL_FRAMES and
            dynamic_stats["b"]["evaluated_frames"] == TOTAL_FRAMES and
            dynamic_stats["a"]["hard_clip_frames"] == 0 and
            dynamic_stats["b"]["hard_clip_frames"] == 0 and
            dynamic_stats["a"]["non_finite_frames"] == 0 and
            dynamic_stats["b"]["non_finite_frames"] == 0
        ),
        "stats": dynamic_stats,
    }
    if not safety_gate["pass"]:
        raise ValueError("Dynamic capture safety gate failed")
    if capture["dynamic"]["a_pcm"]["sha256"] != d1_identity["sha256"]:
        raise ValueError("Candidate A dynamic PCM no longer reproduces frozen D1")

    descriptive_windows = resonance.stable_condition_windows(
        total_frames=TOTAL_FRAMES, sample_rate_hz=SAMPLE_RATE_HZ,
        warmup_seconds=1.0, end_guard_seconds=1.0, window_frames=WINDOW_FRAMES,
    )
    phase = json.loads((Path(properties["resonance_root"]) / "phase.json").read_text(encoding="utf-8"))
    frozen_rows = _read_tsv(r3_root / "windows.tsv")
    frozen_windows = [
        (int(row["start_frame"]), int(row["end_frame_exclusive"])) for row in frozen_rows
    ]
    share_ids = {int(row["window_index"]) for row in phase.get("share_windows", [])}
    target44_windows = [
        window for row, window in zip(frozen_rows, frozen_windows) if int(row["window_index"]) in share_ids
    ]
    if len(target44_windows) != 44:
        raise ValueError("Frozen 44-window target set changed")
    def window_gate(windows_for_gate: list[tuple[int, int]], minimum: float = 3.0) -> dict:
        a_values = _band_errors(d0, a_dynamic, windows_for_gate, "1000-4000")
        b_values = _band_errors(d0, b_dynamic, windows_for_gate, "1000-4000")
        return evaluate_error_gate(
            [left - right for left, right in zip(a_values, b_values)], a_values, b_values,
            minimum_median_improvement_db=minimum, minimum_strict_improvement_fraction=0.6,
        )
    main44_gate = window_gate(target44_windows)
    frozen75_gate = window_gate(frozen_windows)
    descriptive_gate = window_gate(descriptive_windows)
    frozen_protection = {
        band: {
            "A": _error_summary(_band_errors(d0, a_dynamic, frozen_windows, band)),
            "B": _error_summary(_band_errors(d0, b_dynamic, frozen_windows, band)),
        }
        for band in ("20-200", "200-1000", "4000-12000")
    }
    for band in ("20-200", "200-1000", "4000-12000"):
        protection_rows.append({"scope": "dynamic:44", "band": band,
                                "A": _error_summary(_band_errors(d0, a_dynamic, target44_windows, band)),
                                "B": _error_summary(_band_errors(d0, b_dynamic, target44_windows, band))})
    protection_gate = evaluate_protection_gate(protection_rows)
    event_windows = {}
    for event in _read_tsv(Path(properties["r4_root"]) / "inputs" / "events.tsv"):
        center = int(event["source_frame"])
        start = max(0, center - int(0.10 * SAMPLE_RATE_HZ))
        end = min(TOTAL_FRAMES, center + int(0.25 * SAMPLE_RATE_HZ))
        event_windows[event["id"]] = {
            "kind": event["kind"],
            "source_frame": center,
            "A": _error_summary(_band_errors(d0, a_dynamic, [(start, end)], "1000-4000")),
            "B": _error_summary(_band_errors(d0, b_dynamic, [(start, end)], "1000-4000")),
        }
    fixed_improvement_gate = min(primary_b_improvement or [float("-inf")]) >= 6.0
    holdout_gate = all(row["gate"] for row in holdout.values())
    source_reference_gate = bool(d0_identity["sha256"] == r4_experiment["D0_D1_D2"]["D0"]["sha256"])
    all_gates = {
        "fixed_neighbor_improvement": fixed_improvement_gate,
        "holdout_5450_5550": holdout_gate,
        "main_44_window_improvement": main44_gate["pass"],
        "frozen_75_window_description": frozen75_gate["pass"],
        "protection_bands": protection_gate["pass"],
        "dynamic_safety": safety_gate["pass"],
        "frozen_d0_binding": source_reference_gate,
    }
    result = {
        "schema": "vico.s13.c63.rpm_guard_analysis.v2",
        "status": "ANALYZED_DIGITAL_ONLY",
        "candidate_status": "C63_RPM_GUARD_CANDIDATE_DIGITALLY_QUALIFIED"
        if
        all(all_gates.values())
        else "CANDIDATE_REJECTED",
        "candidate_manifest_sha256": properties["candidate_manifest_sha256"],
        "parent_bank_manifest_sha256": candidate["parent_bank_manifest_sha256"],
        "parent_bank_inventory_sha256": candidate["parent_bank_inventory_sha256"],
        "fixed_conditions": fixed,
        "holdout_conditions": holdout,
        "dynamic_window_1_29_descriptive": descriptive_gate,
        "main_44_windows": main44_gate,
        "frozen_75_windows": {
            "count": len(frozen_windows),
            **frozen75_gate,
            "protected_bands": frozen_protection,
        },
        "event_windows": event_windows,
        "protection_gate": protection_gate,
        "dynamic_safety": safety_gate,
        "gate_results": all_gates,
        "frozen_d0": d0_identity,
        "original_5500_loop_reproduction": resonance.reproduce_original_5500_loops(
            app_root, source_root, float(properties["fixed_vehicle_gain"]),
        ),
        "limitations": [
            "Digital candidate only; no production bank replacement, APK, install or audition.",
            "The candidate does not establish speaker, true-car, OEM or human similarity.",
        ],
    }
    _write_json(output_root / "rpm_guard_candidate_metrics.json", result)
    report = [
        "# S13.5 C63 local RPM guard candidate",
        "",
        f"- Candidate status: `{result['candidate_status']}`",
        f"- Candidate manifest SHA: `{result['candidate_manifest_sha256']}`",
        f"- Fixed 5200/6100 1–4 kHz minimum median improvement: {min(primary_b_improvement or [float('nan')]):.3f} dB.",
        f"- Main frozen 44-window gate: {result['main_44_windows']['pass']}; median improvement {result['main_44_windows']['improvement']['median_db']:.3f} dB; strict fraction {result['main_44_windows']['strict_improved_fraction']:.1%}.",
        f"- Frozen 75-window descriptive gate: {result['frozen_75_windows']['pass']}.",
        f"- Protection gate: {result['protection_gate']['pass']}; rows {len(result['protection_gate']['rows'])}.",
        f"- D0 binding: {result['gate_results']['frozen_d0_binding']}; dynamic safety: {result['gate_results']['dynamic_safety']}.",
        f"- Gate results: {result['gate_results']}.",
        "- Original 5500 loops remain exact and production assets remain untouched.",
        "- No APK build/install or human listening was performed.",
    ]
    (output_root / "rpm_guard_candidate_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resonance-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--analyze", action="store_true")
    args = parser.parse_args()
    if args.prepare == args.analyze:
        parser.error("choose exactly one of --prepare or --analyze")
    result = prepare_candidate(args.resonance_root, args.output_root) if args.prepare else analyze_candidate(args.output_root)
    print(json.dumps({key: result.get(key) for key in ("status", "candidate_status", "candidate_root", "candidate_manifest_sha256")}, indent=2))


if __name__ == "__main__":
    main()
