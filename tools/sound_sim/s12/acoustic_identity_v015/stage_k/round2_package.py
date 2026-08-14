"""Content-addressed three-vehicle Stage-K Round-2 diagnostic package."""

from __future__ import annotations

import gc
import hashlib
import json
import os
from pathlib import Path
import shutil
import zipfile
from typing import Mapping

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace
from ..loudness_manager import manage_bundle_loudness, measure_loudness
from ..render_drive_cycle_v10 import build_drive_cycle_trace
from ..render_identity_v02 import _apply_frozen_ptr, _edge_fade, _pcm24_roundtrip, _write_pcm24_wav
from ..stage_d.scenarios import build_stage_d_scenario_trace
from .candidate_profiles import load_stage_k_candidate
from .named_review import _build_operating_trace
from .render_candidate import render_stage_k_candidate, render_stage_k_parent
from .round2_propagation import (
    ROUND2_PARAMETER_GRIDS,
    apply_round2_tuning,
    measure_round2_metrics,
    reconcile_round2_pressure,
)


SAMPLE_RATE_HZ = 48_000
PEAK_LIMIT_DBFS = -1.5
PEAK_LIMIT_LINEAR = float(10.0 ** (PEAK_LIMIT_DBFS / 20.0))
REVIEW_GAIN_LINEAR = 1.25
PACKAGE_ID = "S12_Stage_K_Three_Vehicle_Round2_v1"
SCHEMA_VERSION = "s12-stage-k-three-vehicle-round2-artifact-1"
VEHICLES = ("c63_w204", "gtr_r35", "lfa")
VEHICLE_DIRECTORIES = {
    "c63_w204": "01_C63_W204",
    "gtr_r35": "02_GT-R_R35",
    "lfa": "03_LFA",
}
CANDIDATE_FILENAMES = {
    "c63_w204": "c63_w204_candidate_v2.json",
    "gtr_r35": "gtr_r35_candidate_v2.json",
    "lfa": "lfa_candidate_v2.json",
}
PIPELINE_ORDER = ("frozen_ptr", "edge_fade", "one_fixed_whole_cycle_gain", "pcm24")


