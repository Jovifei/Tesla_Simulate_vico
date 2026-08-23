"""Build an external-only, topic-aware RX-7 R2 comparison package."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, Mapping

import numpy as np
from scipy.io import wavfile

from tools.sound_sim.s12.acoustic_identity_v015.render_identity_v02 import (
    _apply_frozen_ptr,
    _edge_fade,
    _pcm24_roundtrip,
    _write_pcm24_wav,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_d.scenarios import build_stage_d_scenario_trace
from tools.sound_sim.s12.acoustic_identity_v015.stage_g.candidate_profiles import (
    StageGCandidateProfile,
    _validate_payload,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_g.render_candidate import render_stage_g_candidate


class Rx7TopicR2Error(ValueError):
    """Raised when the external RX-7 R2 package cannot be built safely."""


ALLOWED_ROOT = Path(r"E:\Claude_allow\Download")
SOURCE_MANIFEST_NAME = "rx7sim_authorized_r2_manifest_20260823.json"
CANDIDATE_PROFILE_NAME = "rx7_fd_candidate_v4.json"
PARAMETER_GROUP = "rotary_housing_turbo_distribution"
PARAMETER_OVERRIDES = {
    "rotary_pulse_width_scale": 1.08,
    "primary_spool_tau_s": 0.14,
    "secondary_spool_tau_s": 0.28,
    "boost_attack_s": 0.08,
    "boost_release_s": 0.24,
    "blow_off_gain_scale": 1.00,
    "blow_off_release_s": 0.70,
}
_EXPECTED_RECORDINGS = {
    "rx7sim_exhaust_idle": ("idle", "idle", ["怠速"]),
    "rx7sim_exhaust_revShort01": ("steady_low", "cruise", ["转速变化", "音色/机械感"]),
    "rx7sim_exhaust_revMedium01": ("steady_mid", "cruise", ["转速变化", "音色/机械感"]),
    "rx7sim_exhaust_revLong01": ("full_pull", "acceleration", ["加速", "转速变化"]),
    "rx7sim_interior_revLong01": ("full_pull_interior", "acceleration", ["加速", "音色/机械感"]),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inside(value: str | Path, label: str) -> Path:
    root = ALLOWED_ROOT.resolve()
    candidate = Path(value).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise Rx7TopicR2Error(f"{label} is outside allowed root: {candidate}") from exc
    return candidate


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Rx7TopicR2Error(f"cannot read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise Rx7TopicR2Error(f"{label} must be an object: {path}")
    return value


def _native_duration(path: Path) -> tuple[int, int, float]:
    try:
        sample_rate_hz, signal = wavfile.read(str(path))
    except Exception as exc:
        raise Rx7TopicR2Error(f"cannot decode RX-7 WAV: {path}") from exc
    signal = np.asarray(signal)
    if signal.size == 0 or sample_rate_hz <= 0 or signal.shape[0] <= 0:
        raise Rx7TopicR2Error(f"RX-7 WAV is empty: {path}")
    if not np.issubdtype(signal.dtype, np.integer) and not np.isfinite(signal).all():
        raise Rx7TopicR2Error(f"RX-7 WAV has non-finite samples: {path}")
    channels = int(signal.shape[1]) if signal.ndim > 1 else 1
    return int(sample_rate_hz), channels, float(signal.shape[0] / float(sample_rate_hz))


def load_rx7_source_manifest(source_root: Path) -> list[dict[str, Any]]:
    """Validate the five author-recorded R2 sources without copying audio."""

    root = _inside(source_root, "source_root")
    payload = _read_json(root / SOURCE_MANIFEST_NAME, "RX-7 authorization manifest")
    if payload.get("schema_version") != "s12-stage-q-web-authorized-r2-v1":
        raise Rx7TopicR2Error("unexpected RX-7 authorization manifest schema")
    recordings = payload.get("recordings")
    if not isinstance(recordings, list):
        raise Rx7TopicR2Error("RX-7 authorization manifest has no recordings")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in recordings:
        if not isinstance(row, Mapping):
            raise Rx7TopicR2Error("RX-7 recording row is malformed")
        recording_id = str(row.get("recording_id") or "")
        if recording_id not in _EXPECTED_RECORDINGS or recording_id in seen:
            continue
        seen.add(recording_id)
        expected_scenario, candidate_scene, topics = _EXPECTED_RECORDINGS[recording_id]
        path = _inside(str(row.get("external_path") or ""), f"{recording_id}.external_path")
        if not path.is_file():
            raise Rx7TopicR2Error(f"RX-7 source is missing: {path}")
        declared_sha = str(row.get("sha256") or "").lower()
        actual_sha = _sha256(path)
        if declared_sha != actual_sha:
            raise Rx7TopicR2Error(f"RX-7 source SHA mismatch: {recording_id}")
        sample_rate_hz, channels, duration_s = _native_duration(path)
        provenance = row.get("provenance")
        evidence = row.get("evidence")
        if not isinstance(provenance, Mapping) or provenance.get("license") != "CC BY-NC-SA 4.0" or provenance.get("legal_permission") != "CONFIRMED":
            raise Rx7TopicR2Error(f"RX-7 license evidence is incomplete: {recording_id}")
        if not isinstance(evidence, Mapping) or evidence.get("level") != "R2" or evidence.get("r1_eligible") is not False:
            raise Rx7TopicR2Error(f"RX-7 evidence level is not fail-closed R2: {recording_id}")
        result.append({
            "recording_id": recording_id,
            "vehicle_id": "rx7_fd",
            "scenario": expected_scenario,
            "candidate_scene": candidate_scene,
            "focus_topics": topics,
            "path": str(path),
            "sha256": actual_sha,
            "sample_rate_hz": sample_rate_hz,
            "channels": channels,
            "native_duration_s": duration_s,
            "reference_class": "R2",
            "source_url": provenance.get("source_url"),
            "source_repository": provenance.get("source_repository"),
            "source_commit": provenance.get("source_commit"),
            "author": provenance.get("author"),
            "author_recording_page": provenance.get("author_recording_page"),
            "license": provenance.get("license"),
            "license_scope": provenance.get("license_scope"),
            "rights_evidence": provenance.get("rights_evidence"),
            "microphone_perspective": provenance.get("microphone_perspective"),
            "recording_device_agc": provenance.get("recording_device_agc"),
            "source_audio_sha256": provenance.get("source_media_sha256"),
            "derivation": "unaltered_external_author_recording; no loop/pad/gain/eq/agc/resampling",
        })
    if set(seen) != set(_EXPECTED_RECORDINGS):
        raise Rx7TopicR2Error(f"RX-7 source manifest must provide five recordings; found {sorted(seen)}")
    return result


def _load_candidate_payload(candidate_root: Path) -> dict[str, Any]:
    candidate_path = _inside(candidate_root / "candidates" / CANDIDATE_PROFILE_NAME, "candidate profile")
    payload = _read_json(candidate_path, "Stage-G RX-7 candidate")
    _validate_payload(payload)
    target_path = Path(__file__).resolve().parents[1] / "acoustic_identity_v015" / "reference_database" / "rx7_fd_reference_targets.json"
    if str(payload["reference_target"]["sha256"]).lower() != _sha256(target_path).lower():
        raise Rx7TopicR2Error("Stage-G RX-7 reference target SHA mismatch")
    return payload


def _adjusted_candidate(candidate_root: Path) -> dict[str, Any]:
    payload = deepcopy(_load_candidate_payload(candidate_root))
    payload["candidate_id"] = "rx7_fd_r2_topic_v1"
    payload["parent_candidate_id"] = "rx7_fd_stage_g_v4"
    payload["hypothesis"] = "Use one bounded rotary housing/turbo distribution adjustment to improve body continuity and spool transition for clean R2 listening; no event timing change."
    for name, value in PARAMETER_OVERRIDES.items():
        entry = payload["source"][name]
        entry["value"] = float(value)
        entry["source_scope"] = f"{PARAMETER_GROUP}:{name}"
        entry["verification_state"] = "candidate_assumption"
    _validate_payload(payload)
    return payload


def _render_candidate_for_duration(payload: Mapping[str, Any], scene: str, duration_s: float) -> np.ndarray:
    candidate = StageGCandidateProfile(payload)
    trace = build_stage_d_scenario_trace("rx7_fd", scene, duration_s=duration_s)
    rendered = render_stage_g_candidate("rx7_fd", trace, candidate)
    final = _edge_fade(_apply_frozen_ptr(rendered.pressure))
    if final.ndim != 2 or final.shape[1] != 2 or not np.isfinite(final).all() or float(np.max(np.abs(final))) <= 0.0:
        raise Rx7TopicR2Error(f"RX-7 candidate health gate failed for {scene}")
    return final


def build_rx7_topic_package(output_root: Path, source_root: Path, candidate_root: Path) -> dict[str, Any]:
    """Build a fresh external package; never overwrite a previous package."""

    output = _inside(output_root, "output_root")
    source = _inside(source_root, "source_root")
    candidate_root = _inside(candidate_root, "candidate_root")
    if output.exists() and any(output.iterdir()):
        raise Rx7TopicR2Error(f"refusing non-empty output: {output}")
    output.mkdir(parents=True, exist_ok=True)
    records = load_rx7_source_manifest(source)
    payload = _adjusted_candidate(candidate_root)
    candidate_meta_path = output / "candidate_profile.json"
    candidate_meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    rendered_candidates = [
        _render_candidate_for_duration(payload, str(record["candidate_scene"]), float(record["native_duration_s"]))
        for record in records
    ]
    max_peak = max(float(np.max(np.abs(audio))) for audio in rendered_candidates)
    peak_limit_linear = 10.0 ** (-1.5 / 20.0)
    fixed_gain_linear = min(1.0, peak_limit_linear / max_peak)
    fixed_gain_db = 20.0 * float(np.log10(max(fixed_gain_linear, 1e-12)))
    pairs: list[dict[str, Any]] = []
    for index, (record, rendered_candidate) in enumerate(zip(records, rendered_candidates), start=1):
        pair_id = f"rx7_topic_{index:02d}_{record['scenario']}"
        reference_path = output / "audio" / pair_id / "reference.wav"
        candidate_path = output / "audio" / pair_id / "candidate.wav"
        candidate_audio = _pcm24_roundtrip(rendered_candidate * fixed_gain_linear)
        candidate_path.parent.mkdir(parents=True, exist_ok=True)
        if float(np.max(np.abs(candidate_audio))) > peak_limit_linear + 1e-6:
            raise Rx7TopicR2Error(f"RX-7 fixed-gain candidate health gate failed before write: {pair_id}")
        shutil.copyfile(record["path"], reference_path)
        _write_pcm24_wav(candidate_path, candidate_audio)
        candidate_fs, candidate_channels, candidate_duration = _native_duration(candidate_path)
        pairs.append({
            "pair_id": pair_id,
            "file_id": f"{pair_id}-reference-vs-candidate",
            "vehicle_id": "rx7_fd",
            "scenario": record["scenario"],
            "reference_class": "R2",
            "reference_path": str(reference_path),
            "reference_sha256": record["sha256"],
            "candidate_path": str(candidate_path),
            "candidate_sha256": _sha256(candidate_path),
            "candidate_profile_sha256": _sha256(candidate_meta_path),
            "parameter_group": PARAMETER_GROUP,
            "parameter_overrides": PARAMETER_OVERRIDES,
            "fixed_candidate_gain_db": fixed_gain_db,
            "focus_topics": record["focus_topics"],
            "microphone_uncertainty": str(record["microphone_perspective"] or "UNKNOWN") + "; AGC=" + str(record["recording_device_agc"] or "UNKNOWN"),
            "order": {"status": "ORDER_COMPARISON_NOT_QUALIFIED", "reason": "reference has no synchronized RPM/load/throttle/gear/shift trace"},
            "uncertainty": {"legal_permission": "CONFIRMED_NONCOMMERCIAL_CC_BY_NC_SA_4", "stock_exhaust": "UNKNOWN", "rpm_state": "MISSING", "mic_agc": "UNKNOWN"},
            "window": {
                "profile": f"{record['native_duration_s']:.3f}s_native",
                "duration_s": float(record["native_duration_s"]),
                "reference": {"path": str(reference_path), "sha256": record["sha256"], "source_path": record["path"], "sample_rate_hz": record["sample_rate_hz"], "channels": record["channels"], "duration_s": record["native_duration_s"], "derivation": "byte_identical_external_copy_no_gain_eq_agc_resampling"},
                "candidate": {"path": str(candidate_path), "sha256": _sha256(candidate_path), "sample_rate_hz": candidate_fs, "channels": candidate_channels, "duration_s": candidate_duration, "derivation": "stage_g_render_native_duration_no_reference_processing"},
            },
            "provenance": {"source_url": record["source_url"], "source_repository": record["source_repository"], "source_commit": record["source_commit"], "author": record["author"], "author_recording_page": record["author_recording_page"], "license": record["license"], "license_scope": record["license_scope"], "rights_evidence": record["rights_evidence"], "source_audio_sha256": record["source_audio_sha256"]},
        })
    manifest = {
        "schema_version": "s12-professional-long-window-manifest-v1",
        "status": "RX7_R2_TOPIC_DIAGNOSTIC_READY",
        "package_id": "s12-rx7-topic-r2-v1",
        "vehicle_id": "rx7_fd",
        "reference_class": "R2",
        "source_audit_root": str(source),
        "source_audit_manifest": str(source / SOURCE_MANIFEST_NAME),
        "source_audit_manifest_sha256": _sha256(source / SOURCE_MANIFEST_NAME),
        "candidate_profile_path": str(candidate_meta_path),
        "candidate_profile_sha256": _sha256(candidate_meta_path),
        "parameter_group": PARAMETER_GROUP,
        "parameter_overrides": PARAMETER_OVERRIDES,
        "fixed_candidate_gain_db": fixed_gain_db,
        "parameter_changes": 1,
        "pairs": pairs,
        "pair_count": len(pairs),
        "window_profiles_s": sorted({round(float(record["native_duration_s"]), 6) for record in records}),
        "raw_media_policy": "external_only",
        "derivation_policy": "native_source_duration_no_loop_no_padding_no_gain_eq_agc_resampling",
        "order_status": "ORDER_COMPARISON_NOT_QUALIFIED",
        "automatic_tuning_eligible": False,
        "profile_candidate_ready": False,
        "source_modified": False,
    }
    manifest_path = output / "rx7_topic_r2_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    receipt = {
        "schema_version": "s12-rx7-topic-r2-receipt-v1",
        "status": "RX7_R2_TOPIC_PACKAGE_PASS",
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "pair_count": len(pairs),
        "native_durations_s": manifest["window_profiles_s"],
        "reference_class": "R2",
        "parameter_group": PARAMETER_GROUP,
        "parameter_changes": 1,
        "source_modified": False,
        "order_status": "ORDER_COMPARISON_NOT_QUALIFIED",
        "automatic_tuning_eligible": False,
        "profile_candidate_ready": False,
    }
    (output / "rx7_topic_r2_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="构建外部-only RX-7 R2 主题对比包")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    args = parser.parse_args(argv)
    receipt = build_rx7_topic_package(args.output_root, args.source_root, args.candidate_root)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


__all__ = [
    "ALLOWED_ROOT",
    "PARAMETER_GROUP",
    "PARAMETER_OVERRIDES",
    "Rx7TopicR2Error",
    "build_rx7_topic_package",
    "load_rx7_source_manifest",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
