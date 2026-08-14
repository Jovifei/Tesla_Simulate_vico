"""Round-2 v9 Hellcat named audition producer and package handoff.

This module deliberately keeps producer authority in-process.  A package build
can consume only the opaque handle returned by the producer in the same
process; a caller-created mapping or a self-hashed manifest is rejected.
"""

from __future__ import annotations

import binascii
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import threading
from types import MappingProxyType
from typing import Callable, Mapping
import uuid
import wave
import weakref
import zipfile

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace
from ..loudness_manager import measure_loudness
from .crank_clock import build_hellcat_crank_clock
from .render_candidate import render_stage_l_round2_formal_final_pcm_bundle
from .round2_metrics import compute_round2_metrics


PACKAGE_ID = "s12-stage-l-hellcat-intake-roughness-v6"
PRODUCER_SCHEMA = "s12-stage-l-round2-named-artifact-producer-1"
PACKAGE_SCHEMA = "s12-stage-l-round2-named-review-package-1"
STATUS = "PARTIAL / AUTOMATED_GATE_FAIL"
QUALIFICATION_STATUS = "UNQUALIFIED_DIAGNOSTIC_ONLY"
FEEDBACK_STATUS = "DIAGNOSTIC_FEEDBACK_ALLOWED"
ZIP_NAME = "S12_Stage_L_Hellcat_Round2_UNQUALIFIED_DIAGNOSTIC_Review.zip"

FORMAL_WAV_DESTINATIONS = (
    "01_Formal_Comparison/01_Dodge_Hellcat_StageK_Parent_60s.wav",
    "01_Formal_Comparison/02_Dodge_Hellcat_StageL_v8_Baseline_60s.wav",
    "01_Formal_Comparison/03_Dodge_Hellcat_StageL_v9_Candidate_60s.wav",
    "01_Formal_Comparison/04_Dodge_Hellcat_StageL_v9_Candidate_Comfort_60s.wav",
)
DIAGNOSTIC_WAV_DESTINATIONS = (
    "02_Source_Domain_Diagnostics/01_Dodge_Hellcat_SC_Whine_18s.wav",
    "02_Source_Domain_Diagnostics/02_Dodge_Hellcat_HEMI_Rumble_18s.wav",
    "02_Source_Domain_Diagnostics/03_Dodge_Hellcat_SC_HEMI_Combined_18s.wav",
    "02_Source_Domain_Diagnostics/04_Dodge_Hellcat_Afterfire_10s.wav",
)
WAV_DESTINATIONS = FORMAL_WAV_DESTINATIONS + DIAGNOSTIC_WAV_DESTINATIONS
DIAGNOSTIC_DURATIONS_S = {
    "sc_whine": 18.0,
    "hemi_rumble": 18.0,
    "sc_plus_hemi": 18.0,
    "afterfire": 10.0,
}
SAMPLE_RATE_HZ = 48_000
DIAGNOSTIC_SOURCE_STEMS = {
    "sc_whine": ("sc_intake_radiated", "sc_casing_radiated", "sc_bypass_release"),
    "hemi_rumble": (
        "hemi_exhaust_left", "hemi_exhaust_right", "hemi_blowdown_body",
        "hemi_structure_shock", "hemi_mechanical_torque_ripple",
    ),
    "sc_plus_hemi": (
        "sc_intake_radiated", "sc_casing_radiated", "sc_bypass_release",
        "hemi_exhaust_left", "hemi_exhaust_right", "hemi_blowdown_body",
        "hemi_structure_shock", "hemi_mechanical_torque_ripple",
    ),
    "afterfire": ("afterfire",),
}


class ProducedStageLRound2Artifacts:
    """Opaque producer capability; direct construction is intentionally denied."""

    __slots__ = ("_metadata", "__weakref__")

    def __new__(cls, *_args: object, **_kwargs: object):
        raise TypeError("ProducedStageLRound2Artifacts is producer-issued only")

    def __getitem__(self, key: str) -> object:
        return self._metadata[key]

    def __iter__(self):
        return iter(self._metadata)

    def __len__(self) -> int:
        return len(self._metadata)


_CAPABILITIES: weakref.WeakKeyDictionary[ProducedStageLRound2Artifacts, tuple[Path, str]] = weakref.WeakKeyDictionary()
_CONSUMED: weakref.WeakSet[ProducedStageLRound2Artifacts] = weakref.WeakSet()
_CAPABILITY_LOCK = threading.Lock()


def _issue(metadata: Mapping[str, object]) -> ProducedStageLRound2Artifacts:
    handle = object.__new__(ProducedStageLRound2Artifacts)
    handle._metadata = MappingProxyType(dict(metadata))
    manifest = Path(str(handle["artifact_manifest_path"])).resolve()
    _CAPABILITIES[handle] = (manifest, str(handle["artifact_manifest_sha256"]).lower())
    return handle


def _consume(value: object) -> tuple[Path, str]:
    if not isinstance(value, ProducedStageLRound2Artifacts):
        raise ValueError("trusted in-process producer capability is required")
    with _CAPABILITY_LOCK:
        trusted = _CAPABILITIES.pop(value, None)
        if trusted is not None:
            _CONSUMED.add(value)
            return trusted
        if value in _CONSUMED:
            raise ValueError("trusted capability already consumed")
    raise ValueError("trusted in-process producer capability is required")


