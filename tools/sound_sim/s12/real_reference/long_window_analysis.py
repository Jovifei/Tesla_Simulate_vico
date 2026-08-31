"""Build 15/30-second external-only windows for dynamic R2 diagnostics."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from scipy.io import wavfile


class LongWindowError(ValueError):
    """Raised when a requested dynamic window cannot be sourced honestly."""


ALLOWED_ROOT = Path(r"E:\Claude_allow\Download")
WINDOWS = (15.0, 30.0)
VEHICLE_PAIR = {"ferrari_458": "P01", "hellcat": "P02", "rx7_fd": "P03"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inside(root: Path, value: str | Path, label: str) -> Path:
    root = Path(root).resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise LongWindowError(f"{label} escapes allowed root: {candidate}") from exc
    return resolved


def choose_reference_window(total_duration_s: float, anchor_s: float, duration_s: float) -> dict[str, float]:
    total = float(total_duration_s)
    duration = float(duration_s)
    anchor = float(anchor_s)
    if duration not in WINDOWS or total < duration:
        raise LongWindowError(f"reference source is shorter than requested {duration:g}s window")
    start = min(max(0.0, anchor - duration / 2.0), total - duration)
    start = round(start, 6)
    return {"start_s": start, "duration_s": duration, "end_s": round(start + duration, 6)}


def choose_candidate_window(scenario: str, duration_s: float, cycle_duration_s: float = 60.0) -> dict[str, float]:
    duration = float(duration_s)
    cycle = float(cycle_duration_s)
    if duration not in WINDOWS or duration > cycle:
        raise LongWindowError(f"candidate cycle is shorter than requested {duration:g}s window")
    label = str(scenario).lower()
    if "idle" in label or "startup" in label:
        start = 0.0
    elif "launch" in label:
        start = 20.0 if duration <= 15.0 else 8.0
    elif "shift" in label or "acceleration" in label or "track" in label or "full" in label:
        start = 8.0 if duration >= 30.0 else 8.0
    elif "afterfire" in label or "lift" in label or "deceleration" in label:
        start = 34.0
    elif "technical" in label or "turbo" in label:
        start = 20.0 if duration >= 30.0 else 26.0
    else:
        start = 8.0
    start = min(max(0.0, start), cycle - duration)
    return {"start_s": float(start), "duration_s": duration, "end_s": float(start + duration)}


def _read_wav(path: Path) -> tuple[int, np.ndarray]:
    try:
        sample_rate_hz, signal = wavfile.read(str(path))
    except Exception as exc:
        raise LongWindowError(f"cannot decode WAV: {path}") from exc
    if signal.size == 0 or sample_rate_hz <= 0:
        raise LongWindowError(f"source WAV is empty: {path}")
    return int(sample_rate_hz), np.asarray(signal)


def _slice_wav(source: Path, start_s: float, duration_s: float, destination: Path) -> dict[str, Any]:
    sample_rate_hz, signal = _read_wav(source)
    total_duration = signal.shape[0] / float(sample_rate_hz)
    window = choose_reference_window(total_duration, start_s + duration_s / 2.0, duration_s)
    first = int(round(window["start_s"] * sample_rate_hz))
    count = int(round(duration_s * sample_rate_hz))
    last = first + count
    if first < 0 or last > signal.shape[0]:
        raise LongWindowError(f"window exceeds source without padding: {source}")
    clipped = signal[first:last]
    if clipped.shape[0] != count:
        raise LongWindowError(f"window frame count mismatch: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(str(destination), sample_rate_hz, clipped)
    return {
        "path": str(destination),
        "sha256": _sha256(destination),
        "sample_rate_hz": sample_rate_hz,
        "channels": int(clipped.shape[1]) if clipped.ndim > 1 else 1,
        "duration_s": clipped.shape[0] / float(sample_rate_hz),
        "start_s": float(window["start_s"]),
        "end_s": float(window["end_s"]),
        "source_path": str(source),
        "source_sha256": _sha256(source),
        "derivation": "time_slice_only_no_gain_eq_agc_resampling",
    }


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LongWindowError(f"cannot read JSON: {path}") from exc
    if not isinstance(value, dict):
        raise LongWindowError(f"JSON must be an object: {path}")
    return value


def build_long_window_package(
    anchor_manifest_path: Path,
    scenario_manifest_path: Path,
    candidate_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    """Create external 15/30-second reference/candidate windows and manifest."""

    output_root = Path(output_root).resolve()
    allowed = ALLOWED_ROOT.resolve()
    if output_root != allowed and allowed not in output_root.parents:
        raise LongWindowError(f"long-window output must remain under {allowed}")
    if output_root.exists() and any(output_root.iterdir()):
        raise LongWindowError(f"refusing to overwrite non-empty long-window output: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    anchor_manifest_path = Path(anchor_manifest_path).resolve()
    anchor = _json(anchor_manifest_path)
    scenario = _json(Path(scenario_manifest_path).resolve())
    scenario_by_id = {str(row["selection_id"]): row for row in scenario.get("records", []) if isinstance(row, Mapping)}
    candidate_root = Path(candidate_root).resolve()
    pair_key = _json(candidate_root / "sealed" / "pair_key.json").get("pairs", {})
    pairs: list[dict[str, Any]] = []
    for trial in anchor.get("trials", []):
        trial_id = str(trial["trial_id"])
        vehicle_id = str(trial["vehicle_id"])
        source_record = scenario_by_id.get(trial_id)
        if not source_record:
            raise LongWindowError(f"scenario manifest missing selection: {trial_id}")
        reference_source = Path(str(trial["reference_original_wav_path_alias"])).resolve()
        if not reference_source.is_file():
            raise LongWindowError(f"long reference source missing: {reference_source}")
        pair_id = VEHICLE_PAIR.get(vehicle_id)
        if not pair_id or pair_id not in pair_key:
            raise LongWindowError(f"candidate pair mapping missing: {vehicle_id}")
        mapping = pair_key[pair_id]
        candidate_option = next((option for option in ("A", "B") if mapping.get(f"{option}_role") == "candidate"), None)
        if not candidate_option:
            raise LongWindowError(f"candidate role missing in pair key: {pair_id}")
        candidate_source = candidate_root / "listener" / "qualitative_full_cycle_pairs" / f"{pair_id}_{candidate_option}.wav"
        if not candidate_source.is_file():
            raise LongWindowError(f"long candidate source missing: {candidate_source}")
        _, reference_signal = _read_wav(reference_source)
        _, candidate_signal = _read_wav(candidate_source)
        reference_duration = reference_signal.shape[0] / 44100.0
        candidate_duration = candidate_signal.shape[0] / 48000.0
        source_scenario = str(source_record.get("scenario") or "unknown")
        for duration_s in WINDOWS:
            reference_window = choose_reference_window(reference_duration, float(trial["reference_start_s"]), duration_s)
            candidate_window = choose_candidate_window(source_scenario, duration_s, candidate_duration)
            out_prefix = f"{trial_id}_{int(duration_s)}s"
            reference_out = output_root / "audio" / trial_id / f"{out_prefix}_reference.wav"
            candidate_out = output_root / "audio" / trial_id / f"{out_prefix}_candidate.wav"
            reference_meta = _slice_wav(reference_source, reference_window["start_s"], duration_s, reference_out)
            candidate_meta = _slice_wav(candidate_source, candidate_window["start_s"], duration_s, candidate_out)
            pairs.append({
                "pair_id": out_prefix,
                "file_id": f"{out_prefix}-reference-vs-candidate",
                "base_trial_id": trial_id,
                "vehicle_id": vehicle_id,
                "scenario": source_scenario,
                "reference_class": "R3",
                "reference_path": reference_meta["path"],
                "reference_sha256": reference_meta["sha256"],
                "candidate_path": candidate_meta["path"],
                "candidate_sha256": candidate_meta["sha256"],
                "reference_source_path": reference_meta["source_path"],
                "reference_source_sha256": reference_meta["source_sha256"],
                "candidate_source_path": candidate_meta["source_path"],
                "candidate_source_sha256": candidate_meta["source_sha256"],
                "window": {
                    "profile": f"{int(duration_s)}s",
                    "duration_s": duration_s,
                    "reference": reference_meta,
                    "candidate": candidate_meta,
                },
                "dynamic_scope": {
                    "source_scenario": source_scenario,
                    "selection_reason": source_record.get("selection_reason"),
                    "candidate_cycle_contract": "idle→acceleration→full_pull→lift/deceleration→cruise→idle",
                },
                "microphone_uncertainty": "UNKNOWN_PUBLIC_VIDEO_CAPTURE",
                "order": {"status": "ORDER_COMPARISON_NOT_QUALIFIED", "reason": "no synchronized RPM trace"},
                "uncertainty": {"legal_permission": "UNVERIFIED_R3", "stock_exhaust": "UNKNOWN", "rpm_state": "MISSING", "mic_agc": "UNKNOWN"},
            })
    manifest = {
        "schema_version": "s12-professional-long-window-manifest-v1",
        "status": "LONG_WINDOW_R2_R3_DIAGNOSTIC_READY",
        "anchor_manifest_path": str(anchor_manifest_path),
        "anchor_manifest_sha256": _sha256(anchor_manifest_path),
        "scenario_manifest_path": str(Path(scenario_manifest_path).resolve()),
        "scenario_manifest_sha256": _sha256(Path(scenario_manifest_path).resolve()),
        "candidate_root": str(candidate_root),
        "window_profiles_s": list(WINDOWS),
        "pair_count": len(pairs),
        "pairs": pairs,
        "raw_media_policy": "external_only",
        "derivation_policy": "time_slice_only_no_gain_eq_agc_resampling",
        "order_status": "ORDER_COMPARISON_NOT_QUALIFIED",
        "automatic_tuning_eligible": False,
        "profile_candidate_ready": False,
    }
    manifest_path = output_root / "long_window_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    receipt = {
        "schema_version": "s12-professional-long-window-receipt-v1",
        "status": "LONG_WINDOW_BUILD_PASS",
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "pair_count": len(pairs),
        "pairs_by_window": {profile: sum(row["window"]["profile"] == profile for row in pairs) for profile in ("15s", "30s")},
        "scene_counts": {scene: sum(row["scenario"] == scene for row in pairs) for scene in sorted({row["scenario"] for row in pairs})},
        "raw_media_policy": "external_only",
        "order_status": "ORDER_COMPARISON_NOT_QUALIFIED",
        "automatic_tuning_eligible": False,
        "profile_candidate_ready": False,
    }
    (output_root / "long_window_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return receipt


def load_long_window_pairs(manifest_path: Path) -> list[dict[str, Any]]:
    manifest_path = Path(manifest_path).resolve()
    manifest = _json(manifest_path)
    pairs = manifest.get("pairs")
    if manifest.get("schema_version") != "s12-professional-long-window-manifest-v1" or not isinstance(pairs, list) or not pairs:
        raise LongWindowError("invalid long-window manifest")
    result = []
    for pair in pairs:
        row = dict(pair)
        row["manifest_sha256"] = _sha256(manifest_path)
        result.append(row)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 15/30 秒 S12 长窗口 reference/candidate 外部包")
    parser.add_argument("--anchor-manifest", type=Path, required=True)
    parser.add_argument("--scenario-manifest", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    receipt = build_long_window_package(args.anchor_manifest, args.scenario_manifest, args.candidate_root, args.output_root)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


__all__ = ["LongWindowError", "WINDOWS", "build_long_window_package", "choose_candidate_window", "choose_reference_window", "load_long_window_pairs", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
