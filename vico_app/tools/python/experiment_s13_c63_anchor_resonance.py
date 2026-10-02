"""Diagnose whether the C63 5500-RPM anchor resonance transfers to neighbours."""

from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

import experiment_s13_c63_load_coverage as coverage
import export_s12_android_sound_banks as exporter


VEHICLE_KEY = "c63_w204_v6"
SAMPLE_RATE_HZ = 48_000
TOTAL_FRAMES = 1_440_000
CONDITION_FRAMES = 4 * SAMPLE_RATE_HZ
WINDOW_FRAMES = 4_800
ANCHOR_RPM = 5_500.0
TARGET_RPMS = (5_200.0, 5_500.0, 6_100.0)
LOADS = (0.32, 0.92)
SOURCE_ROOT = Path(r"E:\Tesla_speed\prj\tools")
ALLOWED_OUTPUT_ROOT = Path(r"E:\Claude_allow\Download")
DIAGNOSTIC_SOURCE_FILES = (
    "Project/android/app/src/main/java/com/vico/simulator/sound/MatlabStatefulBankRenderer.kt",
    "Project/android/app/src/main/java/com/vico/simulator/sound/S13ReviewSession.kt",
    "Project/android/app/src/test/java/com/vico/simulator/sound/S13C63AnchorResonanceTest.kt",
    "Project/android/app/src/test/java/com/vico/simulator/sound/S13C63RpmCrossTermTest.kt",
    "tools/python/experiment_s13_c63_anchor_resonance.py",
    "tools/python/test_s13_c63_anchor_resonance.py",
    "tools/python/experiment_s13_c63_rpm_guard_bank.py",
    "tools/python/test_s13_c63_rpm_guard_bank.py",
    "Project/android/app/src/test/java/com/vico/simulator/sound/S13C63RpmGuardBankTest.kt",
    "tools/python/experiment_s13_c63_rpm_cross_term.py",
    "tools/python/experiment_s13_c63_load_coverage.py",
    "tools/python/export_s12_android_sound_banks.py",
)
BAND_NAMES = ("200-1000", "950-1250", "1000-4000")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_properties(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            result[key] = value
    return result


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def parse_porcelain_z(payload: bytes) -> list[dict[str, str]]:
    if not isinstance(payload, bytes):
        raise TypeError("git status -z output must be bytes")
    rows = []
    tokens = [token for token in payload.split(b"\0") if token]
    index = 0
    while index < len(tokens):
        token = tokens[index].decode("utf-8", errors="surrogateescape")
        if len(token) < 3 or token[2] != " ":
            raise ValueError(f"Malformed porcelain -z entry: {token!r}")
        status, path = token[:2], token[3:]
        rows.append({"status": status, "path": path})
        index += 1
        if status[0] in {"R", "C"} or status[1] in {"R", "C"}:
            if index >= len(tokens):
                raise ValueError("Rename/copy entry is missing its destination")
            destination = tokens[index].decode("utf-8", errors="surrogateescape")
            rows[-1]["path"] = destination
            rows[-1]["from"] = path
            index += 1
    return rows


def _git(repo_root: Path, *args: str, binary: bool = False) -> bytes | str:
    result = subprocess.check_output(["git", "-C", str(repo_root), *args])
    return result if binary else result.decode("utf-8", errors="surrogateescape").strip()


def _full_worktree_snapshot(repo_root: Path) -> dict:
    raw = _git(repo_root, "status", "--porcelain=v1", "-z", "--untracked-files=all", binary=True)
    rows = parse_porcelain_z(raw)
    files = []
    for row in rows:
        path = repo_root / Path(row["path"].replace("/", "\\"))
        files.append({
            "status": row["status"],
            "path": row["path"],
            "from": row.get("from"),
            "sha256": sha256_file(path) if path.is_file() else None,
        })
    return {
        "schema": "vico.s13.full_worktree_snapshot.v1",
        "branch": _git(repo_root, "branch", "--show-current"),
        "head": _git(repo_root, "rev-parse", "HEAD"),
        "status_z_sha256": sha256_bytes(raw),
        "dirty_path_count": len(files),
        "paths": files,
    }


def _diagnostic_source_snapshot(repo_root: Path) -> dict:
    files = []
    for relative in DIAGNOSTIC_SOURCE_FILES:
        path = repo_root / Path(relative)
        if not path.is_file():
            raise FileNotFoundError(f"Required S13.5 source is missing: {relative}")
        files.append({"path": relative, "sha256": sha256_file(path)})
    return {
        "schema": "vico.s13.anchor_resonance_source_snapshot.v1",
        "branch": _git(repo_root, "branch", "--show-current"),
        "head": _git(repo_root, "rev-parse", "HEAD"),
        "files": files,
    }


def _write_git_evidence(repo_root: Path, output_root: Path) -> tuple[dict, dict]:
    raw = _git(repo_root, "status", "--porcelain=v1", "-z", "--untracked-files=all", binary=True)
    (output_root / "git_status_porcelain_v1-z.bin").write_bytes(raw)
    (output_root / "git_diff_full.patch").write_bytes(
        _git(repo_root, "diff", "--no-ext-diff", "--binary", binary=True),
    )
    (output_root / "git_diff_cached.patch").write_bytes(
        _git(repo_root, "diff", "--cached", "--no-ext-diff", "--binary", binary=True),
    )
    phase_patch = []
    for relative in DIAGNOSTIC_SOURCE_FILES:
        path = repo_root / Path(relative)
        content = path.read_text(encoding="utf-8").splitlines(keepends=True)
        phase_patch.extend(difflib.unified_diff(
            [], content, fromfile="/dev/null", tofile=relative, lineterm="\n",
        ))
    (output_root / "git_diff_phase_sources.patch").write_text("".join(phase_patch), encoding="utf-8")
    full = _full_worktree_snapshot(repo_root)
    _write_json(output_root / "worktree_snapshot.json", full)
    source = _diagnostic_source_snapshot(repo_root)
    _write_json(output_root / "source_code_snapshot.json", source)
    return full, source


def _validate_r4_and_r3(r4_root: Path, r3_root: Path) -> tuple[dict, dict, dict, dict]:
    r4_experiment = json.loads((r4_root / "experiment.json").read_text(encoding="utf-8"))
    r4_snapshot_path = r4_root / "worktree_snapshot.json"
    r3_metrics = json.loads((r3_root / "rpm_cross_term_metrics.json").read_text(encoding="utf-8"))
    r3_manifest = json.loads((r3_root / "capture_manifest.json").read_text(encoding="utf-8"))
    if r4_experiment.get("status") != "ANALYZED_DIGITAL_ONLY":
        raise ValueError("Frozen r4 C63 experiment is incomplete")
    if sha256_file(r4_root / "experiment.json") != "8fd92ebc4ee716d62f728a82f07c6cafdb7936520ffba3a100ab04c87f8c01d0":
        raise ValueError("r4 experiment identity changed")
    if sha256_file(r4_snapshot_path) != "cebdf8a3392c7834e655dfbfe3e3432d444bf09ab5e885061267fa8ad2223136":
        raise ValueError("r4 worktree snapshot identity changed")
    if r3_metrics.get("conclusion") != "RPM_COHERENT_CROSS_TERM_NOT_SUPPORTED":
        raise ValueError("S13.4 negative conclusion is not the frozen input")
    if r3_metrics.get("mixed_window_count") != 44:
        raise ValueError("S13.4 qualified-window count changed")
    if r3_manifest.get("schema") != "vico.s13.c63_rpm_capture.v1" or not r3_manifest.get("tap_pcm_identical"):
        raise ValueError("S13.4 capture manifest is incomplete")
    return r4_experiment, r3_metrics, r3_manifest, _read_properties(r4_root / "inputs/experiment.properties")


def anchor_path_for_target(
    rpm_levels: tuple[float, ...] | list[float], target_rpm: float, anchor_rpm: float,
) -> dict[str, str | int]:
    levels = tuple(float(value) for value in rpm_levels)
    if anchor_rpm not in levels or not math.isfinite(target_rpm):
        raise ValueError("Target and anchor RPM must be finite and the anchor must exist")
    if target_rpm == anchor_rpm:
        return {"role": "same", "anchor_index": levels.index(anchor_rpm)}
    if target_rpm < anchor_rpm:
        upper = next((index for index, value in enumerate(levels) if value >= target_rpm), None)
        if upper is None or levels[upper] != anchor_rpm:
            raise ValueError("5500 anchor is not the upper path for this target")
        return {"role": "upper", "anchor_index": upper}
    lower = next((index for index in range(len(levels) - 1, -1, -1) if levels[index] <= target_rpm), None)
    if lower is None or levels[lower] != anchor_rpm:
        raise ValueError("5500 anchor is not the lower path for this target")
    return {"role": "lower", "anchor_index": lower}


def _power_in_band(samples: np.ndarray, band: str, sample_rate_hz: int = SAMPLE_RATE_HZ) -> float:
    return float(10.0 ** (window_band_db(samples, band, sample_rate_hz) / 10.0))


def window_band_db(samples: np.ndarray, band: str, sample_rate_hz: int = SAMPLE_RATE_HZ) -> float:
    bounds = {
        "20-200": (20.0, 200.0),
        "200-1000": (200.0, 1000.0),
        "950-1250": (950.0, 1250.0),
        "1000-4000": (1000.0, 4000.0),
        "4000-12000": (4000.0, 12000.0),
    }
    if band not in bounds:
        raise ValueError(f"Unknown diagnostic band: {band}")
    signal = np.asarray(samples, dtype=np.float64)
    if signal.ndim != 1 or signal.size < 4 or not np.isfinite(signal).all():
        raise ValueError("Band analysis requires a finite mono window")
    lower, upper = bounds[band]
    taper = np.hanning(signal.size)
    spectrum = np.fft.rfft((signal - np.mean(signal)) * taper)
    power = np.square(np.abs(spectrum)) / (signal.size * float(np.sum(np.square(taper))))
    if signal.size % 2 == 0:
        power[1:-1] *= 2.0
    else:
        power[1:] *= 2.0
    frequency = np.fft.rfftfreq(signal.size, d=1.0 / sample_rate_hz)
    selected = (frequency >= lower) & (frequency < upper)
    return 10.0 * math.log10(max(float(np.sum(power[selected])), 1e-24))


def anchor_self_power_share(
    lower_path: np.ndarray,
    upper_path: np.ndarray,
    lower_index: np.ndarray,
    upper_index: np.ndarray,
    *,
    anchor_index: int,
    rpm_weight: np.ndarray,
    shared_gain: np.ndarray,
    band: str = "1000-4000",
) -> float:
    lower, upper, low_index, high_index = (
        np.asarray(value) for value in (lower_path, upper_path, lower_index, upper_index)
    )
    weight, gain = (np.asarray(value, dtype=np.float64) for value in (rpm_weight, shared_gain))
    if not (lower.shape == upper.shape == low_index.shape == high_index.shape == weight.shape == gain.shape):
        raise ValueError("Anchor-share inputs must be equal-sized")
    if (not np.isfinite(weight).all() or not np.isfinite(gain).all() or
            np.any(weight < 0.0) or np.any(weight > 1.0)):
        raise ValueError("Anchor-share weights and gains must be finite; weights must be in [0, 1]")
    lower_contribution = (1.0 - weight) * gain * lower
    upper_contribution = weight * gain * upper
    anchor = np.where(
        low_index == anchor_index, lower_contribution,
        np.where(high_index == anchor_index, upper_contribution, 0.0),
    )
    total = _power_in_band(lower_contribution, band) + _power_in_band(upper_contribution, band)
    if total <= 0.0:
        raise ValueError("Anchor-share total power is zero")
    return _power_in_band(anchor, band) / total


def stable_condition_windows(
    *, total_frames: int, sample_rate_hz: int, warmup_seconds: float,
    end_guard_seconds: float, window_frames: int,
) -> list[tuple[int, int]]:
    start = int(round(warmup_seconds * sample_rate_hz))
    end = total_frames - int(round(end_guard_seconds * sample_rate_hz))
    if start < 0 or end <= start or window_frames <= 0:
        raise ValueError("Invalid fixed-condition window bounds")
    return [(offset, offset + window_frames) for offset in range(start, end - window_frames + 1, window_frames)]


def _median(values: list[float]) -> float:
    return float(np.median(np.asarray(values, dtype=np.float64))) if values else float("nan")


def evaluate_resonance_gate(
    share_windows: list[dict], source_metrics: dict, transfer_metrics: dict,
) -> dict:
    if not share_windows:
        return {"status": "NOT_SUPPORTED", "reason": "NO_QUALIFIED_WINDOWS", "production_fix_implemented": False}
    share_fraction = float(np.mean([float(row["share_5500"]) >= 0.8 for row in share_windows]))
    intervals = sorted({int(row["interval"]) for row in share_windows})
    source_deltas = []
    transfer_deltas = []
    for load_key, values in source_metrics.items():
        source_deltas.extend([
            float(values["5500"]["band_db"]) - float(values["5200"]["band_db"]),
            float(values["5500"]["band_db"]) - float(values["6100"]["band_db"]),
        ])
        transfer_deltas.extend([
            float(transfer_metrics[load_key]["5200"]["difference_db"]),
            float(transfer_metrics[load_key]["6100"]["difference_db"]),
        ])
    controls_ok = all(
        abs(float(values["5500"]["difference_db"])) <= 1.0
        for values in transfer_metrics.values()
        for _ in (0,)
    )
    supported = (
        share_fraction >= 0.6 and len(intervals) >= 2 and
        all(delta >= 6.0 for delta in source_deltas) and
        all(delta >= 6.0 for delta in transfer_deltas) and controls_ok
    )
    return {
        "status": "5500_STATIONARY_RESONANCE_TRANSFER_SUPPORTED" if supported else "NOT_SUPPORTED",
        "production_fix_implemented": False,
        "share_fraction_ge_0p8": share_fraction,
        "intervals": intervals,
        "source_delta_min_db": min(source_deltas) if source_deltas else None,
        "transfer_delta_min_db": min(transfer_deltas) if transfer_deltas else None,
        "same_point_control_max_abs_db": max(
            abs(float(values["5500"]["difference_db"])) for values in transfer_metrics.values()
        ) if transfer_metrics else None,
    }


def _capture_array(root: Path, manifest: dict, condition: str, name: str, dtype: str = "<f4") -> np.ndarray:
    entry = manifest["conditions"][condition]["files"][name]
    path = root / entry["path"]
    raw = path.read_bytes()
    if sha256_bytes(raw) != entry["sha256"]:
        raise ValueError(f"Capture SHA changed: {condition}/{name}")
    return np.frombuffer(raw, dtype=dtype).astype(np.float64)


def _r3_capture_array(root: Path, manifest: dict, name: str, dtype: str = "<f4") -> np.ndarray:
    entry = manifest["files"][name]
    path = root / entry["path"]
    raw = path.read_bytes()
    if sha256_bytes(raw) != entry["sha256"]:
        raise ValueError(f"S13.4 capture SHA changed: {name}")
    return np.frombuffer(raw, dtype=dtype).astype(np.float64)


def _read_source_controls(source_root: Path, fixed_gain: float) -> dict:
    (
        vehicle_state_trace, _build_drive_cycle_trace, _detect_shift_events,
        _manage_bundle_loudness, _measure_loudness, renderers, apply_ptr,
        _edge_fade, render_stateful,
    ) = exporter._load_source_api(source_root)
    renderer = renderers["c63_w204"]
    controls = {}
    for rpm in TARGET_RPMS:
        for load in LOADS:
            trace = exporter._constant_trace(vehicle_state_trace, rpm, load, 4.0)
            rendered = render_stateful(renderer, "c63_w204", trace)
            mono = exporter._mono_48k(apply_ptr(rendered.pressure))
            controls[f"rpm_{int(rpm)}_load_{int(load * 100)}"] = (
                mono[:CONDITION_FRAMES].astype(np.float64) * float(fixed_gain)
            )
    return controls


def reproduce_original_5500_loops(app_root: Path, source_root: Path, fixed_gain: float) -> dict:
    (
        vehicle_state_trace, _build_drive_cycle_trace, _detect_shift_events,
        _manage_bundle_loudness, _measure_loudness, renderers, apply_ptr,
        _edge_fade, render_stateful,
    ) = exporter._load_source_api(source_root)
    renderer = renderers["c63_w204"]
    bank_root = app_root / coverage.BANK_ASSET_ROOT / VEHICLE_KEY
    results = {}
    for load in LOADS:
        trace = exporter._constant_trace(vehicle_state_trace, ANCHOR_RPM, load, 0.52)
        rendered = render_stateful(renderer, "c63_w204", trace)
        generated = exporter._loop(exporter._mono_48k(apply_ptr(rendered.pressure)))
        generated = (generated * np.float32(fixed_gain)).astype(np.float32)
        path = bank_root / f"rpm_{int(ANCHOR_RPM):04d}_load_{int(load * 100):02d}.wav"
        reference, rate = sf.read(path, dtype="float32", always_2d=False)
        reference = np.asarray(reference, dtype=np.float32)
        if rate != SAMPLE_RATE_HZ or generated.shape != reference.shape:
            raise ValueError(f"5500 loop reproduction shape/rate mismatch: {path.name}")
        if not np.array_equal(generated, reference):
            raise ValueError(f"5500 loop reproduction differs: {path.name}")
        results[f"load_{int(load * 100)}"] = {
            "file": path.name,
            "sha256": sha256_file(path),
            "frames": int(reference.size),
            "max_abs": float(np.max(np.abs(reference))),
        }
    return results


def _band_summary(source: np.ndarray, anchor: np.ndarray, windows: list[tuple[int, int]]) -> dict:
    result = {}
    for band in BAND_NAMES:
        source_values = []
        anchor_values = []
        differences = []
        for start, end in windows:
            source_db = window_band_db(source[start:end], band)
            anchor_db = window_band_db(anchor[start:end], band)
            source_values.append(source_db)
            anchor_values.append(anchor_db)
            differences.append(anchor_db - source_db)
        result[band] = {
            "source_median_db": _median(source_values),
            "anchor_median_db": _median(anchor_values),
            "difference_median_db": _median(differences),
            "difference_p90_db": float(np.percentile(np.abs(differences), 90)),
            "window_count": len(windows),
        }
    return result


def _r3_share_windows(r3_root: Path) -> list[dict]:
    metrics = json.loads((r3_root / "rpm_cross_term_metrics.json").read_text(encoding="utf-8"))
    manifest = json.loads((r3_root / "capture_manifest.json").read_text(encoding="utf-8"))
    windows = _read_tsv(r3_root / "windows.tsv")
    lower = _r3_capture_array(r3_root, manifest, "lower_path")
    upper = _r3_capture_array(r3_root, manifest, "upper_path")
    weight = _r3_capture_array(r3_root, manifest, "rpm_weight")
    gain = _r3_capture_array(r3_root, manifest, "shared_gain")
    low_index = _r3_capture_array(r3_root, manifest, "rpm_lower_index", dtype="u1")
    high_index = _r3_capture_array(r3_root, manifest, "rpm_upper_index", dtype="u1")
    rows = []
    for row, metric in zip(windows, metrics["per_window"]):
        if not metric.get("qualifies"):
            continue
        start, end = int(row["start_frame"]), int(row["end_frame_exclusive"])
        interval = int(metric["rpm_interval_index"])
        share = anchor_self_power_share(
            lower[start:end], upper[start:end], low_index[start:end], high_index[start:end],
            anchor_index=5, rpm_weight=weight[start:end], shared_gain=gain[start:end],
        )
        rows.append({"window_index": int(metric["window_index"]), "interval": interval, "share_5500": share})
    return rows


def prepare_experiment(r4_root: Path, r3_root: Path, output_root: Path, app_root: Path) -> dict:
    r4_root, r3_root, output_root, app_root = (
        path.resolve() for path in (r4_root, r3_root, output_root, app_root)
    )
    try:
        output_root.relative_to(ALLOWED_OUTPUT_ROOT.resolve())
    except ValueError as error:
        raise ValueError("S13.5 output must remain under E:\\Claude_allow\\Download") from error
    r4_experiment, r3_metrics, r3_manifest, r4_props = _validate_r4_and_r3(r4_root, r3_root)
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"S13.5 output root is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    worktree, source_snapshot = _write_git_evidence(app_root, output_root)
    if worktree["head"] != r4_experiment["vico_head"] or worktree["branch"] != r4_experiment["vico_branch"]:
        raise ValueError("Current Vico branch/HEAD differs from frozen S13.2 execution")
    bank_root = app_root / coverage.BANK_ASSET_ROOT / VEHICLE_KEY
    if coverage.bank_sha256_inventory(bank_root) != r4_experiment["base_asset_sha256"]:
        raise ValueError("C63 production bank changed before S13.5")
    share_windows = _r3_share_windows(r3_root)
    phase = {
        "schema": "vico.s13.c63_anchor_resonance.v1",
        "status": "PREPARED",
        "vehicle_key": VEHICLE_KEY,
        "app_root": app_root.as_posix(),
        "source_root": SOURCE_ROOT.as_posix(),
        "r4_root": r4_root.as_posix(),
        "r3_root": r3_root.as_posix(),
        "r4_experiment_sha256": sha256_file(r4_root / "experiment.json"),
        "r4_snapshot_sha256": sha256_file(r4_root / "worktree_snapshot.json"),
        "r3_metrics_sha256": sha256_file(r3_root / "rpm_cross_term_metrics.json"),
        "r3_capture_manifest_sha256": sha256_file(r3_root / "capture_manifest.json"),
        "worktree_snapshot_sha256": sha256_file(output_root / "worktree_snapshot.json"),
        "source_code_snapshot_sha256": sha256_file(output_root / "source_code_snapshot.json"),
        "git_status_z_sha256": sha256_file(output_root / "git_status_porcelain_v1-z.bin"),
        "vico_head": worktree["head"],
        "vico_branch": worktree["branch"],
        "dirty_path_count": worktree["dirty_path_count"],
        "source_commit": r4_props["source_commit"],
        "fixed_vehicle_gain": float(r4_props["fixed_vehicle_gain"]),
        "bank_asset_sha256": r4_experiment["base_asset_sha256"],
        "trace_sha256": r4_props["trace_sha256"],
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "condition_frames": CONDITION_FRAMES,
        "warmup_seconds": 1.0,
        "stable_end_seconds": 4.0,
        "rpm_levels": [700, 1400, 2200, 3200, 4300, 5500, 6800, 7200],
        "target_rpms": list(TARGET_RPMS),
        "loads": list(LOADS),
        "share_window_count": len(share_windows),
        "share_windows": share_windows,
        "gates": {
            "minimum_5500_share_fraction": 0.6,
            "minimum_5500_share": 0.8,
            "minimum_source_neighbor_delta_db": 6.0,
            "minimum_transfer_neighbor_delta_db": 6.0,
            "maximum_same_point_delta_db": 1.0,
            "source_narrow_band": "950-1250",
            "primary_band": "1000-4000",
        },
        "production_audio_change": False,
        "apk_built_or_installed": False,
    }
    _write_json(output_root / "phase.json", phase)
    coverage._write_properties(output_root / "phase.properties", {
        "app_root": app_root,
        "source_root": SOURCE_ROOT,
        "r4_root": r4_root,
        "r3_root": r3_root,
        "output_root": output_root,
        "r4_experiment_sha256": phase["r4_experiment_sha256"],
        "r4_snapshot_sha256": phase["r4_snapshot_sha256"],
        "r3_metrics_sha256": phase["r3_metrics_sha256"],
        "r3_capture_manifest_sha256": phase["r3_capture_manifest_sha256"],
        "worktree_snapshot_sha256": phase["worktree_snapshot_sha256"],
        "source_code_snapshot_sha256": phase["source_code_snapshot_sha256"],
        "fixed_vehicle_gain": phase["fixed_vehicle_gain"],
        "condition_frames": CONDITION_FRAMES,
    })
    return phase


def analyze_experiment(output_root: Path) -> dict:
    output_root = output_root.resolve()
    phase = json.loads((output_root / "phase.json").read_text(encoding="utf-8"))
    manifest_path = output_root / "capture_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("S13.5 Kotlin capture manifest is required")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "vico.s13.c63_anchor_resonance_capture.v1":
        raise ValueError("Unexpected S13.5 capture schema")
    if manifest.get("source_code_snapshot_sha256") != phase["source_code_snapshot_sha256"]:
        raise ValueError("Capture is not bound to the prepared source snapshot")
    if manifest.get("fixed_vehicle_gain") != phase["fixed_vehicle_gain"]:
        raise ValueError("Capture fixed gain differs from frozen bank gain")

    loop_reproduction = reproduce_original_5500_loops(
        Path(phase["app_root"]), Path(phase["source_root"]), float(phase["fixed_vehicle_gain"]),
    )
    controls = _read_source_controls(Path(phase["source_root"]), float(phase["fixed_vehicle_gain"]))
    windows = stable_condition_windows(
        total_frames=CONDITION_FRAMES, sample_rate_hz=SAMPLE_RATE_HZ,
        warmup_seconds=1.0, end_guard_seconds=0.0, window_frames=WINDOW_FRAMES,
    )
    source_metrics = {"load_32": {}, "load_92": {}}
    transfer_metrics = {"load_32": {}, "load_92": {}}
    per_condition = {}
    for load_key, load in (("load_32", 0.32), ("load_92", 0.92)):
        for rpm in TARGET_RPMS:
            condition = f"rpm_{int(rpm)}_load_{int(load * 100)}"
            source = controls[condition]
            lower = _capture_array(output_root, manifest, condition, "lower_path")
            upper = _capture_array(output_root, manifest, condition, "upper_path")
            gain = _capture_array(output_root, manifest, condition, "shared_gain")
            mix = _capture_array(output_root, manifest, condition, "renderer_mix")
            low_index = _capture_array(output_root, manifest, condition, "rpm_lower_index", dtype="u1")
            high_index = _capture_array(output_root, manifest, condition, "rpm_upper_index", dtype="u1")
            if not all(array.size == CONDITION_FRAMES for array in (source, lower, upper, gain, mix, low_index, high_index)):
                raise ValueError(f"Unexpected condition frame count: {condition}")
            role = anchor_path_for_target(tuple(phase["rpm_levels"]), rpm, ANCHOR_RPM)
            anchor = np.where(role["role"] == "lower", lower, upper) * gain
            if role["role"] == "same":
                anchor = lower * gain
            reconstruction = np.where(
                role["role"] == "lower", lower, upper,
            ) * gain
            if role["role"] == "same":
                reconstruction = lower * gain
            # For the 5500 path diagnostic, the chosen path is compared directly;
            # the full renderer mix remains in the capture for identity and safety.
            if np.max(np.abs(mix)) >= 1.0 or not np.isfinite(mix).all():
                raise ValueError(f"Clipped or non-finite Android capture: {condition}")
            summary = _band_summary(source, anchor, windows)
            per_condition[condition] = {
                "rpm": rpm, "load": load, "anchor_role": role["role"],
                "anchor_index": role["anchor_index"], "bands": summary,
                "renderer_mix_rms_db": coverage.window_feature_db(mix[windows[0][0]:windows[-1][1]])["rms"],
                "source_peak": float(np.max(np.abs(source))),
                "anchor_peak": float(np.max(np.abs(anchor))),
            }
            if rpm == ANCHOR_RPM:
                transfer_metrics[load_key]["5500"] = {
                    "difference_db": summary["1000-4000"]["difference_median_db"],
                }
            else:
                transfer_metrics[load_key][str(int(rpm))] = {
                    "difference_db": summary["1000-4000"]["difference_median_db"],
                }

        source_metrics[load_key] = {
            str(int(rpm)): {
                "band_db": per_condition[f"rpm_{int(rpm)}_load_{int(load * 100)}"]["bands"]["1000-4000"]["source_median_db"],
                "narrow_band_db": per_condition[f"rpm_{int(rpm)}_load_{int(load * 100)}"]["bands"]["950-1250"]["source_median_db"],
                "difference_db": per_condition[f"rpm_{int(rpm)}_load_{int(load * 100)}"]["bands"]["1000-4000"]["difference_median_db"],
            }
            for rpm in TARGET_RPMS
        }
    # Gate the source narrow-band as well as the primary-band resonance.
    source_deltas = []
    narrow_deltas = []
    transfer_deltas = []
    same_point = []
    for load_key in source_metrics:
        source_deltas.extend([
            source_metrics[load_key]["5500"]["band_db"] - source_metrics[load_key]["5200"]["band_db"],
            source_metrics[load_key]["5500"]["band_db"] - source_metrics[load_key]["6100"]["band_db"],
        ])
        narrow_deltas.extend([
            source_metrics[load_key]["5500"]["narrow_band_db"] - source_metrics[load_key]["5200"]["narrow_band_db"],
            source_metrics[load_key]["5500"]["narrow_band_db"] - source_metrics[load_key]["6100"]["narrow_band_db"],
        ])
        transfer_deltas.extend([
            transfer_metrics[load_key]["5200"]["difference_db"],
            transfer_metrics[load_key]["6100"]["difference_db"],
        ])
        same_point.append(abs(transfer_metrics[load_key]["5500"]["difference_db"]))
    shares = phase["share_windows"]
    share_fraction = float(np.mean([float(row["share_5500"]) >= 0.8 for row in shares])) if shares else 0.0
    intervals = sorted({int(row["interval"]) for row in shares if float(row["share_5500"]) >= 0.8})
    support = {
        "status": "5500_STATIONARY_RESONANCE_TRANSFER_SUPPORTED"
        if share_fraction >= 0.6 and len(intervals) >= 2 and
        min(source_deltas) >= 6.0 and min(narrow_deltas) >= 6.0 and
        min(transfer_deltas) >= 6.0 and max(same_point) <= 1.0
        else "NOT_SUPPORTED",
        "production_fix_implemented": False,
        "share_fraction_ge_0p8": share_fraction,
        "share_intervals": intervals,
        "source_primary_delta_min_db": min(source_deltas),
        "source_narrow_delta_min_db": min(narrow_deltas),
        "transfer_delta_min_db": min(transfer_deltas),
        "same_point_control_max_abs_db": max(same_point),
    }
    result = {
        "schema": "vico.s13.c63_anchor_resonance_analysis.v1",
        "status": "ANALYZED_DIGITAL_ONLY",
        "conclusion": support["status"],
        "phase_identity": {key: phase[key] for key in (
            "r4_experiment_sha256", "r4_snapshot_sha256", "r3_metrics_sha256",
            "r3_capture_manifest_sha256", "worktree_snapshot_sha256",
            "source_code_snapshot_sha256", "git_status_z_sha256", "trace_sha256",
        )},
        "support_gate": support,
        "share_window_count": len(phase.get("share_windows", [])),
        "original_5500_loop_reproduction": loop_reproduction,
        "source_metrics": source_metrics,
        "transfer_metrics": transfer_metrics,
        "per_condition": per_condition,
        "limitations": [
            "The result is a digital fixed-condition diagnostic, not a phone candidate, APK, audition or true-car proof.",
            "The full-event C63 D1/D2 identity remains separate; this phase intentionally uses no events.",
            "No production renderer, bank, gain/EQ or source algorithm was changed.",
        ],
    }
    _write_json(output_root / "anchor_resonance_metrics.json", result)
    report = [
        "# S13.5 C63 5500-RPM anchor-resonance transfer diagnostic",
        "",
        f"- Conclusion: `{support['status']}`",
        f"- Existing S13.4 windows with 5500 self-power share >= 0.8: {share_fraction:.1%}; intervals: {intervals}.",
        "- Original 5500 RPM load-32/load-92 loops were reproduced byte-for-byte from the frozen S12 source/exporter path.",
        f"- Source 5500-vs-neighbour minimum 1–4 kHz delta: {support['source_primary_delta_min_db']:.3f} dB.",
        f"- Source 5500-vs-neighbour minimum 950–1250 Hz delta: {support['source_narrow_delta_min_db']:.3f} dB.",
        f"- Android 5500-path-vs-source minimum neighbour delta: {support['transfer_delta_min_db']:.3f} dB.",
        f"- Same-point 5500 control maximum absolute difference: {support['same_point_control_max_abs_db']:.3f} dB.",
        "- No production audio change, APK build/install, event playback or audition was performed.",
    ]
    (output_root / "anchor_resonance_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r4-root", type=Path, required=True)
    parser.add_argument("--r3-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--app-root", type=Path, required=True)
    parser.add_argument("--analyze", action="store_true")
    args = parser.parse_args()
    result = analyze_experiment(args.output_root) if args.analyze else prepare_experiment(
        args.r4_root, args.r3_root, args.output_root, args.app_root,
    )
    print(json.dumps({
        "status": result.get("status"),
        "conclusion": result.get("conclusion"),
        "output_root": str(args.output_root.resolve()),
        "share_window_count": result.get("share_window_count"),
    }, indent=2))


if __name__ == "__main__":
    main()
