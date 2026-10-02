"""Prepare and analyze a test-only C63 anchor-interpolation coherence diagnostic."""

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

import experiment_s13_c63_load_coverage as coverage


SAMPLE_RATE_HZ = 48_000
WINDOW_FRAMES = 4_800
TOTAL_FRAMES = 1_440_000
VEHICLE_KEY = "c63_w204_v6"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def summarize_signed_residual(values: list[float] | np.ndarray, minimum_windows: int = 5) -> dict:
    signed = np.asarray(values, dtype=np.float64)
    if signed.ndim != 1 or not np.isfinite(signed).all():
        raise ValueError("Signed residuals must be a finite vector")
    positive = int(np.count_nonzero(signed > 0.0))
    negative = int(np.count_nonzero(signed < 0.0))
    zero = int(signed.size - positive - negative)
    count = int(signed.size)
    return {
        "window_count": count,
        "median_signed_db": float(np.median(signed)) if count else None,
        "positive_windows": positive,
        "negative_windows": negative,
        "zero_windows": zero,
        "positive_fraction": positive / count if count else 0.0,
        "negative_fraction": negative / count if count else 0.0,
        "status": "READY" if count >= minimum_windows else "INSUFFICIENT_STABLE_WINDOWS",
    }


def coherent_cross_term_db(
    components: list[np.ndarray], sample_rate_hz: int = SAMPLE_RATE_HZ,
    band: str = "1000-4000",
) -> float:
    if len(components) < 2:
        raise ValueError("At least two anchor contributions are required")
    arrays = [np.asarray(value, dtype=np.float64) for value in components]
    if any(array.ndim != 1 or array.shape != arrays[0].shape or not np.isfinite(array).all()
           for array in arrays):
        raise ValueError("Anchor contributions must be equal-sized finite mono windows")
    mixed = np.sum(np.stack(arrays), axis=0)
    mixed_power_db = coverage.window_feature_db(mixed, sample_rate_hz)[band]
    individual_power_db = [coverage.window_feature_db(value, sample_rate_hz)[band] for value in arrays]
    incoherent_power = float(np.sum(np.power(10.0, np.asarray(individual_power_db) / 10.0)))
    incoherent_db = 10.0 * math.log10(max(incoherent_power, 1e-24))
    return mixed_power_db - incoherent_db


def evaluate_anchor_coherence(
    residual: dict,
    cross_term: dict,
    *,
    minimum_windows: int = 5,
    minimum_sign_fraction: float = 0.75,
    minimum_cross_term_db: float = 1.0,
) -> dict:
    if residual.get("window_count", 0) < minimum_windows or \
            cross_term.get("window_count", 0) < minimum_windows:
        return {"status": "INSUFFICIENT_STABLE_WINDOWS"}
    residual_median = float(residual["median_signed_db"])
    residual_direction = "positive" if residual_median > 0.0 else "negative" if residual_median < 0.0 else "zero"
    if residual["positive_fraction"] < minimum_sign_fraction or residual_median <= 0.0:
        return {
            "status": "RESIDUAL_SIGN_NOT_ESTABLISHED",
            "residual_direction": residual_direction,
            "required_sign_fraction": minimum_sign_fraction,
        }
    cross_median = float(cross_term["median_cross_term_db"])
    if cross_term["positive_fraction"] < minimum_sign_fraction or cross_median < minimum_cross_term_db:
        return {
            "status": "ANCHOR_COHERENCE_NOT_ESTABLISHED",
            "residual_direction": residual_direction,
            "required_cross_term_db": minimum_cross_term_db,
            "required_positive_fraction": minimum_sign_fraction,
        }
    return {
        "status": "SUPPORTS_FURTHER_PHASE_ABLATION",
        "residual_direction": residual_direction,
        "required_cross_term_db": minimum_cross_term_db,
        "required_positive_fraction": minimum_sign_fraction,
    }


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def _write_tsv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _worktree_snapshot(repo_root: Path) -> dict:
    status = subprocess.check_output(
        ["git", "-C", str(repo_root), "status", "--porcelain=v1", "--untracked-files=all"],
        text=True,
        encoding="utf-8",
    ).strip()
    paths = []
    for line in status.splitlines():
        if len(line) < 4:
            continue
        relative = line[3:]
        path = repo_root / Path(relative.replace("/", "\\"))
        paths.append({"status": line[:2], "path": relative,
                      "sha256": sha256_file(path) if path.is_file() else None})
    branch = subprocess.check_output(
        ["git", "-C", str(repo_root), "branch", "--show-current"], text=True, encoding="utf-8",
    ).strip()
    head = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True, encoding="utf-8",
    ).strip()
    return {"branch": branch, "head": head, "dirty_path_count": len(paths), "paths": paths}


