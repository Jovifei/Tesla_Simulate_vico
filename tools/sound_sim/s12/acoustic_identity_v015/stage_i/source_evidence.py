"""Render the thirteen PCM24 sources consumed by the Stage-I named package."""

from __future__ import annotations

import gc
from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path
import shutil
from typing import Callable, Mapping

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace
from ..loudness_manager import manage_bundle_loudness, measure_loudness
from ..render_drive_cycle_v10 import build_drive_cycle_trace
from ..render_identity_v02 import (
    _apply_frozen_ptr,
    _edge_fade,
    _health,
    _read_pcm24_wav,
    _write_pcm24_wav,
)
from ..stage_d.scenarios import build_stage_d_scenario_trace
from .named_review import REQUIRED_SOURCE_FILE_IDS
from .perceptual_metrics import compute_stage_i_perceptual_metrics


SOURCE_PACKAGE_ID = "S12_Stage_I_Named_Source_Evidence_v1"
SOURCE_STATUS = "SOURCE_EVIDENCE_READY"
CANDIDATE_ROLES = ("a_balanced", "b_whine_forward", "c_softer_mechanical")
_FULL_IDS = {
    "stage_h_v5_baseline_60s": "stage_h",
    "stage_i_v6_a_balanced_60s": "a_balanced",
    "stage_i_v6_b_whine_forward_60s": "b_whine_forward",
    "stage_i_v6_c_softer_mechanical_60s": "c_softer_mechanical",
}
_ACCEL_IDS = {
    "stage_h_blower_only_acceleration": "stage_h",
    "stage_i_a_blower_only_acceleration": "a_balanced",
    "stage_i_b_blower_only_acceleration": "b_whine_forward",
    "stage_i_c_blower_only_acceleration": "c_softer_mechanical",
}
_ANCHORS = {
    "ferrari_458_stage_h_unchanged_60s": "Ferrari_458_StageG_Unchanged_60s.wav",
    "rx7_fd_stage_h_unchanged_60s": "RX7_FD_StageG_Unchanged_60s.wav",
}

StageHRenderer = Callable[[VehicleStateTrace], SourceRender]
StageIRenderer = Callable[[VehicleStateTrace, object], SourceRender]
TraceBuilder = Callable[[str, float], VehicleStateTrace]
ScenarioBuilder = Callable[[str, str, float], VehicleStateTrace]


