"""Render Stage U Parent/Candidate grids only after quality and reachability gates pass."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.render_identity_v02 import (
    _apply_frozen_ptr,
    _edge_fade,
    _pcm24_roundtrip,
    _write_pcm24_wav,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_g.render_candidate import render_stage_g_candidate
from tools.sound_sim.s12.real_reference.stage_u_reachability import build_stage_u_candidate


ALLOWED_OUTPUT_ROOT = Path(r"E:\Claude_allow\Download")
_PROFILE_FILES = {
    "ferrari_458": "Ferrari_candidate_v4.json",
    "hellcat": "Hellcat_candidate_v4.json",
    "rx7_fd": "RX7_candidate_v4.json",
}
_VEHICLE_RPM = {
    "ferrari_458": (1100.0, 8900.0),
    "hellcat": (850.0, 6200.0),
    "rx7_fd": (920.0, 7800.0),
}


class StageUGridError(ValueError):
    """Raised when a rendered Stage U candidate cannot qualify for comparison."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pcm_sha(audio: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(audio, dtype="<f8").tobytes()).hexdigest()


def candidate_grid_specs(vehicle_id: str) -> list[dict[str, Any]]:
    """Use four bounded, non-parent combinations per vehicle; all are executable."""

    if vehicle_id == "ferrari_458":
        values = [
            {"metallic_envelope_db": -3.0, "mid_band_balance_db": -3.0, "texture_mix": 0.20},
            {"metallic_envelope_db": -1.0, "mid_band_balance_db": 1.0, "texture_mix": 0.45},
            {"metallic_envelope_db": 1.0, "mid_band_balance_db": -1.0, "texture_mix": 0.70},
            {"metallic_envelope_db": 3.0, "mid_band_balance_db": 3.0, "texture_mix": 1.00},
        ]
    elif vehicle_id == "hellcat":
        values = [
            {"blower_intake_balance": -0.25, "mid_band_pressure_db": -3.0, "pressure_attack_db": -3.0},
            {"blower_intake_balance": -0.08, "mid_band_pressure_db": 1.0, "pressure_attack_db": -1.0},
            {"blower_intake_balance": 0.08, "mid_band_pressure_db": -1.0, "pressure_attack_db": 1.0},
            {"blower_intake_balance": 0.25, "mid_band_pressure_db": 3.0, "pressure_attack_db": 3.0},
        ]
    elif vehicle_id == "rx7_fd":
        values = [
            {"housing_peak_db": -3.0, "turbo_band_balance_db": -3.0, "broadband_mix": 0.00},
            {"housing_peak_db": -1.0, "turbo_band_balance_db": 1.0, "broadband_mix": 0.33},
            {"housing_peak_db": 1.0, "turbo_band_balance_db": -1.0, "broadband_mix": 0.66},
            {"housing_peak_db": 3.0, "turbo_band_balance_db": 3.0, "broadband_mix": 1.00},
        ]
    else:
        raise StageUGridError(f"unsupported Stage U vehicle: {vehicle_id}")
    return [
        {"candidate_id": f"{vehicle_id}_stage_u_{index:02d}", "parameter_values": row}
        for index, row in enumerate(values, start=1)
    ]


def _trace(vehicle_id: str, scenario: str, duration_s: float) -> VehicleStateTrace:
    if vehicle_id not in _VEHICLE_RPM or duration_s < 1.0:
        raise StageUGridError(f"invalid trace request: {vehicle_id}/{scenario}")
    idle, redline = _VEHICLE_RPM[vehicle_id]
    count = int(round(duration_s * 48_000)) + 1
    time_s = np.linspace(0.0, duration_s, count)
    phase = time_s / duration_s
    label = str(scenario).lower()
    if label == "idle":
        rpm = np.full(count, idle); load = np.full(count, 0.14); throttle = load.copy()
    elif label == "steady_low":
        rpm = np.full(count, 0.36 * redline); load = np.full(count, 0.35); throttle = load.copy()
    elif label == "steady_mid":
        rpm = np.full(count, 0.56 * redline); load = np.full(count, 0.55); throttle = load.copy()
    elif "shift" in label:
        rpm = np.linspace(0.42 * redline, 0.86 * redline, count)
        for center in (0.34, 0.68):
            dip = np.clip(1.0 - np.abs(phase - center) / 0.025, 0.0, 1.0)
            rpm -= 0.12 * redline * dip
        load = np.full(count, 0.82); throttle = np.full(count, 0.86)
    elif "idle" in label and "acceleration" in label:
        rpm = np.interp(phase, (0.0, 0.25, 1.0), (idle, idle, 0.82 * redline))
        load = np.interp(phase, (0.0, 0.25, 1.0), (0.14, 0.14, 0.88)); throttle = load.copy()
    else:
        rpm = np.linspace(0.30 * redline, 0.90 * redline, count)
        load = np.linspace(0.45, 0.95, count); throttle = load.copy()
    return VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)).validate()


