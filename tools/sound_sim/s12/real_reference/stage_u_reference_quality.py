"""Fail-closed reference speech, integrity and scenario-quality gates for Stage U."""
from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np
from scipy.io import wavfile


DEFAULT_CONTINUOUS_SPEECH_THRESHOLD_S = 1.0


class ReferenceQualityError(ValueError):
    """Raised when reference quality metadata is incomplete or forged."""


Vad = Callable[[np.ndarray, int], Iterable[tuple[float, float]]]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _audio(path: Path) -> tuple[np.ndarray, int, int, float]:
    if not path.is_file():
        raise ReferenceQualityError(f"reference file missing: {path}")
    try:
        sample_rate_hz, signal = wavfile.read(str(path))
    except Exception as exc:
        raise ReferenceQualityError(f"reference audio cannot be decoded: {path}") from exc
    values = np.asarray(signal)
    if values.size == 0 or values.shape[0] == 0 or sample_rate_hz <= 0:
        raise ReferenceQualityError(f"reference audio is zero-duration: {path}")
    if not np.issubdtype(values.dtype, np.integer) and not np.isfinite(values).all():
        raise ReferenceQualityError(f"reference audio is non-finite: {path}")
    mono = values.mean(axis=1) if values.ndim > 1 else values
    channels = int(values.shape[1]) if values.ndim > 1 else 1
    return np.asarray(mono, dtype=np.float64), int(sample_rate_hz), channels, float(values.shape[0] / sample_rate_hz)


def _speech_intervals(vad: Vad, signal: np.ndarray, sample_rate_hz: int, label: str) -> list[tuple[float, float]]:
    intervals: list[tuple[float, float]] = []
    for item in vad(signal, sample_rate_hz):
        if not isinstance(item, tuple) or len(item) != 2:
            raise ReferenceQualityError(f"VAD returned malformed interval for {label}")
        start, end = float(item[0]), float(item[1])
        if not np.isfinite((start, end)).all() or start < 0.0 or end <= start:
            raise ReferenceQualityError(f"VAD returned invalid interval for {label}")
        intervals.append((start, end))
    return intervals


def silero_vad_segments(
    audio_path: Path,
    runner_python: Path,
    *,
    command_runner: Callable[..., Any] = subprocess.run,
) -> list[tuple[float, float]]:
    """Invoke the pinned external Silero runner and return second intervals."""

    script = Path(__file__).with_name("stage_u_silero_vad_runner.py")
    result = command_runner(
        [str(runner_python), str(script), "--audio", str(Path(audio_path).resolve())],
        capture_output=True,
        text=True,
        check=False,
    )
    if int(result.returncode) != 0:
        raise ReferenceQualityError(f"Silero VAD runner failed: {str(result.stderr).strip()}")
    try:
        payload = json.loads(str(result.stdout))
    except json.JSONDecodeError as exc:
        raise ReferenceQualityError("Silero VAD runner returned invalid JSON") from exc
    if not isinstance(payload, list):
        raise ReferenceQualityError("Silero VAD runner must return an interval list")
    intervals: list[tuple[float, float]] = []
    for row in payload:
        if not isinstance(row, Mapping):
            raise ReferenceQualityError("Silero VAD interval is malformed")
        start, end = row.get("start_s"), row.get("end_s")
        if isinstance(start, bool) or isinstance(end, bool):
            raise ReferenceQualityError("Silero VAD interval is invalid")
        try:
            interval = (float(start), float(end))
        except (TypeError, ValueError) as exc:
            raise ReferenceQualityError("Silero VAD interval is invalid") from exc
        intervals.append(interval)
    return intervals


