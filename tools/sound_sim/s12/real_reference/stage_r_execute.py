"""Fail-closed Stage-R execution entry points for qualified references.

R2 can produce only relative digital-domain evidence.  R1 produces an
execution plan for the already-validated MATLAB/Stage-N toolchain and refuses
to run if the synchronized state contract is incomplete.  Neither path
creates tuning recommendations or profile changes by itself.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from tools.sound_sim.s12.acoustic_comparator.core import ComparisonCase

from .limited import compare_r2_signals
from .qualification import ReferenceQualificationError, require_r1_reference, qualify_r2_reference


MATLAB_R1_FUNCTIONS = (
    "rpmordermap",
    "ordertrack",
    "orderspectrum",
    "rpmfreqmap",
    "acousticLoudness",
    "acousticSharpness",
    "acousticRoughness",
    "acousticFluctuation",
    "acousticToneToNoiseRatio",
    "acousticProminenceRatio",
)
R1_INPUT_SCHEMA_VERSION = "s12-stage-r1-matlab-inputs-v1"


class StageRExecutionContractError(ValueError):
    """Raised when a Stage-R execution input is incomplete or unsafe."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_unaltered_pcm_wav(path: Path) -> tuple[np.ndarray, int, dict[str, Any]]:
    """Read PCM WAV without gain/EQ/AGC and fold channels only in the comparator."""

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"WAV file not found: {path}")
    with wave.open(str(path), "rb") as stream:
        channels = stream.getnchannels()
        width = stream.getsampwidth()
        sample_rate_hz = stream.getframerate()
        frames = stream.getnframes()
        if stream.getcomptype() != "NONE":
            raise StageRExecutionContractError("compressed WAV is not allowed for analysis")
        raw = stream.readframes(frames)
    if channels < 1 or width not in {1, 2, 3, 4} or sample_rate_hz <= 0:
        raise StageRExecutionContractError("unsupported PCM WAV layout")
    expected_bytes = frames * channels * width
    if len(raw) != expected_bytes:
        raise StageRExecutionContractError(
            f"PCM WAV frame data is truncated: expected={expected_bytes}, actual={len(raw)}"
        )
    values = np.frombuffer(raw, dtype=np.uint8)
    if width == 1:
        decoded = (values.astype(np.float64) - 128.0) / 128.0
    elif width == 2:
        decoded = np.frombuffer(raw, dtype="<i2").astype(np.float64) / (1 << 15)
    elif width == 3:
        packed = values.reshape(-1, 3)
        decoded = packed[:, 0].astype(np.int32) | (packed[:, 1].astype(np.int32) << 8) | (packed[:, 2].astype(np.int32) << 16)
        decoded = np.where(decoded & 0x800000, decoded - (1 << 24), decoded).astype(np.float64) / (1 << 23)
    else:
        decoded = np.frombuffer(raw, dtype="<i4").astype(np.float64) / (1 << 31)
    signal = decoded.reshape(-1, channels)
    if signal.size == 0 or not np.isfinite(signal).all():
        raise StageRExecutionContractError("PCM WAV is empty or non-finite")
    return signal, sample_rate_hz, {
        "channels": channels,
        "sample_width_bits": width * 8,
        "sample_rate_hz": sample_rate_hz,
        "frames": int(frames),
        "sha256": _sha256(path),
    }


def _read_unaltered_pcm_flac(path: Path) -> tuple[np.ndarray, int, dict[str, Any]]:
    """Decode a lossless FLAC source for analysis without changing its rate."""

    ffprobe = shutil.which("ffprobe")
    ffmpeg = shutil.which("ffmpeg")
    if not ffprobe or not ffmpeg:
        raise StageRExecutionContractError("ffmpeg and ffprobe are required for FLAC R1 input")
    probe = subprocess.run(
        [ffprobe, "-v", "error", "-show_streams", "-of", "json", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        raise StageRExecutionContractError(f"ffprobe cannot read FLAC source: {path}")
    try:
        streams = json.loads(probe.stdout).get("streams", [])
        stream = next(row for row in streams if row.get("codec_type") == "audio")
        codec = str(stream.get("codec_name") or "").lower()
        sample_rate_hz = int(stream["sample_rate"])
        channels = int(stream["channels"])
    except (KeyError, TypeError, ValueError, StopIteration, json.JSONDecodeError) as exc:
        raise StageRExecutionContractError(f"FLAC source has incomplete audio metadata: {path}") from exc
    if codec != "flac" or sample_rate_hz <= 0 or channels <= 0:
        raise StageRExecutionContractError(f"unsupported FLAC source metadata: {path}")
    decoded = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(path), "-map", "0:a:0", "-f", "f32le", "-acodec", "pcm_f32le", "pipe:1"],
        check=False,
        capture_output=True,
    )
    if decoded.returncode != 0:
        detail = decoded.stderr.decode("utf-8", errors="replace").strip()[:300]
        raise StageRExecutionContractError(f"ffmpeg cannot decode FLAC source: {path}: {detail}")
    raw = decoded.stdout
    if not raw or len(raw) % (4 * channels) != 0:
        raise StageRExecutionContractError(f"decoded FLAC frame data is truncated: {path}")
    signal = np.frombuffer(raw, dtype="<f4").astype(np.float64).reshape(-1, channels)
    if signal.size == 0 or not np.isfinite(signal).all():
        raise StageRExecutionContractError("decoded FLAC is empty or non-finite")
    return signal, sample_rate_hz, {
        "channels": channels,
        "sample_width_bits": None,
        "sample_rate_hz": sample_rate_hz,
        "frames": int(signal.shape[0]),
        "sha256": _sha256(path),
        "container": "FLAC",
        "decoded_format": "pcm_f32le_without_resampling",
    }