def build_stage_k_three_vehicle_round2_review(
    output_root: str | Path,
    *,
    duration_s: float = 60.0,
    parameter_sets: Mapping[str, Mapping[str, float]] | None = None,
    requested_review_gain_linear: float = REVIEW_GAIN_LINEAR,
) -> dict[str, object]:
    """Build a new package; never overwrite an existing root or package ZIP."""

    if not np.isfinite(duration_s) or duration_s < 1.0:
        raise ValueError("duration_s must be finite and >= 1.0")
    if not np.isfinite(requested_review_gain_linear) or requested_review_gain_linear <= 0.0:
        raise ValueError("requested_review_gain_linear must be finite and > 0")
    root = Path(output_root).resolve()
    if root.exists():
        raise FileExistsError(f"Round-2 package root must be new: {root}")
    if parameter_sets is not None and set(parameter_sets) != set(VEHICLES):
        raise ValueError("parameter_sets must contain exactly C63, GT-R and LFA")
    selected_parameters = {
        vehicle: dict(parameter_sets[vehicle]) if parameter_sets is not None else {
            name: values[1] for name, values in ROUND2_PARAMETER_GRIDS[vehicle].items()
        }
        for vehicle in VEHICLES
    }

    staging = root.parent / f".{root.name}.artifacts"
    if staging.exists():
        raise FileExistsError(f"Round-2 hidden staging root already exists: {staging}")
    staging.mkdir(parents=True, exist_ok=False)
    try:
        vehicles: dict[str, object] = {}
        for vehicle_id in VEHICLES:
            vehicles[vehicle_id] = _build_vehicle(
                staging,
                vehicle_id,
                float(duration_s),
                selected_parameters[vehicle_id],
                float(requested_review_gain_linear),
            )

        manifest: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "package_id": PACKAGE_ID,
            "status": "PARTIAL / AUTOMATED_GATE_FAIL / UNQUALIFIED_DIAGNOSTIC_ONLY",
            "automatic_gate_status": "PARTIAL / AUTOMATED_GATE_FAIL",
            "qualification_status": "UNQUALIFIED_DIAGNOSTIC_ONLY",
            "human_pass": False,
            "csv_content_read": False,
            "human_feedback_content_read": False,
            "duration_s": float(duration_s),
            "vehicle_ids": list(VEHICLES),
            "vehicles": vehicles,
            "review_gain_policy": "one common attenuation-only whole-cycle gain for formal trio; comfort is one static post-PCM gain",
            "pipeline_order": list(PIPELINE_ORDER),
            "source_scope": "C/synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
            "provenance": "Round-2 diagnostic propagation; no OEM calibration claim",
        }
        manifest_path = staging / "artifact_manifest.json"
        manifest_path.write_text(_dump_json(manifest), encoding="utf-8", newline="\n")
        sums_path = staging / "SHA256SUMS.txt"
        sums_path.write_text(_sha256sums(staging), encoding="utf-8", newline="\n")
        zip_path = staging / "S12_Stage_K_Three_Vehicle_Round2_UNQUALIFIED_DIAGNOSTIC_Review.zip"
        _write_zip(staging, zip_path)
        os.replace(staging, root)
        final_manifest = dict(manifest)
        final_manifest.update(
            {
                "output_root": str(root),
                "artifact_manifest": str(root / "artifact_manifest.json"),
                "sha256sums": str(root / "SHA256SUMS.txt"),
                "zip": str(root / zip_path.name),
            }
        )
        return final_manifest
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _build_vehicle(
    root: Path,
    vehicle_id: str,
    duration_s: float,
    parameters: Mapping[str, float],
    requested_gain: float,
) -> dict[str, object]:
    directory = root / VEHICLE_DIRECTORIES[vehicle_id]
    directory.mkdir(parents=True, exist_ok=True)
    package_root = Path(__file__).resolve().parents[1]
    candidate_path = package_root / "targets" / "stage_k_candidates" / CANDIDATE_FILENAMES[vehicle_id]
    candidate = load_stage_k_candidate(candidate_path)
    profile_sha = _sha256_file(candidate_path)
    trace = build_drive_cycle_trace(vehicle_id, duration_s)
    trace_sha = _trace_sha256(trace)

    parent = render_stage_k_parent(vehicle_id, trace)
    baseline = reconcile_round2_pressure(vehicle_id, render_stage_k_candidate(vehicle_id, trace, candidate))
    candidate_render = apply_round2_tuning(
        vehicle_id,
        render_stage_k_candidate(vehicle_id, trace, candidate),
        trace,
        parameters,
    )
    formal_raw = {
        "parent": _formal_source(parent),
        "baseline": _formal_source(baseline),
        "candidate": _formal_source(candidate_render),
    }
    managed = manage_bundle_loudness(
        formal_raw,
        SAMPLE_RATE_HZ,
        target_lufs=-16.0,
        peak_limit_dbfs=PEAK_LIMIT_DBFS,
    )
    formal: dict[str, dict[str, object]] = {}
    final_arrays: dict[str, np.ndarray] = {}
    names = {
        "parent": f"Dodge_{vehicle_id}_StageK_Parent_{int(duration_s)}s.wav",
        "baseline": f"Dodge_{vehicle_id}_StageK_v2_Baseline_{int(duration_s)}s.wav",
        "candidate": f"Dodge_{vehicle_id}_StageK_Round2_Candidate_{int(duration_s)}s.wav",
    }
    for role, audio in managed.segments.items():
        final = _pcm24_roundtrip(np.asarray(audio, dtype=np.float64))
        final_arrays[role] = final
        path = directory / names[role]
        _write_pcm24_wav(path, final)
        formal[role] = _formal_receipt(
            path,
            role=role,
            vehicle_id=vehicle_id,
            profile_sha=profile_sha,
            trace_sha=trace_sha,
            gain_linear=managed.gain_linear,
            headroom_limited=managed.headroom_limited,
        )

    comfort_peak = float(np.max(np.abs(final_arrays["candidate"]))) if final_arrays["candidate"].size else 0.0
    comfort_gain = min(float(requested_gain), PEAK_LIMIT_LINEAR / comfort_peak) if comfort_peak else float(requested_gain)
    comfort = _pcm24_roundtrip(final_arrays["candidate"] * comfort_gain)
    comfort_path = directory / f"Dodge_{vehicle_id}_StageK_Round2_Candidate_Comfort_{int(duration_s)}s.wav"
    _write_pcm24_wav(comfort_path, comfort)
    comfort_receipt = _formal_receipt(
        comfort_path,
        role="comfort",
        vehicle_id=vehicle_id,
        profile_sha=profile_sha,
        trace_sha=trace_sha,
        gain_linear=comfort_gain,
        headroom_limited=bool(comfort_gain < requested_gain),
        input_sha256=formal["candidate"]["sha256"],
    )
    comfort_receipt["comfort_gain_linear"] = comfort_gain
    formal["comfort"] = comfort_receipt

    metrics = measure_round2_metrics(vehicle_id, candidate_render, trace, SAMPLE_RATE_HZ, parent_render=baseline)
    metrics_path = directory / "round2_source_metrics.json"
    metrics_path.write_text(_dump_json({
        "schema_version": SCHEMA_VERSION,
        "vehicle_id": vehicle_id,
        "candidate_id": f"{candidate.candidate_id}_round2_seed",
        "profile_sha256": profile_sha,
        "trace_sha256": trace_sha,
        "parameters": dict(parameters),
        "metrics": metrics,
        "status": "PARTIAL / AUTOMATED_GATE_FAIL / UNQUALIFIED_DIAGNOSTIC_ONLY",
    }), encoding="utf-8", newline="\n")

    diagnostics = _build_diagnostics(directory, vehicle_id, candidate, parameters, profile_sha)
    del parent, baseline, candidate_render, final_arrays, formal_raw, managed
    gc.collect()
    return {
        "vehicle_id": vehicle_id,
        "base_candidate_id": candidate.candidate_id,
        "profile_sha256": profile_sha,
        "round2_parameters": dict(parameters),
        "formal": formal,
        "diagnostics": diagnostics,
        "metrics_json": str(metrics_path.relative_to(root)),
        "trace_sha256": trace_sha,
        "producer": "stage_k.round2_package.build_stage_k_three_vehicle_round2_review",
    }


