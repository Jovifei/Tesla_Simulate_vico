"""Independent Stage-K Round-2 package for the four remaining vehicles.

This module is deliberately a package layer.  The two source facades own the
vehicle-specific source overlays and measurements; this module owns only the
content-addressed review artifact, the shared finalization pipeline, and
short/long package orchestration.  It never reads a caller-provided manifest
or diagnostic claim as evidence.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Callable, Mapping
import wave
import zipfile

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace
from ..loudness_manager import measure_loudness
from ..render_drive_cycle_v10 import build_drive_cycle_trace
from ..render_identity_v02 import _apply_frozen_ptr, _edge_fade, _pcm24_roundtrip, _read_pcm24_wav, _write_pcm24_wav


SAMPLE_RATE_HZ = 48_000
PEAK_LIMIT_DBFS = -1.5
PEAK_LIMIT_LINEAR = float(10.0 ** (PEAK_LIMIT_DBFS / 20.0))
REVIEW_GAIN_LINEAR = 1.25
PACKAGE_ID = "S12_Stage_K_Remaining_Four_Vehicle_Round2_v1"
SCHEMA_VERSION = "s12-stage-k-remaining-four-vehicle-round2-artifact-1"
STATUS = "PARTIAL / AUTOMATED_GATE_FAIL / UNQUALIFIED_DIAGNOSTIC_ONLY"
AUTOMATIC_GATE_STATUS = "PARTIAL / AUTOMATED_GATE_FAIL"
QUALIFICATION_STATUS = "UNQUALIFIED_DIAGNOSTIC_ONLY"
VEHICLES = ("ferrari_458", "rx7_fd", "supra_jza80", "aventador_lp700")
VEHICLE_DIRECTORIES = {
    "ferrari_458": "01_Ferrari_458",
    "rx7_fd": "02_RX7_FD",
    "supra_jza80": "03_Supra_JZA80",
    "aventador_lp700": "04_Aventador_LP700",
}
PIPELINE_ORDER = ("frozen_ptr", "edge_fade", "one_fixed_whole_cycle_gain", "pcm24")

# The names are source views, not additional synthesis layers.  Alternatives
# allow the package to bind the exact stem returned by either facade while
# failing closed if a source does not expose the expected physical component.
DIAGNOSTIC_STEMS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "ferrari_458": (
        ("bank_left", ("left_bank", "exhaust_left_bank", "exhaust")),
        ("bank_right", ("right_bank", "exhaust_right_bank", "exhaust")),
        ("metallic", ("metallic", "metallic_resonance", "radiation")),
        ("shift_recovery", ("shift_recovery_boom", "shift_impact", "afterfire")),
    ),
    "rx7_fd": (
        ("rotary", ("rotary",)),
        ("rotor_housing", ("rotor_housing", "exhaust")),
        ("turbo", ("turbo", "turbine")),
        ("blow_off", ("blow_off", "lift", "afterfire")),
    ),
    "supra_jza80": (
        ("exhaust", ("exhaust",)),
        ("twin_turbo_whistle", ("whistle",)),
        ("turbo_edge", ("edge", "hiband")),
        ("mechanical", ("mechanical",)),
    ),
    "aventador_lp700": (
        ("exhaust", ("exhaust",)),
        ("v12_wail", ("wail",)),
        ("na_scream", ("scream",)),
        ("intake", ("intake", "idle_high")),
    ),
}

_SOURCE_BINDINGS: dict[str, tuple[tuple[str, str], ...]] = {
    "ferrari_458": (
        ("source", "tools/sound_sim/s12/acoustic_identity_v015/sources/flat_plane_v8_source.py"),
        ("profile", "tools/sound_sim/s12/acoustic_identity_v015/targets/stage_g_candidates/Ferrari_candidate_v4.json"),
    ),
    "rx7_fd": (
        ("source", "tools/sound_sim/s12/acoustic_identity_v015/sources/rotary_turbo_source.py"),
        ("profile", "tools/sound_sim/s12/acoustic_identity_v015/targets/stage_g_candidates/RX7_candidate_v4.json"),
    ),
    "supra_jza80": (
        ("source", "tools/sound_sim/s12/acoustic_identity_v015/sources/toyota_i6_turbo_source.py"),
        ("profile", "tools/sound_sim/s12/acoustic_identity_v015/targets/vehicle_acoustic_target.json"),
    ),
    "aventador_lp700": (
        ("source", "tools/sound_sim/s12/acoustic_identity_v015/sources/lamborghini_v12_source.py"),
        ("profile", "tools/sound_sim/s12/acoustic_identity_v015/targets/vehicle_acoustic_target.json"),
    ),
}

_REPO_ROOT = Path(__file__).resolve().parents[5]


def build_stage_k_remaining_four_round2_review(
    output_root: str | Path,
    *,
    duration_s: float = 60.0,
    diagnostic_duration_s: float | None = None,
    parameter_sets: Mapping[str, Mapping[str, float]] | None = None,
    requested_review_gain_linear: float = REVIEW_GAIN_LINEAR,
) -> dict[str, object]:
    """Build a new four-vehicle diagnostic package atomically.

    ``duration_s`` defaults to the formal 60-second review, while tests and
    diagnostics may inject a 1-2 second duration.  A destination that already
    exists is rejected even when empty, so a previous Round-2 package can never
    be overwritten.
    """

    _validate_duration(duration_s, "duration_s")
    diagnostics_duration = float(duration_s if diagnostic_duration_s is None else diagnostic_duration_s)
    _validate_duration(diagnostics_duration, "diagnostic_duration_s")
    if not np.isfinite(requested_review_gain_linear) or requested_review_gain_linear <= 0.0:
        raise ValueError("requested_review_gain_linear must be finite and > 0")
    root = Path(output_root).resolve()
    if root.exists():
        raise FileExistsError(f"remaining four-vehicle Round-2 package root must be new: {root}")
    if parameter_sets is not None and set(parameter_sets) != set(VEHICLES):
        raise ValueError("parameter_sets must contain exactly the four remaining vehicles")

    source_commit, source_dirty, source_status = _git_source_state()
    selected_parameters = _select_parameters(parameter_sets)
    staging = Path(tempfile.mkdtemp(prefix=f".{root.name}.", suffix=".staging", dir=str(root.parent)))
    try:
        vehicle_results: dict[str, object] = {}
        for vehicle_id in VEHICLES:
            vehicle_results[vehicle_id] = _build_vehicle(
                staging,
                vehicle_id,
                float(duration_s),
                diagnostics_duration,
                selected_parameters[vehicle_id],
                float(requested_review_gain_linear),
            )

        manifest: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "package_id": PACKAGE_ID,
            "manifest_source": "builder_derived",
            "caller_manifest_used": False,
            "status": STATUS,
            "automatic_gate_status": AUTOMATIC_GATE_STATUS,
            "qualification_status": QUALIFICATION_STATUS,
            "human_pass": False,
            "csv_content_read": False,
            "human_feedback_content_read": False,
            "source_commit": source_commit,
            "source_dirty": source_dirty,
            "source_status_lines": source_status,
            "duration_s": float(duration_s),
            "diagnostic_duration_s": diagnostics_duration,
            "vehicle_ids": list(VEHICLES),
            "vehicles": vehicle_results,
            "production_source_files": {
                vehicle_id: vehicle_results[vehicle_id]["source_binding"]["source_files"]
                for vehicle_id in VEHICLES
            },
            "review_gain_policy": "one shared Frozen PTR -> edge fade -> fixed whole-cycle gain -> PCM24 per vehicle; comfort is one static post-PCM gain from candidate final PCM",
            "pipeline_order": list(PIPELINE_ORDER),
            "source_scope": "C/synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
            "provenance": "Round-2 diagnostic package; no OEM calibration claim; no human or CSV evidence read",
            "sha256sums_name": "SHA256SUMS.txt",
            "zip_crc32_name": "ZIP_CRC32.json",
        }
        (staging / "artifact_manifest.json").write_text(_dump_json(manifest), encoding="utf-8", newline="\n")
        zip_name = "S12_Stage_K_Remaining_Four_Vehicle_Round2_UNQUALIFIED_DIAGNOSTIC_Review.zip"
        zip_path = staging / zip_name
        _write_zip(staging, zip_path)
        crc_map = {info.filename: int(info.CRC) for info in _zip_infos(zip_path)}
        (staging / "ZIP_CRC32.json").write_text(_dump_json(crc_map), encoding="utf-8", newline="\n")
        (staging / "SHA256SUMS.txt").write_text(_sha256sums(staging), encoding="utf-8", newline="\n")
        os.replace(staging, root)
        result = dict(manifest)
        result.update(
            {
                "output_root": str(root),
                "artifact_manifest": str(root / "artifact_manifest.json"),
                "sha256sums": str(root / "SHA256SUMS.txt"),
                "zip": str(root / zip_name),
                "zip_name": zip_name,
                "zip_crc32": str(root / "ZIP_CRC32.json"),
            }
        )
        return result
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _build_vehicle(
    root: Path,
    vehicle_id: str,
    duration_s: float,
    diagnostic_duration_s: float,
    parameters: Mapping[str, float],
    requested_gain: float,
) -> dict[str, object]:
    adapter = _adapter(vehicle_id)
    package_root = _REPO_ROOT
    source_binding = _source_binding(package_root, vehicle_id)
    trace = _build_trace(vehicle_id, duration_s)
    diagnostic_trace = _build_trace(vehicle_id, diagnostic_duration_s)
    trace_sha = _trace_sha256(trace)
    diagnostic_trace_sha = _trace_sha256(diagnostic_trace)
    baseline = adapter["baseline"](vehicle_id, trace)
    candidate = _call_candidate(adapter["candidate"], vehicle_id, trace, parameters)
    baseline = _validate_render(baseline, trace, vehicle_id)
    candidate = _validate_render(candidate, trace, vehicle_id)

    diagnostic_render = candidate
    if diagnostic_duration_s != duration_s:
        diagnostic_baseline = adapter["baseline"](vehicle_id, diagnostic_trace)
        diagnostic_render = _call_candidate(adapter["candidate"], vehicle_id, diagnostic_trace, parameters)
        _validate_render(diagnostic_baseline, diagnostic_trace, vehicle_id)
        diagnostic_render = _validate_render(diagnostic_render, diagnostic_trace, vehicle_id)

    formal_raw = {
        "baseline": _formal_source(baseline),
        "candidate": _formal_source(candidate),
    }
    diagnostics_raw: dict[str, np.ndarray] = {}
    diagnostic_stem_names: dict[str, str] = {}
    for diagnostic_id, alternatives in DIAGNOSTIC_STEMS[vehicle_id]:
        stem_name = _resolve_stem(diagnostic_render.stems, alternatives, vehicle_id, diagnostic_id)
        diagnostic_stem_names[diagnostic_id] = stem_name
        diagnostics_raw[diagnostic_id] = _formal_source(np.asarray(diagnostic_render.stems[stem_name], dtype=np.float64))

    peak = max(
        (float(np.max(np.abs(array))) for array in (*formal_raw.values(), *diagnostics_raw.values()) if array.size),
        default=0.0,
    )
    whole_cycle_gain = _headroom_gain(peak, requested_gain)
    directory = root / VEHICLE_DIRECTORIES[vehicle_id]
    directory.mkdir(parents=True, exist_ok=True)
    formal: dict[str, dict[str, object]] = {}
    final_arrays: dict[str, np.ndarray] = {}
    formal_names = {
        "baseline": f"{vehicle_id}_Round2_Baseline_{int(duration_s)}s.wav",
        "candidate": f"{vehicle_id}_Round2_Candidate_{int(duration_s)}s.wav",
    }
    for role, raw in formal_raw.items():
        final = _pcm24_roundtrip(np.asarray(raw, dtype=np.float64) * whole_cycle_gain)
        path = directory / formal_names[role]
        _write_pcm24_wav(path, final)
        final_arrays[role] = final
        formal[role] = _receipt(
            path,
            root,
            role=role,
            vehicle_id=vehicle_id,
            source_binding=source_binding,
            profile_sha256=source_binding["profile_sha256"],
            trace_sha256=trace_sha,
            trace_frames=int(trace.time_s.size),
            whole_cycle_gain=whole_cycle_gain,
            headroom_limited=bool(whole_cycle_gain < requested_gain),
            pipeline_order=PIPELINE_ORDER,
        )

    candidate_final = final_arrays["candidate"]
    comfort_gain = _headroom_gain(
        float(np.max(np.abs(candidate_final))) if candidate_final.size else 0.0,
        requested_gain,
    )
    comfort = _pcm24_roundtrip(candidate_final * comfort_gain)
    comfort_path = directory / f"{vehicle_id}_Round2_Candidate_Comfort_{int(duration_s)}s.wav"
    _write_pcm24_wav(comfort_path, comfort)
    formal["comfort"] = _receipt(
        comfort_path,
        root,
        role="comfort",
        vehicle_id=vehicle_id,
        source_binding=source_binding,
        profile_sha256=source_binding["profile_sha256"],
        trace_sha256=trace_sha,
        trace_frames=int(trace.time_s.size),
        whole_cycle_gain=whole_cycle_gain,
        headroom_limited=bool(comfort_gain < requested_gain),
        pipeline_order=PIPELINE_ORDER + ("comfort_static_gain",),
        input_sha256=formal["candidate"]["sha256"],
        comfort_gain=comfort_gain,
    )

    diagnostics: dict[str, dict[str, object]] = {}
    for diagnostic_id, raw in diagnostics_raw.items():
        final = _pcm24_roundtrip(np.asarray(raw, dtype=np.float64) * whole_cycle_gain)
        path = directory / f"{vehicle_id}_Round2_Diagnostic_{diagnostic_id}_{int(diagnostic_duration_s)}s.wav"
        _write_pcm24_wav(path, final)
        diagnostics[diagnostic_id] = _receipt(
            path,
            root,
            role="diagnostic",
            vehicle_id=vehicle_id,
            source_binding=source_binding,
            profile_sha256=source_binding["profile_sha256"],
            trace_sha256=diagnostic_trace_sha,
            trace_frames=int(diagnostic_trace.time_s.size),
            whole_cycle_gain=whole_cycle_gain,
            headroom_limited=bool(whole_cycle_gain < requested_gain),
            pipeline_order=PIPELINE_ORDER,
            source_domain=True,
            diagnostic_id=diagnostic_id,
            source_stem=diagnostic_stem_names[diagnostic_id],
        )

    metrics = _call_metrics(adapter["metrics"], vehicle_id, candidate, trace, baseline)
    metrics_path = directory / "round2_source_metrics.json"
    metrics_payload = {
        "schema_version": SCHEMA_VERSION,
        "package_id": PACKAGE_ID,
        "vehicle_id": vehicle_id,
        "measurement_provenance": "actual_arrays_and_trace",
        "diagnostics_claims_used": False,
        "profile_sha256": source_binding["profile_sha256"],
        "trace_sha256": trace_sha,
        "trace_frames": int(trace.time_s.size),
        "parameters": dict(parameters),
        "metrics": _json_safe(metrics),
        "status": STATUS,
    }
    metrics_path.write_text(_dump_json(metrics_payload), encoding="utf-8", newline="\n")
    result = {
        "vehicle_id": vehicle_id,
        "source_binding": source_binding,
        "profile_sha256": source_binding["profile_sha256"],
        "round2_parameters": dict(parameters),
        "trace_sha256": trace_sha,
        "trace_frames": int(trace.time_s.size),
        "diagnostic_trace_sha256": diagnostic_trace_sha,
        "formal": formal,
        "diagnostics": diagnostics,
        "metrics_json": str(metrics_path.relative_to(root).as_posix()),
        "metrics_sha256": _sha256_file(metrics_path),
        "whole_cycle_gain_linear": float(whole_cycle_gain),
        "producer": "stage_k.round2_remaining_package.build_stage_k_remaining_four_round2_review",
    }
    return result


def _adapter(vehicle_id: str) -> dict[str, Any]:
    if vehicle_id in ("ferrari_458", "rx7_fd"):
        module = importlib.import_module(f"{__package__}.round2_legacy_anchors")
        return {
            "baseline": module.render_round2_baseline,
            "candidate": module.render_round2_candidate,
            "metrics": module.measure_round2_metrics,
            "grids": module.PARAMETER_GRIDS,
        }
    module = importlib.import_module(f"{__package__}.round2_remaining_sources")
    return {
        "baseline": module.render_round2_baseline,
        "candidate": module.render_round2_candidate,
        "metrics": module.measure_round2_metrics,
        "grids": module.PARAMETER_GRIDS,
    }


def _build_trace(vehicle_id: str, duration_s: float) -> VehicleStateTrace:
    """Build a trace with measurable events even for an injected 1-2 s test.

    The canonical drive-cycle helper places its shift windows over a longer
    timeline.  For a short qualification test we compress a canonical 3 s
    state trace into the requested duration, preserving its state ordering and
    recomputing acceleration from the compressed time base.  Formal 60 s
    builds use the canonical trace directly.
    """

    if duration_s >= 3.0:
        return build_drive_cycle_trace(vehicle_id, duration_s)
    expanded = build_drive_cycle_trace(vehicle_id, 3.0)
    count = int(round(duration_s * SAMPLE_RATE_HZ)) + 1
    time_s = np.linspace(0.0, duration_s, count)
    source_time = np.linspace(0.0, 3.0, expanded.time_s.size)
    compressed_source_time = time_s * 3.0 / duration_s
    rpm = np.interp(compressed_source_time, source_time, expanded.rpm)
    load = np.interp(compressed_source_time, source_time, expanded.load)
    throttle = np.interp(compressed_source_time, source_time, expanded.throttle)
    acceleration = np.gradient(rpm / 60.0, time_s)
    return VehicleStateTrace(time_s, rpm, load, throttle, acceleration).validate()


def _select_parameters(parameter_sets: Mapping[str, Mapping[str, float]] | None) -> dict[str, dict[str, float]]:
    selected: dict[str, dict[str, float]] = {}
    for vehicle_id in VEHICLES:
        grids = _adapter(vehicle_id)["grids"]
        if parameter_sets is None:
            selected[vehicle_id] = {name: float(bounds[1]) for name, bounds in grids[vehicle_id].items()}
        else:
            values = dict(parameter_sets[vehicle_id])
            if set(values) != set(grids[vehicle_id]):
                raise ValueError(f"{vehicle_id} parameter keys mismatch")
            selected[vehicle_id] = values
    return selected


def _call_candidate(function: Callable[..., SourceRender], vehicle_id: str, trace: VehicleStateTrace, parameters: Mapping[str, float]) -> SourceRender:
    parameters_count = len(inspect.signature(function).parameters)
    if parameters_count >= 3:
        return function(vehicle_id, trace, parameters)
    return function(vehicle_id, trace)


def _call_metrics(function: Callable[..., Mapping[str, object]], vehicle_id: str, candidate: SourceRender, trace: VehicleStateTrace, baseline: SourceRender) -> Mapping[str, object]:
    parameters = inspect.signature(function).parameters
    if "parent_render" in parameters:
        return function(vehicle_id, candidate, trace, parent_render=baseline)
    return function(vehicle_id, candidate, trace)


def _validate_render(render: SourceRender, trace: VehicleStateTrace, vehicle_id: str) -> SourceRender:
    value = render.validate()
    if value.pressure.shape[0] != trace.time_s.size:
        raise ValueError(f"{vehicle_id} render/trace frame counts differ")
    return value


def _formal_source(render: SourceRender | np.ndarray) -> np.ndarray:
    pressure = np.asarray(render.pressure if isinstance(render, SourceRender) else render, dtype=np.float64)
    return _edge_fade(_apply_frozen_ptr(pressure))


def _resolve_stem(stems: Mapping[str, object], alternatives: tuple[str, ...], vehicle_id: str, diagnostic_id: str) -> str:
    for name in alternatives:
        if name in stems:
            value = np.asarray(stems[name], dtype=np.float64)
            if value.ndim == 2 and value.shape[0] > 0 and np.any(np.isfinite(value)):
                return name
    raise ValueError(f"{vehicle_id} diagnostic {diagnostic_id} has no bound source stem")


def _source_binding(repo_root: Path, vehicle_id: str) -> dict[str, object]:
    source_files: list[dict[str, object]] = []
    profile_files: list[dict[str, object]] = []
    for kind, relative in _SOURCE_BINDINGS[vehicle_id]:
        path = repo_root / relative
        if not path.is_file():
            raise FileNotFoundError(f"source binding file is missing: {path}")
        record = {"path": relative.replace("\\", "/"), "sha256": _sha256_file(path)}
        (source_files if kind == "source" else profile_files).append(record)
    profile_digest = hashlib.sha256(
        "".join(str(record["sha256"]) for record in (*source_files, *profile_files)).encode("ascii")
    ).hexdigest()
    return {
        "source_files": source_files,
        "profile_files": profile_files,
        "profile_sha256": profile_digest,
        "binding_source": "builder_resolved_files",
    }


def _receipt(
    path: Path,
    root: Path,
    *,
    role: str,
    vehicle_id: str,
    source_binding: Mapping[str, object],
    profile_sha256: str,
    trace_sha256: str,
    trace_frames: int,
    whole_cycle_gain: float,
    headroom_limited: bool,
    pipeline_order: tuple[str, ...],
    source_domain: bool = False,
    diagnostic_id: str | None = None,
    source_stem: str | None = None,
    input_sha256: str | None = None,
    comfort_gain: float | None = None,
) -> dict[str, object]:
    audio = np.asarray(_read_pcm24_wav(path), dtype=np.float64)
    with wave.open(str(path), "rb") as stream:
        header = {
            "sample_rate_hz": stream.getframerate(),
            "channels": stream.getnchannels(),
            "pcm_bits": stream.getsampwidth() * 8,
            "frames": stream.getnframes(),
            "audio_format": "PCM24",
        }
    result: dict[str, object] = {
        "path": path.relative_to(root).as_posix(),
        "vehicle_id": vehicle_id,
        "role": role,
        "source_domain": bool(source_domain),
        "source_files": source_binding["source_files"],
        "profile_files": source_binding["profile_files"],
        "production_source_files": source_binding["source_files"],
        "baseline_source_files": source_binding["source_files"],
        "profile_sha256": profile_sha256,
        "trace_sha256": trace_sha256,
        "trace_frames": int(trace_frames),
        "pcm_sha256": _sha256_file(path),
        "sha256": _sha256_file(path),
        "frames": int(audio.shape[0]),
        "header": header,
        "pipeline_order": list(pipeline_order),
        "whole_cycle_gain_linear": float(whole_cycle_gain),
        "headroom_limited": bool(headroom_limited),
        "pcm_health": _pcm_health(audio),
    }
    if diagnostic_id is not None:
        result.update({"diagnostic_id": diagnostic_id, "source_stem": source_stem})
    if input_sha256 is not None:
        result.update({"input_sha256": input_sha256, "comfort_static_gain_applied_once": True, "comfort_gain_linear": float(comfort_gain or 0.0)})
    return result


def _pcm_health(audio: np.ndarray) -> dict[str, object]:
    metrics = measure_loudness(audio, SAMPLE_RATE_HZ)
    finite = bool(np.all(np.isfinite(audio)))
    return {
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "channels": int(audio.shape[1]) if audio.ndim == 2 else 1,
        "pcm_bits": 24,
        "finite": finite,
        "peak_dbfs": float(metrics.peak_dbfs),
        "clipping_count": int(metrics.clipping_count),
        "passes": bool(finite and audio.ndim == 2 and audio.shape[1] == 2 and metrics.clipping_count == 0 and metrics.peak_dbfs <= PEAK_LIMIT_DBFS + 1.0e-6),
    }


def _headroom_gain(peak: float, requested: float) -> float:
    if peak <= 0.0:
        return float(requested)
    return float(min(requested, PEAK_LIMIT_LINEAR / peak))


def _trace_sha256(trace: VehicleStateTrace) -> str:
    digest = hashlib.sha256()
    for values in (trace.time_s, trace.rpm, trace.load, trace.throttle, trace.acceleration_mps2):
        digest.update(np.asarray(values, dtype=np.float64).tobytes())
    return digest.hexdigest()


def _git_source_state() -> tuple[str, bool, list[str]]:
    def run(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(_REPO_ROOT),
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return completed.stdout.strip()

    commit = run("rev-parse", "HEAD")
    status_text = run("status", "--porcelain=v1")
    lines = status_text.splitlines() if status_text else []
    return commit, bool(lines), lines


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256sums(root: Path) -> str:
    excluded = {"SHA256SUMS.txt"}
    rows = []
    for path in sorted(path for path in root.rglob("*") if path.is_file() and path.name not in excluded):
        rows.append(f"{_sha256_file(path)}  {path.relative_to(root).as_posix()}")
    return "\n".join(rows) + "\n"


def _write_zip(root: Path, zip_path: Path) -> None:
    excluded = {zip_path.name, "SHA256SUMS.txt", "ZIP_CRC32.json"}
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(path for path in root.rglob("*") if path.is_file() and path.name not in excluded):
            info = zipfile.ZipInfo(path.relative_to(root).as_posix(), date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def _zip_infos(path: Path) -> list[zipfile.ZipInfo]:
    with zipfile.ZipFile(path) as archive:
        return list(archive.infolist())


def _validate_duration(value: float, name: str) -> None:
    if not np.isfinite(value) or value < 1.0:
        raise ValueError(f"{name} must be finite and >= 1.0")


def _json_safe(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        if not math.isfinite(float(value)):
            return None
        return value
    return value


def _dump_json(value: object) -> str:
    return json.dumps(_json_safe(value), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


__all__ = (
    "AUTOMATIC_GATE_STATUS",
    "PACKAGE_ID",
    "PIPELINE_ORDER",
    "QUALIFICATION_STATUS",
    "REVIEW_GAIN_LINEAR",
    "SCHEMA_VERSION",
    "STATUS",
    "VEHICLES",
    "build_stage_k_remaining_four_round2_review",
)
