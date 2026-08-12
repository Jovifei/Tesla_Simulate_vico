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

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from tools.sound_sim.s12.acoustic_identity_v015.render_drive_cycle_v10 import build_drive_cycle_trace
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.candidate_profiles import (
    PARAMETER_SECTIONS,
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
    stage_k_receipt = _bind_receipt(manifest["stage_k_final_wav"], "Stage-K final WAV")
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

    candidate_artifacts: list[tuple[dict[str, str], dict[str, str]]] = []
    for index, raw_entry in enumerate(raw_candidates):
        entry = _exact_mapping(raw_entry, _CANDIDATE_ENTRY_KEYS, f"candidate entry {index}")
        profile_receipt = _bind_receipt(entry["candidate_profile"], f"candidate {index} profile")
        wav_receipt = _bind_receipt(entry["stage_l_final_wav"], f"candidate {index} final WAV")
        candidate_artifacts.append((profile_receipt, wav_receipt))

    # Production loaders validate Stage-L lineage, parent/reference SHA and exact
    # parameter contracts.  This happens after every receipt is bound and before
    # any expensive render.
    parent_profile = load_stage_l_candidate(parent_receipt["path"])
    candidates = [load_stage_l_candidate(profile["path"]) for profile, _ in candidate_artifacts]
    if len({candidate.candidate_id for candidate in candidates}) != len(candidates):
        raise ValueError("qualification manifest contains duplicate candidate_id")
    if any(candidate.payload["reference_target"]["sha256"] != target_receipt["sha256"] for candidate in candidates):
        raise ValueError("candidate profile reference target does not match manifest")

    probe_trace = build_drive_cycle_trace("hellcat", duration_s=duration)
    probe_trace_sha = _trace_sha256(probe_trace)
    # Search parent is a Stage-L parameter anchor (normally v8).  Its source
    # metrics are measured from its real render, while its final-PCM health is
    # deliberately measured from the frozen Stage-K comparison WAV.
    parent_render = _render_pre_ptr(probe_trace, parent_profile)
    parent_metrics = compute_stage_l_perceptual_metrics(
        parent_render, probe_trace, stage_k_receipt["path"],
    )
    del parent_render
    gc.collect()

    records: list[dict[str, object]] = []
    for candidate, (profile_receipt, wav_receipt) in zip(candidates, candidate_artifacts):
        candidate_render = _render_pre_ptr(probe_trace, candidate)
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
            "full_render_residency_max": 1,
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
        "candidate_profiles": [profile for profile, _ in candidate_artifacts],
        "stage_l_final_wavs": [wav for _, wav in candidate_artifacts],
    }
    return result


def _render_pre_ptr(trace: object, profile: StageLCandidateProfile) -> object:
    source = render_stage_l_candidate(trace, profile)
    return _apply_current_frozen_layers(source, trace, profile, include_l4=True)


def _flatten_parameters(profile: StageLCandidateProfile) -> dict[str, object]:
    return {
        f"{section}.{name}": dict(record)
        for section in PARAMETER_SECTIONS
        for name, record in profile.payload[section].items()
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