def _build_diagnostics(
    root: Path,
    vehicle_id: str,
    candidate: object,
    parameters: Mapping[str, float],
    profile_sha: str,
) -> dict[str, dict[str, object]]:
    specs = {
        "c63_w204": (
            ("C63_BarkBody_18s.wav", "high_load", "bark"),
            ("C63_UpperRoughness_18s.wav", "high_load", "bark_primary"),
            ("C63_Mechanical_18s.wav", "high_load", "mechanical"),
            ("C63_ClosedThrottle_10s.wav", "lift", "closed_throttle_tail"),
        ),
        "gtr_r35": (
            ("GTR_Exhaust_18s.wav", "high_load", "exhaust"),
            ("GTR_TwinTurbo_18s.wav", "high_load", "turbo"),
            ("GTR_ExhaustTurbo_18s.wav", "high_load", "combined"),
            ("GTR_BOV_10s.wav", "lift", "bov"),
        ),
        "lfa": (
            ("LFA_Exhaust_18s.wav", "high_load", "exhaust"),
            ("LFA_OrderFamily_18s.wav", "high_load", "order_family"),
            ("LFA_IntakeMetallic_18s.wav", "high_load", "intake_metallic"),
            ("LFA_ASG_10s.wav", "shift", "lfa_shift_exhaust_reengagement"),
        ),
    }[vehicle_id]
    result: dict[str, dict[str, object]] = {}
    for filename, scenario, stem_name in specs:
        duration = 10.0 if filename.endswith("10s.wav") else 18.0
        trace = (
            _build_operating_trace(vehicle_id, "high_load", duration)
            if scenario == "high_load"
            else build_stage_d_scenario_trace(vehicle_id, scenario, duration)
        )
        raw = render_stage_k_candidate(vehicle_id, trace, candidate)
        tuned = apply_round2_tuning(vehicle_id, raw, trace, parameters)
        audio = _diagnostic_audio(tuned, stem_name)
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        gain = min(1.0, PEAK_LIMIT_LINEAR / peak) if peak else 1.0
        final = _pcm24_roundtrip(audio * gain)
        path = root / filename
        _write_pcm24_wav(path, final)
        result[Path(filename).stem] = {
            "path": str(path.relative_to(root.parent)),
            "role": stem_name,
            "source_domain": True,
            "scenario": scenario,
            "duration_s": float(trace.time_s[-1]),
            "profile_sha256": profile_sha,
            "trace_sha256": _trace_sha256(trace),
            "attenuation_only_gain_linear": float(gain),
            "sha256": _sha256_file(path),
            "frames": int(final.shape[0]),
            "pcm_health": _pcm_health(final),
        }
        del raw, tuned, audio, final
        gc.collect()
    return result