def render_stage_l_round2_named_artifacts(
    output_root: str | Path,
    *,
    trace: VehicleStateTrace,
    stage_k_parent_renderer: Callable[[object], SourceRender],
    stage_l_v8_renderer: Callable[[object], SourceRender],
    stage_l_v9_renderer: Callable[[object], SourceRender],
    source_commit: str,
    stage_k_parent_profile_sha256: str,
    stage_l_v8_profile_sha256: str,
    stage_l_v9_profile_sha256: str,
    trace_version: str,
    candidate_base_commit: str | None = None,
    producer_source_dirty: bool = False,
    producer_source_file_sha256: Mapping[str, str] | None = None,
    diagnostic_durations_s: Mapping[str, float] | None = None,
    formal_target_lufs: float = -16.0,
    formal_peak_limit_dbfs: float = -1.5,
    comfort_requested_gain_db: float = 1.0,
) -> ProducedStageLRound2Artifacts:
    """Render parent/v8/v9 once with one trace and emit a bound handoff."""

    root = Path(output_root).resolve()
    if root.exists():
        raise FileExistsError(f"artifact output root already exists; refusing overwrite: {root}")
    trace.validate()
    _validate_sha(source_commit, 40, "producer source_commit")
    if candidate_base_commit is None:
        candidate_base_commit = source_commit
    _validate_sha(candidate_base_commit, 40, "candidate_base_commit")
    source_file_hashes = dict(producer_source_file_sha256 or {})
    for path, value in source_file_hashes.items():
        _validate_sha(value, 64, f"producer source file {path}")
    for value, label in (
        (stage_k_parent_profile_sha256, "StageK parent profile"),
        (stage_l_v8_profile_sha256, "StageL v8 profile"),
        (stage_l_v9_profile_sha256, "StageL v9 profile"),
    ):
        _validate_sha(value, 64, label)
    durations = dict(DIAGNOSTIC_DURATIONS_S)
    if diagnostic_durations_s is not None:
        durations.update({str(k): float(v) for k, v in diagnostic_durations_s.items()})
    if set(durations) != set(DIAGNOSTIC_DURATIONS_S) or any(
        not math.isfinite(v) or v <= 0.0 for v in durations.values()
    ):
        raise ValueError("diagnostic durations must be positive finite values")
    root.mkdir(parents=True)
    try:
        parent = stage_k_parent_renderer(trace).validate()
        v8 = stage_l_v8_renderer(trace).validate()
        v9 = stage_l_v9_renderer(trace).validate()
        parent_pressure = np.asarray(parent.pressure, dtype=np.float64).copy()
        v8_pressure = np.asarray(v8.pressure, dtype=np.float64).copy()
        v9_pressure = np.asarray(v9.pressure, dtype=np.float64).copy()
        _validate_audio(parent_pressure, "StageK parent pressure")
        _validate_audio(v8_pressure, "StageL v8 pressure")
        _validate_audio(v9_pressure, "StageL v9 pressure")

        bundle = render_stage_l_round2_formal_final_pcm_bundle(
            parent_pressure,
            v8_pressure,
            v9_pressure,
            target_lufs=float(formal_target_lufs),
            peak_limit_dbfs=float(formal_peak_limit_dbfs),
            comfort_requested_gain_db=float(comfort_requested_gain_db),
        )
        expected_order = ("frozen_ptr", "edge_fade", "one_fixed_whole_cycle_gain", "pcm24")
        expected_comfort_order = (*expected_order, "candidate_comfort_static_gain", "pcm24")
        actual_comfort_order = tuple(
            getattr(bundle, "comfort_final_pipeline_order", bundle.comfort_pipeline_order)
        )
        if tuple(bundle.pipeline_order) != expected_order or actual_comfort_order != expected_comfort_order:
            raise ValueError("Round-2 formal bundle pipeline is not frozen")
        trace_sha = _trace_sha256(trace)
        bindings = {
            # `source_commit` is retained as a compatibility alias, but its
            # meaning is now explicit: the producer implementation commit.
            "source_commit": str(source_commit).lower(),
            "producer_source_commit": str(source_commit).lower(),
            "candidate_base_commit": str(candidate_base_commit).lower(),
            "producer_source_dirty": bool(producer_source_dirty),
            "producer_source_file_sha256": source_file_hashes,
            "stage_k_parent_profile_sha256": str(stage_k_parent_profile_sha256).lower(),
            "stage_l_v8_profile_sha256": str(stage_l_v8_profile_sha256).lower(),
            "stage_l_v9_profile_sha256": str(stage_l_v9_profile_sha256).lower(),
            "trace_version": str(trace_version),
            "trace_sha256": trace_sha,
            "candidate_id": "hellcat_stage_l_v9",
        }
        artifacts: dict[str, dict[str, object]] = {}
        formal_values = (
            bundle.parent_pcm,
            bundle.v8_pcm,
            bundle.v9_pcm,
            bundle.comfort_pcm,
        )
        for index, (relative, audio) in enumerate(zip(FORMAL_WAV_DESTINATIONS, formal_values, strict=True)):
            input_sha = None
            if index == 3:
                input_sha = _pcm24_array_payload_sha256(bundle.v9_pcm)
            record = _emit_wav(
                root,
                relative,
                audio,
                "formal_final_pcm_bundle",
                bindings,
                state_kind="formal",
                final_pipeline=list(expected_comfort_order if index == 3 else expected_order),
                final_pcm_input_sha256=input_sha,
                comfort_gain_db=float(bundle.comfort_gain_db) if index == 3 else None,
                common_gain_db=float(bundle.gain_db),
                headroom_limited=bool(bundle.headroom_limited),
            )
            artifacts[relative] = record

        stems = {str(k): np.asarray(v, dtype=np.float64) for k, v in v9.stems.items()}
        diagnostic_audio = {
            "sc_whine": _stem_sum(stems, ("sc_intake_radiated", "sc_casing_radiated", "sc_bypass_release")),
            "hemi_rumble": _stem_sum(stems, ("hemi_exhaust_left", "hemi_exhaust_right", "hemi_blowdown_body")),
            "sc_plus_hemi": _stem_sum(stems, (
                "sc_intake_radiated", "sc_casing_radiated", "sc_bypass_release",
                "hemi_exhaust_left", "hemi_exhaust_right", "hemi_blowdown_body",
            )),
            "afterfire": np.asarray(stems.get("afterfire", np.zeros_like(v9.pressure)), dtype=np.float64),
        }
        diagnostic_keys = tuple(DIAGNOSTIC_DURATIONS_S)
        for relative, key in zip(DIAGNOSTIC_WAV_DESTINATIONS, diagnostic_keys, strict=True):
            if key == "afterfire":
                raw, window_evidence = _afterfire_diagnostic_window_with_metadata(
                    diagnostic_audio[key], durations[key]
                )
            else:
                raw, window_evidence = _source_diagnostic_window(
                    diagnostic_audio[key], durations[key], key
                )
            artifacts[relative] = _emit_wav(
                root,
                relative,
                raw,
                str(v9.diagnostics.get("render_path", "StageL_v9_source_domain")),
                bindings,
                state_kind="source_domain_diagnostic",
                diagnostic_key=key,
                window_evidence=window_evidence,
            )

        metrics = compute_round2_metrics(
            v9,
            trace,
            build_hellcat_crank_clock(trace, 48_000),
            str(root / FORMAL_WAV_DESTINATIONS[2]),
            str(root / FORMAL_WAV_DESTINATIONS[1]),
        )
        # The metrics function consumes the v8 baseline as its reference.  It
        # historically used a generic Stage-K label; make the actual role and
        # both reopened payload/file hashes explicit at the handoff boundary.
        metrics.setdefault("domains", {})["final_pcm24"] = (
            "reopened StageL v9 candidate and StageL v8 baseline PCM24 bytes"
        )
        candidate_path = root / FORMAL_WAV_DESTINATIONS[2]
        baseline_path = root / FORMAL_WAV_DESTINATIONS[1]
        metrics.setdefault("final_pcm24", {})["candidate_role"] = "StageL_v9_candidate"
        metrics["final_pcm24"]["reference_role"] = "StageL_v8_baseline"
        metrics["final_pcm24"]["candidate_file_sha256"] = _sha256(candidate_path)
        metrics["final_pcm24"]["reference_file_sha256"] = _sha256(baseline_path)
        metrics["final_pcm24"]["candidate_pcm_sha256"] = _pcm24_payload_sha256(candidate_path)
        metrics["final_pcm24"]["reference_pcm_sha256"] = _pcm24_payload_sha256(baseline_path)
        metrics_relative = "03_Metrics/round2_metrics.json"
        metrics_path = root / metrics_relative
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_path.write_text(
            json.dumps(metrics, indent=2, sort_keys=True, default=_json_default) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        artifacts[metrics_relative] = {
            "kind": "json",
            "path": str(metrics_path),
            "sha256": _sha256(metrics_path),
            "producer_receipt": {
                "schema_version": PRODUCER_SCHEMA,
                "file_id": metrics_relative,
                "file_sha256": _sha256(metrics_path),
                **bindings,
            },
        }
        handoff = {
            "schema_version": PRODUCER_SCHEMA,
            "package_id": PACKAGE_ID,
            "status": STATUS,
            "qualification_status": QUALIFICATION_STATUS,
            "bindings": bindings,
            "formal_common_gain": {
                "gain_db": float(bundle.gain_db),
                "headroom_limited": bool(bundle.headroom_limited),
                "compressor": False,
                "limiter": False,
                "dynamic_eq": False,
                "per_section_agc": False,
            },
            "artifacts": artifacts,
            "feedback": {"human_pass": False, "csv_content_read": False},
        }
        manifest_path = root / "artifact_manifest.json"
        manifest_path.write_text(
            json.dumps(handoff, indent=2, sort_keys=True, default=_json_default) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return _issue({
            "artifact_manifest_path": str(manifest_path),
            "artifact_manifest_sha256": _sha256(manifest_path),
            "status": STATUS,
            "qualification_status": QUALIFICATION_STATUS,
            "artifact_count": len(artifacts),
        })
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise


def build_round2_unqualified_diagnostic_package(
    output_root: str | Path,
    *,
    produced_artifacts: ProducedStageLRound2Artifacts,
) -> dict[str, object]:
    """Atomically copy a trusted producer handoff into the v6 package."""

    root = Path(output_root).resolve()
    if root.exists():
        raise FileExistsError(f"package output root already exists; refusing overwrite: {root}")
    manifest_path, manifest_sha = _consume(produced_artifacts)
    if not manifest_path.is_file() or _sha256(manifest_path) != manifest_sha:
        raise ValueError("producer manifest SHA binding failed")
    source = json.loads(manifest_path.read_text(encoding="utf-8"))
    _validate_handoff(source)
    staging = root.parent / f".{root.name}.staging-{uuid.uuid4().hex}"
    if staging.exists():
        raise FileExistsError("staging root already exists")
    try:
        staging.mkdir(parents=True)
        copied: dict[str, object] = {}
        wav_artifacts: list[dict[str, object]] = []
        for relative, record in sorted(source["artifacts"].items()):
            source_path = Path(str(record["path"])).resolve()
            if not source_path.is_file() or _sha256(source_path) != str(record.get("sha256", "")).lower():
                raise ValueError(f"producer artifact SHA binding failed: {relative}")
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, destination)
            item = {
                "path": relative,
                "kind": record.get("kind"),
                "sha256": _sha256(destination),
                "source_binding": dict(source["bindings"]),
            }
            if relative in WAV_DESTINATIONS:
                health = _pcm24_health(destination)
                if not health["passes"]:
                    raise ValueError(f"PCM24 health gate failed: {relative}")
                receipt = record.get("producer_receipt")
                if not isinstance(receipt, dict):
                    raise ValueError(f"producer receipt is required: {relative}")
                actual_file_sha = _sha256(destination)
                actual_pcm_sha = _pcm24_payload_sha256(destination)
                if receipt.get("file_sha256") != actual_file_sha or record.get("sha256") != actual_file_sha:
                    raise ValueError(f"producer receipt file SHA binding failed: {relative}")
                if receipt.get("pcm_sha256") != actual_pcm_sha or record.get("pcm_sha256") != actual_pcm_sha:
                    raise ValueError(f"producer receipt PCM SHA binding failed: {relative}")
                if record.get("receipt") != receipt:
                    raise ValueError(f"producer receipt alias binding failed: {relative}")
                if receipt.get("frame_count") != health["frame_count"] or record.get("frame_count") != health["frame_count"]:
                    raise ValueError(f"producer receipt frame binding failed: {relative}")
                if not math.isclose(float(receipt.get("duration_s")), float(health["duration_s"]), rel_tol=0.0, abs_tol=1.0e-12):
                    raise ValueError(f"producer receipt duration binding failed: {relative}")
                if receipt.get("semantic_role") != _semantic_role(relative):
                    raise ValueError(f"producer receipt semantic role failed: {relative}")
                item["pcm_health"] = health
                item["pcm_sha256"] = actual_pcm_sha
                item["producer_receipt"] = receipt
                wav_artifacts.append(item)
            else:
                receipt = record.get("producer_receipt")
                if not isinstance(receipt, dict) or receipt.get("file_sha256") != item["sha256"]:
                    raise ValueError(f"producer artifact receipt SHA binding failed: {relative}")
            copied[relative] = item
        manifest = {
            "schema_version": PACKAGE_SCHEMA,
            "package_id": PACKAGE_ID,
            "status": STATUS,
            "package_status": "PARTIAL",
            "qualification_status": QUALIFICATION_STATUS,
            "feedback_status": FEEDBACK_STATUS,
            "human_feedback_content_read": False,
            "human_pass": False,
            "csv_content_read": False,
            "wav_count": len(wav_artifacts),
            "formal_wav_count": len(FORMAL_WAV_DESTINATIONS),
            "diagnostic_wav_count": len(DIAGNOSTIC_WAV_DESTINATIONS),
            "formal_common_gain": source["formal_common_gain"],
            "artifacts": copied,
            "wav_artifacts": wav_artifacts,
            "source_bindings": source["bindings"],
            "scope": "C-level synthetic; uncalibrated; Hellcat-inspired; not OEM reproduction",
        }
        (staging / "artifact_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True, default=_json_default) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        (staging / "README.md").write_text(
            "# Dodge Hellcat Stage L Round-2 diagnostic package\n\n"
            "Status: `PARTIAL / AUTOMATED_GATE_FAIL`\n"
            "Qualification: `UNQUALIFIED_DIAGNOSTIC_ONLY`\n"
            "This is synthetic, uncalibrated, Hellcat-inspired diagnostic audio; no human pass is claimed.\n",
            encoding="utf-8",
            newline="\n",
        )
        (staging / "SHA256SUMS.txt").write_text(_sha256sums(staging), encoding="utf-8", newline="\n")
        zip_path = staging / ZIP_NAME
        _write_deterministic_zip(staging, zip_path)
        _validate_zip_contents(staging, zip_path)
        os.replace(staging, root)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        **manifest,
        "output_root": str(root),
        "zip_path": str(root / ZIP_NAME),
    }