def render_stage_i_named_sources(
    output_root: str | Path,
    *,
    stage_h_review_root: str | Path,
    stage_i_candidate_paths: Mapping[str, str | Path] | None = None,
    stage_i_profiles: Mapping[str, object] | None = None,
    stage_h_renderer: StageHRenderer | None = None,
    stage_i_renderer: StageIRenderer | None = None,
    full_cycle_duration_s: float = 60.0,
    acceleration_duration_s: float = 8.0,
    event_duration_s: float = 12.0,
    trace_builder: TraceBuilder = build_drive_cycle_trace,
    scenario_builder: ScenarioBuilder = build_stage_d_scenario_trace,
) -> dict[str, object]:
    """Render product and diagnostic sources without building the final ZIP."""
    root = Path(output_root).resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"Stage-I source output must be a new directory: {root}")
    wav_root = root / "wav"
    wav_root.mkdir(parents=True, exist_ok=True)
    review_root = Path(stage_h_review_root).resolve()
    profiles = _resolve_profiles(stage_i_candidate_paths, stage_i_profiles)
    if set(profiles) != set(CANDIDATE_ROLES):
        raise ValueError(f"candidate roles must be exactly {CANDIDATE_ROLES}")
    render_h = stage_h_renderer or _default_stage_h_renderer(review_root)
    render_i = stage_i_renderer or _default_stage_i_renderer()
    stage_h_binding = _stage_h_profile_binding(review_root)

    evidence: dict[str, dict[str, object]] = {}
    files: dict[str, str] = {}
    full_trace = trace_builder("hellcat", _positive_duration(full_cycle_duration_s, "full_cycle_duration_s"))
    full_trace.validate()
    for file_id, role in _FULL_IDS.items():
        render = (
            render_h(full_trace).validate()
            if role == "stage_h"
            else render_i(full_trace, profiles[role]).validate()
        )
        source_metrics = compute_stage_i_perceptual_metrics(render, full_trace)
        source_render_sha256 = _source_render_sha256(render)
        parameter_usage = _candidate_parameter_usage(render, role=role)
        profile_binding = (
            stage_h_binding
            if role == "stage_h"
            else _profile_binding(profiles[role])
        )
        _write_render(
            wav_root,
            file_id,
            render,
            full_trace,
            stem="pressure",
            target_lufs=-16.0,
            product_audio=True,
            candidate_id=_candidate_id(role, profiles),
            evidence=evidence,
            files=files,
        )
        evidence[file_id].update(
            {
                "source_metrics": source_metrics,
                "source_render_sha256": source_render_sha256,
                "source_render_hash_scope": "pressure_and_named_stems_f64le",
                "candidate_parameter_usage": parameter_usage,
                "profile_binding": profile_binding,
            }
        )
        del render
        gc.collect()

    acceleration_trace = scenario_builder(
        "hellcat",
        "acceleration",
        _positive_duration(acceleration_duration_s, "acceleration_duration_s"),
    ).validate()
    blower_group_raw: dict[str, np.ndarray] = {}
    for file_id, role in _ACCEL_IDS.items():
        render = (
            render_h(acceleration_trace).validate()
            if role == "stage_h"
            else render_i(acceleration_trace, profiles[role]).validate()
        )
        blower_group_raw[file_id] = _prepare_audio(render, "blower", file_id)
        if role == "a_balanced":
            _write_render(
                wav_root,
                "stage_i_exhaust_only_acceleration",
                render,
                acceleration_trace,
                stem="exhaust",
                target_lufs=-20.0,
                product_audio=False,
                candidate_id=_candidate_id("a_balanced", profiles),
                evidence=evidence,
                files=files,
            )
        del render
        gc.collect()
    _write_common_attenuation_group(
        wav_root,
        blower_group_raw,
        acceleration_trace,
        {file_id: _candidate_id(role, profiles) for file_id, role in _ACCEL_IDS.items()},
        evidence,
        files,
    )
    del blower_group_raw
    gc.collect()

    event_duration = _positive_duration(event_duration_s, "event_duration_s")
    shift_trace = scenario_builder("hellcat", "shift", event_duration).validate()
    shift_render = render_i(shift_trace, profiles["a_balanced"]).validate()
    _write_render(
        wav_root,
        "stage_i_shift_dip_rebuild_12s",
        shift_render,
        shift_trace,
        stem="blower",
        target_lufs=-20.0,
        product_audio=False,
        candidate_id=_candidate_id("a_balanced", profiles),
        evidence=evidence,
        files=files,
    )
    del shift_render
    gc.collect()
    lift_trace = scenario_builder("hellcat", "lift", event_duration).validate()
    lift_render = render_i(lift_trace, profiles["a_balanced"]).validate()
    _write_render(
        wav_root,
        "stage_i_lift_bypass_12s",
        lift_render,
        lift_trace,
        stem="blower_bypass_release",
        target_lufs=-20.0,
        product_audio=False,
        candidate_id=_candidate_id("a_balanced", profiles),
        evidence=evidence,
        files=files,
    )
    del lift_render
    gc.collect()

    for file_id, filename in _ANCHORS.items():
        source = review_root / "02_Anchor_Mapping" / filename
        if not source.is_file():
            raise ValueError(f"frozen Stage-H anchor is missing: {source}")
        destination = wav_root / f"{file_id}.wav"
        shutil.copyfile(source, destination)
        audio = _read_pcm24_wav(destination)
        health = _require_health(destination, audio)
        files[file_id] = str(destination.resolve())
        evidence[file_id] = {
            "path": files[file_id],
            "sha256": _sha256(destination),
            "source_sha256": _sha256(source),
            "copied_unchanged": True,
            "product_audio": True,
            "stem": "frozen_final_pcm",
            "candidate_id": "Stage H unchanged",
            "trace_sha256": None,
            "fixed_loudness_gain_count": 1,
            "fixed_loudness_gain_inherited": True,
            "health": health,
        }

    if set(files) != set(REQUIRED_SOURCE_FILE_IDS):
        raise RuntimeError("Stage-I source manifest is incomplete")
    manifest = {
        "package_id": SOURCE_PACKAGE_ID,
        "schema_version": "s12-stage-i-source-evidence-2",
        "status": SOURCE_STATUS,
        "sealed_key_read": False,
        "files": files,
        "evidence": evidence,
        "candidate_roles": {
            role: _candidate_id(role, profiles) for role in CANDIDATE_ROLES
        },
        "provenance": "synthetic; uncalibrated; Hellcat-inspired; not OEM reproduction",
    }
    manifest_path = root / "source_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {
        "package_id": SOURCE_PACKAGE_ID,
        "status": SOURCE_STATUS,
        "output_root": str(root),
        "source_manifest": str(manifest_path),
        "source_count": len(files),
    }


