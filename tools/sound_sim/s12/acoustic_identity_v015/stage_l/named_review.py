"""Content-addressed Stage-L Hellcat unqualified diagnostic package builder."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import threading
from types import MappingProxyType
from typing import Callable, Mapping
import wave
import weakref
import zipfile
import zlib

import numpy as np

from .feedback_contract import FEEDBACK_FIELDS
from ..loudness_manager import measure_loudness


PARTIAL = "PARTIAL"
AUTOMATED_GATE_FAIL = "AUTOMATED_GATE_FAIL"
UNQUALIFIED_DIAGNOSTIC_ONLY = "UNQUALIFIED_DIAGNOSTIC_ONLY"
DIAGNOSTIC_FEEDBACK_ALLOWED = "DIAGNOSTIC_FEEDBACK_ALLOWED"
ZIP_NAME = "S12_Stage_L_Hellcat_UNQUALIFIED_DIAGNOSTIC_Review.zip"
PACKAGE_SCOPE = "synthetic; uncalibrated; Hellcat-inspired; vehicle-inspired; not OEM reproduction"
PRODUCER_SCHEMA = "s12-stage-l-named-artifact-producer-2"
PACKAGE_ID = "s12-stage-l-hellcat-intake-roughness-v3"
WAV_DESTINATIONS = (
    "01_Formal_Comparison/01_StageK_Parent_60s.wav",
    "01_Formal_Comparison/02_StageL_Candidate_60s.wav",
    "01_Formal_Comparison/03_StageL_Candidate_Comfort_60s.wav",
    "02_Source_Separation/01_SC_Intake_Aero_Acceleration.wav",
    "02_Source_Separation/02_SC_Gear_Casing_Acceleration.wav",
    "02_Source_Separation/03_HEMI_Exhaust_Body_Acceleration.wav",
    "02_Source_Separation/04_HEMI_Structure_Shock_Acceleration.wav",
    "02_Source_Separation/05_Full_Mix_Acceleration.wav",
    "03_State_Review/01_Idle_12s.wav",
    "03_State_Review/02_Low_Load_12s.wav",
    "03_State_Review/03_High_Load_12s.wav",
    "03_State_Review/04_Shift_12s.wav",
    "03_State_Review/05_Lift_Bypass_12s.wav",
)
METRIC_DESTINATIONS = (
    "04_Metrics/order_map.png",
    "04_Metrics/intake_vs_exhaust_spectrogram.png",
    "04_Metrics/bank_event_timeline.png",
    "04_Metrics/modulation_spectrum.png",
    "04_Metrics/shift_response.png",
    "04_Metrics/stage_l_hellcat_metrics.json",
)


class ProducedStageLArtifacts:
    """Opaque in-process capability issued only by the Stage-L producer."""

    __slots__ = ("_metadata", "__weakref__")

    def __new__(cls, *_args: object, **_kwargs: object) -> "ProducedStageLArtifacts":
        raise TypeError("ProducedStageLArtifacts can only be issued by render_stage_l_named_artifacts")

    def __getitem__(self, key: str) -> object:
        return self._metadata[key]

    def __iter__(self):
        return iter(self._metadata)

    def __len__(self) -> int:
        return len(self._metadata)

    def keys(self):
        return self._metadata.keys()


_TRUSTED_PRODUCER_CAPABILITIES: weakref.WeakKeyDictionary[
    ProducedStageLArtifacts, tuple[Path, str]
] = weakref.WeakKeyDictionary()
_CONSUMED_PRODUCER_CAPABILITIES: weakref.WeakSet[ProducedStageLArtifacts] = weakref.WeakSet()
_PRODUCER_CAPABILITY_LOCK = threading.Lock()


def _issue_produced_artifacts(metadata: Mapping[str, object]) -> ProducedStageLArtifacts:
    handle = object.__new__(ProducedStageLArtifacts)
    handle._metadata = MappingProxyType(dict(metadata))
    manifest_path = Path(str(handle["artifact_manifest_path"])).resolve()
    manifest_sha = str(handle["artifact_manifest_sha256"]).lower()
    _TRUSTED_PRODUCER_CAPABILITIES[handle] = (manifest_path, manifest_sha)
    return handle


def _consume_trusted_producer_manifest(capability: object) -> tuple[Path, str]:
    if not isinstance(capability, ProducedStageLArtifacts):
        raise ValueError("trusted in-process producer capability is required")
    with _PRODUCER_CAPABILITY_LOCK:
        trusted = _TRUSTED_PRODUCER_CAPABILITIES.pop(capability, None)
        if trusted is not None:
            _CONSUMED_PRODUCER_CAPABILITIES.add(capability)
            return trusted
        if capability in _CONSUMED_PRODUCER_CAPABILITIES:
            raise ValueError("trusted capability already consumed")
    raise ValueError("trusted in-process producer capability is required")


def render_stage_l_named_artifacts(
    output_root: str | Path,
    *,
    trace: object,
    parent_renderer: Callable[[object], object],
    candidate_renderer: Callable[[object], object],
    source_commit: str,
    parent_profile_sha256: str,
    candidate_profile_sha256: str,
    trace_version: str,
    candidate_id: str = "hellcat_candidate_v8",
    requested_gain_db: float = 1.9382,
) -> ProducedStageLArtifacts:
    """Produce the hash-bound audio/plot handoff consumed by the package builder.

    The renderers are injected so tests use a short trace while the production
    CLI can pass the exact Stage-K parent and Stage-L candidate paths.  Parent
    and candidate are each invoked once with the identical trace object.
    """
    root = Path(output_root).resolve()
    if root.exists():
        raise FileExistsError(f"artifact output root already exists; refusing overwrite: {root}")
    for label, value in (
        ("parent profile", parent_profile_sha256),
        ("candidate profile", candidate_profile_sha256),
    ):
        _validate_sha_text(value, label)
    if not isinstance(source_commit, str) or len(source_commit) != 40:
        raise ValueError("source_commit must be a full Git SHA")
    if not isinstance(trace_version, str) or not trace_version:
        raise ValueError("trace_version must not be blank")
    trace.validate()
    trace_sha = _trace_sha256(trace)
    bindings = {
        "source_commit": source_commit,
        "candidate_profile_sha256": candidate_profile_sha256.lower(),
        "parent_profile_sha256": parent_profile_sha256.lower(),
        "trace_version": trace_version,
        "trace_sha256": trace_sha,
        "candidate_id": candidate_id,
    }
    root.mkdir(parents=True)
    try:
        parent = parent_renderer(trace).validate()
        parent_path = str(parent.diagnostics.get("render_path", "StageK_parent"))
        parent_pressure = np.asarray(parent.pressure, dtype=np.float64).copy()
        del parent

        candidate = candidate_renderer(trace).validate()
        candidate_path = str(candidate.diagnostics.get("render_path", "StageL_candidate"))
        candidate_pressure = np.asarray(candidate.pressure, dtype=np.float64)
        candidate_stems = {
            str(name): np.asarray(value, dtype=np.float64)
            for name, value in candidate.stems.items()
        }
        _validate_audio(parent_pressure, "parent pressure")
        _validate_audio(candidate_pressure, "candidate pressure")

        common_gain_db = min(
            float(requested_gain_db),
            _headroom_gain_db(max(_peak(parent_pressure), _peak(candidate_pressure))),
        )
        comfort_gain_db = min(float(requested_gain_db), _headroom_gain_db(_peak(candidate_pressure)))
        parent_final_peak_dbfs = _linear_db(_peak(parent_pressure) * (10.0 ** (common_gain_db / 20.0)))
        artifacts: dict[str, object] = {}
        receipt_context = {
            "source_commit": source_commit, "candidate_id": candidate_id,
            "parent_profile_sha256": parent_profile_sha256.lower(),
            "candidate_profile_sha256": candidate_profile_sha256.lower(),
            "trace_version": trace_version, "trace_sha256": trace_sha,
        }
        formal_specs = (
            (WAV_DESTINATIONS[0], parent_pressure, parent_path, common_gain_db),
            (WAV_DESTINATIONS[1], candidate_pressure, candidate_path, common_gain_db),
            (WAV_DESTINATIONS[2], candidate_pressure, candidate_path, comfort_gain_db),
        )
        for relative, raw, render_path, gain_db in formal_specs:
            artifacts[relative] = _emit_wav_artifact(
                root, relative, raw, render_path, float(requested_gain_db), gain_db,
                {"state_kind": "formal"}, receipt_context,
            )
        del formal_specs
        del parent_pressure

        acceleration_specs = (
            (WAV_DESTINATIONS[3], ("sc_intake_radiated",)),
            (WAV_DESTINATIONS[4], ("sc_casing_radiated",)),
            (WAV_DESTINATIONS[5], ("hemi_exhaust_left", "hemi_exhaust_right", "hemi_blowdown_body")),
            (WAV_DESTINATIONS[6], ("hemi_structure_shock", "hemi_mechanical_torque_ripple")),
        )
        acceleration_evidence = {"state_kind": "acceleration", "shift_count": 3, "bypass_event_count": 0}
        for relative, stems in acceleration_specs:
            raw = _window(_stem_sum(candidate_stems, stems), trace, 8.0, 26.0)
            gain_db = min(0.0, _headroom_gain_db(_peak(raw)))
            artifacts[relative] = _emit_wav_artifact(
                root, relative, raw, candidate_path, 0.0, gain_db,
                acceleration_evidence, receipt_context,
            )
            del raw
        raw = _window(candidate_pressure, trace, 8.0, 26.0)
        gain_db = min(0.0, _headroom_gain_db(_peak(raw)))
        artifacts[WAV_DESTINATIONS[7]] = _emit_wav_artifact(
            root, WAV_DESTINATIONS[7], raw, candidate_path, 0.0, gain_db,
            acceleration_evidence, receipt_context,
        )
        del raw

        for relative, state_kind in zip(WAV_DESTINATIONS[8:], ("idle", "low_load", "high_load", "shift", "lift_bypass")):
            scenario_trace, evidence = _state_scenario_trace(trace, state_kind)
            scenario = candidate_renderer(scenario_trace).validate()
            scenario_path = str(scenario.diagnostics.get("render_path", "StageL_candidate"))
            raw = _exact_duration(np.asarray(scenario.pressure, dtype=np.float64), 12.0)
            gain_db = min(0.0, _headroom_gain_db(_peak(raw)))
            artifacts[relative] = _emit_wav_artifact(
                root, relative, raw, scenario_path, 0.0, gain_db, evidence, receipt_context,
            )
            del raw, scenario, scenario_trace

        plot_inputs = _plot_inputs(candidate_pressure, candidate_stems)
        for relative, image in zip(METRIC_DESTINATIONS[:5], plot_inputs):
            destination = root / relative.replace("/", "__")
            _write_png(destination, image)
            artifacts[relative] = _plain_artifact(destination, "png", bindings)
        metrics_path = root / METRIC_DESTINATIONS[5].replace("/", "__")
        metrics_payload = {
            "schema_version": "s12-stage-l-named-diagnostic-metrics-1",
            "status": "PARTIAL / AUTOMATED_GATE_FAIL",
            "qualification_status": UNQUALIFIED_DIAGNOSTIC_ONLY,
            "source_paths": {"parent": parent_path, "candidate": candidate_path},
            "trace_binding": {"trace_version": trace_version, "trace_sha256": trace_sha},
            "formal_common_gain_db": common_gain_db,
            "parent_peak_dbfs": parent_final_peak_dbfs,
            "candidate_peak_dbfs": _linear_db(_peak(candidate_pressure) * (10.0 ** (common_gain_db / 20.0))),
            "scope": PACKAGE_SCOPE,
        }
        metrics_path.write_text(
            json.dumps(metrics_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n",
        )
        artifacts[METRIC_DESTINATIONS[5]] = _plain_artifact(metrics_path, "json", bindings)
        handoff = {
            "schema_version": PRODUCER_SCHEMA,
            "package_id": PACKAGE_ID,
            "status": "PARTIAL / AUTOMATED_GATE_FAIL",
            "qualification_status": UNQUALIFIED_DIAGNOSTIC_ONLY,
            "bindings": bindings,
            "formal_common_gain": {
                "requested_gain_db": float(requested_gain_db), "actual_gain_db": common_gain_db,
                "headroom_limited": common_gain_db < float(requested_gain_db) - 1.0e-9,
                "compressor": False, "limiter": False, "eq": False, "per_section_agc": False,
            },
            "artifacts": artifacts,
        }
        handoff_path = root / "stage_l_named_artifacts.json"
        handoff_path.write_text(
            json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n",
        )
        return _issue_produced_artifacts({
            "status": "PARTIAL / AUTOMATED_GATE_FAIL",
            "qualification_status": UNQUALIFIED_DIAGNOSTIC_ONLY,
            "artifact_manifest_path": str(handoff_path),
            "artifact_manifest_sha256": _sha256(handoff_path),
            "artifact_count": len(artifacts),
        })
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise


def _emit_wav_artifact(
    root: Path,
    relative: str,
    raw_audio: np.ndarray,
    render_path: str,
    requested_gain_db: float,
    actual_gain_db: float,
    event_evidence: Mapping[str, object],
    receipt_context: Mapping[str, str],
) -> dict[str, object]:
    """Write and measure one WAV before the caller releases its render arrays."""
    raw = np.asarray(raw_audio, dtype=np.float64)
    final = raw * (10.0 ** (actual_gain_db / 20.0))
    destination = root / relative.replace("/", "__")
    _write_pcm24(destination, final)
    health = _pcm24_health(destination)
    if not health["passes"]:
        raise ValueError(f"produced WAV failed health gate: {relative}")
    raw_loudness = measure_loudness(raw, 48_000)
    raw_lufs = float(raw_loudness.integrated_lufs)
    raw_peak_dbfs = float(raw_loudness.peak_dbfs)
    final_lufs = raw_lufs + actual_gain_db if math.isfinite(raw_lufs) else raw_lufs
    final_peak_dbfs = raw_peak_dbfs + actual_gain_db if math.isfinite(raw_peak_dbfs) else raw_peak_dbfs
    pcm_sha = _sha256(destination)
    receipt = {
        "schema_version": PRODUCER_SCHEMA,
        "package_id": PACKAGE_ID,
        "status": "PARTIAL / AUTOMATED_GATE_FAIL",
        "file_id": relative,
        "semantic_role": _semantic_role(relative),
        "frame_count": health["frame_count"],
        "duration_s": health["duration_s"],
        "window": _semantic_window(relative),
        "source_stems": list(_source_stems(relative)),
        **receipt_context,
        "source_render_path": render_path,
        "pcm_sha256": pcm_sha,
        "event_evidence": dict(event_evidence),
    }
    return {
        "kind": "pcm24_wav", "path": str(destination), "sha256": pcm_sha,
        "pcm_sha256": pcm_sha, "producer_receipt": receipt,
        "requested_gain_db": requested_gain_db, "actual_gain_db": actual_gain_db,
        "headroom_limited": actual_gain_db < requested_gain_db - 1.0e-9,
        "raw_lufs": raw_lufs,
        "final_lufs": final_lufs,
        "raw_peak_dbfs": raw_peak_dbfs,
        "final_peak_dbfs": final_peak_dbfs,
        "source_render_path": render_path,
        "profile_binding": {
            "parent_profile_sha256": receipt_context["parent_profile_sha256"],
            "candidate_profile_sha256": receipt_context["candidate_profile_sha256"],
        },
        "trace_binding": {
            "trace_version": receipt_context["trace_version"],
            "trace_sha256": receipt_context["trace_sha256"],
        },
    }


def _validate_audio(value: np.ndarray, label: str) -> None:
    if value.ndim != 2 or value.shape[1] != 2 or not value.size or not np.all(np.isfinite(value)):
        raise ValueError(f"{label} must be finite non-empty stereo audio")


def _stem_sum(stems: Mapping[str, np.ndarray], names: tuple[str, ...]) -> np.ndarray:
    missing = [name for name in names if name not in stems]
    if missing:
        raise ValueError(f"candidate render is missing diagnostic stems: {missing}")
    return sum((stems[name] for name in names), np.zeros_like(next(iter(stems.values()))))


def _window(audio: np.ndarray, trace: object, start_s: float, end_s: float) -> np.ndarray:
    target = int(round((end_s - start_s) * 48_000))
    start = int(round(start_s * 48_000))
    end = start + target
    values = np.asarray(audio)
    if values.shape[0] >= end:
        return values[start:end].copy()
    if not values.shape[0]:
        raise ValueError("cannot construct semantic window from empty audio")
    repeats = int(math.ceil(target / values.shape[0]))
    return np.tile(values, (repeats, 1))[:target].copy()


def _exact_duration(audio: np.ndarray, duration_s: float) -> np.ndarray:
    target = int(round(duration_s * 48_000))
    values = np.asarray(audio)
    if values.shape[0] >= target:
        return values[:target].copy()
    repeats = int(math.ceil(target / values.shape[0]))
    return np.tile(values, (repeats, 1))[:target].copy()


def _state_scenario_trace(template: object, state_kind: str) -> tuple[object, dict[str, object]]:
    time_s = np.linspace(0.0, 12.0, 1201, dtype=np.float64)
    if state_kind == "idle":
        rpm = 760.0 + 18.0 * np.sin(2.0 * np.pi * time_s / 3.0)
        load = np.full_like(time_s, 0.12); throttle = np.full_like(time_s, 0.08)
        shifts, bypasses = 0, 0
    elif state_kind == "low_load":
        rpm = 1250.0 + 850.0 * time_s / 12.0
        load = np.full_like(time_s, 0.32); throttle = np.full_like(time_s, 0.28)
        shifts, bypasses = 0, 0
    elif state_kind == "high_load":
        rpm = 2400.0 + 3000.0 * time_s / 12.0
        load = np.full_like(time_s, 0.90); throttle = np.full_like(time_s, 0.95)
        shifts, bypasses = 0, 0
    elif state_kind == "shift":
        phase = np.mod(time_s, 3.0) / 3.0
        rpm = 2600.0 + 2500.0 * phase
        load = np.full_like(time_s, 0.88); throttle = np.full_like(time_s, 0.93)
        for event_s in (3.0, 6.0, 9.0):
            throttle[np.abs(time_s - event_s) <= 0.10] = 0.18
        shifts, bypasses = 3, 0
    elif state_kind == "lift_bypass":
        rpm = np.where(time_s < 5.0, 4800.0 + 80.0 * time_s, 5200.0 - 260.0 * (time_s - 5.0))
        load = np.where(time_s < 5.0, 0.92, 0.08)
        throttle = np.where(time_s < 5.0, 0.96, 0.02)
        shifts, bypasses = 0, 1
    else:
        raise ValueError(f"unknown state scenario: {state_kind}")
    trace = template.__class__(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)).validate()
    evidence = {
        "state_kind": state_kind, "shift_count": shifts, "bypass_event_count": bypasses,
        "load_min": float(np.min(load)), "load_max": float(np.max(load)),
        "throttle_min": float(np.min(throttle)), "throttle_max": float(np.max(throttle)),
    }
    return trace, evidence


def _headroom_gain_db(peak: float) -> float:
    return -1.5 - _linear_db(peak)


def _peak(audio: np.ndarray) -> float:
    return float(np.max(np.abs(audio))) if audio.size else 0.0


def _linear_db(value: float) -> float:
    return float(20.0 * math.log10(max(float(value), 1.0e-30)))


def _write_pcm24(path: Path, audio: np.ndarray) -> None:
    _validate_audio(np.asarray(audio), str(path))
    pcm = np.clip(np.rint(np.asarray(audio, dtype=np.float64) * 8388607.0), -8388608, 8388607).astype("<i4")
    packed = pcm.reshape(-1).view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(3)
        stream.setframerate(48_000)
        stream.writeframes(packed)


def _trace_sha256(trace: object) -> str:
    digest = hashlib.sha256()
    for name in ("time_s", "rpm", "load", "throttle", "acceleration_mps2"):
        values = np.ascontiguousarray(np.asarray(getattr(trace, name), dtype="<f8"))
        digest.update(name.encode("ascii") + b"\0" + values.tobytes())
    return digest.hexdigest()


def _plot_inputs(pressure: np.ndarray, stems: Mapping[str, np.ndarray]) -> tuple[np.ndarray, ...]:
    mono = np.mean(pressure, axis=1)
    spectrum = np.abs(np.fft.rfft(mono))
    intake = np.mean(stems["sc_intake_radiated"], axis=1)
    exhaust = np.mean(stems["hemi_exhaust_left"] + stems["hemi_exhaust_right"], axis=1)
    structure = np.mean(stems["hemi_structure_shock"], axis=1)
    shift = np.mean(stems["hellcat_shift_reengagement"], axis=1)
    return (
        _vector_image(spectrum),
        _vector_image(np.abs(np.fft.rfft(intake)) + np.abs(np.fft.rfft(exhaust))),
        _vector_image(np.abs(exhaust)),
        _vector_image(np.abs(np.fft.rfft(structure))),
        _vector_image(np.abs(shift)),
    )


def _vector_image(values: np.ndarray, width: int = 96, height: int = 48) -> np.ndarray:
    source = np.asarray(values, dtype=np.float64).reshape(-1)
    sample = np.interp(np.linspace(0, max(source.size - 1, 0), width), np.arange(source.size), source)
    normalized = sample / max(float(np.max(sample)), 1.0e-30)
    image = np.zeros((height, width), dtype=np.uint8)
    for column, value in enumerate(normalized):
        rows = max(1, int(round(value * (height - 1))))
        image[height - rows :, column] = np.linspace(80, 255, rows, dtype=np.uint8)
    return image


def _write_png(path: Path, image: np.ndarray) -> None:
    pixels = np.asarray(image, dtype=np.uint8)
    height, width = pixels.shape
    raw = b"".join(b"\x00" + pixels[row].tobytes() for row in range(height))
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def _plain_artifact(path: Path, kind: str, bindings: Mapping[str, object]) -> dict[str, object]:
    return {
        "kind": kind, "path": str(path), "sha256": _sha256(path),
        "profile_binding": {
            "parent_profile_sha256": bindings["parent_profile_sha256"],
            "candidate_profile_sha256": bindings["candidate_profile_sha256"],
        },
        "trace_binding": {
            "trace_version": bindings["trace_version"], "trace_sha256": bindings["trace_sha256"],
        },
    }


def _validate_sha_text(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value.lower()):
        raise ValueError(f"{label} SHA-256 is invalid")
    return value.lower()


def build_unqualified_diagnostic_package(
    output_root: str | Path,
    *,
    produced_artifacts: ProducedStageLArtifacts | None,
    task6_gate_status: Mapping[str, object],
    render: bool = True,
) -> dict[str, object]:
    """Package a handoff authenticated by an in-process producer capability.

    This function never renders audio.  The producer must supply all WAVs and
    plots through the opaque handle returned by ``render_stage_l_named_artifacts``.
    """

    _validate_task6_failure(task6_gate_status)
    root = Path(output_root).resolve()
    status = _status(root)
    if not render:
        return status
    source_manifest, expected_artifact_manifest_sha256 = _consume_trusted_producer_manifest(produced_artifacts)
    if root.exists():
        raise FileExistsError(f"output root already exists; refusing overwrite: {root}")
    manifest_sha = _sha256(source_manifest)
    if manifest_sha != expected_artifact_manifest_sha256:
        raise ValueError("artifact input manifest SHA256 mismatch")
    source = json.loads(source_manifest.read_text(encoding="utf-8"))
    if source.get("schema_version") != PRODUCER_SCHEMA:
        raise ValueError("unsupported producer artifact input schema")
    if source.get("package_id") != PACKAGE_ID or source.get("status") != "PARTIAL / AUTOMATED_GATE_FAIL":
        raise ValueError("producer package identity or status is invalid")
    bindings = source.get("bindings")
    artifacts = source.get("artifacts")
    if not isinstance(bindings, dict) or not isinstance(artifacts, dict):
        raise ValueError("artifact input requires bindings and artifacts objects")
    required = set(WAV_DESTINATIONS + METRIC_DESTINATIONS)
    if set(artifacts) != required:
        raise ValueError("artifact input destinations do not match the required package tree")
    _validate_formal_gain(source.get("formal_common_gain"))
    _validate_producer_handoff(source)

    root.mkdir(parents=True)
    copied: list[dict[str, object]] = []
    wav_evidence: list[dict[str, object]] = []
    try:
        for relative in sorted(required):
            record = artifacts[relative]
            if not isinstance(record, dict):
                raise ValueError(f"artifact record must be an object: {relative}")
            source_path = Path(str(record.get("path", ""))).resolve()
            expected_sha = str(record.get("sha256", "")).lower()
            if not source_path.is_file() or len(expected_sha) != 64 or _sha256(source_path) != expected_sha:
                raise ValueError(f"artifact SHA256 binding failed: {relative}")
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, destination)
            output_sha = _sha256(destination)
            item: dict[str, object] = {
                "path": relative,
                "sha256": output_sha,
                "kind": record.get("kind"),
                "source_binding": dict(bindings),
                "profile_binding": {
                    "candidate_profile_sha256": bindings.get("candidate_profile_sha256"),
                    "parent_profile_sha256": bindings.get("parent_profile_sha256"),
                },
                "trace_binding": {
                    "trace_version": bindings.get("trace_version"),
                    "trace_sha256": bindings.get("trace_sha256"),
                },
            }
            if relative in WAV_DESTINATIONS:
                health = _pcm24_health(destination)
                if not health["passes"]:
                    raise ValueError(f"PCM24 health gate failed: {relative}")
                receipt = record["producer_receipt"]
                if (
                    receipt["frame_count"] != health["frame_count"]
                    or abs(float(receipt["duration_s"]) - float(health["duration_s"])) > 1.0 / 48_000
                ):
                    raise ValueError(f"producer receipt frame count or duration mismatch: {relative}")
                for field in (
                    "requested_gain_db", "actual_gain_db", "headroom_limited",
                    "raw_lufs", "final_lufs", "raw_peak_dbfs", "final_peak_dbfs",
                ):
                    if field not in record:
                        raise ValueError(f"WAV artifact missing {field}: {relative}")
                    item[field] = record[field]
                item["pcm_sha256"] = output_sha
                item["pcm_health"] = health
                wav_evidence.append(item)
            elif relative.endswith(".png"):
                if destination.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
                    raise ValueError(f"invalid PNG signature: {relative}")
            else:
                json.loads(destination.read_text(encoding="utf-8"))
            copied.append(item)

        feedback_path = root / "05_Feedback/Jovi_Stage_L_Hellcat_Feedback.csv"
        _write_blank_feedback(feedback_path, str(source.get("package_id", "")))
        manifest = {
            **{key: value for key, value in status.items() if key != "output_root"},
            "schema_version": "s12-stage-l-unqualified-diagnostic-package-1",
            "package_id": source.get("package_id"),
            "status": "PARTIAL / AUTOMATED_GATE_FAIL",
            "scope": PACKAGE_SCOPE,
            "artifact_input_sha256": manifest_sha,
            "full_pipeline_peak_residency": 5,
            "formal_final_provenance": "NOT_AVAILABLE",
            "qualified_for_profile_freeze": False,
            "formal_common_gain": source["formal_common_gain"],
            "timeline": "0-8 idle; 8-26 acceleration + 3 shifts; 26-36 full pull; 36-46 lift/afterfire/bypass; 46-52 coast; 52-60 idle return",
            "artifacts": copied,
            "wav_artifacts": wav_evidence,
        }
        (root / "artifact_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n",
        )
        (root / "00_OPEN_ME_FIRST.md").write_text(_readme(), encoding="utf-8", newline="\n")
        (root / "SHA256SUMS.txt").write_text(_sha256sums(root), encoding="utf-8", newline="\n")
        zip_path = root / ZIP_NAME
        _write_deterministic_zip(root, zip_path)
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    return {**manifest, "output_root": str(root), "zip_path": str(zip_path)}


def _validate_task6_failure(status: Mapping[str, object]) -> None:
    if status.get("residency_max") != 5:
        raise ValueError("Task6 residency_max must be the observed value 5")
    if status.get("formal_final_provenance") != "NOT_AVAILABLE":
        raise ValueError("Task6 formal final provenance must be NOT_AVAILABLE")


def _status(root: Path) -> dict[str, object]:
    return {
        "package_status": PARTIAL,
        "gate_status": AUTOMATED_GATE_FAIL,
        "qualification_status": UNQUALIFIED_DIAGNOSTIC_ONLY,
        "feedback_status": DIAGNOSTIC_FEEDBACK_ALLOWED,
        "human_feedback_present": False,
        "output_root": str(root),
    }


def _validate_formal_gain(value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError("formal_common_gain must be an object")
    required = {"requested_gain_db", "actual_gain_db", "headroom_limited", "compressor", "limiter", "eq", "per_section_agc"}
    if set(value) != required:
        raise ValueError("formal_common_gain fields do not match the contract")
    if any(value[name] is not False for name in ("compressor", "limiter", "eq", "per_section_agc")):
        raise ValueError("formal comparison may not use compressor, limiter, EQ, or per-section AGC")


def _pcm24_health(path: Path) -> dict[str, object]:
    with wave.open(str(path), "rb") as stream:
        channels, width, rate = stream.getnchannels(), stream.getsampwidth(), stream.getframerate()
        frames = stream.getnframes()
        payload = stream.readframes(frames)
    valid_format = (rate, channels, width) == (48_000, 2, 3) and frames > 0
    if not valid_format or len(payload) != frames * channels * width:
        return {"sample_rate_hz": rate, "channels": channels, "pcm_bits": width * 8, "finite": False, "peak_dbfs": float("inf"), "clipping_count": -1, "passes": False}
    raw = np.frombuffer(payload, dtype=np.uint8).reshape(-1, 3)
    values = raw[:, 0].astype(np.int32) | (raw[:, 1].astype(np.int32) << 8) | (raw[:, 2].astype(np.int32) << 16)
    values = np.where(values & 0x800000, values - 0x1000000, values).astype(np.float64) / 8388608.0
    peak = float(np.max(np.abs(values))) if values.size else 0.0
    peak_dbfs = float(20.0 * np.log10(max(peak, 1.0e-30)))
    clipping = int(np.count_nonzero(np.abs(values) >= 1.0))
    passes = bool(np.all(np.isfinite(values)) and peak_dbfs <= -1.5 + 1.0e-6 and clipping == 0)
    return {"sample_rate_hz": rate, "channels": channels, "pcm_bits": 24, "frame_count": frames, "duration_s": frames / rate, "finite": True, "peak_dbfs": peak_dbfs, "clipping_count": clipping, "passes": passes}


def _semantic_role(relative: str) -> str:
    roles = (
        "formal_parent", "formal_candidate", "formal_candidate_comfort",
        "source_sc_intake_aero", "source_sc_gear_casing", "source_hemi_exhaust_body",
        "source_hemi_structure_shock", "source_full_mix", "state_idle", "state_low_load",
        "state_high_load", "state_shift", "state_lift_bypass",
    )
    return roles[WAV_DESTINATIONS.index(relative)]


def _semantic_window(relative: str) -> dict[str, float]:
    if relative in WAV_DESTINATIONS[:3]:
        return {"start_s": 0.0, "end_s": 60.0}
    if relative in WAV_DESTINATIONS[3:8]:
        return {"start_s": 8.0, "end_s": 26.0}
    return {"start_s": 0.0, "end_s": 12.0}


def _source_stems(relative: str) -> tuple[str, ...]:
    mapping = {
        WAV_DESTINATIONS[0]: ("stage_k_parent_pressure",),
        WAV_DESTINATIONS[1]: ("stage_l_candidate_pressure",),
        WAV_DESTINATIONS[2]: ("stage_l_candidate_pressure",),
        WAV_DESTINATIONS[3]: ("sc_intake_radiated",),
        WAV_DESTINATIONS[4]: ("sc_casing_radiated",),
        WAV_DESTINATIONS[5]: ("hemi_exhaust_left", "hemi_exhaust_right", "hemi_blowdown_body"),
        WAV_DESTINATIONS[6]: ("hemi_structure_shock", "hemi_mechanical_torque_ripple"),
        WAV_DESTINATIONS[7]: ("stage_l_candidate_pressure",),
    }
    return mapping.get(relative, ("stage_l_semantic_scenario_pressure",))


def _validate_producer_handoff(source: Mapping[str, object]) -> None:
    bindings = source["bindings"]
    required_bindings = {
        "source_commit", "candidate_profile_sha256", "parent_profile_sha256",
        "trace_version", "trace_sha256", "candidate_id",
    }
    if set(bindings) != required_bindings:
        raise ValueError("producer bindings do not match the exact schema")
    seen_pcm: dict[str, str] = {}
    for relative in WAV_DESTINATIONS:
        record = source["artifacts"][relative]
        receipt = record.get("producer_receipt") if isinstance(record, dict) else None
        if not isinstance(receipt, dict):
            raise ValueError(f"producer receipt is required: {relative}")
        expected = {
            "schema_version": PRODUCER_SCHEMA,
            "package_id": PACKAGE_ID,
            "status": source["status"],
            "file_id": relative,
            "semantic_role": _semantic_role(relative),
            "frame_count": receipt.get("frame_count"),
            "duration_s": receipt.get("duration_s"),
            "window": _semantic_window(relative),
            "source_stems": list(_source_stems(relative)),
            "source_commit": bindings["source_commit"],
            "candidate_id": bindings["candidate_id"],
            "parent_profile_sha256": bindings["parent_profile_sha256"],
            "candidate_profile_sha256": bindings["candidate_profile_sha256"],
            "trace_version": bindings["trace_version"],
            "trace_sha256": bindings["trace_sha256"],
            "source_render_path": record.get("source_render_path"),
            "pcm_sha256": record.get("sha256"),
            "event_evidence": receipt.get("event_evidence"),
        }
        if receipt != expected or record.get("pcm_sha256") != record.get("sha256"):
            raise ValueError(f"producer receipt binding mismatch: {relative}")
        if not isinstance(receipt["frame_count"], int) or receipt["frame_count"] <= 0:
            raise ValueError(f"producer frame count is invalid: {relative}")
        _validate_event_evidence(relative, receipt["event_evidence"])
        pcm = str(record["sha256"])
        previous = seen_pcm.get(pcm)
        if previous is not None:
            allowed = {previous, relative} == {WAV_DESTINATIONS[1], WAV_DESTINATIONS[2]}
            if not allowed:
                raise ValueError(f"producer semantic roles may not share identical PCM: {previous}, {relative}")
            if source["artifacts"][previous]["actual_gain_db"] != record["actual_gain_db"]:
                raise ValueError("candidate/comfort identical PCM requires identical actual gain")
        seen_pcm[pcm] = relative


def _validate_event_evidence(relative: str, value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"producer event evidence is required: {relative}")
    role = _semantic_role(relative)
    if role.startswith("formal_"):
        if value.get("state_kind") != "formal":
            raise ValueError(f"formal producer event evidence mismatch: {relative}")
        return
    if role.startswith("source_"):
        if value.get("state_kind") != "acceleration" or value.get("shift_count") != 3:
            raise ValueError(f"acceleration producer event evidence mismatch: {relative}")
        return
    expected_kind = role.removeprefix("state_")
    if value.get("state_kind") != expected_kind:
        raise ValueError(f"state producer event evidence mismatch: {relative}")
    shifts = value.get("shift_count")
    bypasses = value.get("bypass_event_count")
    load_min, load_max = value.get("load_min"), value.get("load_max")
    throttle_min, throttle_max = value.get("throttle_min"), value.get("throttle_max")
    if not all(isinstance(item, (int, float)) for item in (load_min, load_max, throttle_min, throttle_max)):
        raise ValueError(f"state load/throttle evidence is incomplete: {relative}")
    valid = {
        "idle": shifts == 0 and bypasses == 0 and load_max <= 0.20 and throttle_max <= 0.15,
        "low_load": shifts == 0 and bypasses == 0 and 0.20 <= load_min <= load_max <= 0.50,
        "high_load": shifts == 0 and bypasses == 0 and load_min >= 0.75 and throttle_min >= 0.75,
        "shift": shifts == 3 and bypasses == 0 and throttle_min < 0.30 and throttle_max > 0.80,
        "lift_bypass": shifts == 0 and bypasses >= 1 and load_min < 0.15 and load_max > 0.80 and throttle_min < 0.05,
    }[expected_kind]
    if not valid:
        raise ValueError(f"state semantic conditions are not proven: {relative}")


def _write_blank_feedback(path: Path, package_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FEEDBACK_FIELDS, lineterminator="\n")
        writer.writeheader()
        for relative in WAV_DESTINATIONS:
            row = {field: "" for field in FEEDBACK_FIELDS}
            row.update({"package_id": package_id, "file_id": relative, "vehicle_id": "hellcat_inspired"})
            writer.writerow(row)


def _readme() -> str:
    return "\n".join((
        "# S12 Stage L Hellcat UNQUALIFIED DIAGNOSTIC Named Review", "",
        "Status: `PARTIAL / AUTOMATED_GATE_FAIL`.",
        "Qualification: `UNQUALIFIED_DIAGNOSTIC_ONLY`.",
        "Feedback: `DIAGNOSTIC_FEEDBACK_ALLOWED`.", "",
        "Task 6 observed full-render residency 5 and formal final provenance NOT_AVAILABLE.",
        "This package cannot qualify or freeze a profile and contains no submitted human result.",
        "All audio is synthetic, uncalibrated, Hellcat-inspired, vehicle-inspired, and not an OEM reproduction.",
        "Formal parent and candidate use one common static headroom-safe gain with no compressor, limiter, EQ, or per-section AGC.", "",
    ))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256sums(root: Path) -> str:
    excluded = {"SHA256SUMS.txt", ZIP_NAME}
    return "".join(
        f"{_sha256(path)}  {path.relative_to(root).as_posix()}\n"
        for path in sorted(root.rglob("*")) if path.is_file() and path.name not in excluded
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


__all__ = (
    "AUTOMATED_GATE_FAIL", "DIAGNOSTIC_FEEDBACK_ALLOWED", "PARTIAL",
    "ProducedStageLArtifacts", "UNQUALIFIED_DIAGNOSTIC_ONLY", "build_unqualified_diagnostic_package",
    "render_stage_l_named_artifacts",
)