def _validate_handoff(source: Mapping[str, object]) -> None:
    if source.get("schema_version") != PRODUCER_SCHEMA or source.get("package_id") != PACKAGE_ID:
        raise ValueError("producer handoff schema/package mismatch")
    if source.get("status") != STATUS or source.get("qualification_status") != QUALIFICATION_STATUS:
        raise ValueError("producer handoff status mismatch")
    bindings = source.get("bindings")
    artifacts = source.get("artifacts")
    if not isinstance(bindings, dict) or not isinstance(artifacts, dict):
        raise ValueError("producer handoff bindings/artifacts are required")
    expected_artifacts = set(WAV_DESTINATIONS) | {"03_Metrics/round2_metrics.json"}
    if set(artifacts) != expected_artifacts:
        raise ValueError("producer handoff artifact set is not exact")
    for relative in WAV_DESTINATIONS:
        record = artifacts[relative]
        if not isinstance(record, dict) or not isinstance(record.get("producer_receipt"), dict):
            raise ValueError(f"producer receipt is required: {relative}")
        receipt = record["producer_receipt"]
        if record.get("receipt") != receipt:
            raise ValueError(f"producer receipt alias mismatch: {relative}")
        if receipt.get("schema_version") != PRODUCER_SCHEMA or receipt.get("file_id") != relative:
            raise ValueError(f"producer receipt identity mismatch: {relative}")
        for key, value in bindings.items():
            if receipt.get(key) != value:
                raise ValueError(f"producer receipt binding mismatch: {relative}")
        if receipt.get("semantic_role") != _semantic_role(relative):
            raise ValueError(f"producer receipt semantic role mismatch: {relative}")
        if receipt.get("file_sha256") != record.get("sha256"):
            raise ValueError(f"producer receipt file SHA binding mismatch: {relative}")
        if receipt.get("pcm_sha256") != record.get("pcm_sha256"):
            raise ValueError(f"producer receipt PCM SHA binding mismatch: {relative}")
        if receipt.get("frame_count") != record.get("frame_count") or not isinstance(receipt.get("duration_s"), (int, float)):
            raise ValueError(f"producer receipt duration binding mismatch: {relative}")
        if not math.isclose(float(receipt["duration_s"]), float(record.get("duration_s")), rel_tol=0.0, abs_tol=1.0e-12):
            raise ValueError(f"producer receipt duration value mismatch: {relative}")
        if relative in FORMAL_WAV_DESTINATIONS:
            pipeline = receipt.get("pipeline_order", receipt.get("final_pipeline"))
            expected_pipeline = ["frozen_ptr", "edge_fade", "one_fixed_whole_cycle_gain", "pcm24"]
            if relative == FORMAL_WAV_DESTINATIONS[3]:
                expected_pipeline += ["candidate_comfort_static_gain", "pcm24"]
            if pipeline != expected_pipeline:
                raise ValueError(f"formal pipeline binding mismatch: {relative}")
            if receipt.get("final_pcm_sha256") != record.get("pcm_sha256"):
                raise ValueError(f"formal final PCM SHA binding mismatch: {relative}")
        else:
            evidence = receipt.get("event_evidence")
            required_evidence = {
                "diagnostic_key", "source_domain_diagnostic", "source_stems",
                "window_start_sample", "window_end_sample", "window_start_s",
                "window_end_s", "output_duration_s", "window_policy",
            }
            if not isinstance(evidence, dict) or not required_evidence.issubset(evidence):
                raise ValueError(f"diagnostic window evidence is incomplete: {relative}")

    comfort = artifacts[FORMAL_WAV_DESTINATIONS[3]]["producer_receipt"]
    candidate = artifacts[FORMAL_WAV_DESTINATIONS[2]]["producer_receipt"]
    if comfort.get("final_pcm_input_sha256") != candidate.get("pcm_sha256"):
        raise ValueError("Comfort input PCM is not the formal v9 candidate PCM")

    metrics_relative = "03_Metrics/round2_metrics.json"
    metrics_record = artifacts[metrics_relative]
    if not isinstance(metrics_record, dict) or not isinstance(metrics_record.get("producer_receipt"), dict):
        raise ValueError("metrics producer receipt is required")
    metrics_receipt = metrics_record["producer_receipt"]
    if metrics_receipt.get("schema_version") != PRODUCER_SCHEMA or metrics_receipt.get("file_id") != metrics_relative:
        raise ValueError("metrics producer receipt identity mismatch")
    if metrics_receipt.get("file_sha256") != metrics_record.get("sha256"):
        raise ValueError("metrics producer receipt SHA binding mismatch")
    for key, value in bindings.items():
        if metrics_receipt.get(key) != value:
            raise ValueError("metrics producer receipt binding mismatch")
    metrics_path = Path(str(metrics_record.get("path"))).resolve()
    if not metrics_path.is_file():
        raise ValueError("metrics artifact path is missing")
    metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    final_pcm = metrics_payload.get("final_pcm24")
    candidate_record = artifacts[FORMAL_WAV_DESTINATIONS[2]]
    baseline_record = artifacts[FORMAL_WAV_DESTINATIONS[1]]
    if not isinstance(final_pcm, dict) or final_pcm.get("candidate_role") != "StageL_v9_candidate" or final_pcm.get("reference_role") != "StageL_v8_baseline":
        raise ValueError("metrics final PCM roles are not exact")
    if final_pcm.get("candidate_file_sha256") != candidate_record.get("sha256") or final_pcm.get("reference_file_sha256") != baseline_record.get("sha256"):
        raise ValueError("metrics final PCM file SHA bindings are not exact")
    if final_pcm.get("candidate_pcm_sha256") != candidate_record.get("pcm_sha256") or final_pcm.get("reference_pcm_sha256") != baseline_record.get("pcm_sha256"):
        raise ValueError("metrics final PCM payload SHA bindings are not exact")