def validate_reference_quality(
    records: Sequence[Mapping[str, Any]],
    vad: Vad,
    *,
    continuous_speech_threshold_s: float = DEFAULT_CONTINUOUS_SPEECH_THRESHOLD_S,
) -> list[dict[str, Any]]:
    """Validate reference inputs before a candidate grid can be rendered."""

    if not callable(vad) or not np.isfinite(continuous_speech_threshold_s) or continuous_speech_threshold_s <= 0.0:
        raise ReferenceQualityError("VAD and a positive continuous speech threshold are required")
    candidate_scenarios: dict[str, set[str]] = {}
    normalized: list[dict[str, Any]] = []
    for record in records:
        reference_id = str(record.get("reference_id") or "")
        path = Path(str(record.get("reference_path") or ""))
        declared_sha = str(record.get("reference_sha256") or "").lower()
        scenario = str(record.get("scenario") or "")
        matching_scenario = str(record.get("matching_trace_scenario") or "")
        candidate_audio_id = str(record.get("candidate_audio_id") or "")
        if not all((reference_id, scenario, matching_scenario, candidate_audio_id)):
            raise ReferenceQualityError("reference_id, scenario, matching_trace_scenario and candidate_audio_id are required")
        actual_sha = _sha256(path)
        if declared_sha != actual_sha:
            raise ReferenceQualityError(f"reference SHA mismatch: {reference_id}")
        signal, sample_rate_hz, channels, duration_s = _audio(path)
        speech = _speech_intervals(vad, signal, sample_rate_hz, reference_id)
        max_speech_s = max((end - start for start, end in speech), default=0.0)
        candidate_scenarios.setdefault(candidate_audio_id, set()).add(scenario)
        normalized.append({
            "reference_id": reference_id,
            "vehicle_id": str(record.get("vehicle_id") or "UNKNOWN"),
            "scenario": scenario,
            "matching_trace_scenario": matching_scenario,
            "candidate_audio_id": candidate_audio_id,
            "reference_path": str(path.resolve()),
            "reference_sha256": actual_sha,
            "sample_rate_hz": sample_rate_hz,
            "channels": channels,
            "duration_s": duration_s,
            "microphone_uncertainty": str(record.get("microphone_uncertainty") or "UNKNOWN"),
            "manual_contamination_review": str(record.get("manual_contamination_review") or "NOT_REVIEWED"),
            "speech_intervals_s": speech,
            "longest_continuous_speech_s": max_speech_s,
            "speech_threshold_s": float(continuous_speech_threshold_s),
        })
    reused = {candidate_id for candidate_id, scenarios in candidate_scenarios.items() if len(scenarios) > 1}
    for row in normalized:
        speech_contaminated = row["longest_continuous_speech_s"] > continuous_speech_threshold_s
        scenario_compatible = row["scenario"] == row["matching_trace_scenario"]
        row["scenario_compatible"] = scenario_compatible
        if speech_contaminated:
            row["status"] = "REFERENCE_SPEECH_CONTAMINATED"
        elif row["candidate_audio_id"] in reused:
            row["status"] = "CANDIDATE_SCENARIO_REUSE_FORBIDDEN"
        elif not scenario_compatible:
            row["status"] = "SCENARIO_NOT_COMPARABLE"
        elif row["manual_contamination_review"] == "CONTAMINATED":
            row["status"] = "REFERENCE_MANUAL_CONTAMINATION"
        else:
            row["status"] = "REFERENCE_QUALITY_PASS"
        row["grid_eligible"] = row["status"] == "REFERENCE_QUALITY_PASS"
    return normalized


def summarize_reference_quality(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return a machine-readable matrix summary for Stage U reports."""

    rows = [dict(record) for record in records]
    return {
        "schema_version": "s12-stage-u-reference-quality-matrix-v1",
        "status": "REFERENCE_QUALITY_MATRIX_READY",
        "record_count": len(rows),
        "status_counts": dict(Counter(str(row.get("status")) for row in rows)),
        "eligible_count": sum(bool(row.get("grid_eligible")) for row in rows),
        "records": rows,
    }


__all__ = [
    "DEFAULT_CONTINUOUS_SPEECH_THRESHOLD_S",
    "ReferenceQualityError",
    "silero_vad_segments",
    "summarize_reference_quality",
    "validate_reference_quality",
]
