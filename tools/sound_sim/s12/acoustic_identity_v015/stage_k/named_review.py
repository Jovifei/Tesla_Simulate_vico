"""Build the explicit four-vehicle Stage-K listening package.

This is intentionally a *named* engineering review, not an anonymous human
qualification package.  It exposes vehicle names and diagnostic stems so Jovi
can locate a perceptual defect.  No sealed key is read or generated.
"""

from __future__ import annotations

import hashlib
import json
import gc
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
from typing import Mapping

import numpy as np

from ..acoustic_analysis import compute_order_map, write_order_map, write_spectrogram
from ..contracts import SourceRender, VehicleStateTrace
from ..loudness_manager import LoudnessMetrics, manage_bundle_loudness, measure_loudness
from ..render_drive_cycle_v10 import build_drive_cycle_trace
from ..render_identity_v02 import _apply_frozen_ptr, _edge_fade, _pcm24_roundtrip, _read_pcm24_wav, _write_pcm24_wav
from ..stage_d.scenarios import build_stage_d_scenario_trace
from .candidate_profiles import STAGE_K_VEHICLES, load_stage_k_candidate
from .feedback_contract import FEEDBACK_FIELDS, write_feedback_template
from .perceptual_metrics import compute_stage_k_perceptual_metrics
from .render_candidate import render_stage_k_candidate, render_stage_k_parent


SAMPLE_RATE_HZ = 48000
REVIEW_GAIN_LINEAR = 1.25
REVIEW_GAIN_DB = float(20.0 * np.log10(REVIEW_GAIN_LINEAR))
PEAK_LIMIT_DBFS = -1.5
PEAK_LIMIT_LINEAR = float(10.0 ** (PEAK_LIMIT_DBFS / 20.0))
PACKAGE_ID = "S12_Stage_K_Named_Review_v1"
STAGE_K_REVIEW_VEHICLES = STAGE_K_VEHICLES
_VEHICLE_DIRECTORIES = {
    "hellcat": "01_Hellcat",
    "c63_w204": "02_C63_W204",
    "gtr_r35": "03_GT-R_R35",
    "lfa": "04_LFA",
}
_CANDIDATE_FILENAMES = {
    "hellcat": "hellcat_candidate_v7.json",
    "c63_w204": "c63_w204_candidate_v2.json",
    "gtr_r35": "gtr_r35_candidate_v2.json",
    "lfa": "lfa_candidate_v2.json",
}
_DIAGNOSTIC_STEMS = {
    "hellcat": (
        ("Hellcat_BlowerOnly_Acceleration.wav", "blower", "acceleration"),
        ("Hellcat_ExhaustOnly_Acceleration.wav", "exhaust", "acceleration"),
        ("Hellcat_BypassOnly_Lift.wav", "blower_bypass_release", "lift"),
    ),
    "c63_w204": (
        ("C63_ExhaustOnly_Acceleration.wav", "exhaust", "acceleration"),
        ("C63_BarkOnly_Acceleration.wav", "bark", "acceleration"),
        ("C63_MechanicalOnly_Acceleration.wav", "mechanical", "acceleration"),
    ),
    "gtr_r35": (
        ("GTR_ExhaustOnly_Acceleration.wav", "exhaust", "acceleration"),
        ("GTR_TwoTurboOnly_Acceleration.wav", "turbo", "acceleration"),
        ("GTR_BOVOnly_Lift.wav", "bov", "lift"),
    ),
    "lfa": (
        ("LFA_ASG_Shift.wav", "lfa_shift_torque_cut", "shift"),
        ("LFA_IntakeReopen_Shift.wav", "lfa_shift_intake_reopen", "shift"),
        ("LFA_Overrun_Lift.wav", "lfa_overrun", "lift"),
    ),
}