def _emit_wav(
    root: Path,
    relative: str,
    audio: np.ndarray,
    render_path: str,
    bindings: Mapping[str, str],
    *,
    state_kind: str,
    diagnostic_key: str | None = None,
    final_pipeline: list[str] | None = None,
    final_pcm_input_sha256: str | None = None,
    comfort_gain_db: float | None = None,
    common_gain_db: float | None = None,
    headroom_limited: bool = False,
    window_evidence: Mapping[str, object] | None = None,
) -> dict[str, object]:
    final = np.asarray(audio, dtype=np.float64)
    if final.ndim == 1:
        final = final[:, None]
    if final.ndim != 2 or final.shape[1] != 2 or not final.size or not np.all(np.isfinite(final)):
        raise ValueError(f"audio must be finite stereo: {relative}")
    limit = 10.0 ** (-1.5 / 20.0)
    peak = float(np.max(np.abs(final)))
    attenuation = min(1.0, limit / peak) if peak else 1.0
    final = final * attenuation
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write_pcm24(destination, final)
    health = _pcm24_health(destination)
    if not health["passes"]:
        raise ValueError(f"WAV health failed: {relative}")
    payload_sha = _pcm24_payload_sha256(destination)
    file_sha = _sha256(destination)
    evidence = {"state_kind": state_kind}
    if diagnostic_key:
        evidence["diagnostic_key"] = diagnostic_key
        evidence["source_domain_diagnostic"] = True
    if window_evidence is not None:
        evidence.update(dict(window_evidence))
    receipt: dict[str, object] = {
        "schema_version": PRODUCER_SCHEMA,
        "package_id": PACKAGE_ID,
        "status": STATUS,
        "file_id": relative,
        "semantic_role": _semantic_role(relative),
        "frame_count": health["frame_count"],
        "duration_s": health["duration_s"],
        "pcm_sha256": payload_sha,
        "file_sha256": file_sha,
        "source_render_path": render_path,
        "event_evidence": evidence,
        **dict(bindings),
        "headroom_limited": bool(headroom_limited or attenuation < 1.0),
    }
    record: dict[str, object] = {
        "kind": "pcm24_wav",
        "path": str(destination),
        "sha256": file_sha,
        "pcm_sha256": payload_sha,
        "producer_receipt": receipt,
        "receipt": receipt,
        "frame_count": health["frame_count"],
        "duration_s": health["duration_s"],
        "pcm_health": health,
    }
    if final_pipeline is not None:
        if final_pcm_input_sha256 is None:
            final_pcm_input_sha256 = payload_sha
        receipt.update({
            "final_pcm_sha256": payload_sha,
            "final_pcm_input_sha256": final_pcm_input_sha256,
            "pipeline_order": final_pipeline,
        })
        record.update({
            "final_pcm_sha256": payload_sha,
            "final_pcm_input_sha256": final_pcm_input_sha256,
            "pipeline_order": final_pipeline,
        })
        if common_gain_db is not None:
            receipt["common_gain_db"] = float(common_gain_db)
            record["common_gain_db"] = float(common_gain_db)
        if comfort_gain_db is not None:
            receipt["comfort_static_gain_db"] = float(comfort_gain_db)
            record["comfort_static_gain_db"] = float(comfort_gain_db)
    return record


