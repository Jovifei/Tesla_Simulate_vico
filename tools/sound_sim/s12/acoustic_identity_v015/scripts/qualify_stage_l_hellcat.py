"""Build and qualify Stage-L Hellcat evidence from hash-bound production artifacts."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
import sys
from typing import Any
import weakref
import wave

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from tools.sound_sim.s12.acoustic_identity_v015.render_drive_cycle_v10 import build_drive_cycle_trace
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.candidate_profiles import (
    StageLCandidateProfile,
    load_stage_l_candidate,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.candidate_search import (
    qualify_stage_l_candidates,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.perceptual_metrics import (
    compute_stage_l_perceptual_metrics,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.reference_distance import (
    compute_stage_l_reference_distance,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_k.candidate_profiles import (
    load_stage_k_candidate,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_k.render_candidate import (
    render_stage_k_candidate,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.render_candidate import (
    _apply_current_frozen_layers,
    render_stage_l_candidate,
)


_MANIFEST_SCHEMA = "s12-stage-l-qualification-manifest-1"
_MANIFEST_KEYS = {
    "schema_version", "probe_duration_s", "search_parent_profile", "stage_k_final_wav",
    "reference_target", "reference_trace", "identity_evidence", "isolation_evidence",
    "track_p_evidence", "candidates",
}
_RECEIPT_KEYS = {"path", "sha256"}
_AUDIO_ENTRY_KEYS = {"path", "sha256", "production_receipt"}
_CANDIDATE_ENTRY_KEYS = {"candidate_profile", "stage_l_final_wav"}


def run_stage_l_qualification_manifest(
    manifest_path: str | Path, expected_manifest_sha256: str,
) -> dict[str, object]:
    """Render probes and derive qualification evidence; no metrics are accepted as input."""
    manifest_file = Path(manifest_path).resolve()
    raw = manifest_file.read_bytes()
    manifest_sha = _sha_text(expected_manifest_sha256, "qualification manifest SHA-256")
    if hashlib.sha256(raw).hexdigest() != manifest_sha:
        raise ValueError("qualification manifest SHA-256 mismatch")
    try:
        payload: Any = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("qualification manifest is not UTF-8 JSON") from exc
    manifest = _exact_mapping(payload, _MANIFEST_KEYS, "qualification manifest")
    if manifest["schema_version"] != _MANIFEST_SCHEMA:
        raise ValueError("qualification manifest schema_version mismatch")
    duration = _finite_number(manifest["probe_duration_s"], "probe_duration_s")
    if not 8.0 <= duration <= 12.0:
        raise ValueError("probe_duration_s must be within 8..12 seconds")

    parent_receipt = _bind_receipt(manifest["search_parent_profile"], "search parent profile")
    stage_k_entry = _exact_mapping(manifest["stage_k_final_wav"], _AUDIO_ENTRY_KEYS, "Stage-K final WAV")
    stage_k_receipt = _bind_receipt(
        {"path": stage_k_entry["path"], "sha256": stage_k_entry["sha256"]}, "Stage-K final WAV",
    )
    stage_k_production = _bind_receipt(stage_k_entry["production_receipt"], "Stage-K production audio receipt")
    target_receipt = _bind_receipt(manifest["reference_target"], "reference target")
    identity_receipt = _bind_receipt(manifest["identity_evidence"], "identity evidence")
    isolation_receipt = _bind_receipt(manifest["isolation_evidence"], "isolation evidence")
    track_p_receipt = _bind_receipt(manifest["track_p_evidence"], "Track-P evidence")
    trace = _exact_mapping(
        manifest["reference_trace"], {"version", "trace_sha256", "evidence"}, "reference trace",
    )
    if not isinstance(trace["version"], str) or not trace["version"]:
        raise ValueError("reference trace version is invalid")
    trace_sha = _sha_text(trace["trace_sha256"], "reference trace SHA-256")
    trace_receipt = _bind_receipt(trace["evidence"], "trace evidence")
    raw_candidates = manifest["candidates"]
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise ValueError("qualification manifest candidates must be a non-empty array")

    candidate_artifacts: list[tuple[dict[str, str], dict[str, str], dict[str, str]]] = []
    for index, raw_entry in enumerate(raw_candidates):
        entry = _exact_mapping(raw_entry, _CANDIDATE_ENTRY_KEYS, f"candidate entry {index}")
        profile_receipt = _bind_receipt(entry["candidate_profile"], f"candidate {index} profile")
        wav_entry = _exact_mapping(entry["stage_l_final_wav"], _AUDIO_ENTRY_KEYS, f"candidate {index} final WAV")
        wav_receipt = _bind_receipt(
            {"path": wav_entry["path"], "sha256": wav_entry["sha256"]}, f"candidate {index} final WAV",
        )
        production_receipt = _bind_receipt(
            wav_entry["production_receipt"], f"candidate {index} production audio receipt",
        )
        candidate_artifacts.append((profile_receipt, wav_receipt, production_receipt))

    # Production loaders validate Stage-L lineage, parent/reference SHA and exact
    # parameter contracts.  This happens after every receipt is bound and before
    # any expensive render.
    parent_profile = load_stage_k_candidate(parent_receipt["path"])
    candidates = [load_stage_l_candidate(profile["path"]) for profile, _, _ in candidate_artifacts]
    if len({candidate.candidate_id for candidate in candidates}) != len(candidates):
        raise ValueError("qualification manifest contains duplicate candidate_id")
    if any(candidate.payload["reference_target"]["sha256"] != target_receipt["sha256"] for candidate in candidates):
        raise ValueError("candidate profile reference target does not match manifest")
    _bind_production_audio_receipt(
        stage_k_production["path"], stage_k_production["sha256"], wav_path=stage_k_receipt["path"],
        expected_artifact_kind="stage_k_final_pcm24", expected_profile_id=parent_profile.candidate_id,
        expected_profile_sha256=parent_receipt["sha256"], expected_trace_version=trace["version"],
        expected_trace_sha256=trace_sha,
    )
    for candidate, (profile_receipt, wav_receipt, production_receipt) in zip(candidates, candidate_artifacts):
        _bind_production_audio_receipt(
            production_receipt["path"], production_receipt["sha256"], wav_path=wav_receipt["path"],
            expected_artifact_kind="stage_l_final_pcm24", expected_profile_id=candidate.candidate_id,
            expected_profile_sha256=profile_receipt["sha256"], expected_trace_version=trace["version"],
            expected_trace_sha256=trace_sha,
        )

    probe_trace = build_drive_cycle_trace("hellcat", duration_s=duration)
    probe_trace_sha = _trace_sha256(probe_trace)
    # Search parent is a Stage-L parameter anchor (normally v8).  Its source
    # metrics are measured from its real render, while its final-PCM health is
    # deliberately measured from the frozen Stage-K comparison WAV.
    residency = _RenderResidency()
    parent_render = residency.observe(render_stage_k_candidate("hellcat", probe_trace, parent_profile))
    parent_metrics = compute_stage_l_perceptual_metrics(
        parent_render, probe_trace, stage_k_receipt["path"],
    )
    del parent_render
    gc.collect()

    records: list[dict[str, object]] = []
    for candidate, (profile_receipt, wav_receipt, _) in zip(candidates, candidate_artifacts):
        candidate_render = _render_pre_ptr(probe_trace, candidate, residency)
        metrics = compute_stage_l_perceptual_metrics(
            candidate_render, probe_trace, wav_receipt["path"],
        )
        del candidate_render
        gc.collect()
        reference = compute_stage_l_reference_distance(
            stage_k_receipt["path"], wav_receipt["path"], target_receipt["path"],
            profile_path=profile_receipt["path"],
            expected_stage_k_wav_sha256=stage_k_receipt["sha256"],
            expected_stage_l_wav_sha256=wav_receipt["sha256"],
            expected_target_sha256=target_receipt["sha256"],
            expected_profile_sha256=profile_receipt["sha256"],
            trace_version=trace["version"],
            expected_trace_sha256=trace_sha,
            trace_evidence_path=trace_receipt["path"],
            expected_trace_evidence_sha256=trace_receipt["sha256"],
            identity_evidence_path=identity_receipt["path"],
            expected_identity_evidence_sha256=identity_receipt["sha256"],
            isolation_evidence_path=isolation_receipt["path"],
            expected_isolation_evidence_sha256=isolation_receipt["sha256"],
            track_p_evidence_path=track_p_receipt["path"],
            expected_track_p_evidence_sha256=track_p_receipt["sha256"],
        )
        records.append({
            "candidate_id": candidate.candidate_id,
            "parameters": _flatten_parameters(candidate),
            "probe_duration_s": duration,
            "full_render_residency_max": residency.maximum,
            "metrics": metrics,
            "reference_distance": reference,
        })

    result = qualify_stage_l_candidates(
        records,
        parent_parameters=_flatten_parameters(parent_profile),
        parent_metrics=parent_metrics,
    )
    result["qualification_input_receipt"] = {
        "path": str(manifest_file), "schema_version": _MANIFEST_SCHEMA, "sha256": manifest_sha,
    }
    result["probe_trace_receipt"] = {
        "builder": "build_drive_cycle_trace(hellcat)", "duration_s": duration,
        "sha256": probe_trace_sha,
    }
    result["artifact_receipts"] = {
        "search_parent_profile": parent_receipt,
        "stage_k_final_wav": stage_k_receipt,
        "reference_target": target_receipt,
        "trace_evidence": trace_receipt,
        "identity_evidence": identity_receipt,
        "isolation_evidence": isolation_receipt,
        "track_p_evidence": track_p_receipt,
        "stage_k_production_audio_receipt": stage_k_production,
        "candidate_profiles": [profile for profile, _, _ in candidate_artifacts],
        "stage_l_final_wavs": [wav for _, wav, _ in candidate_artifacts],
        "stage_l_production_audio_receipts": [receipt for _, _, receipt in candidate_artifacts],
    }
    return result


class _RenderResidency:
    """Measure runner-visible live full renders by object lifetime."""

    def __init__(self) -> None:
        self._references: dict[int, weakref.ReferenceType[object]] = {}
        self.maximum = 0

    def observe(self, render: object) -> object:
        self._references = {
            identity: reference
            for identity, reference in self._references.items()
            if reference() is not None
        }
        identity = id(render)
        if identity not in self._references:
            self._references[identity] = weakref.ref(render)
        live = sum(reference() is not None for reference in self._references.values())
        self.maximum = max(self.maximum, live)
        if self.maximum > 1:
            raise ValueError("more than one full SourceRender is resident")
        return render


def _render_pre_ptr(
    trace: object, profile: StageLCandidateProfile, residency: _RenderResidency,
) -> object:
    source = residency.observe(render_stage_l_candidate(trace, profile))
    rendered = residency.observe(
        _apply_current_frozen_layers(source, trace, profile, include_l4=True)
    )
    return rendered


def _bind_production_audio_receipt(
    receipt_path: str | Path, expected_receipt_sha256: str, *, wav_path: str | Path,
    expected_artifact_kind: str, expected_profile_id: str,
    expected_profile_sha256: str, expected_trace_version: str,
    expected_trace_sha256: str,
) -> Mapping[str, object]:
    """Validate the exact production provenance binding for one final PCM WAV."""
    receipt_file = Path(receipt_path).resolve()
    receipt_sha = _sha_text(expected_receipt_sha256, "audio receipt SHA-256")
    raw = receipt_file.read_bytes()
    if hashlib.sha256(raw).hexdigest() != receipt_sha:
        raise ValueError("audio receipt SHA-256 mismatch")
    try:
        payload: Any = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("audio receipt is not UTF-8 JSON") from exc
    receipt = _exact_mapping(payload, {
        "schema_version", "artifact_kind", "producer_api", "profile_kind", "profile_id",
        "profile_sha256", "trace_version", "trace_sha256", "wav_sha256", "reopened_pcm24",
    }, "production audio receipt")
    if receipt["schema_version"] != "s12-stage-l-produced-audio-receipt-1":
        raise ValueError("production audio receipt schema mismatch")
    expected = {
        "artifact_kind": expected_artifact_kind,
        "profile_id": expected_profile_id,
        "profile_sha256": _sha_text(expected_profile_sha256, "profile SHA-256"),
        "trace_version": expected_trace_version,
        "trace_sha256": _sha_text(expected_trace_sha256, "trace SHA-256"),
    }
    for name, value in expected.items():
        if receipt[name] != value:
            raise ValueError(f"production audio receipt {name.replace('_', ' ')} mismatch")
    if not isinstance(receipt["producer_api"], str) or not receipt["producer_api"]:
        raise ValueError("production audio receipt producer API is invalid")
    expected_producer = {
        "stage_k_final_pcm24": "stage_k.named_review.render_stage_k_candidate_pcm24",
        "stage_l_final_pcm24": "stage_l.named_review.render_stage_l_candidate_pcm24",
    }[expected_artifact_kind]
    if receipt["producer_api"] != expected_producer:
        raise ValueError("production audio receipt producer API mismatch")
    expected_profile_kind = "stage_k_candidate" if expected_artifact_kind.startswith("stage_k") else "stage_l_candidate"
    if receipt["profile_kind"] != expected_profile_kind:
        raise ValueError("production audio receipt profile kind is invalid")
    wav_file = Path(wav_path).resolve()
    actual_wav_sha = hashlib.sha256(wav_file.read_bytes()).hexdigest()
    if receipt["wav_sha256"] != actual_wav_sha:
        raise ValueError("production audio receipt WAV SHA-256 mismatch")
    pcm = _exact_mapping(
        receipt["reopened_pcm24"],
        {"sample_rate_hz", "channels", "pcm_bits", "finite", "clipping_count"},
        "production audio receipt reopened PCM24",
    )
    try:
        with wave.open(str(wav_file), "rb") as stream:
            reopened = {
                "sample_rate_hz": stream.getframerate(), "channels": stream.getnchannels(),
                "pcm_bits": 8 * stream.getsampwidth(), "finite": True,
                "clipping_count": _pcm24_clipping_count(stream.readframes(stream.getnframes())),
            }
    except (OSError, wave.Error) as exc:
        raise ValueError("production audio receipt WAV cannot be reopened") from exc
    if pcm != reopened or reopened != {
        "sample_rate_hz": 48000, "channels": 2, "pcm_bits": 24,
        "finite": True, "clipping_count": 0,
    }:
        raise ValueError("production audio receipt reopened PCM24 contract mismatch")
    return receipt


def _pcm24_clipping_count(raw: bytes) -> int:
    if len(raw) % 3:
        raise ValueError("production PCM24 byte count is invalid")
    triples = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
    values = (
        triples[:, 0].astype(np.int32)
        | (triples[:, 1].astype(np.int32) << 8)
        | (triples[:, 2].astype(np.int32) << 16)
    )
    values = np.where(values & 0x800000, values - 0x1000000, values)
    return int(np.count_nonzero((values <= -0x800000) | (values >= 0x7FFFFF)))


def _flatten_parameters(profile: object) -> dict[str, object]:
    return {
        name: dict(profile.payload[section][parameter])
        for name in profile.requested_parameters()
        for section, parameter in (name.split(".", 1),)
    }


def _bind_receipt(value: object, label: str) -> dict[str, str]:
    receipt = _exact_mapping(value, _RECEIPT_KEYS, f"{label} receipt")
    path_value = receipt["path"]
    if not isinstance(path_value, str) or not path_value:
        raise ValueError(f"{label} path is invalid")
    path = Path(path_value).resolve()
    if not path.is_file():
        raise ValueError(f"{label} is missing")
    expected = _sha_text(receipt["sha256"], f"{label} SHA-256")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"{label} SHA-256 mismatch")
    return {"path": str(path), "sha256": expected}


def _trace_sha256(trace: object) -> str:
    digest = hashlib.sha256()
    for name in ("time_s", "rpm", "load", "throttle", "acceleration_mps2"):
        values = np.ascontiguousarray(np.asarray(getattr(trace, name), dtype="<f8"))
        digest.update(name.encode("ascii") + b"\0")
        digest.update(values.tobytes())
    return digest.hexdigest()


def _exact_mapping(value: object, keys: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError(f"{label} must have exact keys {sorted(keys)}")
    return value


def _sha_text(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} is invalid")
    normalized = value.lower()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise ValueError(f"{label} is invalid")
    return normalized


def _finite_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(float(value)):
        raise ValueError(f"{label} must be finite")
    return float(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, nargs="?", help="hash-bound Stage-L evidence manifest")
    parser.add_argument("--input-sha256", help="required SHA-256 of the manifest bytes")
    parser.add_argument("--output", type=Path, help="optional deterministic result JSON")
    args = parser.parse_args(argv)
    if args.manifest is None:
        parser.error("manifest is required unless --help is used")
    if args.input_sha256 is None:
        parser.error("--input-sha256 is required")
    try:
        result = run_stage_l_qualification_manifest(args.manifest, args.input_sha256)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    serialized = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