def build_stage_k_named_review(
    output_root: str | Path,
    *,
    duration_s: float = 60.0,
    requested_review_gain_linear: float = REVIEW_GAIN_LINEAR,
    candidate_paths: Mapping[str, str | Path] | None = None,
) -> dict[str, object]:
    """Render the four named Stage-K baseline/candidate review package.

    ``duration_s`` is configurable for focused tests.  The formal package uses
    60 seconds and follows the canonical continuous drive-cycle timeline.  All
    files for one vehicle share one attenuation-only review gain; no section or
    diagnostic receives an independent gain.
    """

    if not np.isfinite(duration_s) or duration_s < 1.0:
        raise ValueError("duration_s must be finite and >= 1.0")
    if not np.isfinite(requested_review_gain_linear) or requested_review_gain_linear <= 0.0:
        raise ValueError("review gain must be finite and > 0")
    root = Path(output_root).resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"Stage-K named review output must be a new directory: {root}")
    return _build_stage_k_named_review_streaming(
        root=root,
        duration_s=float(duration_s),
        requested_review_gain_linear=float(requested_review_gain_linear),
        candidate_paths=candidate_paths,
    )
    for directory in _VEHICLE_DIRECTORIES.values():
        (root / directory).mkdir(parents=True, exist_ok=True)
    metrics_root = root / "05_Metrics"
    feedback_root = root / "06_Feedback"
    metrics_root.mkdir(parents=True, exist_ok=True)
    feedback_root.mkdir(parents=True, exist_ok=True)

    package_root = Path(__file__).resolve().parents[1]
    resolved_candidates = _resolve_candidate_paths(package_root, candidate_paths)
    candidates = {vehicle: load_stage_k_candidate(path) for vehicle, path in resolved_candidates.items()}
    vehicle_results: dict[str, object] = {}
    feedback_rows: list[dict[str, str]] = []

    scenario_duration = 12.0 if duration_s >= 12.0 else max(2.0, float(duration_s))
    for vehicle_id in STAGE_K_VEHICLES:
        directory = root / _VEHICLE_DIRECTORIES[vehicle_id]
        cycle_trace = build_drive_cycle_trace(vehicle_id, duration_s)
        baseline_render = render_stage_k_parent(vehicle_id, cycle_trace)
        candidate_render = render_stage_k_candidate(vehicle_id, cycle_trace, candidates[vehicle_id])
        scenario_traces = {
            "Low_Load_12s": _build_operating_trace(vehicle_id, "low_load", scenario_duration),
            "High_Load_12s": _build_operating_trace(vehicle_id, "high_load", scenario_duration),
            "Shift_12s": build_stage_d_scenario_trace(vehicle_id, "shift", scenario_duration),
            "Lift_Deceleration_12s": build_stage_d_scenario_trace(vehicle_id, "lift", scenario_duration),
        }
        formal: dict[str, dict[str, np.ndarray | SourceRender]] = {
            "baseline": {"render": baseline_render, "audio": _formal_audio(baseline_render)},
            "candidate": {"render": candidate_render, "audio": _formal_audio(candidate_render)},
        }
        for name, trace in scenario_traces.items():
            scenario_render = render_stage_k_candidate(vehicle_id, trace, candidates[vehicle_id])
            formal[name] = {"render": scenario_render, "audio": _formal_audio(scenario_render)}

        diagnostics = _diagnostic_audio(candidates[vehicle_id], vehicle_id, scenario_traces)
        raw_arrays = [np.asarray(value, dtype=np.float64) for value in formal_audio_values(formal)] + list(diagnostics.values())
        common_gain = _common_review_gain(raw_arrays, float(requested_review_gain_linear))
        written: dict[str, str] = {}
        for key, filename in (("baseline", "Baseline_60s.wav"), ("candidate", "StageK_Candidate_60s.wav"), *tuple((name, name + ".wav") for name in scenario_traces)):
            audio = _pcm24_roundtrip(np.asarray(formal[key]["audio"], dtype=np.float64) * common_gain)
            path = _write_pcm24_wav(directory / filename, audio)
            _assert_pcm_health(path)
            written[key] = str(path)
        diagnostic_paths: dict[str, str] = {}
        for filename, audio in diagnostics.items():
            path = _write_pcm24_wav(directory / filename, _pcm24_roundtrip(audio * common_gain))
            _assert_pcm_health(path)
            diagnostic_paths[filename] = str(path)

        baseline_final = _read_pcm24_wav(Path(written["baseline"]))
        candidate_final = _read_pcm24_wav(Path(written["candidate"]))
        baseline_loudness = _loudness_payload(measure_loudness(baseline_final))
        candidate_loudness = _loudness_payload(measure_loudness(candidate_final))
        source_metrics = compute_stage_k_perceptual_metrics(candidate_render, cycle_trace, SAMPLE_RATE_HZ, vehicle_id=vehicle_id)
        vehicle_metrics = {
            "vehicle_id": vehicle_id,
            "candidate_id": candidates[vehicle_id].candidate_id,
            "candidate_parameter_usage": candidate_render.diagnostics.get("candidate_parameter_usage", {}),
            "source_metrics": _json_safe(source_metrics),
            "cycle_trace": _trace_metadata(cycle_trace),
            "scenario_duration_s": scenario_duration,
            "pipeline_order": list(candidate_render.diagnostics.get("pipeline_order", ())),
            "review_loudness": {
                "requested_gain_linear": float(requested_review_gain_linear),
                "requested_gain_db": float(20.0 * np.log10(requested_review_gain_linear)),
                "applied_gain_linear": common_gain,
                "applied_gain_db": float(20.0 * np.log10(common_gain)),
                "headroom_limited": bool(common_gain < requested_review_gain_linear),
                "pair_common": True,
                "raw_lufs": {"baseline": _loudness_payload(measure_loudness(np.asarray(formal["baseline"]["audio"])))["integrated_lufs"], "candidate": _loudness_payload(measure_loudness(np.asarray(formal["candidate"]["audio"])))["integrated_lufs"]},
                "final_lufs": {"baseline": baseline_loudness["integrated_lufs"], "candidate": candidate_loudness["integrated_lufs"]},
                "raw_peak_dbfs": {"baseline": _loudness_payload(measure_loudness(np.asarray(formal["baseline"]["audio"])))["peak_dbfs"], "candidate": _loudness_payload(measure_loudness(np.asarray(formal["candidate"]["audio"])))["peak_dbfs"]},
                "final_peak_dbfs": {"baseline": baseline_loudness["peak_dbfs"], "candidate": candidate_loudness["peak_dbfs"]},
            },
            "baseline_wav": str(Path(written["baseline"])),
            "candidate_wav": str(Path(written["candidate"])),
            "diagnostic_wavs": diagnostic_paths,
            "provenance": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
        }
        metrics_path = metrics_root / f"{vehicle_id}_stage_k_metrics.json"
        metrics_path.write_text(json.dumps(_json_safe(vehicle_metrics), indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        if duration_s >= 8.0:
            candidate_audio = _read_pcm24_wav(Path(written["candidate"]))
            write_spectrogram(metrics_root / f"{vehicle_id}_spectrogram.png", candidate_audio, SAMPLE_RATE_HZ)
            write_order_map(metrics_root / f"{vehicle_id}_order_map.png", compute_order_map(candidate_audio, cycle_trace, SAMPLE_RATE_HZ))
        vehicle_results[vehicle_id] = {
            "directory": _VEHICLE_DIRECTORIES[vehicle_id],
            "baseline_wav": written["baseline"],
            "candidate_wav": written["candidate"],
            "scenario_wavs": {name: written[name] for name in scenario_traces},
            "diagnostic_wavs": diagnostic_paths,
            "metrics_json": str(metrics_path),
            "review_loudness": vehicle_metrics["review_loudness"],
            "health": {"baseline": _audio_health(baseline_final), "candidate": _audio_health(candidate_final)},
        }
        for key in ("Baseline_60s.wav", "StageK_Candidate_60s.wav", *tuple(name + ".wav" for name in scenario_traces)):
            feedback_rows.append({"file_id": Path(key).stem, "vehicle_id": vehicle_id})

    feedback_path = feedback_root / "Jovi_Stage_K_Named_Feedback.csv"
    write_feedback_template(feedback_path, feedback_rows)
    manifest = {
        "package_id": PACKAGE_ID,
        "status": "PARTIAL / AUTOMATED_GATE_FAIL",
        "automatic_gate_status": "PARTIAL / AUTOMATED_GATE_FAIL",
        "named_review_status": "WAITING_FOR_JOVI_STAGE_K_NAMED_REVIEW",
        "human_feedback_present": False,
        "sealed_key_read": False,
        "qualified_for_profile_freeze": False,
        "duration_s": float(duration_s),
        "scenario_duration_s": scenario_duration,
        "vehicle_ids": list(STAGE_K_VEHICLES),
        "vehicles": _json_safe(vehicle_results),
        "requested_review_gain_linear": float(requested_review_gain_linear),
        "requested_review_gain_db": float(20.0 * np.log10(requested_review_gain_linear)),
        "review_policy": "common baseline/candidate gain; attenuation-only headroom cap; no compressor/limiter/EQ/per-section AGC",
        "timeline": "0-8 idle; 8-26 acceleration + 3 shifts; 26-36 full pull; 36-46 lift/afterfire; 46-52 coast; 52-60 idle return",
        "provenance": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
    }
    manifest_path = root / "artifact_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    (root / "00_OPEN_ME_FIRST.md").write_text(_open_me_first(root, manifest), encoding="utf-8", newline="\n")
    (root / "SHA256SUMS.txt").write_text(_sha256sums(root), encoding="utf-8", newline="\n")
    zip_path = root / "S12_Stage_K_Named_Review.zip"
    _zip_tree(root, zip_path)
    return {**manifest, "output_root": str(root), "zip": str(zip_path), "feedback_csv": str(feedback_path), "requested_review_gain_linear": float(requested_review_gain_linear)}


def _build_stage_k_named_review_streaming(
    *,
    root: Path,
    duration_s: float,
    requested_review_gain_linear: float,
    candidate_paths: Mapping[str, str | Path] | None,
) -> dict[str, object]:
    """Build a named package without retaining multiple long SourceRenders.

    Each render is finalized and spilled to a private ``.npy`` file before the
    next render starts.  This is required for the formal 60-second package:
    the source layer contains many stereo float64 stems and retaining the six
    formal renders plus diagnostics can exhaust the process address space.
    """

    for directory in _VEHICLE_DIRECTORIES.values():
        (root / directory).mkdir(parents=True, exist_ok=True)
    metrics_root = root / "05_Metrics"
    feedback_root = root / "06_Feedback"
    metrics_root.mkdir(parents=True, exist_ok=True)
    feedback_root.mkdir(parents=True, exist_ok=True)
    package_root = Path(__file__).resolve().parents[1]
    resolved_candidates = _resolve_candidate_paths(package_root, candidate_paths)
    candidates = {vehicle: load_stage_k_candidate(path) for vehicle, path in resolved_candidates.items()}
    vehicle_results: dict[str, object] = {}
    feedback_rows: list[dict[str, str]] = []
    scenario_duration = 12.0 if duration_s >= 12.0 else max(2.0, float(duration_s))

    with tempfile.TemporaryDirectory(prefix=".stage_k_named_", dir=str(root)) as temp_root:
        for vehicle_id in STAGE_K_VEHICLES:
            result, rows = _stream_one_vehicle_review(
                root=root,
                temp_root=Path(temp_root),
                metrics_root=metrics_root,
                vehicle_id=vehicle_id,
                candidate=candidates[vehicle_id],
                candidate_path=resolved_candidates[vehicle_id],
                duration_s=duration_s,
                scenario_duration=scenario_duration,
                requested_review_gain_linear=requested_review_gain_linear,
            )
            vehicle_results[vehicle_id] = result
            feedback_rows.extend(rows)

    feedback_path = feedback_root / "Jovi_Stage_K_Named_Feedback.csv"
    write_feedback_template(feedback_path, feedback_rows)
    manifest = {
        "package_id": PACKAGE_ID,
        "status": "PARTIAL / AUTOMATED_GATE_FAIL",
        "automatic_gate_status": "PARTIAL / AUTOMATED_GATE_FAIL",
        "named_review_status": "WAITING_FOR_JOVI_STAGE_K_NAMED_REVIEW",
        "human_feedback_present": False,
        "sealed_key_read": False,
        "qualified_for_profile_freeze": False,
        "duration_s": float(duration_s),
        "scenario_duration_s": float(scenario_duration),
        "vehicle_ids": list(STAGE_K_VEHICLES),
        "vehicles": _json_safe(vehicle_results),
        "requested_review_gain_linear": float(requested_review_gain_linear),
        "requested_review_gain_db": float(20.0 * np.log10(requested_review_gain_linear)),
        "review_policy": "common baseline/candidate gain; attenuation-only headroom cap; no compressor/limiter/EQ/per-section AGC",
        "timeline": "0-8 idle; 8-26 acceleration + 3 shifts; 26-36 full pull; 36-46 lift/afterfire; 46-52 coast; 52-60 idle return",
        "provenance": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
    }
    manifest_path = root / "artifact_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    (root / "00_OPEN_ME_FIRST.md").write_text(_open_me_first(root, manifest), encoding="utf-8", newline="\n")
    (root / "SHA256SUMS.txt").write_text(_sha256sums(root), encoding="utf-8", newline="\n")
    zip_path = root / "S12_Stage_K_Named_Review.zip"
    _zip_tree(root, zip_path)
    return {
        **manifest,
        "output_root": str(root),
        "zip": str(zip_path),
        "feedback_csv": str(feedback_path),
        "requested_review_gain_linear": float(requested_review_gain_linear),
    }


def _run_isolated_render(
    *,
    vehicle_id: str,
    candidate_path: Path | None,
    mode: str,
    stem_name: str | None,
    duration_s: float,
    output_path: Path,
    metadata_path: Path,
) -> dict[str, object]:
    """Run one render in a fresh Python process and return its metadata."""

    repo_root = Path(__file__).resolve().parents[5]
    command = [
        sys.executable,
        "-m",
        "tools.sound_sim.s12.acoustic_identity_v015.stage_k.render_worker",
        "--vehicle-id",
        vehicle_id,
        "--mode",
        mode,
        "--duration-s",
        str(float(duration_s)),
        "--output-path",
        str(output_path.resolve()),
        "--metadata-path",
        str(metadata_path.resolve()),
    ]
    if candidate_path is not None:
        command.extend(("--candidate-path", str(candidate_path.resolve())))
    if stem_name is not None:
        command.extend(("--stem-name", stem_name))
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(repo_root) + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
    completed = subprocess.run(
        command,
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"isolated Stage-K render failed ({vehicle_id}/{mode}/{stem_name}): "
            f"exit={completed.returncode}; stderr={completed.stderr[-2000:]}"
        )
    if not output_path.is_file() or not metadata_path.is_file():
        raise RuntimeError(f"isolated Stage-K render did not produce evidence: {output_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError("isolated Stage-K render metadata must be an object")
    return metadata


def _stream_one_vehicle_review(
    *,
    root: Path,
    temp_root: Path,
    metrics_root: Path,
    vehicle_id: str,
    candidate: object,
    candidate_path: Path,
    duration_s: float,
    scenario_duration: float,
    requested_review_gain_linear: float,
) -> tuple[dict[str, object], list[dict[str, str]]]:
    directory = root / _VEHICLE_DIRECTORIES[vehicle_id]
    spill_root = temp_root / vehicle_id
    spill_root.mkdir(parents=True, exist_ok=True)
    cycle_trace = build_drive_cycle_trace(vehicle_id, duration_s)
    scenario_traces = {
        "Low_Load_12s": _build_operating_trace(vehicle_id, "low_load", scenario_duration),
        "High_Load_12s": _build_operating_trace(vehicle_id, "high_load", scenario_duration),
        "Shift_12s": build_stage_d_scenario_trace(vehicle_id, "shift", scenario_duration),
        "Lift_Deceleration_12s": build_stage_d_scenario_trace(vehicle_id, "lift", scenario_duration),
    }
    formal_specs = (
        ("baseline", "Baseline_60s.wav"),
        ("candidate", "StageK_Candidate_60s.wav"),
        *tuple((name, name + ".wav") for name in scenario_traces),
    )
    raw_paths: dict[str, Path] = {}
    raw_loudness: dict[str, dict[str, object]] = {}
    raw_peaks: list[float] = []
    source_metrics: dict[str, object] = {}
    candidate_usage: Mapping[str, object] = {}
    pipeline_order: tuple[str, ...] = ()

    for key, _filename in formal_specs:
        mode = "cycle" if key in {"baseline", "candidate"} else key
        raw_path = spill_root / f"{key}.npy"
        meta_path = spill_root / f"{key}.json"
        meta = _run_isolated_render(
            vehicle_id=vehicle_id,
            candidate_path=None if key == "baseline" else candidate_path,
            mode=mode,
            stem_name=None,
            duration_s=duration_s if key in {"baseline", "candidate"} else scenario_duration,
            output_path=raw_path,
            metadata_path=meta_path,
        )
        raw_paths[key] = raw_path
        raw_loudness[key] = dict(meta["loudness"])
        raw_peaks.append(float(meta["peak_linear"]))
        if key == "candidate":
            source_metrics = dict(meta.get("source_metrics", {}))
            candidate_usage = dict(meta.get("candidate_parameter_usage", {}))
            pipeline_order = tuple(meta.get("pipeline_order", ()))

    diagnostic_paths_raw: dict[str, Path] = {}
    for filename, stem_name, scenario in _DIAGNOSTIC_STEMS[vehicle_id]:
        mode = "Shift_12s" if scenario == "shift" else "Lift_Deceleration_12s" if scenario == "lift" else "High_Load_12s"
        raw_path = spill_root / (Path(filename).stem + ".npy")
        meta_path = spill_root / (Path(filename).stem + ".json")
        meta = _run_isolated_render(
            vehicle_id=vehicle_id,
            candidate_path=candidate_path,
            mode=mode,
            stem_name=stem_name,
            duration_s=scenario_duration,
            output_path=raw_path,
            metadata_path=meta_path,
        )
        raw_loudness[filename] = dict(meta["loudness"])
        raw_peaks.append(float(meta["peak_linear"]))
        diagnostic_paths_raw[filename] = raw_path

    common_gain = _common_review_gain_from_peak(max(raw_peaks, default=0.0), requested_review_gain_linear)
    written: dict[str, str] = {}
    for key, filename in formal_specs:
        audio = np.load(raw_paths[key], allow_pickle=False)
        final_audio = _pcm24_roundtrip(np.asarray(audio, dtype=np.float64) * common_gain)
        path = _write_pcm24_wav(directory / filename, final_audio)
        _assert_pcm_health(path)
        written[key] = str(path)
        del audio, final_audio
        gc.collect()
    diagnostic_paths: dict[str, str] = {}
    for filename, raw_path in diagnostic_paths_raw.items():
        audio = np.load(raw_path, allow_pickle=False)
        final_audio = _pcm24_roundtrip(np.asarray(audio, dtype=np.float64) * common_gain)
        path = _write_pcm24_wav(directory / filename, final_audio)
        _assert_pcm_health(path)
        diagnostic_paths[filename] = str(path)
        del audio, final_audio
        gc.collect()

    all_written_paths = {
        filename: Path(written[key])
        for key, filename in formal_specs
    }
    all_written_paths.update(diagnostic_paths)
    final_file_evidence: dict[str, dict[str, object]] = {}
    for filename, path in all_written_paths.items():
        final_audio = _read_pcm24_wav(path)
        final_loudness = _loudness_payload(measure_loudness(final_audio))
        final_health = _audio_health(final_audio)
        if filename == "Baseline_60s.wav":
            raw_key = "baseline"
        elif filename == "StageK_Candidate_60s.wav":
            raw_key = "candidate"
        else:
            raw_key = Path(filename).stem
        raw = raw_loudness[raw_key if raw_key in raw_loudness else filename]
        final_file_evidence[filename] = {
            "path": str(path),
            "raw_lufs": float(raw["integrated_lufs"]),
            "final_lufs": float(final_loudness["integrated_lufs"]),
            "raw_peak_dbfs": float(raw["peak_dbfs"]),
            "final_peak_dbfs": float(final_loudness["peak_dbfs"]),
            "requested_gain_db": float(20.0 * np.log10(requested_review_gain_linear)),
            "actual_gain_db": float(20.0 * np.log10(common_gain)),
            "headroom_limited": bool(common_gain < requested_review_gain_linear),
            "health": final_health,
        }
        del final_audio
        gc.collect()

    baseline_final = _read_pcm24_wav(Path(written["baseline"]))
    baseline_loudness = {
        key: value
        for key, value in final_file_evidence["Baseline_60s.wav"].items()
        if key in {"final_lufs", "final_peak_dbfs"}
    }
    baseline_health = final_file_evidence["Baseline_60s.wav"]["health"]
    del baseline_final
    gc.collect()
    candidate_final = _read_pcm24_wav(Path(written["candidate"]))
    candidate_loudness = {
        key: value
        for key, value in final_file_evidence["StageK_Candidate_60s.wav"].items()
        if key in {"final_lufs", "final_peak_dbfs"}
    }
    candidate_health = final_file_evidence["StageK_Candidate_60s.wav"]["health"]
    if duration_s >= 8.0:
        write_spectrogram(metrics_root / f"{vehicle_id}_spectrogram.png", candidate_final, SAMPLE_RATE_HZ)
        write_order_map(metrics_root / f"{vehicle_id}_order_map.png", compute_order_map(candidate_final, cycle_trace, SAMPLE_RATE_HZ))
    del candidate_final
    gc.collect()

    vehicle_metrics = {
        "vehicle_id": vehicle_id,
        "candidate_id": getattr(candidate, "candidate_id", "unknown"),
        "candidate_parameter_usage": candidate_usage,
        "source_metrics": _json_safe(source_metrics),
        "cycle_trace": _trace_metadata(cycle_trace),
        "scenario_duration_s": scenario_duration,
        "pipeline_order": list(pipeline_order),
        "review_loudness": {
            "requested_gain_linear": float(requested_review_gain_linear),
            "requested_gain_db": float(20.0 * np.log10(requested_review_gain_linear)),
            "applied_gain_linear": common_gain,
            "applied_gain_db": float(20.0 * np.log10(common_gain)),
            "headroom_limited": bool(common_gain < requested_review_gain_linear),
            "pair_common": True,
            "raw_lufs": {"baseline": final_file_evidence["Baseline_60s.wav"]["raw_lufs"], "candidate": final_file_evidence["StageK_Candidate_60s.wav"]["raw_lufs"]},
            "final_lufs": {"baseline": final_file_evidence["Baseline_60s.wav"]["final_lufs"], "candidate": final_file_evidence["StageK_Candidate_60s.wav"]["final_lufs"]},
            "raw_peak_dbfs": {"baseline": final_file_evidence["Baseline_60s.wav"]["raw_peak_dbfs"], "candidate": final_file_evidence["StageK_Candidate_60s.wav"]["raw_peak_dbfs"]},
            "final_peak_dbfs": {"baseline": final_file_evidence["Baseline_60s.wav"]["final_peak_dbfs"], "candidate": final_file_evidence["StageK_Candidate_60s.wav"]["final_peak_dbfs"]},
            "files": final_file_evidence,
        },
        "baseline_wav": str(Path(written["baseline"])),
        "candidate_wav": str(Path(written["candidate"])),
        "diagnostic_wavs": diagnostic_paths,
        "provenance": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
    }
    metrics_path = metrics_root / f"{vehicle_id}_stage_k_metrics.json"
    metrics_path.write_text(json.dumps(_json_safe(vehicle_metrics), indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    vehicle_result = {
        "directory": _VEHICLE_DIRECTORIES[vehicle_id],
        "baseline_wav": written["baseline"],
        "candidate_wav": written["candidate"],
        "scenario_wavs": {name: written[name] for name in scenario_traces},
        "diagnostic_wavs": diagnostic_paths,
        "metrics_json": str(metrics_path),
        "review_loudness": vehicle_metrics["review_loudness"],
        "health": {
            "baseline": baseline_health,
            "candidate": candidate_health,
            "files": {filename: evidence["health"] for filename, evidence in final_file_evidence.items()},
        },
    }
    rows = [
        {"file_id": Path(filename).stem, "vehicle_id": vehicle_id}
        for _key, filename in formal_specs
    ]
    return vehicle_result, rows


def _resolve_candidate_paths(package_root: Path, paths: Mapping[str, str | Path] | None) -> dict[str, Path]:
    if paths is None:
        root = package_root / "targets" / "stage_k_candidates"
        return {vehicle: root / _CANDIDATE_FILENAMES[vehicle] for vehicle in STAGE_K_VEHICLES}
    if set(paths) != set(STAGE_K_VEHICLES):
        raise ValueError("candidate_paths must contain exactly the four Stage-K vehicles")
    return {vehicle: Path(paths[vehicle]).resolve() for vehicle in STAGE_K_VEHICLES}


def _formal_audio(render: SourceRender) -> np.ndarray:
    ptr_audio = _edge_fade(_apply_frozen_ptr(render.pressure))
    managed = manage_bundle_loudness({"cycle": ptr_audio}, SAMPLE_RATE_HZ, target_lufs=-16.0, peak_limit_dbfs=PEAK_LIMIT_DBFS)
    return _pcm24_roundtrip(managed.segments["cycle"])


def formal_audio_values(formal: Mapping[str, Mapping[str, object]]) -> tuple[np.ndarray, ...]:
    return tuple(np.asarray(value["audio"], dtype=np.float64) for value in formal.values())


def _diagnostic_audio(candidate: object, vehicle_id: str, traces: Mapping[str, VehicleStateTrace]) -> dict[str, np.ndarray]:
    result: dict[str, np.ndarray] = {}
    for filename, stem_name, scenario in _DIAGNOSTIC_STEMS[vehicle_id]:
        trace = traces["Shift_12s"] if scenario == "shift" else traces["Lift_Deceleration_12s"] if scenario == "lift" else traces["High_Load_12s"]
        # A diagnostic trace has to be rendered from its own state; reusing the
        # cycle render would put the wrong transient at the wrong time.  The
        # explicitly loaded candidate is passed through so custom candidate
        # paths cannot silently fall back to a different profile.
        scenario_render = render_stage_k_candidate(vehicle_id, trace, candidate)
        if stem_name == "turbo":
            stem = sum(
                (np.asarray(scenario_render.stems.get(name, np.zeros_like(scenario_render.pressure)), dtype=np.float64)
                 for name in ("turbo_primary", "turbo_secondary", "turbo_sidebands", "intake_duct")),
                np.zeros_like(scenario_render.pressure),
            )
        elif stem_name == "bov":
            stem = np.asarray(scenario_render.stems.get("wastegate", np.zeros_like(scenario_render.pressure)), dtype=np.float64)
        else:
            stem = np.asarray(scenario_render.stems.get(stem_name, np.zeros_like(scenario_render.pressure)), dtype=np.float64)
        result[filename] = _pcm24_roundtrip(_edge_fade(_apply_frozen_ptr(stem)))
    return result


def _diagnostic_audio_one(
    candidate: object,
    vehicle_id: str,
    trace: VehicleStateTrace,
    stem_name: str,
) -> np.ndarray:
    """Render and finalize one diagnostic stem, releasing its SourceRender."""

    scenario_render = render_stage_k_candidate(vehicle_id, trace, candidate)
    if stem_name == "turbo":
        stem = sum(
            (
                np.asarray(
                    scenario_render.stems.get(name, np.zeros_like(scenario_render.pressure)),
                    dtype=np.float64,
                )
                for name in ("turbo_primary", "turbo_secondary", "turbo_sidebands", "intake_duct")
            ),
            np.zeros_like(scenario_render.pressure),
        )
    elif stem_name == "bov":
        stem = np.asarray(
            scenario_render.stems.get("wastegate", np.zeros_like(scenario_render.pressure)),
            dtype=np.float64,
        )
    else:
        stem = np.asarray(
            scenario_render.stems.get(stem_name, np.zeros_like(scenario_render.pressure)),
            dtype=np.float64,
        )
    audio = _pcm24_roundtrip(_edge_fade(_apply_frozen_ptr(stem)))
    del stem, scenario_render
    gc.collect()
    return audio


def _default_candidate_path(vehicle_id: str) -> Path:
    return Path(__file__).resolve().parents[1] / "targets" / "stage_k_candidates" / _CANDIDATE_FILENAMES[vehicle_id]


def _build_operating_trace(vehicle_id: str, state: str, duration_s: float) -> VehicleStateTrace:
    idle = {"hellcat": 820.0, "c63_w204": 750.0, "gtr_r35": 1000.0, "lfa": 900.0}[vehicle_id]
    rpm = 1900.0 if state == "low_load" else 5200.0
    load = 0.20 if state == "low_load" else 0.90
    throttle = load
    count = int(round(duration_s * SAMPLE_RATE_HZ)) + 1
    time_s = np.linspace(0.0, duration_s, count)
    return VehicleStateTrace(time_s, np.full(count, max(idle, rpm)), np.full(count, load), np.full(count, throttle), np.zeros(count)).validate()


def _common_review_gain(arrays: list[np.ndarray], requested: float) -> float:
    peak = max((float(np.max(np.abs(array))) for array in arrays if array.size), default=0.0)
    return _common_review_gain_from_peak(peak, requested)


def _common_review_gain_from_peak(peak: float, requested: float) -> float:
    """Return one attenuation-only review gain from a previously measured peak."""

    if peak <= 0.0:
        return float(requested)
    return float(min(requested, PEAK_LIMIT_LINEAR / peak))


def _assert_pcm_health(path: Path) -> None:
    audio = _read_pcm24_wav(path)
    health = _audio_health(audio)
    if not health["passes"]:
        raise ValueError(f"Stage-K named WAV health gate failed: {path}")


def _audio_health(audio: np.ndarray) -> dict[str, object]:
    metrics = measure_loudness(audio, SAMPLE_RATE_HZ)
    return {
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "channels": 2,
        "pcm_bits": 24,
        "finite": bool(np.all(np.isfinite(audio))),
        "peak_dbfs": float(metrics.peak_dbfs),
        "clipping_count": int(metrics.clipping_count),
        "passes": bool(np.all(np.isfinite(audio)) and metrics.clipping_count == 0 and metrics.peak_dbfs <= PEAK_LIMIT_DBFS + 1.0e-6),
    }


def _loudness_payload(metrics: LoudnessMetrics) -> dict[str, object]:
    return {"integrated_lufs": float(metrics.integrated_lufs), "rms_dbfs": float(metrics.rms_dbfs), "peak_dbfs": float(metrics.peak_dbfs), "crest_factor_db": float(metrics.crest_factor_db), "clipping_count": int(metrics.clipping_count)}


def _trace_metadata(trace: VehicleStateTrace) -> dict[str, object]:
    return {"duration_s": float(trace.time_s[-1]), "samples": int(trace.time_s.size), "rpm_start": float(trace.rpm[0]), "rpm_end": float(trace.rpm[-1]), "load_start": float(trace.load[0]), "load_end": float(trace.load[-1]), "throttle_start": float(trace.throttle[0]), "throttle_end": float(trace.throttle[-1])}


def _open_me_first(root: Path, manifest: Mapping[str, object]) -> str:
    lines = [
        "# S12 Stage K 四车具名试听包",
        "",
        "状态：`WAITING_FOR_JOVI_STAGE_K_NAMED_REVIEW`（自动门禁若未完成则同时保留 `PARTIAL / AUTOMATED_GATE_FAIL`）。",
        "",
        "这是具名工程校准包，不是匿名盲听资格包；没有读取任何 sealed key，也没有填写虚构的人耳结果。",
        "",
        "## 试听顺序",
        "",
        "先比较每个车型目录内的 `Baseline_60s.wav` 与 `StageK_Candidate_60s.wav`，再听 `Low_Load_12s.wav`、`High_Load_12s.wav`、`Shift_12s.wav`、`Lift_Deceleration_12s.wav`。诊断 stem 只用于定位声源，不是正式产品音频。",
        "",
        "60 秒时间线：0–8 秒怠速；8–26 秒加速并含 3 次换挡；26–36 秒 full pull；36–46 秒收油/回火；46–52 秒 coast；52–60 秒回到怠速。测试短时构建会在 manifest 中记录实际 duration。",
        "",
        f"试听增响请求为 1.25x（{REVIEW_GAIN_DB:.4f} dB）。同一车辆的 baseline/candidate/场景/诊断文件共用一个 attenuation-only 增益，若峰值余量不足只会衰减；不使用 compressor、limiter、EQ 或分段 AGC。",
        "",
        "所有参数和音频均为 synthetic / uncalibrated / vehicle-inspired / not OEM reproduction。请把反馈写入 `06_Feedback/Jovi_Stage_K_Named_Feedback.csv`。",
        "",
    ]
    for vehicle_id in STAGE_K_REVIEW_VEHICLES:
        lines.extend((f"## {vehicle_id}", "", f"目录：`{root / _VEHICLE_DIRECTORIES[vehicle_id]}`", f"Baseline：`{root / _VEHICLE_DIRECTORIES[vehicle_id] / 'Baseline_60s.wav'}`", f"Candidate：`{root / _VEHICLE_DIRECTORIES[vehicle_id] / 'StageK_Candidate_60s.wav'}`", ""))
    return "\n".join(lines)


def _open_me_first(root: Path, manifest: Mapping[str, object]) -> str:
    """Readable UTF-8 handoff page for the named calibration package."""

    lines = [
        "# S12 Stage K Four-Vehicle Named Review",
        "",
        "Status: `WAITING_FOR_JOVI_STAGE_K_NAMED_REVIEW`; automatic qualification remains separately reported.",
        "",
        "This is a named engineering calibration package, not an anonymous qualification package. No sealed key was read and no human result was invented.",
        "",
        "## Listening order",
        "",
        "For each vehicle, compare `Baseline_60s.wav` with `StageK_Candidate_60s.wav`, then listen to the four 12-second state clips. Diagnostic stems locate a source; they are not product audio.",
        "",
        "The formal timeline is 0-8 s idle, 8-26 s acceleration with three shifts, 26-36 s full pull, 36-46 s lift/afterfire, 46-52 s coast, and 52-60 s idle return. Short test builds record their actual duration in the manifest.",
        "",
        f"The requested review boost is 1.25x ({REVIEW_GAIN_DB:.4f} dB). Each vehicle uses one common attenuation-only gain for baseline, candidate, state, and diagnostic files; headroom may reduce it. No compressor, limiter, EQ, or per-section AGC is used.",
        "",
        "All output is synthetic / uncalibrated / vehicle-inspired / not OEM reproduction. Enter feedback in `06_Feedback/Jovi_Stage_K_Named_Feedback.csv`.",
        "",
    ]
    for vehicle_id in STAGE_K_REVIEW_VEHICLES:
        directory = root / _VEHICLE_DIRECTORIES[vehicle_id]
        lines.extend(
            (
                f"## {vehicle_id}",
                "",
                f"Directory: `{directory}`",
                f"Baseline: `{directory / 'Baseline_60s.wav'}`",
                f"Candidate: `{directory / 'StageK_Candidate_60s.wav'}`",
                "",
            )
        )
    return "\n".join(lines)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256sums(root: Path) -> str:
    lines = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name not in {"SHA256SUMS.txt", "S12_Stage_K_Named_Review.zip"}:
            lines.append(f"{_sha256(path)}  {path.relative_to(root).as_posix()}\n")
    return "".join(lines)


def _zip_tree(root: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path in {zip_path, root / "S12_Stage_K_Named_Review.zip"}:
                continue
            info = zipfile.ZipInfo(path.relative_to(root).as_posix())
            info.date_time = (2020, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def _json_safe(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (int, str, bool)) or value is None:
        return value
    return str(value)


__all__ = ("PACKAGE_ID", "REVIEW_GAIN_DB", "REVIEW_GAIN_LINEAR", "STAGE_K_REVIEW_VEHICLES", "build_stage_k_named_review")
