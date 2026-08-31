"""Labelled final-PCM evidence used by Stage G automatic qualification."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np

from ..acoustic_analysis.reference_feature_extractor import extract_reference_features
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
from ..render_realism_v10 import _RENDERERS, _SAMPLE_RATE_HZ, _render_stateful


ANCHOR_VEHICLE_IDS = ("ferrari_458", "hellcat", "rx7_fd")
DEFAULT_REFERENCE_WINDOWS: dict[str, tuple[float, float]] = {
    "idle": (0.0, 8.0),
    "acceleration": (8.0, 26.0),
    "afterfire": (36.0, 46.0),
}
PIPELINE_ORDER = (
    "independent_source_with_candidate_overrides",
    "idle_dynamics",
    "deterministic_afterfire",
    "low_frequency_body",
    "exhaust_rumble",
    "shift_dynamics",
    "named_transient_peak_shaping",
    "common_pre_ptr_equalization",
    "frozen_ptr",
    "edge_fade",
    "one_fixed_whole_cycle_gain",
    "pcm24",
    "reference_feature_extractor",
)

StageGRenderer = Callable[[str, VehicleStateTrace], SourceRender]


def extract_final_pcm_reference_features(
    wav_path: str | Path,
    windows: Mapping[str, tuple[float, float]] = DEFAULT_REFERENCE_WINDOWS,
) -> dict[str, object]:
    """Run the authoritative extractor on explicit final-PCM windows."""
    ordered = _validate_windows(windows)
    return extract_reference_features(Path(wav_path), segments=ordered)


def build_stage_g_reference_evidence(
    vehicle_id: str,
    output_root: str | Path,
    *,
    stage_g_renderer: StageGRenderer,
    duration_s: float = 60.0,
    windows: Mapping[str, tuple[float, float]] = DEFAULT_REFERENCE_WINDOWS,
    candidate_sha256: str,
) -> dict[str, object]:
    """Render Stage C and Stage G from one trace and measure final PCM.

    Exactly one fixed loudness gain is applied to each complete cycle.  State
    files are byte-domain slices of the reopened PCM24 full-cycle WAV, and the
    feature extractor runs on that same reopened file.
    """
    if vehicle_id not in ANCHOR_VEHICLE_IDS:
        raise ValueError(f"unsupported Stage-G reference vehicle_id: {vehicle_id!r}")
    if not callable(stage_g_renderer):
        raise TypeError("stage_g_renderer must be callable")
    if not np.isfinite(duration_s) or duration_s < 1.0:
        raise ValueError("duration_s must be finite and >= 1.0")
    if len(candidate_sha256) != 64 or any(char not in "0123456789abcdefABCDEF" for char in candidate_sha256):
        raise ValueError("candidate_sha256 must be a 64-character hexadecimal digest")
    ordered_windows = _validate_windows(windows, duration_s=duration_s)

    trace = build_drive_cycle_trace(vehicle_id, duration_s)
    trace_sha = _trace_sha256(trace)
    vehicle_root = Path(output_root) / vehicle_id
    vehicle_root.mkdir(parents=True, exist_ok=True)
    roles: dict[str, object] = {}

    renderers: dict[str, StageGRenderer] = {
        "stage_c": lambda current_vehicle, current_trace: _render_stateful(
            _RENDERERS[current_vehicle], current_vehicle, current_trace
        ),
        "stage_g": stage_g_renderer,
    }
    for role, renderer in renderers.items():
        role_root = vehicle_root / role
        role_root.mkdir(parents=True, exist_ok=True)
        source = renderer(vehicle_id, trace).validate()
        ptr_audio = _edge_fade(_apply_frozen_ptr(source.pressure))
        managed = manage_bundle_loudness(
            {"full_cycle": ptr_audio},
            _SAMPLE_RATE_HZ,
            target_lufs=-16.0,
            peak_limit_dbfs=-1.5,
        )
        full_cycle_path = _write_pcm24_wav(
            role_root / "full_cycle.wav", managed.segments["full_cycle"]
        )
        reopened = _read_pcm24_wav(full_cycle_path)
        features = extract_final_pcm_reference_features(full_cycle_path, ordered_windows)
        state_files: dict[str, object] = {}
        for state_id, (start_s, end_s) in ordered_windows.items():
            start = int(round(start_s * _SAMPLE_RATE_HZ))
            end = int(round(end_s * _SAMPLE_RATE_HZ))
            state_path = _write_pcm24_wav(role_root / f"{state_id}.wav", reopened[start:end])
            state_files[state_id] = {
                "path": str(state_path),
                "sha256": _sha256(state_path),
                "start_s": start_s,
                "end_s": end_s,
                "frames": end - start,
            }
        roles[role] = {
            "full_cycle_path": str(full_cycle_path),
            "full_cycle_sha256": _sha256(full_cycle_path),
            "whole_cycle_gain_db": managed.gain_db,
            "headroom_limited": managed.headroom_limited,
            "loudness": asdict(measure_loudness(reopened, _SAMPLE_RATE_HZ)),
            "health": _health(reopened),
            "feature_extractor": features,
            "state_files": state_files,
        }

    evidence: dict[str, object] = {
        "schema_version": "s12-stage-g-reference-evidence-1",
        "vehicle_id": vehicle_id,
        "duration_s": float(duration_s),
        "sample_rate_hz": _SAMPLE_RATE_HZ,
        "candidate_sha256": candidate_sha256.lower(),
        "trace_sha256": {"stage_c": trace_sha, "stage_g": trace_sha},
        "trace_source": "build_drive_cycle_trace v10",
        "reference_windows_s": {
            state: [float(bounds[0]), float(bounds[1])]
            for state, bounds in ordered_windows.items()
        },
        "pipeline_order": list(PIPELINE_ORDER),
        "loudness_policy": {
            "target_lufs": -16.0,
            "peak_limit_dbfs": -1.5,
            "gain_scope": f"one fixed gain per complete {duration_s:g}-second role cycle",
        },
        "provenance": "C/synthetic actual PCM compared with B/R2 relative targets; uncalibrated; not OEM reproduction",
        "roles": roles,
    }
    evidence_path = vehicle_root / "reference_evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return evidence


def _validate_windows(
    windows: Mapping[str, tuple[float, float]],
    *,
    duration_s: float | None = None,
) -> dict[str, tuple[float, float]]:
    if tuple(windows) != ("idle", "acceleration", "afterfire"):
        raise ValueError("reference windows must be ordered idle, acceleration, afterfire")
    result: dict[str, tuple[float, float]] = {}
    for state_id, bounds in windows.items():
        if not isinstance(bounds, (tuple, list)) or len(bounds) != 2:
            raise ValueError(f"invalid reference window for {state_id!r}")
        start_s, end_s = (float(bounds[0]), float(bounds[1]))
        if not np.isfinite(start_s) or not np.isfinite(end_s) or not 0.0 <= start_s < end_s:
            raise ValueError(f"invalid reference window for {state_id!r}")
        if duration_s is not None and end_s > duration_s:
            raise ValueError(f"reference window {state_id!r} exceeds cycle duration")
        if (end_s - start_s) * _SAMPLE_RATE_HZ < 4096:
            raise ValueError(f"reference window {state_id!r} is too short for the extractor")
        result[state_id] = (start_s, end_s)
    return result


def _trace_sha256(trace: VehicleStateTrace) -> str:
    digest = hashlib.sha256()
    for name in ("time_s", "rpm", "load", "throttle", "acceleration_mps2"):
        digest.update(name.encode("ascii"))
        values = np.ascontiguousarray(getattr(trace, name), dtype="<f8")
        digest.update(values.tobytes())
    return digest.hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
