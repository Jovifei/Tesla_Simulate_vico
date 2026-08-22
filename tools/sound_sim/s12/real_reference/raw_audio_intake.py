"""Fail-closed intake for a lawful original audio + synchronized state package.

The package is deliberately separate from URL/video intake.  Original WAV or
FLAC files and telemetry remain under the approved external download root; the
repository receives only the generated contract/manifest when a caller elects
to copy that metadata into Git.  This module never copies, normalizes, gains,
resamples, or rewrites the original audio.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import subprocess
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .qualification import qualify_r1_reference, qualify_r2_reference


ALLOWED_DOWNLOAD_ROOT = Path(r"E:\Claude_allow\Download")
SCHEMA_VERSION = "s12-stage-q-raw-audio-r1-v1"
_AUDIO_EXTENSIONS = {".wav", ".flac"}


class RawReferenceIntakeError(ValueError):
    """Base error for an invalid or incomplete original-reference package."""


class RawReferencePathError(RawReferenceIntakeError):
    """Raised when a path escapes the approved external root."""


class RawReferenceContractError(RawReferenceIntakeError):
    """Raised for a package contract that can be recorded but is not R1."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(root: Path, path: Path, label: str) -> Path:
    root_resolved = Path(root).resolve()
    path_resolved = Path(path).resolve()
    if path_resolved != root_resolved and root_resolved not in path_resolved.parents:
        raise RawReferencePathError(f"{label} must remain under approved download root: {path_resolved}")
    return path_resolved