def _validate_r4(r4_root: Path) -> tuple[dict, dict, dict, dict]:
    experiment_path = r4_root / "experiment.json"
    metrics_path = r4_root / "metrics.json"
    props_path = r4_root / "inputs" / "experiment.properties"
    if not all(path.is_file() for path in (experiment_path, metrics_path, props_path)):
        raise FileNotFoundError("Completed r4 C63 experiment artifacts are required")
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    if experiment.get("status") != "ANALYZED_DIGITAL_ONLY":
        raise ValueError("r4 C63 load-coverage experiment is not fully analyzed")
    if experiment.get("analysis_sha256") != sha256_file(metrics_path):
        raise ValueError("r4 metrics SHA does not match the experiment manifest")
    properties = {}
    for line in props_path.read_text(encoding="utf-8").splitlines():
        key, value = line.split("=", 1)
        properties[key] = value
    return experiment, metrics, properties, json.loads((r4_root / "worktree_snapshot.json").read_text(encoding="utf-8"))


def prepare_anchor_windows(r4_root: Path, output_root: Path) -> dict:
    r4_root, output_root = r4_root.resolve(), output_root.resolve()
    experiment, metrics, properties, _ = _validate_r4(r4_root)
    app_root = Path(properties["app_root"])
    bank_root = app_root / coverage.BANK_ASSET_ROOT / VEHICLE_KEY
    output_root = coverage.validate_candidate_root(output_root, bank_root)
    if app_root in output_root.parents:
        raise ValueError("Anchor-coherence outputs must be outside the Vico repository")
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"Anchor-coherence output root is not empty: {output_root}")
    if coverage.bank_sha256_inventory(bank_root) != experiment["base_asset_sha256"]:
        raise ValueError("Frozen C63 bank changed after S13.2")
    if properties["source_commit"] != coverage.SOURCE_COMMIT:
        raise ValueError("r4 experiment is bound to an unexpected source commit")

    trace_rows = _read_tsv(r4_root / "inputs" / "trace_points.tsv")
    points = [{key: float(row[key]) for key in (
        "time_s", "rpm", "load", "throttle", "acceleration_mps2",
    )} for row in trace_rows]
    events = [{"id": row["id"], "kind": row["kind"],
               "start_frame": int(row["crop_start_frame"]), "sample_count": int(row["samples"])}
              for row in _read_tsv(r4_root / "inputs" / "events.tsv")]
    requested, _, smoothed = coverage.build_renderer_load_trajectory(
        points, 0.32, 0.92, total_frames=TOTAL_FRAMES,
    )
    windows = coverage.classify_load_windows(requested, smoothed, events)
    stable = [window for window in windows if window["group"] == "in_range" and window["eligible"]]
    if len(stable) < 5:
        raise ValueError("Insufficient stable in-range windows for anchor-coherence analysis")

    output_root.mkdir(parents=True, exist_ok=True)
    _write_tsv(
        output_root / "windows.tsv",
        ["window_index", "start_frame", "end_frame_exclusive", "requested_mean", "smoothed_mean"],
        [[index, window["start_frame"], window["end_frame_exclusive"],
          window["requested_mean"], window["smoothed_mean"]]
         for index, window in enumerate(stable)],
    )
    snapshot = _worktree_snapshot(app_root)
    _write_json(output_root / "source_snapshot.json", snapshot)
    phase = {
        "schema": "vico.s13.c63_anchor_coherence.v1",
        "status": "WINDOWS_PREPARED",
        "r4_root": r4_root.as_posix(),
        "r4_metrics_sha256": sha256_file(r4_root / "metrics.json"),
        "r4_experiment_sha256": sha256_file(r4_root / "experiment.json"),
        "vico_worktree_snapshot_sha256": sha256_file(output_root / "source_snapshot.json"),
        "vico_head": snapshot["head"],
        "vico_branch": snapshot["branch"],
        "dirty_path_count": snapshot["dirty_path_count"],
        "bank_asset_sha256": experiment["base_asset_sha256"],
        "stable_in_range_window_count": len(stable),
        "window_frames": 4_800,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "d0_sha256": experiment["D0_D1_D2"]["D0"]["sha256"],
        "d1_sha256": experiment["D0_D1_D2"]["D1"]["sha256"],
        "trace_sha256": experiment["trace_sha256"],
        "event_schedule_sha256": experiment["event_schedule_sha256"],
    }
    _write_json(output_root / "phase.json", phase)
    coverage._write_properties(output_root / "phase.properties", {
        "app_root": app_root,
        "r4_root": r4_root,
        "anchor_output_root": output_root,
        "vehicle_key": VEHICLE_KEY,
        "source_commit": experiment["source_commit"],
        "trace_sha256": experiment["trace_sha256"],
        "manifest_sha256": experiment["bank_manifest_sha256"],
        "event_schedule_sha256": experiment["event_schedule_sha256"],
        "stable_window_count": len(stable),
        "window_frames": WINDOW_FRAMES,
        "total_frames": TOTAL_FRAMES,
        "d0_path": experiment["D0_D1_D2"]["D0"]["path"],
        "phone_a_path": (r4_root / "renders" / "A.f32le"),
    })
    return phase