def _write_pcm24(path: Path, audio: np.ndarray) -> None:
    array = np.asarray(audio, dtype=np.float64)
    if array.ndim == 1:
        array = array[:, None]
    if array.shape[1] != 2:
        raise ValueError("PCM24 output must be stereo")
    quantized = np.clip(np.rint(array * 8388607.0), -8388608.0, 8388607.0).astype(np.int32)
    raw = quantized.reshape(-1)
    payload = np.empty(raw.size * 3, dtype=np.uint8)
    payload[0::3] = raw & 0xFF
    payload[1::3] = (raw >> 8) & 0xFF
    payload[2::3] = (raw >> 16) & 0xFF
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(3)
        stream.setframerate(48_000)
        stream.writeframes(payload.tobytes())


def _pcm24_health(path: Path) -> dict[str, object]:
    with wave.open(str(path), "rb") as stream:
        channels, width, rate, frames = (
            stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getnframes()
        )
        payload = stream.readframes(frames)
    valid = (rate, channels, width) == (48_000, 2, 3) and len(payload) == frames * 6
    if not valid:
        return {"sample_rate_hz": rate, "channels": channels, "pcm_bits": width * 8, "frame_count": frames, "duration_s": frames / rate if rate else 0.0, "finite": False, "peak_dbfs": float("inf"), "clipping_count": -1, "passes": False}
    values = np.frombuffer(payload, dtype=np.uint8).reshape(-1, 3)
    ints = values[:, 0].astype(np.int32) | (values[:, 1].astype(np.int32) << 8) | (values[:, 2].astype(np.int32) << 16)
    ints = np.where((ints & 0x800000) != 0, ints - 0x1000000, ints)
    floats = ints.astype(np.float64) / 8388608.0
    peak = float(np.max(np.abs(floats))) if floats.size else 0.0
    peak_dbfs = float(20.0 * np.log10(max(peak, 1.0e-30)))
    clipping = int(np.count_nonzero(np.abs(floats) >= 1.0))
    return {"sample_rate_hz": rate, "channels": channels, "pcm_bits": 24, "frame_count": frames, "duration_s": frames / rate, "finite": bool(np.all(np.isfinite(floats))), "peak_dbfs": peak_dbfs, "clipping_count": clipping, "passes": bool(np.all(np.isfinite(floats)) and clipping == 0 and peak_dbfs <= -1.5 + 1.0e-6)}