def read_unaltered_pcm_audio(path: Path) -> tuple[np.ndarray, int, dict[str, Any]]:
    """Read a qualified lossless WAV/FLAC source without gain, EQ, or resampling."""

    path = Path(path)
    if path.suffix.lower() == ".wav":
        return read_unaltered_pcm_wav(path)
    if path.suffix.lower() == ".flac":
        if not path.is_file():
            raise FileNotFoundError(f"FLAC file not found: {path}")
        return _read_unaltered_pcm_flac(path)
    raise StageRExecutionContractError("R1 source must be an uncompressed PCM WAV or lossless FLAC")


def _reference_path(record: Mapping[str, Any]) -> Path:
    path = Path(str(record.get("external_path", "")))
    if not path.is_file():
        raise StageRExecutionContractError(f"reference external_path is not readable: {path}")
    expected = record.get("sha256")
    if expected and _sha256(path) != expected:
        raise StageRExecutionContractError(f"reference SHA-256 mismatch: {path}")
    return path


def _normalise_trace_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def _resolve_trace_path(owner: Mapping[str, Any], key: str, *, fallback_root: Path | None = None) -> Path:
    containers = [owner]
    for container_name in ("state_bindings", "analysis_contract"):
        container = owner.get(container_name)
        if isinstance(container, Mapping):
            containers.append(container)
    raw: object | None = None
    for container in containers:
        if container.get(key):
            raw = container[key]
            break
    if not raw:
        raise StageRExecutionContractError(f"R1 state trace path missing: {key}")
    path = Path(str(raw))
    if not path.is_absolute():
        root = owner.get("trace_root")
        if not root:
            for container in containers[1:]:
                if container.get("trace_root"):
                    root = container["trace_root"]
                    break
        if root:
            path = Path(str(root)) / path
        elif fallback_root is not None:
            path = fallback_root / path
        else:
            raise StageRExecutionContractError(f"relative R1 trace path needs trace_root: {key}")
    if not path.is_file():
        raise StageRExecutionContractError(f"R1 state trace is not readable: {path}")
    return path


def _read_trace_table(path: Path) -> dict[str, np.ndarray]:
    """Read a small numeric CSV/JSON state table without guessing units."""

    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise StageRExecutionContractError(f"R1 trace CSV has no header: {path}")
            rows = list(reader)
        if not rows:
            raise StageRExecutionContractError(f"R1 trace CSV is empty: {path}")
        names = {_normalise_trace_key(name): name for name in reader.fieldnames if name is not None}
        table: dict[str, np.ndarray] = {}
        for normalised, original in names.items():
            values: list[float] = []
            for row in rows:
                raw = row.get(original, "")
                if raw is None or str(raw).strip() == "":
                    raise StageRExecutionContractError(f"R1 trace contains a blank value in {original}: {path}")
                try:
                    values.append(float(raw))
                except ValueError as exc:
                    raise StageRExecutionContractError(f"R1 trace value is not numeric in {original}: {path}") from exc
            table[normalised] = np.asarray(values, dtype=np.float64)
        return table
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, Mapping):
            table = {}
            for key, values in payload.items():
                if not isinstance(values, (list, tuple)):
                    continue
                try:
                    table[_normalise_trace_key(key)] = np.asarray(values, dtype=np.float64)
                except (TypeError, ValueError) as exc:
                    raise StageRExecutionContractError(f"R1 JSON trace value is not numeric: {path}") from exc
            if table:
                return table
        elif isinstance(payload, list):
            try:
                return {"value": np.asarray(payload, dtype=np.float64)}
            except (TypeError, ValueError) as exc:
                raise StageRExecutionContractError(f"R1 JSON trace value is not numeric: {path}") from exc
        raise StageRExecutionContractError(f"R1 JSON trace must contain numeric arrays: {path}")
    raise StageRExecutionContractError(f"R1 trace must be CSV or JSON: {path}")