def _resolve_profiles(
    paths: Mapping[str, str | Path] | None,
    profiles: Mapping[str, object] | None,
) -> dict[str, object]:
    if (paths is None) == (profiles is None):
        raise ValueError("provide exactly one of stage_i_candidate_paths or stage_i_profiles")
    if profiles is not None:
        return dict(profiles)
    assert paths is not None
    if set(paths) != set(CANDIDATE_ROLES):
        raise ValueError(f"candidate roles must be exactly {CANDIDATE_ROLES}")
    from .candidate_profiles import load_stage_i_candidate

    return {role: load_stage_i_candidate(paths[role]) for role in CANDIDATE_ROLES}


def _default_stage_h_renderer(review_root: Path) -> StageHRenderer:
    candidate_path = Path(_stage_h_profile_binding(review_root)["profile_path"])
    from ..stage_h.candidate_profiles import load_stage_h_candidate
    from ..stage_h.render_candidate import render_stage_h_candidate

    candidate = load_stage_h_candidate(candidate_path)
    return lambda trace: render_stage_h_candidate("hellcat", trace, candidate)


def _default_stage_i_renderer() -> StageIRenderer:
    from .render_candidate import render_stage_i_candidate

    return lambda trace, profile: render_stage_i_candidate("hellcat", trace, profile)  # type: ignore[arg-type]


def _write_render(
    wav_root: Path,
    file_id: str,
    render: SourceRender,
    trace: VehicleStateTrace,
    *,
    stem: str,
    target_lufs: float,
    product_audio: bool,
    candidate_id: str,
    evidence: dict[str, dict[str, object]],
    files: dict[str, str],
) -> None:
    ptr = _prepare_audio(render, stem, file_id)
    managed = manage_bundle_loudness(
        {file_id: ptr},
        48000,
        target_lufs=target_lufs,
        peak_limit_dbfs=-1.5,
    )
    destination = wav_root / f"{file_id}.wav"
    _write_pcm24_wav(destination, managed.segments[file_id])
    reopened = _read_pcm24_wav(destination)
    health = _require_health(destination, reopened)
    loudness = measure_loudness(reopened)
    files[file_id] = str(destination.resolve())
    evidence[file_id] = {
        "path": files[file_id],
        "sha256": _sha256(destination),
        "copied_unchanged": False,
        "product_audio": product_audio,
        "stem": stem,
        "candidate_id": candidate_id,
        "trace_sha256": _trace_sha256(trace),
        "fixed_loudness_gain_count": 1,
        "fixed_loudness_gain_db": float(managed.gain_db),
        "headroom_limited": bool(managed.headroom_limited),
        "loudness": {
            "integrated_lufs": float(loudness.integrated_lufs),
            "rms_dbfs": float(loudness.rms_dbfs),
            "peak_dbfs": float(loudness.peak_dbfs),
            "crest_factor_db": float(loudness.crest_factor_db),
            "clipping_count": int(loudness.clipping_count),
        },
        "health": health,
        "pipeline": [
            "pre_ptr_source_or_named_stem",
            "frozen_ptr",
            "edge_fade",
            "one_fixed_segment_gain",
            "pcm24",
        ],
    }


def _prepare_audio(render: SourceRender, stem: str, file_id: str) -> np.ndarray:
    if stem == "pressure":
        raw = np.asarray(render.pressure, dtype=np.float64)
    else:
        if stem not in render.stems:
            raise ValueError(f"required diagnostic stem {stem!r} is missing for {file_id}")
        raw = np.asarray(render.stems[stem], dtype=np.float64)
    return _edge_fade(_apply_frozen_ptr(raw))