def _pcm24_payload_sha256(path: Path) -> str:
    with wave.open(str(path), "rb") as stream:
        payload = stream.readframes(stream.getnframes())
    return hashlib.sha256(payload).hexdigest()


def _pcm24_array_payload_sha256(audio: np.ndarray) -> str:
    array = np.asarray(audio, dtype=np.float64)
    if array.ndim == 1:
        array = array[:, None]
    quantized = np.clip(np.rint(array * 8388607.0), -8388608.0, 8388607.0).astype(np.int32)
    raw = quantized.reshape(-1)
    payload = np.empty(raw.size * 3, dtype=np.uint8)
    payload[0::3] = raw & 0xFF
    payload[1::3] = (raw >> 8) & 0xFF
    payload[2::3] = (raw >> 16) & 0xFF
    return hashlib.sha256(payload.tobytes()).hexdigest()


def _exact_duration(audio: np.ndarray, duration_s: float) -> np.ndarray:
    count = max(1, int(round(float(duration_s) * 48_000)))
    array = np.asarray(audio, dtype=np.float64)
    if array.ndim == 1:
        array = array[:, None]
    if array.shape[0] == count:
        return array.copy()
    if array.shape[0] == 0:
        return np.zeros((count, 2), dtype=np.float64)
    return np.resize(array, (count, array.shape[1])).astype(np.float64, copy=False)