def analyze_anchor_components(output_root: Path) -> dict:
    output_root = output_root.resolve()
    phase_path = output_root / "phase.json"
    if not phase_path.is_file():
        raise FileNotFoundError("Anchor-coherence window manifest is required")
    phase = json.loads(phase_path.read_text(encoding="utf-8"))
    r4_root = Path(phase["r4_root"])
    experiment, metrics, properties, _ = _validate_r4(r4_root)
    app_root = Path(properties["app_root"])
    recorded_source_snapshot = json.loads((output_root / "source_snapshot.json").read_text(encoding="utf-8"))
    if _worktree_snapshot(app_root) != recorded_source_snapshot:
        raise ValueError("Vico source worktree changed during the anchor-component capture")
    bank_root = app_root / coverage.BANK_ASSET_ROOT / VEHICLE_KEY
    current_snapshot = _worktree_snapshot(app_root)
    recorded_snapshot = json.loads((output_root / "source_snapshot.json").read_text(encoding="utf-8"))
    if current_snapshot != recorded_snapshot:
        raise ValueError("Vico source worktree changed during anchor-coherence capture")
    if coverage.bank_sha256_inventory(bank_root) != phase["bank_asset_sha256"]:
        raise ValueError("Original C63 bank changed during anchor-coherence capture")
    if sha256_file(r4_root / "metrics.json") != phase["r4_metrics_sha256"]:
        raise ValueError("r4 metrics changed during anchor-coherence capture")

    window_rows = _read_tsv(output_root / "windows.tsv")
    if len(window_rows) != phase["stable_in_range_window_count"]:
        raise ValueError("Stable-window manifest count changed")
    component_rows = _read_tsv(output_root / "components.tsv")
    expected_anchors = {(int(row["rpm"]), float(row["load"]))
                        for row in _read_tsv(r4_root / "variants" / "A" / "loops.tsv")}
    if {(int(row["rpm"]), float(row["load"])) for row in component_rows} != expected_anchors:
        raise ValueError("Anchor contribution inventory is incomplete")

    window_count = len(window_rows)
    window_frames = int(phase["window_frames"])
    expected_samples = window_count * window_frames
    components = {}
    for row in component_rows:
        path = output_root / row["path"]
        raw = path.read_bytes()
        if sha256_bytes(raw) != row["sha256"] or len(raw) != expected_samples * 4:
            raise ValueError(f"Anchor PCM shape or SHA mismatch: {path.name}")
        components[(int(row["rpm"]), float(row["load"]))] = np.frombuffer(raw, dtype="<f4").reshape(
            window_count, window_frames,
        ).astype(np.float64)

    component_sum = np.sum(np.stack(list(components.values())), axis=0)
    renderer_mix_raw = (output_root / "renderer_mix_stable_windows.f32le").read_bytes()
    phone_a_raw = (output_root / "phone_A_stable_windows.f32le").read_bytes()
    if len(renderer_mix_raw) != expected_samples * 4 or len(phone_a_raw) != expected_samples * 4:
        raise ValueError("Stable-window mixture PCM has an incomplete frame count")
    renderer_mix = np.frombuffer(renderer_mix_raw, dtype="<f4").reshape(window_count, window_frames).astype(np.float64)
    phone_a = np.frombuffer(phone_a_raw, dtype="<f4").reshape(window_count, window_frames).astype(np.float64)
    component_error = component_sum - renderer_mix
    phone_error = renderer_mix - phone_a
    component_max = float(np.max(np.abs(component_error)))
    component_rmse = float(np.sqrt(np.mean(np.square(component_error))))
    phone_max = float(np.max(np.abs(phone_error)))
    phone_rmse = float(np.sqrt(np.mean(np.square(phone_error))))
    if component_max > 2e-5 or component_rmse > 2e-6:
        raise ValueError("Anchor contributions do not reconstruct the continuous-only renderer")
    if phone_max > 2e-5 or phone_rmse > 2e-6:
        raise ValueError("Eventless A renderer differs inside the frozen stable windows")

    d0_info = experiment["D0_D1_D2"]["D0"]
    d0_full, d0_rate = sf.read(d0_info["path"], dtype="float32", always_2d=True)
    if d0_rate != SAMPLE_RATE_HZ or d0_full.shape != (TOTAL_FRAMES + 1, 1):
        raise ValueError("D0 comparison support changed")
    d0 = d0_full[:TOTAL_FRAMES, 0]
    starts = [int(row["start_frame"]) for row in window_rows]
    bands = []
    for window_index, start in enumerate(starts):
        d0_feature = coverage.window_feature_db(d0[start:start + window_frames])
        a_feature = coverage.window_feature_db(phone_a[window_index])
        components_for_window = [values[window_index] for values in components.values()]
        cross_db = coherent_cross_term_db(components_for_window, band="1000-4000")
        active = sum(
            coverage.window_feature_db(values[window_index])["1000-4000"] > -80.0
            for values in components.values()
        )
        bands.append({
            "start_frame": start,
            "signed_d0_to_a_1_4khz_db": a_feature["1000-4000"] - d0_feature["1000-4000"],
            "coherent_cross_term_1_4khz_db": cross_db,
            "active_anchor_count": int(active),
        })
    residual = summarize_signed_residual(
        [row["signed_d0_to_a_1_4khz_db"] for row in bands], minimum_windows=5,
    )
    cross_terms = [row["coherent_cross_term_1_4khz_db"] for row in bands]
    coherence = summarize_signed_residual(cross_terms, minimum_windows=5)
    coherence["median_cross_term_db"] = coherence.pop("median_signed_db")
    support = evaluate_anchor_coherence(residual, coherence)
    summary = {
        "schema": "vico.s13.c63_anchor_coherence_analysis.v1",
        "status": "ANCHOR_COHERENCE_DIAGNOSTIC_COMPLETE",
        "conclusion": support["status"],
        "support_gate": support,
        "stable_window_count": window_count,
        "residual_sign": residual,
        "coherent_cross_term": coherence,
        "component_reconstruction": {
            "max_abs_vs_continuous_renderer": component_max,
            "rmse_vs_continuous_renderer": component_rmse,
            "max_abs_vs_frozen_phone_a": phone_max,
            "rmse_vs_frozen_phone_a": phone_rmse,
            "production_renderer_modified": False,
            "original_bank_modified": False,
        },
        "per_window": bands,
        "limitations": [
            "This diagnostic measures current anchor-mixture coherence; it does not alter renderer code or bank assets.",
            "High-load non-event windows remain insufficient; no inference is made for the high edge.",
            "Positive coherence is not proof of perceptual or true-car similarity.",
        ],
    }
    metrics_path = output_root / "anchor_coherence_metrics.json"
    _write_json(metrics_path, summary)
    report = [
        "# S13.3 C63 anchor-interpolation coherence diagnostic",
        "",
        f"- Conclusion: `{support['status']}`",
        f"- Signed D0→A 1–4 kHz median: {residual['median_signed_db']:.3f} dB; positive windows: {residual['positive_fraction']:.1%}.",
        f"- Coherent cross-term 1–4 kHz median: {coherence['median_cross_term_db']:.3f} dB; positive windows: {coherence['positive_fraction']:.1%}.",
        f"- Stable in-range windows: {window_count}; high-load non-event windows remain insufficient.",
        f"- Anchor-sum reconstruction: max-abs {component_max:.3g}, RMSE {component_rmse:.3g}.",
        "- No production renderer, S12 bank, gain/EQ, APK, or phone state was changed.",
        "- This is a diagnostic result only; it is not a perceptual fix or human/true-car acceptance.",
    ]
    (output_root / "anchor_coherence_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r4-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--analyze", action="store_true")
    args = parser.parse_args()
    if args.analyze:
        result = analyze_anchor_components(args.output_root)
        print(json.dumps({
            "status": result["status"],
            "conclusion": result["conclusion"],
            "stable_window_count": result["stable_window_count"],
            "residual_sign": result["residual_sign"],
            "coherent_cross_term": result["coherent_cross_term"],
            "report_path": str(args.output_root.resolve() / "anchor_coherence_report.md"),
        }, indent=2))
    else:
        result = prepare_anchor_windows(args.r4_root, args.output_root)
        print(json.dumps({
            "status": result["status"],
            "output_root": str(args.output_root.resolve()),
            "stable_in_range_window_count": result["stable_in_range_window_count"],
            "trace_sha256": result["trace_sha256"],
        }, indent=2))


if __name__ == "__main__":
    main()