def _normalise_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def _audio_metadata(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix not in _AUDIO_EXTENSIONS:
        raise RawReferenceContractError("original audio must be .wav or .flac")
    if suffix == ".wav":
        try:
            with wave.open(str(path), "rb") as stream:
                if stream.getcomptype() != "NONE":
                    raise RawReferenceContractError("compressed WAV is not an original PCM analysis signal")
                sample_rate_hz = stream.getframerate()
                frames = stream.getnframes()
                channels = stream.getnchannels()
                width_bits = stream.getsampwidth() * 8
        except (OSError, wave.Error) as exc:
            raise RawReferenceContractError(f"cannot read PCM WAV: {path}") from exc
        if sample_rate_hz <= 0 or frames <= 0 or channels <= 0:
            raise RawReferenceContractError("original WAV has invalid sample rate, channels, or frame count")
        return {
            "container": "WAV",
            "codec": "PCM",
            "channels": channels,
            "sample_rate_hz": sample_rate_hz,
            "sample_width_bits": width_bits,
            "frames": frames,
            "duration_s": frames / float(sample_rate_hz),
        }
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RawReferenceContractError("ffprobe is required to inspect original FLAC")
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RawReferenceContractError(f"ffprobe cannot read original FLAC: {result.stderr.strip()[:300]}")
    try:
        payload = json.loads(result.stdout)
        stream = next(row for row in payload.get("streams", []) if row.get("codec_type") == "audio")
    except (json.JSONDecodeError, StopIteration) as exc:
        raise RawReferenceContractError("original FLAC has no readable audio stream") from exc
    codec = str(stream.get("codec_name") or "").lower()
    if codec != "flac":
        raise RawReferenceContractError(".flac path did not contain a FLAC audio stream")
    try:
        sample_rate_hz = int(stream["sample_rate"])
        channels = int(stream["channels"])
        duration_raw = stream.get("duration")
        try:
            duration_s = float(duration_raw)
        except (TypeError, ValueError):
            duration_s = float(payload.get("format", {}).get("duration"))
    except (KeyError, TypeError, ValueError) as exc:
        raise RawReferenceContractError("original FLAC is missing sample-rate/channel/duration metadata") from exc
    if sample_rate_hz <= 0 or channels <= 0 or duration_s <= 0:
        raise RawReferenceContractError("original FLAC has invalid audio metadata")
    return {
        "container": "FLAC",
        "codec": "FLAC",
        "channels": channels,
        "sample_rate_hz": sample_rate_hz,
        "sample_width_bits": None,
        "frames": int(round(sample_rate_hz * duration_s)),
        "duration_s": duration_s,
    }


def _read_table(path: Path) -> dict[str, list[float]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise RawReferenceContractError(f"state trace CSV has no header: {path}")
            rows = list(reader)
        if not rows:
            raise RawReferenceContractError(f"state trace CSV is empty: {path}")
        table: dict[str, list[float]] = {}
        for field in reader.fieldnames:
            if field is None:
                continue
            key = _normalise_key(field)
            values: list[float] = []
            for row in rows:
                raw = row.get(field, "")
                if raw is None or not str(raw).strip():
                    raise RawReferenceContractError(f"blank value in state trace column {field}: {path}")
                try:
                    values.append(float(raw))
                except ValueError as exc:
                    raise RawReferenceContractError(f"non-numeric state value in {field}: {path}") from exc
            table[key] = values
        return table
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RawReferenceContractError(f"cannot parse state trace JSON: {path}") from exc
        if not isinstance(payload, Mapping):
            raise RawReferenceContractError(f"state trace JSON must contain named arrays: {path}")
        table = {}
        for key, values in payload.items():
            if not isinstance(values, list) or not values:
                continue
            try:
                table[_normalise_key(key)] = [float(value) for value in values]
            except (TypeError, ValueError) as exc:
                raise RawReferenceContractError(f"non-numeric state array {key}: {path}") from exc
        if not table:
            raise RawReferenceContractError(f"state trace JSON has no numeric arrays: {path}")
        return table
    raise RawReferenceContractError(f"state trace must be CSV or JSON: {path}")


def _column(table: Mapping[str, list[float]], aliases: tuple[str, ...], field: str, *, required: bool = True) -> list[float] | None:
    for alias in aliases:
        key = _normalise_key(alias)
        if key in table:
            values = list(table[key])
            if not values:
                raise RawReferenceContractError(f"state trace column is empty: {field}")
            return values
    if required:
        raise RawReferenceContractError(f"state trace column missing: {field}")
    return None


def _validate_units(units: Mapping[str, Any]) -> dict[str, str]:
    required = {
        "time_s": "s",
        "rpm": "rpm",
        "load": "fraction_0_1",
        "throttle": "fraction_0_1",
        "gear": "integer_index",
        "shift_event": "0_or_1",
    }
    if not isinstance(units, Mapping):
        raise RawReferenceContractError("state.units is required; do not guess telemetry units")
    missing = [key for key, expected in required.items() if units.get(key) != expected]
    if missing:
        raise RawReferenceContractError("state.units missing or mismatched: " + ", ".join(missing))
    return {key: str(units[key]) for key in required}


def _trace_root(state: Mapping[str, Any], root: Path) -> Path:
    raw_root = state.get("trace_root") or root
    trace_root_candidate = Path(str(raw_root))
    if not trace_root_candidate.is_absolute():
        trace_root_candidate = root / trace_root_candidate
    return _inside(root, trace_root_candidate, "state.trace_root")


def _trace_path(state: Mapping[str, Any], key: str, root: Path) -> Path:
    trace_root = _trace_root(state, root)
    raw = state.get(key)
    if not raw:
        raise RawReferenceContractError(f"state.{key} is required")
    return _inside(root, trace_root / str(raw), f"state.{key}")


def _validate_state(state: Mapping[str, Any], *, root: Path, audio: Mapping[str, Any]) -> dict[str, Any]:
    units = _validate_units(state.get("units"))
    window = state.get("time_window")
    if not isinstance(window, Mapping):
        raise RawReferenceContractError("state.time_window with start_s/end_s is required")
    try:
        start_s = float(window["start_s"])
        end_s = float(window["end_s"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RawReferenceContractError("state.time_window must contain numeric start_s/end_s") from exc
    if end_s <= start_s or start_s < 0 or end_s > float(audio["duration_s"]) + 1.0 / float(audio["sample_rate_hz"]):
        raise RawReferenceContractError("state.time_window is outside the original audio duration")

    paths = {
        key: _trace_path(state, key, root)
        for key in ("rpm_trace_path", "load_throttle_trace_path", "gear_shift_trace_path")
    }
    tables = {key: _read_table(path) for key, path in paths.items()}
    rpm_time = _column(tables["rpm_trace_path"], ("time_s", "timestamp_s", "time"), "rpm.time_s")
    load_time = _column(tables["load_throttle_trace_path"], ("time_s", "timestamp_s", "time"), "load_throttle.time_s")
    gear_time = _column(tables["gear_shift_trace_path"], ("time_s", "timestamp_s", "time"), "gear_shift.time_s")
    rpm = _column(tables["rpm_trace_path"], ("rpm", "engine_rpm"), "rpm")
    load = _column(tables["load_throttle_trace_path"], ("load", "engine_load", "load_fraction"), "load")
    throttle = _column(tables["load_throttle_trace_path"], ("throttle", "throttle_pct", "throttle_fraction"), "throttle")
    gear = _column(tables["gear_shift_trace_path"], ("gear", "gear_index", "gear_number"), "gear")
    shift = _column(tables["gear_shift_trace_path"], ("shift_event", "shift", "gear_shift"), "shift_event", required=False)
    if shift is None:
        shift = [0.0] + [1.0 if b != a else 0.0 for a, b in zip(gear, gear[1:])]
        shift_source = "derived_from_synchronized_gear"
    else:
        shift_source = "recorded_trace_column"
    fields = {"rpm": (rpm_time, rpm), "load": (load_time, load), "throttle": (load_time, throttle), "gear": (gear_time, gear), "shift_event": (gear_time, shift)}
    for name, (time_values, values) in fields.items():
        if len(time_values) != len(values) or len(time_values) < 2:
            raise RawReferenceContractError(f"state {name} and time lengths are inconsistent")
        if any(not math.isfinite(float(value)) for value in time_values):
            raise RawReferenceContractError(f"state {name} time contains non-finite values")
        if any(not (float(a) < float(b)) for a, b in zip(time_values, time_values[1:])):
            raise RawReferenceContractError(f"state {name} time must be strictly increasing")
        if any(not math.isfinite(float(value)) for value in values):
            raise RawReferenceContractError(f"state {name} contains non-finite values")
        if time_values[0] > start_s or time_values[-1] < end_s:
            raise RawReferenceContractError(f"state {name} does not cover the requested time window")
    if any(value <= 0 for value in rpm):
        raise RawReferenceContractError("RPM trace must be positive")
    if any(value < 0 or value > 1 for value in load + throttle):
        raise RawReferenceContractError("load/throttle traces must use fraction_0_1 in [0, 1]")
    if any(value < 0 for value in gear) or any(value not in (0, 1) for value in shift):
        raise RawReferenceContractError("gear/shift values are outside the declared units")
    return {
        "trace_root": str(_trace_root(state, root)),
        "rpm_trace_path": str(paths["rpm_trace_path"]),
        "load_throttle_trace_path": str(paths["load_throttle_trace_path"]),
        "gear_shift_trace_path": str(paths["gear_shift_trace_path"]),
        "raw_trace_sha256": {key: _sha256(path) for key, path in paths.items()},
        "row_counts": {key: len(_column(tables[key], ("time_s", "timestamp_s", "time"), key) or []) for key in paths},
        "time_window": {"start_s": start_s, "end_s": end_s},
        "units": units,
        "shift_source": shift_source,
        "synchronization": "timestamp_bound_state_traces",
    }


def _base_record(spec: Mapping[str, Any], audio_path: Path, audio: Mapping[str, Any], audio_sha256: str) -> dict[str, Any]:
    recording_id = str(spec.get("recording_id") or "").strip()
    vehicle_id = str(spec.get("vehicle_id") or "").strip()
    scenario = str(spec.get("scenario") or "").strip()
    exact_trim = str(spec.get("exact_vehicle_trim") or "").strip()
    source_kind = str(spec.get("source_kind") or "controlled_raw_audio").strip()
    return {
        "schema_version": SCHEMA_VERSION,
        "recording_id": recording_id,
        "reference_id": "r1:" + hashlib.sha256(recording_id.encode("utf-8")).hexdigest()[:16],
        "vehicle_id": vehicle_id,
        "scenario": scenario,
        "external_path": str(audio_path),
        "relative_path": audio_path.name,
        "sha256": audio_sha256,
        "file_present": True,
        "audio": dict(audio),
        "source_url": spec.get("source_url"),
        "provenance": {
            "source_kind": source_kind,
            "source_url": spec.get("source_url"),
            "source_alias": spec.get("source_alias"),
            "legal_permission": spec.get("license_status") or spec.get("legal_permission") or "UNVERIFIED",
            "rights_evidence": spec.get("rights_evidence"),
            "exact_vehicle_trim": exact_trim,
            "stock_identity": "VERIFIED_EXACT_TRIM" if exact_trim else "UNVERIFIED",
            "stock_exhaust_confirmation": spec.get("stock_exhaust_confirmation"),
            "microphone_perspective": spec.get("microphone_position") or "UNKNOWN",
            "recording_device_agc": spec.get("recording_device_agc") or "UNKNOWN",
            "raw_audio_confirmed": bool(spec.get("raw_audio_confirmed")),
            "raw_media_stored_outside_git": True,
        },
        "analysis_contract": {
            "analysis_signal": "unaltered_analysis_signal",
            "rpm_state_status": "MISSING_RPM_STATE",
            "load_throttle_status": "MISSING",
            "gear_shift_status": "MISSING",
            "estimated_rpm_status": "NOT_ATTEMPTED",
            "loudness_matched_audition_signal": "NOT_CREATED",
        },
    }


def _record_spec(spec: Mapping[str, Any], *, root: Path) -> dict[str, Any]:
    if not isinstance(spec, Mapping):
        raise RawReferenceContractError("each raw reference spec must be an object")
    raw_audio = spec.get("audio_path")
    if not raw_audio:
        raise RawReferenceContractError("audio_path is required")
    audio_candidate = Path(str(raw_audio))
    if not audio_candidate.is_absolute():
        audio_candidate = root / audio_candidate
    audio_path = _inside(root, audio_candidate, "audio_path")
    if not audio_path.is_file():
        raise RawReferenceContractError(f"original audio does not exist: {audio_path}")
    audio = _audio_metadata(audio_path)
    record = _base_record(spec, audio_path, audio, _sha256(audio_path))
    state_error: str | None = None
    try:
        state = _validate_state(spec.get("state") or {}, root=root, audio=audio)
        record["state_bindings"] = state
        record["time_window"] = state["time_window"]
        record["analysis_contract"].update(
            {
                "rpm_state_status": "SYNCED",
                "load_throttle_status": "SYNCED",
                "gear_shift_status": "SYNCED",
                "trace_paths": {key: state[key] for key in ("rpm_trace_path", "load_throttle_trace_path", "gear_shift_trace_path")},
                "state_units": state["units"],
                "state_synchronization": state["synchronization"],
            }
        )
    except RawReferenceContractError as exc:
        state_error = str(exc)
        record["state_validation_error"] = state_error
    r1_gate = qualify_r1_reference(record)
    r2_gate = qualify_r2_reference(record)
    if r1_gate["eligible"]:
        level = "R1"
    elif r2_gate["eligible"]:
        level = "R2"
    else:
        level = "R3"
    record["evidence"] = {
        "level": level,
        "r1_gate": r1_gate,
        "r2_gate": r2_gate,
        "r1_eligible": bool(r1_gate["eligible"]),
        "r2_eligible": bool(r2_gate["eligible"]),
        "automatic_tuning_eligible": False,
        "order_hard_gate": bool(r1_gate["eligible"]),
        "reason": "R1 原始音频与同步状态合同通过。" if r1_gate["eligible"] else state_error or "R1 合同不完整，保持有限或定性证据。",
    }
    return record


def render_raw_intake_report(manifest: Mapping[str, Any]) -> str:
    lines = [
        "# S12 原始音频与同步状态入库审计",
        "",
        f"状态：`{manifest.get('status', 'UNKNOWN')}`；R1 数量：`{manifest.get('r1_count', 0)}`。",
        "",
        "原始音频和状态文件只保留在批准的外部目录；本报告不复制 WAV/FLAC，不做增益、EQ、AGC 或采样率改写。",
        "",
        "| 记录 | 车型 | 工况 | 证据 | 音频 SHA | 状态同步 | 限制 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for record in manifest.get("records", []):
        evidence = record.get("evidence", {})
        lines.append(
            f"| `{record.get('recording_id', '—')}` | `{record.get('vehicle_id') or '—'}` | `{record.get('scenario') or '—'}` | `{evidence.get('level', 'ERROR')}` | `{str(record.get('sha256') or '—')[:12]}` | `{record.get('analysis_contract', {}).get('rpm_state_status', '—')}` | {evidence.get('reason') or record.get('state_validation_error') or '—'} |"
        )
    lines.extend(
        [
            "",
            "R1 记录仍必须通过 Stage R 的 WAV/FLAC、状态长度、单位、时间窗口、SHA 绑定和 MATLAB/MoSQITo 收据；本入库状态不会自动启动调参。",
            "",
        ]
    )
    return "\n".join(lines)


def ingest_raw_reference_specs(
    specs: Iterable[Mapping[str, Any]],
    *,
    output_root: Path,
    allowed_root: Path = ALLOWED_DOWNLOAD_ROOT,
) -> dict[str, Any]:
    """Validate external original-audio specs without copying raw media."""

    allowed_root = Path(allowed_root).resolve()
    # The audit manifest is intentionally allowed in the repository or another
    # caller-selected metadata root; only raw audio and state paths are fenced
    # to the approved external download root.
    output_root = Path(output_root).resolve()
    if (output_root / "reference_manifest.json").exists() or (output_root / "R1_Reference_Intake_Report.md").exists():
        raise RawReferenceContractError(f"refusing to overwrite existing raw-intake audit files: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for index, spec in enumerate(specs, start=1):
        try:
            records.append(_record_spec(spec, root=allowed_root))
        except RawReferencePathError:
            raise
        except (OSError, RawReferenceContractError, TypeError) as exc:
            records.append(
                {
                    "recording_id": f"raw_spec_{index:02d}",
                    "status": "RAW_REFERENCE_INTAKE_REJECTED",
                    "error": str(exc),
                    "evidence": {"level": "R3", "r1_eligible": False, "r2_eligible": False, "automatic_tuning_eligible": False},
                }
            )
    r1_count = sum(record.get("evidence", {}).get("r1_eligible") is True for record in records)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "R1_REFERENCE_PACKAGE_READY" if records and r1_count == len(records) else "R1_REFERENCE_PACKAGE_LIMITED",
        "allowed_download_root": str(allowed_root),
        "raw_media_policy": "external_only_not_in_git",
        "records": records,
        "r1_count": r1_count,
        "automatic_tuning_eligible": False,
        "profile_freeze_authorized": False,
    }
    (output_root / "reference_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (output_root / "R1_Reference_Intake_Report.md").write_text(render_raw_intake_report(manifest), encoding="utf-8", newline="\n")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="审计外部原始 WAV/FLAC 与同步状态合同，不复制原始媒体")
    parser.add_argument("--spec-json", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    specs = json.loads(args.spec_json.read_text(encoding="utf-8"))
    if not isinstance(specs, list):
        parser.error("--spec-json must contain a JSON array")
    manifest = ingest_raw_reference_specs(specs, output_root=args.output_root)
    print(f"status={manifest['status']}")
    print(f"records={len(manifest['records'])}")
    print(f"r1_count={manifest['r1_count']}")
    return 0 if manifest["status"] == "R1_REFERENCE_PACKAGE_READY" else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "ALLOWED_DOWNLOAD_ROOT",
    "RawReferenceContractError",
    "RawReferenceIntakeError",
    "RawReferencePathError",
    "SCHEMA_VERSION",
    "ingest_raw_reference_specs",
    "render_raw_intake_report",
]