def _windowed_array(
    audio: np.ndarray,
    duration_s: float,
    *,
    start_s: float,
    event_aligned: bool,
) -> tuple[np.ndarray, dict[str, object]]:
    """Extract a named source-domain window and return auditable evidence."""
    array = np.asarray(audio, dtype=np.float64)
    if array.ndim == 1:
        array = array[:, None]
    count = max(1, int(round(float(duration_s) * SAMPLE_RATE_HZ)))
    requested_start = max(0.0, float(start_s))
    start = min(max(0, int(round(requested_start * SAMPLE_RATE_HZ))), max(0, array.shape[0] - 1))
    stop = min(array.shape[0], start + count)
    selected = array[start:stop]
    if selected.shape[0] != count:
        selected = np.resize(selected, (count, array.shape[1])).astype(np.float64, copy=False)
    evidence = {
        "window_start_sample": int(start),
        "window_end_sample": int(stop),
        "window_start_s": float(start / SAMPLE_RATE_HZ),
        "window_end_s": float(stop / SAMPLE_RATE_HZ),
        "output_duration_s": float(count / SAMPLE_RATE_HZ),
        "event_aligned": bool(event_aligned),
        "window_policy": "actual_source_array_slice_then_length_bound",
    }
    return selected.copy(), evidence


def _source_diagnostic_window(
    audio: np.ndarray,
    duration_s: float,
    diagnostic_key: str,
) -> tuple[np.ndarray, dict[str, object]]:
    # The canonical 60 s trace uses the third-shift/high-load window beginning
    # at 24 s.  Short injected fixtures cannot contain that interval, so they
    # explicitly fall back to their available origin rather than pretending
    # that a zero-padded slice came from 24 s.
    duration = np.asarray(audio).shape[0] / SAMPLE_RATE_HZ
    start_s = 24.0 if duration >= 42.0 else 0.0
    window, evidence = _windowed_array(
        audio, duration_s, start_s=start_s, event_aligned=False
    )
    evidence["source_stems"] = list(DIAGNOSTIC_SOURCE_STEMS[diagnostic_key])
    evidence["diagnostic_key"] = diagnostic_key
    return window, evidence


def _afterfire_diagnostic_window(audio: np.ndarray, duration_s: float) -> np.ndarray:
    """Return a duration-limited window anchored on the first real event."""
    return _afterfire_diagnostic_window_with_metadata(audio, duration_s)[0]