def _trace_column(table: Mapping[str, np.ndarray], aliases: tuple[str, ...], field: str, *, required: bool = True) -> np.ndarray | None:
    for alias in aliases:
        key = _normalise_trace_key(alias)
        if key in table:
            value = np.asarray(table[key], dtype=np.float64).reshape(-1)
            if value.size == 0:
                raise StageRExecutionContractError(f"R1 trace column is empty: {field}")
            return value
    if required:
        raise StageRExecutionContractError(f"R1 trace column missing: {field}")
    return None


def _trace_sha256(bundle: Mapping[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for name in ("time_s", "rpm", "load", "throttle", "gear", "shift_event"):
        values = np.asarray(bundle[name], dtype="<f8")
        digest.update(name.encode("ascii"))
        digest.update(b"\0")
        digest.update(values.tobytes())
    return digest.hexdigest()


def _trace_window(owner: Mapping[str, Any]) -> tuple[float, float]:
    window = owner.get("time_window")
    if not isinstance(window, Mapping):
        raise StageRExecutionContractError("R1 time_window with start_s/end_s is required")
    try:
        start = float(window["start_s"])
        end = float(window["end_s"])
    except (KeyError, TypeError, ValueError) as exc:
        raise StageRExecutionContractError("R1 time_window must contain numeric start_s/end_s") from exc
    if not np.isfinite([start, end]).all() or end <= start:
        raise StageRExecutionContractError("R1 time_window must be finite and end_s > start_s")
    return start, end


def _resample_linear(values: np.ndarray, source_time_s: np.ndarray, target_time_s: np.ndarray, *, field: str) -> np.ndarray:
    """Interpolate a continuous state field onto the audio sample grid."""

    if source_time_s.size != values.size:
        raise StageRExecutionContractError(f"R1 state/audio sample count mismatch: {field} time/value lengths differ")
    if source_time_s.size < 2:
        raise StageRExecutionContractError(f"R1 state trace needs at least two timestamped samples: {field}")
    if not np.isfinite(source_time_s).all() or not np.isfinite(values).all():
        raise StageRExecutionContractError(f"R1 state traces contain non-finite values: {field}")
    if np.any(np.diff(source_time_s) <= 0):
        raise StageRExecutionContractError(f"R1 state trace time must be strictly increasing: {field}")
    tolerance = max(1e-9, 1.0e-6 / max(1.0, float(source_time_s[-1] - source_time_s[0])))
    if target_time_s[0] < source_time_s[0] - tolerance or target_time_s[-1] > source_time_s[-1] + tolerance:
        raise StageRExecutionContractError(
            f"R1 state/audio sample count mismatch: {field} trace time range "
            f"[{source_time_s[0]:.9g}, {source_time_s[-1]:.9g}] does not cover "
            f"audio window [{target_time_s[0]:.9g}, {target_time_s[-1]:.9g}]"
        )
    # np.interp clamps at the edges.  The explicit coverage check above makes
    # that clamp an endpoint tolerance only, never an implicit extrapolation.
    return np.interp(target_time_s, source_time_s, values).astype(np.float64, copy=False)


def _resample_discrete(values: np.ndarray, source_time_s: np.ndarray, target_time_s: np.ndarray, *, field: str) -> np.ndarray:
    """Nearest-neighbour resampling for gear and shift-event state."""

    if source_time_s.size != values.size:
        raise StageRExecutionContractError(f"R1 state/audio sample count mismatch: {field} time/value lengths differ")
    if source_time_s.size < 2:
        raise StageRExecutionContractError(f"R1 state trace needs at least two timestamped samples: {field}")
    if not np.isfinite(source_time_s).all() or not np.isfinite(values).all():
        raise StageRExecutionContractError(f"R1 state traces contain non-finite values: {field}")
    if np.any(np.diff(source_time_s) <= 0):
        raise StageRExecutionContractError(f"R1 state trace time must be strictly increasing: {field}")
    tolerance = max(1e-9, 1.0e-6 / max(1.0, float(source_time_s[-1] - source_time_s[0])))
    if target_time_s[0] < source_time_s[0] - tolerance or target_time_s[-1] > source_time_s[-1] + tolerance:
        raise StageRExecutionContractError(
            f"R1 state/audio sample count mismatch: {field} trace time range "
            f"[{source_time_s[0]:.9g}, {source_time_s[-1]:.9g}] does not cover "
            f"audio window [{target_time_s[0]:.9g}, {target_time_s[-1]:.9g}]"
        )
    right = np.searchsorted(source_time_s, target_time_s, side="left")
    right = np.clip(right, 0, source_time_s.size - 1)
    left = np.clip(right - 1, 0, source_time_s.size - 1)
    choose_right = np.abs(source_time_s[right] - target_time_s) < np.abs(target_time_s - source_time_s[left])
    indices = np.where(choose_right, right, left)
    return values[indices].astype(np.float64, copy=False)


def _load_state_bundle(owner: Mapping[str, Any], *, frame_count: int, sample_rate_hz: int, fallback_root: Path | None) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    rpm_path = _resolve_trace_path(owner, "rpm_trace_path", fallback_root=fallback_root)
    load_path = _resolve_trace_path(owner, "load_throttle_trace_path", fallback_root=fallback_root)
    gear_path = _resolve_trace_path(owner, "gear_shift_trace_path", fallback_root=fallback_root)
    rpm_table = _read_trace_table(rpm_path)
    load_table = _read_trace_table(load_path)
    gear_table = _read_trace_table(gear_path)
    rpm = _trace_column(rpm_table, ("rpm", "engine_rpm"), "rpm")
    load = _trace_column(load_table, ("load", "engine_load", "load_fraction"), "load")
    throttle = _trace_column(load_table, ("throttle", "throttle_pct", "throttle_fraction"), "throttle")
    gear = _trace_column(gear_table, ("gear", "gear_index", "gear_number"), "gear")
    shift_event = _trace_column(gear_table, ("shift", "shift_event", "gear_shift"), "shift_event", required=False)
    if shift_event is None:
        shift_event = np.concatenate(([0.0], (np.diff(gear) != 0).astype(np.float64)))
        shift_source = "derived_from_gear_transition"
    else:
        shift_source = "recorded_trace_column"
    time_sources = {
        "rpm": _trace_column(rpm_table, ("time_s", "timestamp_s", "time"), "rpm.time_s", required=False),
        "load": _trace_column(load_table, ("time_s", "timestamp_s", "time"), "load.time_s", required=False),
        "throttle": _trace_column(load_table, ("time_s", "timestamp_s", "time"), "throttle.time_s", required=False),
        "gear": _trace_column(gear_table, ("time_s", "timestamp_s", "time"), "gear.time_s", required=False),
        "shift_event": _trace_column(gear_table, ("time_s", "timestamp_s", "time"), "shift_event.time_s", required=False),
    }
    values = {
        "rpm": np.asarray(rpm, dtype=np.float64),
        "load": np.asarray(load, dtype=np.float64),
        "throttle": np.asarray(throttle, dtype=np.float64),
        "gear": np.asarray(gear, dtype=np.float64),
        "shift_event": np.asarray(shift_event, dtype=np.float64),
    }
    source_sizes = {name: int(value.size) for name, value in values.items()}
    has_time = [time_sources[name] is not None for name in values]
    if any(has_time) and not all(has_time):
        raise StageRExecutionContractError("R1 state trace time columns are not aligned")
    if all(has_time):
        source_times = {name: np.asarray(time_sources[name], dtype=np.float64) for name in values}
        for name, source_time in source_times.items():
            if source_time.size != values[name].size:
                raise StageRExecutionContractError(f"R1 state/audio sample count mismatch: {name} time/value lengths differ")
            if source_time.size < 2 or not np.isfinite(source_time).all() or np.any(np.diff(source_time) <= 0):
                raise StageRExecutionContractError(f"R1 state trace time must be strictly increasing: {name}")
        time_source = "recorded_trace_columns"
    else:
        source_times = {}
        time_source = "sample_index_at_audio_sample_rate"
    default_time_s = np.arange(frame_count, dtype=np.float64) / float(sample_rate_hz)
    sample_aligned_time = bool(
        all(has_time)
        and all(source_times[name].size == frame_count for name in values)
        and all(np.allclose(source_times[name], default_time_s, rtol=0.0, atol=1e-9) for name in values)
    )
    needs_window = any(size != frame_count for size in source_sizes.values()) or (all(has_time) and not sample_aligned_time)
    if needs_window:
        window = _trace_window(owner)
        target_time_s = np.linspace(window[0], window[1], frame_count, dtype=np.float64)
    else:
        target_time_s = default_time_s
    if source_times:
        if sample_aligned_time:
            bundle = {"time_s": target_time_s, **values}
            resampling = "none_audio_sample_aligned"
        else:
            bundle = {
                "time_s": target_time_s,
                "rpm": _resample_linear(values["rpm"], source_times["rpm"], target_time_s, field="rpm"),
                "load": _resample_linear(values["load"], source_times["load"], target_time_s, field="load"),
                "throttle": _resample_linear(values["throttle"], source_times["throttle"], target_time_s, field="throttle"),
                "gear": _resample_discrete(values["gear"], source_times["gear"], target_time_s, field="gear"),
                "shift_event": _resample_discrete(values["shift_event"], source_times["shift_event"], target_time_s, field="shift_event"),
            }
            resampling = "timestamp_interpolation_to_audio_sample_grid"
    else:
        if len(set(source_sizes.values())) != 1 or any(value.size != frame_count for value in values.values()):
            raise StageRExecutionContractError(
                f"R1 state/audio sample count mismatch: frames={frame_count}, traces={source_sizes}; "
                "lower-rate traces require timestamp columns"
            )
        bundle = {"time_s": target_time_s, **values}
        resampling = "none_audio_sample_aligned"
    if not all(np.isfinite(value).all() for value in bundle.values()):
        raise StageRExecutionContractError("R1 state traces contain non-finite values")
    if np.any(bundle["rpm"] <= 0):
        raise StageRExecutionContractError("R1 RPM trace must be positive; estimated or zero RPM is not qualified")
    if np.any(bundle["load"] < 0) or np.any(bundle["load"] > 1) or np.any(bundle["throttle"] < 0) or np.any(bundle["throttle"] > 1):
        raise StageRExecutionContractError("R1 load/throttle must be normalized fractions in [0, 1]")
    if np.any(bundle["gear"] < 0):
        raise StageRExecutionContractError("R1 gear trace must be non-negative")
    expected_sha = owner.get("state_trace_sha256")
    if not expected_sha and isinstance(owner.get("state_bindings"), Mapping):
        expected_sha = owner["state_bindings"].get("trace_sha256")
    actual_sha = _trace_sha256(bundle)
    if expected_sha and str(expected_sha).lower() != actual_sha:
        raise StageRExecutionContractError(f"R1 state trace SHA-256 mismatch: expected={expected_sha}, actual={actual_sha}")
    return bundle, {
        "rpm_trace_path": str(rpm_path),
        "load_throttle_trace_path": str(load_path),
        "gear_shift_trace_path": str(gear_path),
        "trace_sha256": actual_sha,
        "shift_source": shift_source,
        "time_source": time_source,
        "resampling": resampling,
        "source_trace_lengths": source_sizes,
        "frame_count": frame_count,
        "sample_rate_hz": sample_rate_hz,
    }


def _pcm24_stereo(signal: np.ndarray) -> tuple[np.ndarray, str]:
    value = np.asarray(signal, dtype=np.float64)
    if value.ndim != 2 or value.shape[1] not in {1, 2}:
        raise StageRExecutionContractError("R1 MATLAB input supports only mono or stereo WAV")
    if value.shape[1] == 1:
        value = np.repeat(value, 2, axis=1)
        policy = "mono_duplicated_for_stage_n_stereo_input"
    else:
        policy = "original_stereo_channels_preserved"
    pcm24 = np.rint(np.clip(value, -1.0, 1.0) * ((1 << 23) - 1)).astype(np.int32)
    return pcm24, policy


def _write_r1_mat(path: Path, *, vehicle_id: str, scenario: str, source_sha256: str, pcm24: np.ndarray, sample_rate_hz: int, state: Mapping[str, np.ndarray], state_sha256: str, side: str) -> str:
    try:
        from scipy.io import savemat
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise StageRExecutionContractError("SciPy is required to prepare MATLAB R1 inputs") from exc
    savemat(
        path,
        {
            "vehicle_id": vehicle_id,
            "scenario": scenario,
            "side": side,
            "sample_rate_hz": np.asarray([[sample_rate_hz]], dtype=np.float64),
            "signal_pcm24": pcm24,
            "rpm": state["rpm"],
            "state_trace": state["gear"],
            "load": state["load"],
            "throttle": state["throttle"],
            "gear": state["gear"],
            "shift_event": state["shift_event"],
            "time_s": state["time_s"],
            "source_wav_sha256": source_sha256,
            "state_trace_sha256": state_sha256,
        },
        do_compression=True,
        long_field_names=True,
    )
    return _sha256(path)


def prepare_r1_matlab_inputs(
    reference_record: Mapping[str, Any],
    candidate_path: Path,
    *,
    candidate_meta: Mapping[str, Any],
    output_root: Path,
) -> dict[str, Any]:
    """Prepare two SHA-bound MAT inputs for the existing MATLAB Stage-N runners.

    This function only validates and packages inputs.  It never starts MATLAB,
    estimates RPM, applies gain/EQ/AGC, or produces a tuning decision.  The
    output root is an external/ignored working area because the MAT files
    contain the unaltered analysis waveform.
    """

    plan = build_r1_execution_plan(reference_record, candidate_meta)
    candidate_path = Path(candidate_path)
    if not candidate_path.is_file():
        raise StageRExecutionContractError(f"R1 candidate WAV is not readable: {candidate_path}")
    output_root = Path(output_root)
    if output_root.exists():
        raise StageRExecutionContractError(f"refusing to overwrite R1 MATLAB input root: {output_root}")
    reference_path = Path(str(plan["reference"]["external_path"]))
    reference_signal, reference_rate, reference_header = read_unaltered_pcm_audio(reference_path)
    candidate_signal, candidate_rate, candidate_header = read_unaltered_pcm_audio(candidate_path)
    if reference_rate != candidate_rate:
        raise StageRExecutionContractError(
            f"R1 sample-rate mismatch: reference={reference_rate}, candidate={candidate_rate}; resampling is not implicit"
        )
    vehicle_id = str(reference_record.get("vehicle_id"))
    scenario = str(reference_record.get("scenario") or reference_record.get("scenario_hint"))
    reference_state, reference_state_meta = _load_state_bundle(
        reference_record,
        frame_count=int(reference_header["frames"]),
        sample_rate_hz=reference_rate,
        fallback_root=reference_path.parent,
    )
    candidate_state, candidate_state_meta = _load_state_bundle(
        candidate_meta,
        frame_count=int(candidate_header["frames"]),
        sample_rate_hz=candidate_rate,
        fallback_root=candidate_path.parent,
    )
    reference_window = _trace_window(reference_record)
    candidate_window = _trace_window(candidate_meta)
    if not np.isclose(reference_window[1] - reference_window[0], candidate_window[1] - candidate_window[0], rtol=0.0, atol=1.0 / reference_rate):
        raise StageRExecutionContractError("R1 reference/candidate time-window durations are not aligned")
    reference_pcm24, reference_channel_policy = _pcm24_stereo(reference_signal)
    candidate_pcm24, candidate_channel_policy = _pcm24_stereo(candidate_signal)
    output_root.mkdir(parents=True)
    reference_mat = output_root / "reference.mat"
    candidate_mat = output_root / "candidate.mat"
    reference_mat_sha = _write_r1_mat(
        reference_mat,
        vehicle_id=vehicle_id,
        scenario=scenario,
        source_sha256=str(reference_header["sha256"]),
        pcm24=reference_pcm24,
        sample_rate_hz=reference_rate,
        state=reference_state,
        state_sha256=str(reference_state_meta["trace_sha256"]),
        side="reference",
    )
    candidate_mat_sha = _write_r1_mat(
        candidate_mat,
        vehicle_id=vehicle_id,
        scenario=scenario,
        source_sha256=str(candidate_header["sha256"]),
        pcm24=candidate_pcm24,
        sample_rate_hz=candidate_rate,
        state=candidate_state,
        state_sha256=str(candidate_state_meta["trace_sha256"]),
        side="candidate",
    )
    manifest = {
        "schema_version": R1_INPUT_SCHEMA_VERSION,
        "status": "READY_FOR_MANUAL_MATLAB_EXECUTION",
        "source_policy": "external WAV is referenced by SHA; unaltered analysis waveform is packaged only in the external MAT working root",
        "automatic_tuning_eligible": False,
        "order_hard_gate": True,
        "vehicle_id": vehicle_id,
        "scenario": scenario,
        "sample_rate_hz": reference_rate,
        "state_units": {"time_s": "s", "rpm": "rpm", "load": "fraction_0_1", "throttle": "fraction_0_1", "gear": "integer_index", "shift_event": "0_or_1"},
        "reference_window": {"start_s": reference_window[0], "end_s": reference_window[1]},
        "candidate_window": {"start_s": candidate_window[0], "end_s": candidate_window[1]},
        "inputs": {
            "reference": {
                "mat_file": reference_mat.name,
                "mat_sha256": reference_mat_sha,
                "source_wav": str(reference_path),
                "source_wav_sha256": reference_header["sha256"],
                "frames": reference_header["frames"],
                "state": reference_state_meta,
                "channel_policy": reference_channel_policy,
            },
            "candidate": {
                "mat_file": candidate_mat.name,
                "mat_sha256": candidate_mat_sha,
                "source_wav": str(candidate_path),
                "source_wav_sha256": candidate_header["sha256"],
                "frames": candidate_header["frames"],
                "state": candidate_state_meta,
                "channel_policy": candidate_channel_policy,
                "candidate_id": candidate_meta["candidate_id"],
            },
        },
        "matlab_entrypoints": {
            "script_root": "tools/sound_sim/s12/acoustic_comparator/matlab",
            "order": "s12_stage_n_run_order_analysis(input_root, output_root)",
            "psychoacoustics": "s12_stage_n_run_psychoacoustic_analysis(input_root, output_root)",
            "manual_desktop_only": True,
            "required_functions": list(MATLAB_R1_FUNCTIONS),
        },
        "mosqito_entrypoint": {
            "module": "tools.sound_sim.s12.acoustic_comparator.psychoacoustics.mosqito_adapter",
            "mode": "--project-input-root",
            "manual_receipt_required": True,
        },
        "tuning_authority": plan["automatic_tuning_authority"],
    }
    (output_root / "input_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def _r2_case(record: Mapping[str, Any], candidate_meta: Mapping[str, Any], sample_rate_hz: int) -> ComparisonCase:
    vehicle_id = str(record.get("vehicle_id", ""))
    scenario = str(record.get("scenario") or record.get("scenario_hint") or "")
    if not vehicle_id or not scenario:
        raise StageRExecutionContractError("R2 reference must identify vehicle and scenario")
    missing = [name for name in ("vehicle_id", "scenario", "candidate_id") if not candidate_meta.get(name)]
    if missing:
        raise StageRExecutionContractError("R2 candidate metadata missing: " + ", ".join(missing))
    candidate_scenario = str(candidate_meta["scenario"])
    if candidate_scenario != scenario:
        raise StageRExecutionContractError("candidate/reference scenario mismatch")
    if str(candidate_meta["vehicle_id"]) != vehicle_id:
        raise StageRExecutionContractError("candidate/reference vehicle mismatch")
    return ComparisonCase(
        vehicle_id=vehicle_id,
        scenario=scenario,
        reference_id=str(record.get("reference_id") or record.get("recording_id")),
        candidate_id=str(candidate_meta["candidate_id"]),
        sample_rate_hz=sample_rate_hz,
        reference_rpm=(0.0, 0.0),
        candidate_rpm=(0.0, 0.0),
        reference_load=(0.0, 0.0),
        candidate_load=(0.0, 0.0),
        analysis_domain="unaltered_analysis_signal",
        reference_kind="external_recording",
        reference_provenance=f"authorised R2 reference {record.get('recording_id')}",
        candidate_source_commit=str(candidate_meta.get("source_commit") or "unspecified"),
        channel_policy="recorded_channels_folded_to_mono_for_comparison",
        microphone_setup_uncertainty="R2 capture metadata incomplete; relative-only",
        loudness_match_policy="analysis_unaltered_audition_separate",
    )


def run_r2_limited_comparison(
    reference_record: Mapping[str, Any],
    candidate_path: Path,
    *,
    candidate_meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the permitted R2 relative comparison for one external reference."""

    gate = qualify_r2_reference(dict(reference_record))
    if not gate["eligible"]:
        raise ReferenceQualificationError(
            f"reference {reference_record.get('recording_id', '<unknown>')} is not R2-eligible: "
            + ", ".join(gate["missing"])
        )
    candidate_meta = dict(candidate_meta or {})
    reference_path = _reference_path(reference_record)
    reference, reference_rate, reference_header = read_unaltered_pcm_wav(reference_path)
    candidate, candidate_rate, candidate_header = read_unaltered_pcm_wav(Path(candidate_path))
    if reference_rate != candidate_rate:
        raise StageRExecutionContractError(
            f"sample-rate mismatch: reference={reference_rate}, candidate={candidate_rate}; resampling is not implicit"
        )
    case = _r2_case(reference_record, candidate_meta, reference_rate)
    result = compare_r2_signals(
        reference,
        candidate,
        case,
        dict(reference_record),
        candidate_scenario=case.scenario,
    )
    result.update(
        {
            "status": "R2_LIMITED_COMPARISON_COMPLETE",
            "comparison_scope": "relative_digital_domain_only",
            "reference_header": reference_header,
            "candidate_header": candidate_header,
            "reference_id": case.reference_id,
            "candidate_id": case.candidate_id,
            "automatic_tuning_eligible": False,
            "parameter_recommendations": [],
            "difference_report": {
                "vehicle_id": case.vehicle_id,
                "scenario": case.scenario,
                "spectral_residual": result.get("spectral", {}),
                "band_residual": result.get("bands", {}),
                "loudness_residual": result.get("loudness", {}),
                "psychoacoustic_residual": result.get("psychoacoustics", {}),
                "transient_residual": result.get("transients", {}),
                "order_residual": result.get("order", {}).get("comparison"),
                "reference_uncertainty": "R2/no synchronized RPM-state; relative only",
                "human_score": None,
            },
        }
    )
    return result


def build_r1_execution_plan(
    reference_record: Mapping[str, Any],
    candidate_meta: Mapping[str, Any],
) -> dict[str, Any]:
    """Prepare, but do not execute, a full R1 MATLAB/Stage-N comparison."""

    gate = require_r1_reference(dict(reference_record))
    reference_path = _reference_path(reference_record)
    required = ("vehicle_id", "scenario", "candidate_id", "candidate_sha256", "state_trace_sha256", "rpm_trace_path", "load_throttle_trace_path", "gear_shift_trace_path")
    missing = [name for name in required if not candidate_meta.get(name)]
    if missing:
        raise StageRExecutionContractError("R1 candidate metadata missing: " + ", ".join(missing))
    if str(candidate_meta["vehicle_id"]) != str(reference_record.get("vehicle_id")):
        raise StageRExecutionContractError("R1 candidate/reference vehicle mismatch")
    if str(candidate_meta["scenario"]) != str(reference_record.get("scenario") or reference_record.get("scenario_hint")):
        raise StageRExecutionContractError("R1 candidate/reference scenario mismatch")
    return {
        "status": "READY_FOR_R1_MATLAB_EXECUTION",
        "qualification": gate,
        "reference": {
            "reference_id": reference_record.get("reference_id") or reference_record.get("recording_id"),
            "external_path": str(reference_path),
            "sha256": reference_record.get("sha256"),
        },
        "candidate": dict(candidate_meta),
        "alignment_contract": {
            "dimensions": ["vehicle", "scenario", "rpm_range", "load_throttle", "gear_shift", "time_window", "sample_rate", "channel_policy"],
            "analysis_signal": "unaltered_analysis_signal",
            "audition_signal": "loudness_matched_audition_signal_separate",
            "estimated_rpm_allowed": False,
        },
        "matlab_required_functions": list(MATLAB_R1_FUNCTIONS),
        "input_preparation": {
            "schema_version": R1_INPUT_SCHEMA_VERSION,
            "function": "prepare_r1_matlab_inputs",
            "output_policy": "external_or_ignored_working_root; MAT contains unaltered analysis waveform",
        },
        "matlab_entrypoints": {
            "order": "s12_stage_n_run_order_analysis(input_root, output_root)",
            "psychoacoustics": "s12_stage_n_run_psychoacoustic_analysis(input_root, output_root)",
            "manual_desktop_only": True,
        },
        "mosqito_entrypoint": {
            "module": "tools.sound_sim.s12.acoustic_comparator.psychoacoustics.mosqito_adapter",
            "mode": "--project-input-root",
            "manual_receipt_required": True,
        },
        "required_receipts": ["matlab_order_session_receipt", "matlab_psychoacoustic_session_receipt", "mosqito_project_receipt"],
        "order_hard_gate": True,
        "automatic_tuning_authority": "WITHHELD_UNTIL_STAGE_S_HUMAN_FEEDBACK_AND_HARD_GATES",
    }


def write_r2_outputs(result: Mapping[str, Any], out_dir: Path) -> dict[str, Path]:
    """Write a Chinese R2 result/report without creating recommendation files."""

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / "stage_r_r2_limited_result.json"
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    report_path = out_dir / "S12_Stage_R_R2_Limited_Difference_Report.md"
    report_path.write_text(
        "\n".join(
            [
                "# S12 Stage R2 有限真实声浪差异报告",
                "",
                "状态：`R2_LIMITED_COMPARISON_COMPLETE`",
                "",
                "本报告只表示已授权 R2 参考与本地候选在未增益分析信号上的相对数字域差异。没有同步 RPM/state，因此不输出阶次硬门、不输出 OEM 绝对门限，也不生成参数建议。",
                "",
                f"车型：`{result.get('case', {}).get('vehicle_id')}`；工况：`{result.get('case', {}).get('scenario')}`。",
                "",
                "## 差异结果",
                "",
                "```json",
                json.dumps(result.get("difference_report", {}), indent=2, ensure_ascii=False, sort_keys=True),
                "```",
                "",
                "试听必须使用独立的响度匹配副本；本结果中的分析信号没有使用响度匹配副本。R2 结果仍需 Jovi 中文听审后才能进入任何后续判断。",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    return {"result": result_path, "report": report_path}


def _load_manifest_record(path: Path, recording_id: str) -> dict[str, Any]:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    for record in manifest.get("recordings", []):
        if record.get("recording_id") == recording_id or record.get("reference_id") == recording_id:
            return dict(record)
    raise StageRExecutionContractError(f"recording_id not found in manifest: {recording_id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="执行受资格门约束的 S12 Stage R R2 比较或生成 R1 MATLAB 执行计划")
    parser.add_argument("--mode", choices=("r2", "r1-plan"), required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--recording-id", required=True)
    parser.add_argument("--candidate-wav", type=Path)
    parser.add_argument("--candidate-meta", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    record = _load_manifest_record(args.manifest, args.recording_id)
    meta = json.loads(args.candidate_meta.read_text(encoding="utf-8")) if args.candidate_meta else {}
    if args.mode == "r2":
        if args.candidate_wav is None:
            raise SystemExit("--candidate-wav is required for --mode r2")
        result = run_r2_limited_comparison(record, args.candidate_wav, candidate_meta=meta)
        write_r2_outputs(result, args.output)
    else:
        plan = build_r1_execution_plan(record, meta)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(plan, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through CLI smoke tests
    raise SystemExit(main())


__all__ = [
    "MATLAB_R1_FUNCTIONS",
    "R1_INPUT_SCHEMA_VERSION",
    "StageRExecutionContractError",
    "build_r1_execution_plan",
    "prepare_r1_matlab_inputs",
    "read_unaltered_pcm_wav",
    "run_r2_limited_comparison",
    "write_r2_outputs",
]