def _write_common_attenuation_group(
    wav_root: Path,
    raw_audio: Mapping[str, np.ndarray],
    trace: VehicleStateTrace,
    candidate_ids: Mapping[str, str],
    evidence: dict[str, dict[str, object]],
    files: dict[str, str],
) -> None:
    measured = {
        file_id: float(measure_loudness(audio).integrated_lufs)
        for file_id, audio in raw_audio.items()
    }
    if not all(np.isfinite(value) for value in measured.values()):
        raise ValueError("blower diagnostic group has non-finite raw loudness")
    target_lufs = min(-20.0, min(measured.values()))
    max_peak = max(_peak_dbfs(audio) for audio in raw_audio.values())
    peak_gain = -1.5 - max_peak if np.isfinite(max_peak) else 0.0
    common_gain_db = min(0.0, target_lufs - min(measured.values()), peak_gain)
    scale = 10.0 ** (common_gain_db / 20.0)
    for file_id, audio in raw_audio.items():
        destination = wav_root / f"{file_id}.wav"
        _write_pcm24_wav(destination, audio * scale)
        reopened = _read_pcm24_wav(destination)
        health = _require_health(destination, reopened)
        loudness = measure_loudness(reopened)
        files[file_id] = str(destination.resolve())
        evidence[file_id] = {
            "path": files[file_id],
            "sha256": _sha256(destination),
            "copied_unchanged": False,
            "product_audio": False,
            "stem": "blower",
            "candidate_id": candidate_ids[file_id],
            "trace_sha256": _trace_sha256(trace),
            "fixed_loudness_gain_count": 1,
            "group_id": "blower_only_acceleration",
            "group_raw_integrated_lufs": measured[file_id],
            "group_target_lufs": target_lufs,
            "group_gain_db": common_gain_db,
            "headroom_limited": peak_gain < min(0.0, target_lufs - min(measured.values())),
            "loudness": {
                "integrated_lufs": float(loudness.integrated_lufs),
                "rms_dbfs": float(loudness.rms_dbfs),
                "peak_dbfs": float(loudness.peak_dbfs),
                "crest_factor_db": float(loudness.crest_factor_db),
                "clipping_count": int(loudness.clipping_count),
            },
            "health": health,
            "pipeline": [
                "pre_ptr_named_blower_stem",
                "frozen_ptr",
                "edge_fade",
                "shared_attenuation_only_group_gain",
                "pcm24",
            ],
        }


def _peak_dbfs(audio: np.ndarray) -> float:
    peak = float(np.max(np.abs(np.asarray(audio, dtype=np.float64)), initial=0.0))
    return float(20.0 * np.log10(peak)) if peak > 0.0 else float("-inf")


def _source_render_sha256(render: SourceRender) -> str:
    digest = hashlib.sha256()
    _update_array_hash(digest, "pressure", render.pressure)
    for name in sorted(render.stems):
        _update_array_hash(digest, name, render.stems[name])
    return digest.hexdigest()


def _update_array_hash(digest, name: str, values: np.ndarray) -> None:
    array = np.asarray(values, dtype="<f8")
    digest.update(name.encode("utf-8"))
    digest.update(array.shape[0].to_bytes(8, "little"))
    digest.update(array.shape[1].to_bytes(8, "little"))
    digest.update(array.tobytes())


def _candidate_parameter_usage(
    render: SourceRender,
    *,
    role: str,
) -> dict[str, object]:
    usage = render.diagnostics.get("candidate_parameter_usage")
    if not isinstance(usage, Mapping):
        raise ValueError("full render candidate_parameter_usage evidence is missing")
    if role == "stage_h":
        if set(usage) != {"requested", "consumed", "unused"}:
            raise ValueError("Stage-H legacy candidate_parameter_usage must use exact three-key contract")
        requested = _usage_string_list(usage, "requested")
        consumed = _usage_string_list(usage, "consumed")
        unused = _usage_string_list(usage, "unused")
        return {
            "requested": requested,
            "read": consumed,
            "configured": consumed,
            "active": None,
            "inactive": None,
            "consumed": consumed,
            "unused": unused,
            "activity_verification": "NOT_AVAILABLE_LEGACY_STAGE_H",
        }
    if role not in CANDIDATE_ROLES:
        raise ValueError(f"unknown Stage-I candidate usage role: {role}")
    keys = {
        "requested",
        "read",
        "configured",
        "active",
        "inactive",
        "consumed",
        "unused",
    }
    if set(usage) != keys:
        raise ValueError("Stage-I candidate_parameter_usage must use exact seven-key contract")
    normalized = {key: _usage_string_list(usage, key) for key in keys}
    read = set(normalized["read"])
    active = set(normalized["active"])
    inactive = set(normalized["inactive"])
    if (
        active & inactive
        or active | inactive != read
        or set(normalized["configured"]) != read
        or set(normalized["consumed"]) != read
    ):
        raise ValueError("Stage-I active/inactive usage evidence is inconsistent")
    return {
        "requested": normalized["requested"],
        "read": normalized["read"],
        "configured": normalized["configured"],
        "active": normalized["active"],
        "inactive": normalized["inactive"],
        "consumed": normalized["consumed"],
        "unused": normalized["unused"],
        "activity_verification": "MEASURED_STAGE_I_RENDER_ACTIVITY",
    }