def _afterfire_diagnostic_window_with_metadata(
    audio: np.ndarray, duration_s: float
) -> tuple[np.ndarray, dict[str, object]]:
    """Return an event-aligned window and the exact source slice metadata."""
    array = np.asarray(audio, dtype=np.float64)
    if array.ndim == 1:
        array = array[:, None]
    magnitude = np.max(np.abs(array), axis=1) if array.size else np.zeros(0, dtype=np.float64)
    active = np.flatnonzero(magnitude > 1.0e-12)
    if not active.size:
        window, evidence = _windowed_array(
            array, duration_s, start_s=0.0, event_aligned=False
        )
        evidence.update({
            "source_stems": list(DIAGNOSTIC_SOURCE_STEMS["afterfire"]),
            "diagnostic_key": "afterfire",
            "event_onset_sample": None,
            "event_onset_s": None,
        })
        return window, evidence
    count = max(1, int(round(float(duration_s) * 48_000)))
    lead = min(int(round(0.250 * 48_000)), max(0, count // 4))
    start = max(0, int(active[0]) - lead)
    window, evidence = _windowed_array(
        array, duration_s, start_s=start / SAMPLE_RATE_HZ, event_aligned=True
    )
    evidence.update({
        "source_stems": list(DIAGNOSTIC_SOURCE_STEMS["afterfire"]),
        "diagnostic_key": "afterfire",
        "event_onset_sample": int(active[0]),
        "event_onset_s": float(active[0] / SAMPLE_RATE_HZ),
    })
    return window, evidence


def _stem_sum(stems: Mapping[str, np.ndarray], names: tuple[str, ...]) -> np.ndarray:
    first = np.asarray(stems[names[0]], dtype=np.float64)
    return sum((np.asarray(stems[name], dtype=np.float64) for name in names), np.zeros_like(first))


def _trace_sha256(trace: VehicleStateTrace) -> str:
    payload = json.dumps({
        "time_s": np.asarray(trace.time_s, dtype=np.float64).tolist(),
        "rpm": np.asarray(trace.rpm, dtype=np.float64).tolist(),
        "load": np.asarray(trace.load, dtype=np.float64).tolist(),
        "throttle": np.asarray(trace.throttle, dtype=np.float64).tolist(),
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_audio(value: np.ndarray, label: str) -> None:
    if value.ndim != 2 or value.shape[1] != 2 or value.shape[0] == 0 or not np.all(np.isfinite(value)):
        raise ValueError(f"{label} must be finite stereo audio")


def _validate_sha(value: object, length: int, label: str) -> None:
    if not isinstance(value, str) or len(value) != length or any(ch not in "0123456789abcdefABCDEF" for ch in value):
        raise ValueError(f"{label} must be a hexadecimal SHA")


def _semantic_role(relative: str) -> str:
    if relative in FORMAL_WAV_DESTINATIONS:
        return ("formal_parent", "formal_v8_baseline", "formal_v9_candidate", "formal_v9_comfort")[FORMAL_WAV_DESTINATIONS.index(relative)]
    return ("diagnostic_sc_whine", "diagnostic_hemi_rumble", "diagnostic_sc_hemi_combined", "diagnostic_afterfire")[DIAGNOSTIC_WAV_DESTINATIONS.index(relative)]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256sums(root: Path) -> str:
    excluded = {"SHA256SUMS.txt", ZIP_NAME}
    return "".join(
        f"{_sha256(path)}  {path.relative_to(root).as_posix()}\n"
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name not in excluded
    )


def _write_deterministic_zip(root: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path == zip_path:
                continue
            info = zipfile.ZipInfo(path.relative_to(root).as_posix(), date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)


def _validate_zip_contents(root: Path, zip_path: Path) -> None:
    """Validate the archive while staging, before the atomic directory rename."""
    expected = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != zip_path
    }
    with zipfile.ZipFile(zip_path, "r") as archive:
        if archive.testzip() is not None:
            raise ValueError("deterministic ZIP CRC validation failed")
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)) or set(names) != expected:
            raise ValueError("deterministic ZIP member set validation failed")
        for info in infos:
            member = root / Path(info.filename)
            if not member.is_file() or archive.read(info.filename) != member.read_bytes():
                raise ValueError(f"deterministic ZIP member bytes validation failed: {info.filename}")
            if info.CRC != (binascii.crc32(member.read_bytes()) & 0xFFFFFFFF):
                raise ValueError(f"deterministic ZIP member CRC validation failed: {info.filename}")


def _json_default(value: object) -> object:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


__all__ = (
    "DIAGNOSTIC_DURATIONS_S", "DIAGNOSTIC_WAV_DESTINATIONS", "FORMAL_WAV_DESTINATIONS",
    "PACKAGE_ID", "PACKAGE_SCHEMA", "PRODUCER_SCHEMA", "ProducedStageLRound2Artifacts",
    "WAV_DESTINATIONS", "build_round2_unqualified_diagnostic_package",
    "render_stage_l_round2_named_artifacts", "_write_deterministic_zip",
)
