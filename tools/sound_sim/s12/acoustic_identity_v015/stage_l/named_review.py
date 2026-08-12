"""Content-addressed Stage-L Hellcat unqualified diagnostic package builder."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
from typing import Callable, Mapping
import wave
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
    requested_gain_db: float = 1.9382,
) -> dict[str, object]:
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
        common_gain = 10.0 ** (common_gain_db / 20.0)
        formal_parent = parent_pressure * common_gain
        formal_candidate = candidate_pressure * common_gain
        comfort_gain_db = min(float(requested_gain_db), _headroom_gain_db(_peak(candidate_pressure)))
        formal_comfort = candidate_pressure * (10.0 ** (comfort_gain_db / 20.0))

        audio: dict[str, tuple[np.ndarray, str, float, float]] = {
            WAV_DESTINATIONS[0]: (formal_parent, parent_path, common_gain_db, float(requested_gain_db)),
            WAV_DESTINATIONS[1]: (formal_candidate, candidate_path, common_gain_db, float(requested_gain_db)),
            WAV_DESTINATIONS[2]: (formal_comfort, candidate_path, comfort_gain_db, float(requested_gain_db)),
            WAV_DESTINATIONS[3]: (_stem_sum(candidate_stems, ("sc_intake_radiated",)), candidate_path, 0.0, 0.0),
            WAV_DESTINATIONS[4]: (_stem_sum(candidate_stems, ("sc_casing_radiated",)), candidate_path, 0.0, 0.0),
            WAV_DESTINATIONS[5]: (_stem_sum(candidate_stems, (
                "hemi_exhaust_left", "hemi_exhaust_right", "hemi_blowdown_body",
            )), candidate_path, 0.0, 0.0),
            WAV_DESTINATIONS[6]: (_stem_sum(candidate_stems, (
                "hemi_structure_shock", "hemi_mechanical_torque_ripple",
            )), candidate_path, 0.0, 0.0),
            WAV_DESTINATIONS[7]: (candidate_pressure, candidate_path, 0.0, 0.0),
            WAV_DESTINATIONS[8]: (_window(candidate_pressure, trace, 0.0, 8.0), candidate_path, 0.0, 0.0),
            WAV_DESTINATIONS[9]: (_window(candidate_pressure, trace, 8.0, 20.0), candidate_path, 0.0, 0.0),
            WAV_DESTINATIONS[10]: (_window(candidate_pressure, trace, 20.0, 32.0), candidate_path, 0.0, 0.0),
            WAV_DESTINATIONS[11]: (_window(candidate_pressure, trace, 8.0, 20.0), candidate_path, 0.0, 0.0),
            WAV_DESTINATIONS[12]: (_window(candidate_pressure, trace, 36.0, 48.0), candidate_path, 0.0, 0.0),
        }
        artifacts: dict[str, object] = {}
        for relative in WAV_DESTINATIONS:
            samples, render_path, gain_db, requested_db = audio[relative]
            raw = np.asarray(samples, dtype=np.float64) / (10.0 ** (gain_db / 20.0)) if gain_db != 0.0 else np.asarray(samples, dtype=np.float64)
            if relative not in WAV_DESTINATIONS[:3]:
                gain_db = min(0.0, _headroom_gain_db(_peak(raw)))
                samples = raw * (10.0 ** (gain_db / 20.0))
            destination = root / relative.replace("/", "__")
            _write_pcm24(destination, samples)
            health = _pcm24_health(destination)
            if not health["passes"]:
                raise ValueError(f"produced WAV failed health gate: {relative}")
            raw_loudness = measure_loudness(raw, 48_000)
            final_loudness = measure_loudness(samples, 48_000)
            artifacts[relative] = {
                "kind": "pcm24_wav", "path": str(destination), "sha256": _sha256(destination),
                "requested_gain_db": requested_db, "actual_gain_db": gain_db,
                "headroom_limited": gain_db < requested_db - 1.0e-9,
                "raw_lufs": float(raw_loudness.integrated_lufs),
                "final_lufs": float(final_loudness.integrated_lufs),
                "raw_peak_dbfs": float(raw_loudness.peak_dbfs),
                "final_peak_dbfs": float(final_loudness.peak_dbfs),
                "source_render_path": render_path,
                "profile_binding": {
                    "parent_profile_sha256": parent_profile_sha256.lower(),
                    "candidate_profile_sha256": candidate_profile_sha256.lower(),
                },
                "trace_binding": {"trace_version": trace_version, "trace_sha256": trace_sha},
            }

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
            "parent_peak_dbfs": _linear_db(_peak(formal_parent)),
            "candidate_peak_dbfs": _linear_db(_peak(formal_candidate)),
            "scope": PACKAGE_SCOPE,
        }
        metrics_path.write_text(
            json.dumps(metrics_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n",
        )
        artifacts[METRIC_DESTINATIONS[5]] = _plain_artifact(metrics_path, "json", bindings)
        handoff = {
            "schema_version": "s12-stage-l-named-artifact-input-1",
            "package_id": "s12-stage-l-hellcat-intake-roughness-v1",
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
        return {
            "status": "PARTIAL / AUTOMATED_GATE_FAIL",
            "qualification_status": UNQUALIFIED_DIAGNOSTIC_ONLY,
            "artifact_manifest_path": str(handoff_path),
            "artifact_manifest_sha256": _sha256(handoff_path),
            "artifact_count": len(artifacts),
        }
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise


def _validate_audio(value: np.ndarray, label: str) -> None:
    if value.ndim != 2 or value.shape[1] != 2 or not value.size or not np.all(np.isfinite(value)):
        raise ValueError(f"{label} must be finite non-empty stereo audio")


def _stem_sum(stems: Mapping[str, np.ndarray], names: tuple[str, ...]) -> np.ndarray:
    missing = [name for name in names if name not in stems]
    if missing:
        raise ValueError(f"candidate render is missing diagnostic stems: {missing}")
    return sum((stems[name] for name in names), np.zeros_like(next(iter(stems.values()))))


def _window(audio: np.ndarray, trace: object, start_s: float, end_s: float) -> np.ndarray:
    duration = float(np.asarray(trace.time_s)[-1])
    if duration <= start_s:
        return np.asarray(audio).copy()
    start = int(round(start_s * 48_000))
    end = min(audio.shape[0], int(round(end_s * 48_000)))
    return np.asarray(audio[start:max(start + 1, end)]).copy()


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
    task6_gate_status: Mapping[str, object],
    artifact_manifest_path: str | Path | None = None,
    expected_artifact_manifest_sha256: str | None = None,
    render: bool = True,
) -> dict[str, object]:
    """Copy a hash-bound renderer handoff into a deterministic diagnostic package.

    This function never renders audio.  The producer must supply all WAVs and
    plots through a SHA-bound artifact-input manifest.
    """

    _validate_task6_failure(task6_gate_status)
    root = Path(output_root).resolve()
    status = _status(root)
    if not render:
        return status
    if artifact_manifest_path is None or expected_artifact_manifest_sha256 is None:
        raise ValueError("artifact manifest path and expected SHA256 are required")
    if root.exists():
        raise FileExistsError(f"output root already exists; refusing overwrite: {root}")
    source_manifest = Path(artifact_manifest_path).resolve()
    manifest_sha = _sha256(source_manifest)
    if manifest_sha != expected_artifact_manifest_sha256.lower():
        raise ValueError("artifact input manifest SHA256 mismatch")
    source = json.loads(source_manifest.read_text(encoding="utf-8"))
    if source.get("schema_version") != "s12-stage-l-named-artifact-input-1":
        raise ValueError("unsupported artifact input schema")
    bindings = source.get("bindings")
    artifacts = source.get("artifacts")
    if not isinstance(bindings, dict) or not isinstance(artifacts, dict):
        raise ValueError("artifact input requires bindings and artifacts objects")
    required = set(WAV_DESTINATIONS + METRIC_DESTINATIONS)
    if set(artifacts) != required:
        raise ValueError("artifact input destinations do not match the required package tree")
    _validate_formal_gain(source.get("formal_common_gain"))

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
    return {"sample_rate_hz": rate, "channels": channels, "pcm_bits": 24, "finite": True, "peak_dbfs": peak_dbfs, "clipping_count": clipping, "passes": passes}


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
    "UNQUALIFIED_DIAGNOSTIC_ONLY", "build_unqualified_diagnostic_package",
    "render_stage_l_named_artifacts",
)
