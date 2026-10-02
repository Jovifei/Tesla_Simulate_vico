"""Capture and analyze a test-only C63 RPM-blend cross-term diagnostic."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import soundfile as sf

import analyze_s13_c63_anchor_coherence as anchor
import experiment_s13_c63_load_coverage as coverage


SAMPLE_RATE_HZ = 48_000
TOTAL_FRAMES = 1_440_000
WINDOW_FRAMES = 4_800
VEHICLE_KEY = "c63_w204_v6"
EXPECTED_R4_EXPERIMENT_SHA256 = "8fd92ebc4ee716d62f728a82f07c6cafdb7936520ffba3a100ab04c87f8c01d0"
EXPECTED_R4_SNAPSHOT_SHA256 = "cebdf8a3392c7834e655dfbfe3e3432d444bf09ab5e885061267fa8ad2223136"
ALLOWED_OUTPUT_ROOT = Path(r"E:\Claude_allow\Download")
BANDS = ("200-1000", "1000-4000")
DIAGNOSTIC_SOURCE_FILES = (
    "Project/android/app/src/main/java/com/vico/simulator/sound/MatlabStatefulBankRenderer.kt",
    "Project/android/app/src/main/java/com/vico/simulator/sound/S13ReviewSession.kt",
    "Project/android/app/src/main/java/com/vico/simulator/sound/S13ReviewContract.kt",
    "Project/android/app/src/main/java/com/vico/simulator/sound/S13ReviewPackageLoader.kt",
    "Project/android/app/src/main/java/com/vico/simulator/sound/MatlabSoundBank.kt",
    "Project/android/app/src/main/java/com/vico/simulator/sound/FloatWavDecoder.kt",
    "Project/android/app/src/main/java/com/vico/simulator/sound/MatlabPowertrainController.kt",
    "Project/android/app/src/main/java/com/vico/simulator/sound/SoundModel.kt",
    "Project/android/app/src/test/java/com/vico/simulator/sound/MatlabStatefulBankRendererTest.kt",
    "Project/android/app/src/test/java/com/vico/simulator/sound/S13C63RpmCrossTermTest.kt",
    "tools/python/experiment_s13_c63_rpm_cross_term.py",
    "tools/python/test_s13_c63_rpm_cross_term.py",
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _read_properties(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            result[key] = value
    return result


def _diagnostic_source_snapshot(repo_root: Path) -> dict:
    files = []
    for relative in DIAGNOSTIC_SOURCE_FILES:
        path = repo_root / Path(relative)
        if not path.is_file():
            raise FileNotFoundError(f"Required S13.4 source is missing: {relative}")
        files.append({"path": relative, "sha256": sha256_file(path)})
    return {
        "branch": coverage._git_value(repo_root, "branch", "--show-current"),
        "head": coverage._git_value(repo_root, "rev-parse", "HEAD"),
        "files": files,
    }


def _validate_frozen_inputs(r4_root: Path, anchor_root: Path) -> tuple[dict, dict, dict]:
    experiment_path = r4_root / "experiment.json"
    snapshot_path = r4_root / "worktree_snapshot.json"
    anchor_phase_path = anchor_root / "phase.json"
    anchor_metrics_path = anchor_root / "anchor_coherence_metrics.json"
    if not all(path.is_file() for path in (
        experiment_path, snapshot_path, anchor_phase_path, anchor_metrics_path,
        anchor_root / "windows.tsv", anchor_root / "source_snapshot.json",
    )):
        raise FileNotFoundError("Frozen S13.2/S13.3 C63 evidence is incomplete")
    experiment_sha = sha256_file(experiment_path)
    snapshot_sha = sha256_file(snapshot_path)
    if experiment_sha != EXPECTED_R4_EXPERIMENT_SHA256:
        raise ValueError("S13.2 r4 experiment manifest SHA changed")
    if snapshot_sha != EXPECTED_R4_SNAPSHOT_SHA256:
        raise ValueError("S13.2 dirty worktree snapshot SHA changed")
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    phase = json.loads(anchor_phase_path.read_text(encoding="utf-8"))
    metrics = json.loads(anchor_metrics_path.read_text(encoding="utf-8"))
    if experiment.get("status") != "ANALYZED_DIGITAL_ONLY":
        raise ValueError("S13.2 C63 evidence is not complete")
    if experiment.get("analysis_sha256") != sha256_file(r4_root / "metrics.json"):
        raise ValueError("S13.2 metrics do not match their manifest")
    if phase.get("r4_experiment_sha256") != experiment_sha:
        raise ValueError("S13.3 phase is not bound to the frozen r4 experiment")
    if phase.get("vico_worktree_snapshot_sha256") != sha256_file(anchor_root / "source_snapshot.json"):
        raise ValueError("S13.3 source snapshot SHA is inconsistent")
    if phase.get("stable_in_range_window_count") != 75 or metrics.get("stable_window_count") != 75:
        raise ValueError("The frozen 75-window S13.3 support changed")
    if metrics.get("conclusion") != "SUPPORTS_FURTHER_PHASE_ABLATION":
        raise ValueError("S13.3 diagnostic no longer supports this bounded attribution step")
    if experiment.get("D0_D1_D2", {}).get("D1", {}).get("sha256") != \
            "127f2c08a9977e43510633bbbad44ee989f7d112b79d5876bff99b99a7ef0b4f":
        raise ValueError("Frozen D1 identity changed")
    return experiment, phase, metrics


def prepare_capture(r4_root: Path, anchor_root: Path, output_root: Path) -> dict:
    r4_root, anchor_root, output_root = (
        path.resolve() for path in (r4_root, anchor_root, output_root)
    )
    try:
        output_root.relative_to(ALLOWED_OUTPUT_ROOT.resolve())
    except ValueError as error:
        raise ValueError("S13.4 outputs must stay under E:\\Claude_allow\\Download") from error
    experiment, anchor_phase, _ = _validate_frozen_inputs(r4_root, anchor_root)
    r4_properties = _read_properties(r4_root / "inputs" / "experiment.properties")
    app_root = Path(r4_properties["app_root"]).resolve()
    bank_root = app_root / coverage.BANK_ASSET_ROOT / VEHICLE_KEY
    output_root = coverage.validate_candidate_root(output_root, bank_root)
    if app_root in output_root.parents:
        raise ValueError("S13.4 evidence must remain outside the Vico repository")
    if not bank_root.is_dir() or coverage.bank_sha256_inventory(bank_root) != experiment["base_asset_sha256"]:
        raise ValueError("Original C63 production bank differs from the frozen S13.2 inventory")

    anchor_snapshot = json.loads((anchor_root / "source_snapshot.json").read_text(encoding="utf-8"))
    full_snapshot = coverage._worktree_snapshot(app_root)
    source_snapshot = _diagnostic_source_snapshot(app_root)
    if source_snapshot["branch"] != anchor_snapshot["branch"] or \
            source_snapshot["head"] != anchor_snapshot["head"]:
        raise ValueError("Vico branch or HEAD changed since the S13.3 capture")
    _write_json(output_root / "worktree_snapshot.json", full_snapshot)
    source_snapshot_path = output_root / "source_code_snapshot.json"
    _write_json(source_snapshot_path, source_snapshot)
    windows_bytes = (anchor_root / "windows.tsv").read_bytes()
    (output_root / "windows.tsv").write_bytes(windows_bytes)

    d0 = experiment["D0_D1_D2"]["D0"]
    d1 = experiment["D0_D1_D2"]["D1"]
    phase = {
        "schema": "vico.s13.c63_rpm_cross_term.v1",
        "status": "CAPTURE_PREPARED",
        "vehicle_key": VEHICLE_KEY,
        "r4_root": r4_root.as_posix(),
        "anchor_root": anchor_root.as_posix(),
        "app_root": app_root.as_posix(),
        "r4_experiment_sha256": sha256_file(r4_root / "experiment.json"),
        "r4_snapshot_sha256": sha256_file(r4_root / "worktree_snapshot.json"),
        "r4_metrics_sha256": sha256_file(r4_root / "metrics.json"),
        "anchor_phase_sha256": sha256_file(anchor_root / "phase.json"),
        "anchor_metrics_sha256": sha256_file(anchor_root / "anchor_coherence_metrics.json"),
        "anchor_windows_sha256": sha256_bytes(windows_bytes),
        "source_snapshot_sha256": sha256_file(source_snapshot_path),
        "vico_head": source_snapshot["head"],
        "vico_branch": source_snapshot["branch"],
        "dirty_path_count": full_snapshot["dirty_path_count"],
        "worktree_snapshot_sha256": sha256_file(output_root / "worktree_snapshot.json"),
        "bank_asset_sha256": experiment["base_asset_sha256"],
        "trace_sha256": experiment["trace_sha256"],
        "event_schedule_sha256": experiment["event_schedule_sha256"],
        "d0_path": d0["path"],
        "d0_sha256": d0["sha256"],
        "d0_frames": d0["frames"],
        "d1_path": d1["path"],
        "d1_sha256": d1["sha256"],
        "d1_frames": d1["frames"],
        "fixed_vehicle_gain": experiment["fixed_vehicle_gain"],
        "window_count": 75,
        "window_frames": WINDOW_FRAMES,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "total_frames": TOTAL_FRAMES,
        "rpm_levels": sorted({int(row["rpm"]) for row in anchor._read_tsv(
            r4_root / "variants" / "A" / "loops.tsv",
        )}),
        "qualification": {
            "minimum_mixed_fraction": 0.8,
            "weight_min": 0.2,
            "weight_max": 0.8,
            "minimum_windows": 20,
            "minimum_adjacent_rpm_intervals": 2,
            "minimum_1_4khz_median_improvement_db": 1.0,
            "minimum_1_4khz_improved_window_fraction": 0.6,
            "lower_band_median_and_p90_must_not_regress": True,
        },
        "limitations": [
            "Pno_cross is an energy-domain counterfactual; it is never PCM or a playable candidate.",
            "High-load windows, production sound-path changes, APK changes, and phone audition are out of scope.",
        ],
    }
    _write_json(output_root / "phase.json", phase)
    coverage._write_properties(output_root / "phase.properties", {
        "app_root": app_root,
        "r4_root": r4_root,
        "anchor_root": anchor_root,
        "output_root": output_root,
        "source_snapshot_sha256": phase["source_snapshot_sha256"],
        "r4_experiment_sha256": phase["r4_experiment_sha256"],
        "anchor_phase_sha256": phase["anchor_phase_sha256"],
        "anchor_windows_sha256": phase["anchor_windows_sha256"],
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "total_frames": TOTAL_FRAMES,
    })
    return phase


def _validate_vectors(*values: np.ndarray) -> tuple[np.ndarray, ...]:
    arrays = tuple(np.asarray(value, dtype=np.float64) for value in values)
    if not arrays or any(array.ndim != 1 or array.shape != arrays[0].shape for array in arrays):
        raise ValueError("RPM cross-term inputs must be equal-sized mono windows")
    if arrays[0].size < 4 or any(not np.isfinite(array).all() for array in arrays):
        raise ValueError("RPM cross-term windows must be finite and contain at least four frames")
    return arrays


def _spectrum_pair(left: np.ndarray, right: np.ndarray, sample_rate_hz: int) -> tuple[dict, dict, dict]:
    if sample_rate_hz <= 0:
        raise ValueError("Sample rate must be positive")
    size = left.size
    taper = np.hanning(size)
    norm = size * float(np.sum(np.square(taper)))
    left_fft = np.fft.rfft((left - np.mean(left)) * taper)
    right_fft = np.fft.rfft((right - np.mean(right)) * taper)
    left_power = np.square(np.abs(left_fft)) / norm
    right_power = np.square(np.abs(right_fft)) / norm
    cross_power = np.real(left_fft * np.conjugate(right_fft)) / norm
    one_sided = np.ones(left_power.shape, dtype=np.float64)
    one_sided[1:-1 if size % 2 == 0 else None] = 2.0
    frequency = np.fft.rfftfreq(size, d=1.0 / sample_rate_hz)
    result = []
    for power in (left_power, right_power, cross_power):
        result.append({
            band: float(np.sum(power[(frequency >= lower) & (frequency < upper)] * one_sided[
                (frequency >= lower) & (frequency < upper)
            ]))
            for band, lower, upper in (
                ("200-1000", 200.0, 1_000.0),
                ("1000-4000", 1_000.0, 4_000.0),
            )
        })
    return result[0], result[1], result[2]


def _db(power: float) -> float:
    return 10.0 * math.log10(max(power, 1e-24))


def analyze_window(
    lower_path: np.ndarray,
    upper_path: np.ndarray,
    rpm_weight: np.ndarray,
    shared_gain: np.ndarray,
    renderer_mix: np.ndarray,
    desktop_reference: np.ndarray,
    *,
    event_contribution: np.ndarray | None = None,
    sample_rate_hz: int = SAMPLE_RATE_HZ,
) -> dict:
    lower, upper, weight, gain, mix, desktop = _validate_vectors(
        lower_path, upper_path, rpm_weight, shared_gain, renderer_mix, desktop_reference,
    )
    if np.any(weight < 0.0) or np.any(weight > 1.0) or np.any(gain < 0.0):
        raise ValueError("RPM weights and common gain are outside their renderer domain")
    if np.max(np.abs(mix)) >= 1.0:
        raise ValueError("clipped renderer samples cannot support the cross-term estimate")
    events = np.zeros(mix.shape, dtype=np.float64) if event_contribution is None else \
        _validate_vectors(event_contribution)[0]
    if events.shape != mix.shape:
        raise ValueError("Event contribution has a different sample window")

    lower_contribution = (1.0 - weight) * lower * gain
    upper_contribution = weight * upper * gain
    reconstructed = lower_contribution + upper_contribution + events
    reconstruction_max = float(np.max(np.abs(reconstructed - mix)))
    if reconstruction_max > 1e-6:
        raise ValueError(f"RPM paths do not reconstruct the renderer mix: {reconstruction_max:.3g}")

    lower_power, upper_power, cross_power = _spectrum_pair(
        lower_contribution, upper_contribution, sample_rate_hz,
    )
    desktop_features = coverage.window_feature_db(desktop, sample_rate_hz)
    mix_features = coverage.window_feature_db(mix, sample_rate_hz)
    bands = {}
    for band in BANDS:
        no_cross_power = lower_power[band] + upper_power[band]
        coherent_power = no_cross_power + 2.0 * cross_power[band]
        if coherent_power < -1e-12:
            raise ValueError("Cross-term formula produced negative coherent power")
        coherent_db = _db(coherent_power)
        no_cross_db = _db(no_cross_power)
        if coherent_power > max(1e-24, no_cross_power * 1e-10) and \
                abs(coherent_db - mix_features[band]) > 0.02:
            raise ValueError("Cross-term spectrum does not share the renderer window normalization")
        coherent_error = abs(coherent_db - desktop_features[band])
        no_cross_error = abs(no_cross_db - desktop_features[band])
        bands[band] = {
            "lower_path_power": lower_power[band],
            "upper_path_power": upper_power[band],
            "cross_power": cross_power[band],
            "no_cross_power": no_cross_power,
            "coherent_power": max(coherent_power, 0.0),
            "cross_term_db": coherent_db - no_cross_db,
            "coherent_db": coherent_db,
            "no_cross_db": no_cross_db,
            "desktop_db": desktop_features[band],
            "coherent_residual_db": coherent_db - desktop_features[band],
            "coherent_error_db": coherent_error,
            "no_cross_error_db": no_cross_error,
            "error_improvement_db": coherent_error - no_cross_error,
        }
    return {"frames": int(mix.size), "reconstruction_max_abs": reconstruction_max, "bands": bands}


def classify_mixed_window(
    lower_index: np.ndarray,
    upper_index: np.ndarray,
    rpm_weight: np.ndarray,
    *,
    minimum_fraction: float = 0.8,
    weight_min: float = 0.2,
    weight_max: float = 0.8,
) -> dict:
    lower, upper, weight = _validate_vectors(lower_index, upper_index, rpm_weight)
    if np.any(lower < 0) or np.any(upper < 0) or np.any(weight < 0) or np.any(weight > 1):
        raise ValueError("RPM anchor indices or blend weights are invalid")
    mask = (upper == lower + 1) & (weight >= weight_min) & (weight <= weight_max)
    fraction = float(np.mean(mask))
    if not np.any(mask):
        return {"qualifies": False, "mixed_fraction": fraction, "rpm_interval_index": None}
    intervals, counts = np.unique(lower[mask].astype(np.int64), return_counts=True)
    dominant = int(intervals[np.argmax(counts)])
    return {
        "qualifies": fraction >= minimum_fraction,
        "mixed_fraction": fraction,
        "rpm_interval_index": dominant,
        "mixed_interval_frames": {str(int(level)): int(count) for level, count in zip(intervals, counts)},
    }


def evaluate_support_gate(windows: list[dict]) -> dict:
    valid = [item for item in windows if item.get("qualifies")]
    intervals = sorted({int(item["rpm_interval_index"]) for item in valid})
    if len(valid) < 20 or len(intervals) < 2:
        return {
            "status": "INSUFFICIENT_MIXED_RPM_WINDOWS",
            "valid_window_count": len(valid),
            "rpm_interval_indices": intervals,
            "required_windows": 20,
            "required_intervals": 2,
        }

    metrics = {}
    passed = True
    for band in BANDS:
        coherent = np.asarray([item["bands"][band]["coherent_error_db"] for item in valid])
        no_cross = np.asarray([item["bands"][band]["no_cross_error_db"] for item in valid])
        residual = np.asarray([item["bands"][band]["coherent_residual_db"] for item in valid])
        cross_term = np.asarray([item["bands"][band]["cross_term_db"] for item in valid])
        improvements = coherent - no_cross
        median_improvement = float(np.median(improvements))
        improved_fraction = float(np.mean(improvements > 0.0))
        median_no_worse = float(np.median(no_cross)) <= float(np.median(coherent))
        p90_no_worse = float(np.percentile(no_cross, 90)) <= float(np.percentile(coherent, 90))
        if band == "1000-4000":
            band_pass = median_improvement >= 1.0 and p90_no_worse and improved_fraction >= 0.6
        else:
            band_pass = median_no_worse and p90_no_worse
        metrics[band] = {
            "coherent_residual_median_db": float(np.median(residual)),
            "coherent_residual_positive_fraction": float(np.mean(residual > 0.0)),
            "cross_term_median_db": float(np.median(cross_term)),
            "cross_term_positive_fraction": float(np.mean(cross_term > 0.0)),
            "coherent_error_median_db": float(np.median(coherent)),
            "no_cross_error_median_db": float(np.median(no_cross)),
            "coherent_error_p90_db": float(np.percentile(coherent, 90)),
            "no_cross_error_p90_db": float(np.percentile(no_cross, 90)),
            "median_improvement_db": median_improvement,
            "improved_window_fraction": improved_fraction,
            "pass": band_pass,
        }
        passed = passed and band_pass
    return {
        "status": "RPM_CROSS_TERM_IS_A_MATERIAL_CONTRIBUTOR" if passed
        else "RPM_COHERENT_CROSS_TERM_NOT_SUPPORTED",
        "valid_window_count": len(valid),
        "rpm_interval_indices": intervals,
        "bands": metrics,
        "audio_fix_demonstrated": False,
    }


def _read_f32le(path: Path, frames: int) -> np.ndarray:
    raw = path.read_bytes()
    if len(raw) != frames * 4:
        raise ValueError(f"Unexpected float32 frame count: {path}")
    return np.frombuffer(raw, dtype="<f4").astype(np.float64)


def _read_capture_array(root: Path, manifest: dict, name: str, frames: int) -> np.ndarray:
    entry = manifest.get("files", {}).get(name)
    if not isinstance(entry, dict):
        raise ValueError(f"Capture is missing {name}")
    path = root / entry["path"]
    raw = path.read_bytes()
    if entry.get("sha256") != sha256_bytes(raw) or len(raw) != frames * 4:
        raise ValueError(f"Capture hash or shape mismatch: {name}")
    return np.frombuffer(raw, dtype="<f4").astype(np.float64)


def analyze_capture(output_root: Path) -> dict:
    output_root = output_root.resolve()
    phase = json.loads((output_root / "phase.json").read_text(encoding="utf-8"))
    r4_root, anchor_root, app_root = map(Path, (
        phase["r4_root"], phase["anchor_root"], phase["app_root"],
    ))
    experiment, anchor_phase, _ = _validate_frozen_inputs(r4_root, anchor_root)
    current_snapshot = _diagnostic_source_snapshot(app_root)
    snapshot_path = output_root / "source_code_snapshot.json"
    if current_snapshot != json.loads(snapshot_path.read_text(encoding="utf-8")):
        raise ValueError("S13.4 diagnostic source changed during capture")
    if sha256_file(snapshot_path) != phase["source_snapshot_sha256"]:
        raise ValueError("S13.4 diagnostic source snapshot binding changed")
    if coverage.bank_sha256_inventory(
        app_root / coverage.BANK_ASSET_ROOT / VEHICLE_KEY,
    ) != phase["bank_asset_sha256"]:
        raise ValueError("Original C63 production bank changed during capture")
    if sha256_file(output_root / "windows.tsv") != phase["anchor_windows_sha256"]:
        raise ValueError("Frozen S13.3 window manifest changed")
    if sha256_file(r4_root / "experiment.json") != EXPECTED_R4_EXPERIMENT_SHA256 or \
            sha256_file(r4_root / "worktree_snapshot.json") != EXPECTED_R4_SNAPSHOT_SHA256:
        raise ValueError("Frozen S13.2 identity changed during capture")
    if sha256_file(anchor_root / "phase.json") != phase["anchor_phase_sha256"] or \
            sha256_file(anchor_root / "anchor_coherence_metrics.json") != phase["anchor_metrics_sha256"]:
        raise ValueError("Frozen S13.3 evidence changed during capture")

    capture_path = output_root / "capture_manifest.json"
    manifest = json.loads(capture_path.read_text(encoding="utf-8"))
    frames = TOTAL_FRAMES
    if manifest.get("schema") != "vico.s13.c63_rpm_capture.v1" or \
            manifest.get("frames") != frames or \
            manifest.get("source_snapshot_sha256") != phase["source_snapshot_sha256"]:
        raise ValueError("S13.4 capture manifest is not bound to this phase")
    if manifest.get("tap_pcm_identical") is not True or \
            manifest.get("tap_on_pcm_sha256") != manifest.get("tap_off_pcm_sha256"):
        raise ValueError("Tap-on and tap-off PCM identities differ")
    if manifest.get("mix_stats", {}).get("hard_clip_frames") != 0 or \
            manifest.get("mix_stats", {}).get("non_finite_frames") != 0:
        raise ValueError("Captured renderer reported clipping or non-finite output")

    capture = {
        name: _read_capture_array(output_root, manifest, name, frames)
        for name in ("lower_path", "upper_path", "rpm_weight", "shared_gain", "event_contribution", "renderer_mix")
    }
    for name in ("rpm_lower_index", "rpm_upper_index"):
        entry = manifest.get("files", {}).get(name, {})
        raw = (output_root / entry.get("path", "")).read_bytes()
        if entry.get("sha256") != sha256_bytes(raw) or len(raw) != frames:
            raise ValueError(f"Capture hash or shape mismatch: {name}")
        capture[name] = np.frombuffer(raw, dtype=np.uint8)

    window_rows = anchor._read_tsv(output_root / "windows.tsv")
    if len(window_rows) != 75:
        raise ValueError("Frozen S13.3 stable-window count changed")
    starts = [int(row["start_frame"]) for row in window_rows]
    ends = [int(row["end_frame_exclusive"]) for row in window_rows]
    if any(end - start != WINDOW_FRAMES for start, end in zip(starts, ends)) or any(
        left_end > right_start for left_end, right_start in zip(ends, starts[1:])
    ):
        raise ValueError("S13.3 windows are not fixed-length, non-overlapping 100 ms windows")

    d0_info = experiment["D0_D1_D2"]["D0"]
    if sha256_file(Path(d0_info["path"])) != d0_info["sha256"]:
        raise ValueError("Frozen D0 desktop reference SHA changed")
    d0_stereo, d0_rate = sf.read(d0_info["path"], dtype="float32", always_2d=True)
    if d0_rate != SAMPLE_RATE_HZ or d0_stereo.shape != (TOTAL_FRAMES + 1, 1):
        raise ValueError("Frozen D0 sample rate or frame count changed")
    d0 = d0_stereo[:TOTAL_FRAMES, 0].astype(np.float64)
    phone_a_path = r4_root / "renders" / "A.f32le"
    phone_a = _read_f32le(phone_a_path, frames)
    if sha256_file(phone_a_path) != experiment["D0_D1_D2"]["D1"]["sha256"]:
        raise ValueError("Frozen D1 renderer A identity changed")
    if sha256_bytes((output_root / "windows.tsv").read_bytes()) != phase["anchor_windows_sha256"]:
        raise ValueError("Stable-window identity changed")

    levels = np.asarray(phase["rpm_levels"], dtype=np.int64)
    per_window = []
    selected = []
    for window_index, (start, end) in enumerate(zip(starts, ends)):
        section = slice(start, end)
        classification = classify_mixed_window(
            capture["rpm_lower_index"][section], capture["rpm_upper_index"][section],
            capture["rpm_weight"][section],
        )
        row = {
            "window_index": window_index,
            "start_frame": start,
            "end_frame_exclusive": end,
            **classification,
        }
        if not classification["qualifies"]:
            per_window.append(row)
            continue
        for name in capture:
            if capture[name].size != frames:
                raise ValueError(f"Captured stream length changed: {name}")
        result = analyze_window(
            capture["lower_path"][section], capture["upper_path"][section],
            capture["rpm_weight"][section], capture["shared_gain"][section],
            capture["renderer_mix"][section], d0[section],
            event_contribution=capture["event_contribution"][section],
        )
        renderer_error = capture["renderer_mix"][section] - phone_a[section]
        phone_max = float(np.max(np.abs(renderer_error)))
        phone_rmse = float(np.sqrt(np.mean(np.square(renderer_error))))
        if phone_max > 2e-5 or phone_rmse > 2e-6:
            raise ValueError("S13.4 tap-on renderer no longer matches frozen D1 on a selected window")
        row.update(result)
        row["renderer_vs_d1_max_abs"] = phone_max
        row["renderer_vs_d1_rmse"] = phone_rmse
        for anchor_index in (capture["rpm_lower_index"][section], capture["rpm_upper_index"][section]):
            if np.any(anchor_index >= levels.size):
                raise ValueError("Captured RPM anchor index exceeds frozen C63 levels")
        selected.append(row)
        per_window.append(row)

    support = evaluate_support_gate(selected)
    status = support["status"]
    result = {
        "schema": "vico.s13.c63_rpm_cross_term_analysis.v1",
        "status": "ANALYZED_DIGITAL_ONLY",
        "conclusion": status,
        "phase_identity": {
            key: phase[key] for key in (
                "r4_experiment_sha256", "r4_snapshot_sha256", "anchor_phase_sha256",
                "anchor_windows_sha256", "source_snapshot_sha256", "trace_sha256",
                "event_schedule_sha256", "d0_sha256", "d1_sha256",
            )
        },
        "stable_window_count": len(window_rows),
        "mixed_window_count": len(selected),
        "mixed_rpm_intervals": support.get("rpm_interval_indices", []),
        "support_gate": support,
        "per_window": per_window,
        "limitations": [
            "Pno_cross = Px + Py is an energy-domain counterfactual and is not playable PCM.",
            "The test-only tap does not change production audio calculation order or bank/gain/EQ assets.",
            "A positive diagnostic does not demonstrate an audio fix, phone listening quality, or true-car identity.",
            "High-load support, APK build/install, phone audition, and vehicle/OEM validation remain out of scope.",
        ],
    }
    metrics_path = output_root / "rpm_cross_term_metrics.json"
    _write_json(metrics_path, result)
    report = [
        "# S13.4 C63 RPM-blend cross-term attribution",
        "",
        f"- Conclusion: `{status}`",
        f"- Eligible stable RPM-mixed windows: {len(selected)}/{len(window_rows)} across intervals {support.get('rpm_interval_indices', [])}.",
        "- Support gate compares the current coherent renderer and an energy-only no-cross counterfactual against frozen desktop D0.",
        "- `Pno_cross = Px + Py` is not PCM and must not be played, exported, installed, or called a candidate.",
        "- No production bank, renderer calculation order, gain/EQ, APK, or phone state was changed.",
        "- High-load, human audition and true-car/OEM similarity remain unqualified.",
    ]
    if support.get("bands"):
        for band, values in support["bands"].items():
            report.append(
                f"- {band} Hz: coherent residual median {values['coherent_residual_median_db']:+.3f} dB; "
                f"cross-term median {values['cross_term_median_db']:+.3f} dB "
                f"({values['cross_term_positive_fraction']:.1%} positive); "
                f"median absolute-error improvement {values['median_improvement_db']:.3f} dB; "
                f"improved windows {values['improved_window_fraction']:.1%}; gate `{'PASS' if values['pass'] else 'FAIL'}`."
            )
    (output_root / "rpm_cross_term_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r4-root", type=Path, required=True)
    parser.add_argument("--anchor-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--analyze", action="store_true")
    args = parser.parse_args()
    result = analyze_capture(args.output_root) if args.analyze else prepare_capture(
        args.r4_root, args.anchor_root, args.output_root,
    )
    print(json.dumps({
        "status": result.get("status"),
        "conclusion": result.get("conclusion"),
        "mixed_window_count": result.get("mixed_window_count"),
        "output_root": str(args.output_root.resolve()),
    }, indent=2))


if __name__ == "__main__":
    main()