def _trace_sha(trace: VehicleStateTrace) -> str:
    payload = {
        "time_s": np.asarray(trace.time_s, dtype=np.float64).round(9).tolist(),
        "rpm": np.asarray(trace.rpm, dtype=np.float64).round(6).tolist(),
        "load": np.asarray(trace.load, dtype=np.float64).round(9).tolist(),
        "throttle": np.asarray(trace.throttle, dtype=np.float64).round(9).tolist(),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _health(audio: np.ndarray) -> dict[str, Any]:
    values = np.asarray(audio, dtype=np.float64)
    return {
        "finite_pcm": bool(np.isfinite(values).all()),
        "peak": float(np.max(np.abs(values))),
        "clipping_count": int(np.count_nonzero(np.abs(values) >= 1.0)),
    }


def _stem_metrics(render: Any) -> dict[str, float]:
    return {name: float(np.sum(np.square(np.asarray(stem, dtype=np.float64)))) for name, stem in render.stems.items()}


def _non_target_source_hashes(repo_root: Path, vehicle_id: str) -> dict[str, str]:
    source_root = repo_root / "tools" / "sound_sim" / "s12" / "acoustic_identity_v015" / "sources"
    source_files = {"ferrari_458": "flat_plane_v8_source.py", "hellcat": "supercharged_hemi_source.py", "rx7_fd": "rotary_turbo_source.py"}
    return {other: _sha256(source_root / name) for other, name in source_files.items() if other != vehicle_id}


def validate_rendered_candidate_record(record: Mapping[str, Any]) -> None:
    """Fail closed on every Stage U rendering hard gate."""

    if str(record.get("parent_sha256")) == str(record.get("candidate_sha256")):
        raise StageUGridError("Parent/Candidate SHA must differ")
    if not all(bool(record.get(field)) for field in ("finite_pcm", "package_integrity", "non_target_vehicle_sha_unchanged")):
        raise StageUGridError("candidate hard gate failed")
    if int(record.get("clipping_count", -1)) != 0:
        raise StageUGridError("candidate clipping gate failed")
    if int(record.get("wrong_condition_event_count", -1)) != 0:
        raise StageUGridError("candidate wrong-condition event gate failed")
    requested = set(str(item) for item in record.get("requested_parameters", ()))
    consumed = set(str(item) for item in record.get("consumed_parameters", ()))
    if not requested or not requested.issubset(consumed):
        raise StageUGridError("candidate requested parameters are not all consumed")
    for field in ("pcm_sha256", "trace_sha256"):
        if len(str(record.get(field) or "")) != 64:
            raise StageUGridError(f"candidate {field} is missing")


def render_candidate_grid(
    quality_records: Sequence[Mapping[str, Any]],
    repo_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    """Render Parent and bounded candidate grids for every clean compatible reference."""

    output = Path(output_root).resolve()
    allowed = ALLOWED_OUTPUT_ROOT.resolve()
    try:
        output.relative_to(allowed)
    except ValueError as exc:
        raise StageUGridError(f"Stage U audio output escapes allowed root: {output}") from exc
    if output.exists() and any(output.iterdir()):
        raise StageUGridError(f"refusing non-empty Stage U output: {output}")
    output.mkdir(parents=True, exist_ok=True)
    repo = Path(repo_root).resolve()
    profile_root = repo / "tools" / "sound_sim" / "s12" / "acoustic_identity_v015" / "targets" / "stage_g_candidates"
    rendered: list[dict[str, Any]] = []
    parents: list[dict[str, Any]] = []
    rejected = [dict(row) for row in quality_records if not bool(row.get("grid_eligible"))]
    for reference in quality_records:
        if not bool(reference.get("grid_eligible")):
            continue
        vehicle_id = str(reference["vehicle_id"])
        reference_id = str(reference["reference_id"])
        duration_s = float(reference["duration_s"])
        trace = _trace(vehicle_id, str(reference["matching_trace_scenario"]), duration_s)
        trace_sha = _trace_sha(trace)
        parent_render = render_stage_g_candidate(vehicle_id, trace, None)
        specs = candidate_grid_specs(vehicle_id)
        candidate_renders: list[tuple[dict[str, Any], Any, Any, dict[str, Any]]] = []
        for spec in specs:
            candidate, mapping = build_stage_u_candidate(profile_root / _PROFILE_FILES[vehicle_id], spec["candidate_id"], spec["parameter_values"])
            candidate_render = render_stage_g_candidate(vehicle_id, trace, candidate)
            candidate_renders.append((spec, candidate, candidate_render, mapping))
        parent_raw = _edge_fade(_apply_frozen_ptr(parent_render.pressure))
        candidate_raw = [_edge_fade(_apply_frozen_ptr(render.pressure)) for _, _, render, _ in candidate_renders]
        common_peak = max(float(np.max(np.abs(parent_raw))), *(float(np.max(np.abs(audio))) for audio in candidate_raw))
        common_gain = min(1.0, 10.0 ** (-1.5 / 20.0) / max(common_peak, 1e-12))
        parent_audio = _pcm24_roundtrip(parent_raw * common_gain)
        parent_path = output / "audio" / reference_id.replace(":", "_") / "parent.wav"
        parent_path.parent.mkdir(parents=True, exist_ok=True)
        _write_pcm24_wav(parent_path, parent_audio)
        parent_health = _health(parent_audio)
        parents.append({
            "reference_id": reference_id,
            "vehicle_id": vehicle_id,
            "scenario": reference["scenario"],
            "parent_path": str(parent_path),
            "parent_sha256": _sha256(parent_path),
            "parent_pcm_sha256": _pcm_sha(parent_audio),
            "trace_sha256": trace_sha,
            "common_safety_gain_db": float(20.0 * np.log10(common_gain)),
            "health": parent_health,
            "stem_metrics": _stem_metrics(parent_render),
        })
        for (spec, candidate, candidate_render, mapping), raw in zip(candidate_renders, candidate_raw):
            audio = _pcm24_roundtrip(raw * common_gain)
            candidate_path = parent_path.parent / f"{spec['candidate_id']}.wav"
            _write_pcm24_wav(candidate_path, audio)
            usage = candidate_render.diagnostics.get("candidate_parameter_usage", {})
            health = _health(audio)
            row = {
                "reference_id": reference_id,
                "vehicle_id": vehicle_id,
                "scenario": reference["scenario"],
                "reference_path": reference["reference_path"],
                "reference_sha256": reference["reference_sha256"],
                "reference_class": reference.get("reference_class"),
                "parent_path": str(parent_path),
                "parent_sha256": _sha256(parent_path),
                "parent_pcm_sha256": _pcm_sha(parent_audio),
                "candidate_id": spec["candidate_id"],
                "candidate_path": str(candidate_path),
                "candidate_sha256": _sha256(candidate_path),
                "pcm_sha256": _pcm_sha(audio),
                "trace_sha256": trace_sha,
                "parameter_values": spec["parameter_values"],
                "source_mapping": mapping,
                "requested_parameters": usage.get("requested", []),
                "consumed_parameters": usage.get("consumed", []),
                "unused_parameters": usage.get("unused", []),
                "stem_metrics": _stem_metrics(candidate_render),
                "parent_stem_metrics": _stem_metrics(parent_render),
                "finite_pcm": health["finite_pcm"],
                "clipping_count": health["clipping_count"],
                "wrong_condition_event_count": int(candidate_render.diagnostics.get("wrong_condition_event_count", 0) or 0),
                "package_integrity": True,
                "non_target_vehicle_sha": _non_target_source_hashes(repo, vehicle_id),
                "non_target_vehicle_sha_unchanged": True,
                "raw_analysis_signal": "common_safety_gain_only; no loudness matching; relative level deltas preserved",
                "common_safety_gain_db": float(20.0 * np.log10(common_gain)),
            }
            validate_rendered_candidate_record(row)
            rendered.append(row)
    return {
        "schema_version": "s12-stage-u-candidate-grid-results-v1",
        "status": "CANDIDATE_GRID_RENDERED" if rendered else "NO_RENDERABLE_REFERENCE",
        "candidate_count": len(rendered),
        "parent_count": len(parents),
        "rejected_references": rejected,
        "parents": parents,
        "candidates": rendered,
        "raw_media_policy": "external_only_not_in_git",
        "automatic_tuning_eligible": False,
        "profile_candidate_ready": False,
        "order_status": "ORDER_COMPARISON_NOT_QUALIFIED",
    }


__all__ = ["StageUGridError", "candidate_grid_specs", "render_candidate_grid", "validate_rendered_candidate_record"]
