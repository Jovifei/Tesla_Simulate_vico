"""Deterministic profile-bound Stage-I boost and lift probe evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace
from .candidate_profiles import StageICandidateProfile
from .render_candidate import render_stage_i_candidate


_RATE = 48000


def build_stage_i_response_probe(
    candidate_label: str,
    profile: StageICandidateProfile,
) -> dict[str, object]:
    """Render fixed boost/lift probes directly from one validated profile."""
    if not isinstance(candidate_label, str) or not candidate_label:
        raise ValueError("candidate_label must be non-empty")
    if not isinstance(profile, StageICandidateProfile):
        raise ValueError("profile must be a StageICandidateProfile")
    boost_trace = _boost_trace()
    lift_trace = _lift_trace()
    boost_render = render_stage_i_candidate("hellcat", boost_trace, profile).validate()
    lift_render = render_stage_i_candidate("hellcat", lift_trace, profile).validate()
    count = boost_render.pressure.shape[0]
    if lift_render.pressure.shape[0] != count:
        raise RuntimeError("standard boost and lift probe lengths drifted")

    boost_state = _audio_state(boost_trace, count)
    lift_state = _audio_state(lift_trace, count)
    boost_command = np.clip((boost_state[1] * boost_state[2] - 0.01) / 0.80, 0.0, 1.0)
    bypass_gate = ((lift_state[2] < 0.25) & (np.arange(count) >= int(0.80 * _RATE))).astype(np.float64)
    boost_response = _rms_envelope(_required_stem(boost_render, "blower"))
    bypass_response = _rms_envelope(_required_stem(lift_render, "blower_bypass_release"))
    arrays = {
        "boost_response": boost_response,
        "boost_command": boost_command,
        "bypass_response": bypass_response,
        "bypass_gate": bypass_gate,
    }
    binding = candidate_profile_binding(profile)
    evidence = {
        "schema_version": "s12-stage-i-response-probe-evidence-1",
        "candidate_label": candidate_label,
        **binding,
        "probes": {
            "boost": _render_evidence(boost_trace, boost_render),
            "lift": _render_evidence(lift_trace, lift_render),
        },
        "array_sha256": {name: array_sha256(value) for name, value in arrays.items()},
    }
    return {"sample_rate_hz": _RATE, **arrays, "evidence": evidence}


def build_final_pcm_source_evidence(
    candidate_label: str,
    profile: StageICandidateProfile,
    render: SourceRender,
    final_pcm_path: str | Path,
) -> dict[str, str]:
    """Bind a final PCM byte stream to its candidate profile and source render."""
    if not isinstance(candidate_label, str) or not candidate_label:
        raise ValueError("candidate_label must be non-empty")
    render.validate()
    path = Path(final_pcm_path)
    if not path.is_file():
        raise ValueError(f"final PCM file does not exist: {path}")
    return {
        "schema_version": "s12-stage-i-final-pcm-source-evidence-1",
        "candidate_label": candidate_label,
        **candidate_profile_binding(profile),
        "render_sha256": source_render_sha256(render),
        "final_pcm_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def candidate_profile_binding(profile: StageICandidateProfile) -> dict[str, str]:
    canonical = json.dumps(profile.payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    candidate_sha = hashlib.sha256(canonical).hexdigest()
    profile_sha = hashlib.sha256(profile.path.read_bytes()).hexdigest() if profile.path is not None and profile.path.is_file() else candidate_sha
    return {
        "candidate_id": profile.candidate_id,
        "candidate_sha256": candidate_sha,
        "profile_sha256": profile_sha,
    }


def array_sha256(values: np.ndarray) -> str:
    normalized = np.ascontiguousarray(np.asarray(values, dtype="<f8"))
    digest = hashlib.sha256()
    digest.update(normalized.ndim.to_bytes(2, "little"))
    for size in normalized.shape:
        digest.update(int(size).to_bytes(8, "little"))
    digest.update(normalized.tobytes())
    return digest.hexdigest()


def trace_sha256(trace: VehicleStateTrace) -> str:
    trace.validate()
    digest = hashlib.sha256()
    for values in (trace.time_s, trace.rpm, trace.load, trace.throttle, trace.acceleration_mps2):
        digest.update(bytes.fromhex(array_sha256(values)))
    return digest.hexdigest()


def source_render_sha256(render: SourceRender) -> str:
    render.validate()
    digest = hashlib.sha256()
    digest.update(bytes.fromhex(array_sha256(render.pressure)))
    for name in sorted(render.stems):
        digest.update(name.encode("utf-8"))
        digest.update(bytes.fromhex(array_sha256(render.stems[name])))
    return digest.hexdigest()


def _boost_trace() -> VehicleStateTrace:
    epsilon = 1.0 / _RATE
    time_s = np.asarray((0.0, 0.20, 0.20 + epsilon, 1.00, 1.00 + epsilon, 1.50), dtype=np.float64)
    rpm = np.full(time_s.size, 3600.0)
    load = np.asarray((0.05, 0.05, 0.90, 0.90, 0.05, 0.05), dtype=np.float64)
    throttle = load.copy()
    return VehicleStateTrace(time_s, rpm, load, throttle, np.zeros(time_s.size)).validate()


def _lift_trace() -> VehicleStateTrace:
    epsilon = 1.0 / _RATE
    time_s = np.asarray((0.0, 0.60, 0.80, 0.80 + epsilon, 1.20, 1.50), dtype=np.float64)
    rpm = np.asarray((4200.0, 4400.0, 4400.0, 4400.0, 3600.0, 3000.0), dtype=np.float64)
    load = np.asarray((0.90, 0.90, 0.90, 0.10, 0.10, 0.10), dtype=np.float64)
    throttle = np.asarray((0.90, 0.90, 0.90, 0.05, 0.05, 0.05), dtype=np.float64)
    return VehicleStateTrace(time_s, rpm, load, throttle, np.zeros(time_s.size)).validate()


def _audio_state(trace: VehicleStateTrace, count: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / _RATE
    return tuple(np.interp(time_s, trace.time_s, values) for values in (trace.rpm, trace.load, trace.throttle))  # type: ignore[return-value]


def _required_stem(render: SourceRender, name: str) -> np.ndarray:
    if name not in render.stems:
        raise ValueError(f"standard probe render is missing required stem {name!r}")
    return np.asarray(render.stems[name], dtype=np.float64)


def _rms_envelope(audio: np.ndarray) -> np.ndarray:
    mono = np.mean(np.asarray(audio, dtype=np.float64), axis=1)
    size = max(int(0.005 * _RATE), 1)
    return np.sqrt(np.maximum(np.convolve(np.square(mono), np.ones(size) / size, mode="same"), 0.0))


def _render_evidence(trace: VehicleStateTrace, render: SourceRender) -> dict[str, object]:
    return {
        "trace_sha256": trace_sha256(trace),
        "render_sha256": source_render_sha256(render),
        "stem_sha256": {
            name: array_sha256(_required_stem(render, name))
            for name in ("blower", "blower_bypass_release")
        },
    }


__all__ = (
    "array_sha256",
    "build_final_pcm_source_evidence",
    "build_stage_i_response_probe",
    "candidate_profile_binding",
    "source_render_sha256",
    "trace_sha256",
)