def _usage_string_list(usage: Mapping[str, object], key: str) -> list[str]:
    values = usage[key]
    if not isinstance(values, (list, tuple)) or not all(isinstance(item, str) for item in values):
        raise ValueError(f"candidate_parameter_usage.{key} must be a string list")
    return list(values)


def _stage_h_profile_binding(review_root: Path) -> dict[str, object]:
    candidate_path = (
        Path(__file__).resolve().parents[1]
        / "targets"
        / "stage_h_candidates"
        / "Hellcat_candidate_v5.json"
    )
    if not candidate_path.is_file():
        raise ValueError(f"authoritative Stage-H candidate is missing: {candidate_path}")
    authoritative_sha = _sha256(candidate_path)
    review_copy = review_root / "candidates" / "hellcat_StageH_candidate_v5.json"
    review_sha = _sha256(review_copy) if review_copy.is_file() else None
    if review_sha is not None and review_sha != authoritative_sha:
        raise ValueError("review candidate copy does not match authoritative Stage-H candidate")
    payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    return {
        "candidate_id": str(payload["candidate_id"]),
        "profile_path": str(candidate_path.resolve()),
        "profile_sha256": authoritative_sha,
        "review_copy_path": str(review_copy.resolve()) if review_copy.is_file() else None,
        "review_copy_sha256": review_sha,
        "binding_source": "repository_authoritative_stage_h_profile",
    }


def _profile_binding(profile: object) -> dict[str, object]:
    payload = getattr(profile, "payload", None)
    if isinstance(payload, Mapping):
        normalized: object = payload
    elif is_dataclass(profile):
        normalized = asdict(profile)
    elif hasattr(profile, "__dict__"):
        normalized = vars(profile)
    else:
        normalized = {"candidate_id": str(getattr(profile, "candidate_id", type(profile).__name__))}
    canonical = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    path_value = getattr(profile, "path", None)
    path = Path(path_value).resolve() if path_value is not None else None
    return {
        "candidate_id": str(getattr(profile, "candidate_id", "unknown")),
        "profile_path": str(path) if path is not None else None,
        "profile_sha256": hashlib.sha256(canonical).hexdigest(),
        "profile_file_sha256": _sha256(path) if path is not None and path.is_file() else None,
        "binding_source": "candidate_payload_canonical_sha256",
    }


def _require_health(path: Path, audio: np.ndarray) -> dict[str, object]:
    health = _health(audio)
    if (
        not bool(health["finite"])
        or int(health["clipping_count"]) != 0
        or float(health["peak_dbfs"]) > -1.5 + 1e-6
    ):
        raise ValueError(f"Stage-I source WAV health gate failed: {path}")
    return health


def _trace_sha256(trace: VehicleStateTrace) -> str:
    digest = hashlib.sha256()
    for array in (
        trace.time_s,
        trace.rpm,
        trace.load,
        trace.throttle,
        trace.acceleration_mps2,
    ):
        normalized = np.asarray(array, dtype="<f8")
        digest.update(normalized.shape[0].to_bytes(8, "little"))
        digest.update(normalized.tobytes())
    return digest.hexdigest()


def _candidate_id(role: str, profiles: Mapping[str, object]) -> str:
    if role == "stage_h":
        return "Hellcat_candidate_v5"
    profile = profiles[role]
    value = getattr(profile, "candidate_id", role)
    return str(value)


def _positive_duration(value: float, field: str) -> float:
    if not np.isfinite(value) or value <= 0.0:
        raise ValueError(f"{field} must be finite and > 0")
    return float(value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = (
    "CANDIDATE_ROLES",
    "SOURCE_PACKAGE_ID",
    "SOURCE_STATUS",
    "render_stage_i_named_sources",
)