def _formal_source(render: SourceRender) -> np.ndarray:
    return _edge_fade(_apply_frozen_ptr(np.asarray(render.pressure, dtype=np.float64)))


def _diagnostic_audio(render: SourceRender, stem_name: str) -> np.ndarray:
    pressure = np.asarray(render.pressure, dtype=np.float64)
    if stem_name == "turbo":
        return sum((np.asarray(render.stems.get(name, np.zeros_like(pressure)), dtype=np.float64) for name in ("turbo_primary", "turbo_secondary", "turbo_sidebands", "intake_duct")), np.zeros_like(pressure))
    if stem_name == "combined":
        return np.asarray(render.stems.get("exhaust", np.zeros_like(pressure)), dtype=np.float64) + _diagnostic_audio(render, "turbo")
    if stem_name == "bov":
        return np.asarray(render.stems.get("wastegate", np.zeros_like(pressure)), dtype=np.float64)
    if stem_name == "intake_metallic":
        return np.asarray(render.stems.get("intake", np.zeros_like(pressure)), dtype=np.float64) + np.asarray(render.stems.get("metallic", np.zeros_like(pressure)), dtype=np.float64)
    return np.asarray(render.stems.get(stem_name, np.zeros_like(pressure)), dtype=np.float64)


def _formal_receipt(
    path: Path,
    *,
    role: str,
    vehicle_id: str,
    profile_sha: str,
    trace_sha: str,
    gain_linear: float,
    headroom_limited: bool,
    input_sha256: str | None = None,
) -> dict[str, object]:
    audio = _read_pcm24(path)
    record = {
        "path": path.relative_to(path.parents[1]).as_posix(),
        "vehicle_id": vehicle_id,
        "role": role,
        "source_domain": False,
        "sha256": _sha256_file(path),
        "frames": int(audio.shape[0]),
        "duration_s": float(audio.shape[0] / SAMPLE_RATE_HZ),
        "profile_sha256": profile_sha,
        "trace_sha256": trace_sha,
        "pipeline_order": list(PIPELINE_ORDER),
        "common_gain_linear": float(gain_linear),
        "headroom_limited": bool(headroom_limited),
        "pcm_health": _pcm_health(audio),
    }
    if input_sha256 is not None:
        record["input_sha256"] = input_sha256
    return record


def _pcm_health(audio: np.ndarray) -> dict[str, object]:
    metrics = measure_loudness(audio, SAMPLE_RATE_HZ)
    return {
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "channels": int(audio.shape[1]) if audio.ndim == 2 else 1,
        "pcm_bits": 24,
        "finite": bool(np.all(np.isfinite(audio))),
        "peak_dbfs": float(metrics.peak_dbfs),
        "clipping_count": int(metrics.clipping_count),
        "passes": bool(np.all(np.isfinite(audio)) and audio.ndim == 2 and audio.shape[1] == 2 and metrics.clipping_count == 0 and metrics.peak_dbfs <= PEAK_LIMIT_DBFS + 1.0e-6),
    }


def _read_pcm24(path: Path) -> np.ndarray:
    from ..render_identity_v02 import _read_pcm24_wav

    return np.asarray(_read_pcm24_wav(path), dtype=np.float64)


def _trace_sha256(trace: VehicleStateTrace) -> str:
    digest = hashlib.sha256()
    for values in (trace.time_s, trace.rpm, trace.load, trace.throttle, trace.acceleration_mps2):
        digest.update(np.asarray(values, dtype=np.float64).tobytes())
    return digest.hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256sums(root: Path) -> str:
    rows = []
    for path in sorted(path for path in root.rglob("*") if path.is_file() and path.name != "SHA256SUMS.txt"):
        rows.append(f"{_sha256_file(path)}  {path.relative_to(root).as_posix()}")
    return "\n".join(rows) + "\n"


def _write_zip(root: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(path for path in root.rglob("*") if path.is_file() and path != zip_path):
            info = zipfile.ZipInfo(path.relative_to(root).as_posix(), date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def _dump_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


__all__ = ("PACKAGE_ID", "SCHEMA_VERSION", "build_stage_k_three_vehicle_round2_review")
