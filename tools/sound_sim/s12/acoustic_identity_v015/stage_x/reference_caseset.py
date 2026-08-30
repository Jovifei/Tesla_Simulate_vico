"""Stage X/Y scenario-bound reference case set.

The case set keeps scenario windows and independent recordings as different
concepts. A single recording split into several windows can support several
diagnostic scenarios but counts only once at the engineering selection gate.
Video-derived audio is always R3 regardless of a legacy manifest label.
"""

from __future__ import annotations

import hashlib
import json
import re
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .reference_governance import (
    classify_reference_evidence,
    effective_caseset_evidence,
    source_identity,
    summarize_reference_cases,
)

CASESET_SCHEMA = "s12.stage_y.reference_case_set.v2"
CASE_SCHEMA = "s12.stage_y.reference_case.v2"

SCENARIOS = (
    "hot_idle",
    "steady_low",
    "steady_mid",
    "steady_high",
    "tip_in",
    "full_pull",
    "shift",
    "lift",
    "afterfire",
    "idle_return",
)

SPEECH_BAND_LO_HZ = 300.0
SPEECH_BAND_HI_HZ = 3400.0
ANALYSIS_LO_HZ = 60.0
ANALYSIS_HI_HZ = 11000.0
SYLLABIC_LO_HZ = 2.0
SYLLABIC_HI_HZ = 8.0
SPEECH_PROB_REJECT = 0.50
ENGINE_TO_SPEECH_RATIO_REJECT_DB = -3.0


@dataclass
class ReferenceCase:
    vehicle_id: str
    scenario: str
    reference_id: str
    source_id: str
    recording_session_id: str
    audio_path: str
    audio_sha256: str
    evidence_level: str
    rights_status: str
    sample_rate: int
    start_s: float
    end_s: float
    microphone_position: str
    agc_post_processing: str
    speech_music_contamination: dict[str, Any]
    rpm_trace: list[float] | None
    load_trace: list[float] | None
    gear_trace: list[float] | None
    uncertainty: dict[str, Any]
    allowed_metrics: list[str]
    status: str = "BOUND"
    segment_sha256: str = ""
    rejection_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CASE_SCHEMA,
            "vehicle_id": self.vehicle_id,
            "scenario": self.scenario,
            "reference_id": self.reference_id,
            "source_id": self.source_id,
            "recording_session_id": self.recording_session_id,
            "audio_path": self.audio_path,
            "audio_sha256": self.audio_sha256,
            "segment_sha256": self.segment_sha256,
            "evidence_level": self.evidence_level,
            "rights_status": self.rights_status,
            "sample_rate": self.sample_rate,
            "start_s": self.start_s,
            "end_s": self.end_s,
            "microphone_position": self.microphone_position,
            "agc_post_processing": self.agc_post_processing,
            "speech_music_contamination": self.speech_music_contamination,
            "rpm_trace": self.rpm_trace,
            "load_trace": self.load_trace,
            "gear_trace": self.gear_trace,
            "uncertainty": self.uncertainty,
            "allowed_metrics": self.allowed_metrics,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
        }


def _decode_pcm24(raw: bytes) -> np.ndarray:
    values = np.frombuffer(raw, dtype=np.uint8)
    if values.size % 3:
        raise ValueError("invalid PCM24 byte count")
    triples = values.reshape(-1, 3).astype(np.int32)
    signed = triples[:, 0] | (triples[:, 1] << 8) | (triples[:, 2] << 16)
    signed = np.where(signed & 0x800000, signed - 0x1000000, signed)
    return signed.astype(np.float64) / 8388608.0


def read_wav_mono(path: str | Path) -> tuple[np.ndarray, int]:
    """Read integer PCM WAV as finite float64 mono."""
    source = Path(path)
    if source.suffix.lower() != ".wav":
        raise ValueError(
            f"reference decoder currently requires WAV; convert FLAC losslessly first: {source}"
        )
    with wave.open(str(source), "rb") as handle:
        sample_rate = int(handle.getframerate())
        channels = int(handle.getnchannels())
        width = int(handle.getsampwidth())
        raw = handle.readframes(handle.getnframes())
    if width == 2:
        frames = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    elif width == 3:
        frames = _decode_pcm24(raw)
    elif width == 4:
        frames = np.frombuffer(raw, dtype="<i4").astype(np.float64) / 2147483648.0
    else:
        raise ValueError(f"unsupported PCM width {width * 8}-bit: {source}")
    if channels > 1:
        if frames.size % channels:
            raise ValueError(f"PCM channel topology is invalid: {source}")
        frames = frames.reshape(-1, channels).mean(axis=1)
    if not np.all(np.isfinite(frames)):
        raise ValueError(f"reference PCM is not finite: {source}")
    return frames, sample_rate


def _linear_resample(audio: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate:
        return np.asarray(audio, dtype=np.float64).copy()
    if source_rate <= 0 or target_rate <= 0:
        raise ValueError("sample rates must be positive")
    values = np.asarray(audio, dtype=np.float64)
    if values.size < 2:
        return values.copy()
    target_count = max(1, int(round(values.size * target_rate / source_rate)))
    source_x = np.linspace(0.0, 1.0, values.size, endpoint=False)
    target_x = np.linspace(0.0, 1.0, target_count, endpoint=False)
    return np.interp(target_x, source_x, values).astype(np.float64)


def _stft_magnitude(audio: np.ndarray, frame: int = 2048, hop: int = 512) -> tuple[np.ndarray, int]:
    values = np.asarray(audio, dtype=np.float64)
    minimum = frame + hop
    if values.size < minimum:
        values = np.pad(values, (0, minimum - values.size))
    count = 1 + (values.size - frame) // hop
    window = np.hanning(frame)
    spectra = np.stack(
        [
            np.abs(np.fft.rfft(values[index * hop : index * hop + frame] * window))
            for index in range(count)
        ]
    )
    return spectra, hop


def detect_speech(audio: np.ndarray, sample_rate: int) -> dict[str, Any]:
    """Deterministic speech-contamination heuristic."""
    spectra, hop = _stft_magnitude(audio)
    freqs = np.fft.rfftfreq(2048, 1.0 / sample_rate)
    analysis = spectra[:, (freqs >= ANALYSIS_LO_HZ) & (freqs <= ANALYSIS_HI_HZ)]
    speech = spectra[:, (freqs >= SPEECH_BAND_LO_HZ) & (freqs <= SPEECH_BAND_HI_HZ)]
    low = spectra[:, (freqs >= ANALYSIS_LO_HZ) & (freqs < SPEECH_BAND_LO_HZ)]
    high = spectra[:, (freqs > SPEECH_BAND_HI_HZ) & (freqs <= ANALYSIS_HI_HZ)]
    total_power = float(np.sum(np.square(analysis))) + 1.0e-12
    speech_power = float(np.sum(np.square(speech)))
    speech_ratio = speech_power / total_power
    engine_power = float(np.sum(np.square(low)) + np.sum(np.square(high)))
    engine_to_speech_ratio_db = 10.0 * np.log10(
        max(engine_power, 1.0e-12) / max(speech_power, 1.0e-12)
    )

    envelope = np.sqrt(np.mean(np.square(speech), axis=1) + 1.0e-15)
    envelope_mean = float(np.mean(envelope))
    modulation_depth = float(np.std(envelope) / envelope_mean) if envelope_mean > 1.0e-9 else 0.0
    if envelope.size >= 16 and modulation_depth > 1.0e-6:
        modulation = np.abs(np.fft.rfft((envelope - envelope_mean) * np.hanning(envelope.size)))
        mod_freqs = np.fft.rfftfreq(envelope.size, d=hop / sample_rate)
        syllabic_ratio = float(
            np.sum(np.square(modulation[(mod_freqs >= SYLLABIC_LO_HZ) & (mod_freqs <= SYLLABIC_HI_HZ)]))
            / (np.sum(np.square(modulation)) + 1.0e-15)
        )
    else:
        syllabic_ratio = 0.0
    band_score = float(np.clip(speech_ratio / 0.50, 0.0, 1.0))
    syllabic_score = float(
        np.clip(modulation_depth / 0.40, 0.0, 1.0)
        * np.clip(syllabic_ratio / 0.30, 0.0, 1.0)
    )
    probability = float(np.clip(0.5 * band_score + 0.5 * syllabic_score, 0.0, 1.0))
    contaminated = bool(
        probability >= SPEECH_PROB_REJECT
        or engine_to_speech_ratio_db < ENGINE_TO_SPEECH_RATIO_REJECT_DB
    )
    return {
        "detector": "s12_stage_y_speech_band_heuristic_v2",
        "speech_band_energy_ratio": speech_ratio,
        "modulation_depth": modulation_depth,
        "syllabic_modulation_ratio": syllabic_ratio,
        "engine_to_speech_ratio_db": engine_to_speech_ratio_db,
        "speech_probability": probability,
        "speech_contaminated": contaminated,
        "thresholds": {
            "speech_probability_reject": SPEECH_PROB_REJECT,
            "engine_to_speech_ratio_reject_db": ENGINE_TO_SPEECH_RATIO_REJECT_DB,
        },
    }


def _cleanest_subwindow(
    audio: np.ndarray,
    sample_rate: int,
    start: float,
    end: float,
    *,
    min_duration_s: float = 4.0,
    step_s: float = 2.0,
) -> tuple[tuple[float, float], dict[str, Any]] | None:
    duration = end - start
    if duration <= min_duration_s:
        detection = detect_speech(audio[int(start * sample_rate) : int(end * sample_rate)], sample_rate)
        return ((start, end), detection) if not detection["speech_contaminated"] else None
    candidates: list[tuple[float, dict[str, Any]]] = []
    offset = 0.0
    while offset + min_duration_s <= duration + 1.0e-9:
        sub_start = start + offset
        sub_end = sub_start + min_duration_s
        detection = detect_speech(audio[int(sub_start * sample_rate) : int(sub_end * sample_rate)], sample_rate)
        if not detection["speech_contaminated"]:
            candidates.append((offset, detection))
        offset += step_s
    if not candidates:
        return None
    offset, detection = min(
        candidates,
        key=lambda item: (item[1]["speech_probability"], -item[1]["engine_to_speech_ratio_db"]),
    )
    return (start + offset, start + offset + min_duration_s), detection


def _segment_hash(audio: np.ndarray, sample_rate: int, start: float, end: float) -> str:
    segment = np.ascontiguousarray(
        audio[int(start * sample_rate) : int(end * sample_rate)],
        dtype=np.float64,
    )
    digest = hashlib.sha256()
    digest.update(str(sample_rate).encode("ascii"))
    digest.update(f"{start:.9f}:{end:.9f}".encode("ascii"))
    digest.update(segment.tobytes())
    return digest.hexdigest()


_SEGMENT_MAP = {
    "hot_idle": "idle",
    "steady_low": "steady_rpm",
    "steady_mid": "steady_rpm",
    "steady_high": "steady_rpm",
    "tip_in": "acceleration",
    "full_pull": "acceleration",
    "shift": "acceleration",
    "lift": "deceleration",
    "afterfire": "deceleration",
    "idle_return": "deceleration",
}


def _parse_window(intent: str) -> tuple[float, float] | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*s?", intent)
    if not match:
        return None
    start, end = float(match.group(1)), float(match.group(2))
    return (start, end) if end > start else None


def _rights_for_level(level: str) -> str:
    if level == "R1":
        return "R1_RIGHTS_CLEARED"
    if level.startswith("R2"):
        return "R2_RELATIVE_REVIEW_ONLY"
    return "R3_PRIVATE_DIAGNOSTIC_ONLY"


def _allowed_metrics(level: str, synchronized_rpm: bool) -> list[str]:
    allowed = ["raw_dynamic", "loudness_matched_timbre", "psychoacoustic_relative"]
    if level == "R1" and synchronized_rpm:
        allowed.append("order_domain")
    return allowed


def _build_case(
    *,
    vehicle_id: str,
    scenario: str,
    audio_path: Path,
    audio_sha256: str,
    audio: np.ndarray,
    sample_rate: int,
    start: float,
    end: float,
    source_record: dict[str, Any],
    human_note: str | None,
) -> ReferenceCase:
    evidence = classify_reference_evidence(source_record)
    identity = source_identity({**source_record, "audio_path": str(audio_path), "audio_sha256": audio_sha256})
    segment = audio[int(start * sample_rate) : int(end * sample_rate)]
    detection = detect_speech(segment, sample_rate)
    if detection["speech_contaminated"]:
        refined = _cleanest_subwindow(audio, sample_rate, start, end)
        if refined is not None:
            (start, end), detection = refined
            detection["subwindow_refined"] = True
    if human_note:
        detection["human_review"] = human_note
        detection["speech_contaminated"] = True

    level = evidence["effective_evidence_level"]
    synchronized = bool(source_record.get("synchronized_state"))
    case = ReferenceCase(
        vehicle_id=vehicle_id,
        scenario=scenario,
        reference_id=f"{vehicle_id}:{identity['source_id']}:{scenario}:{start:.3f}-{end:.3f}",
        source_id=identity["source_id"],
        recording_session_id=identity["recording_session_id"],
        audio_path=str(audio_path),
        audio_sha256=audio_sha256,
        evidence_level=level,
        rights_status=_rights_for_level(level),
        sample_rate=sample_rate,
        start_s=start,
        end_s=end,
        microphone_position=str(source_record.get("microphone_position") or "UNVERIFIED"),
        agc_post_processing=str(
            source_record.get("agc_post_processing")
            or source_record.get("recording_device_agc")
            or "UNKNOWN_AGC_POSSIBLE"
        ),
        speech_music_contamination=detection,
        rpm_trace=source_record.get("rpm_trace"),
        load_trace=source_record.get("load_trace"),
        gear_trace=source_record.get("gear_trace"),
        uncertainty={
            "rpm_synchronised": synchronized,
            "stock_state_verified": bool(source_record.get("stock_state_verified")),
            "agc_verified": bool(source_record.get("agc_verified")),
            "evidence_governance": evidence,
            "notes": source_record.get("risk") or source_record.get("notes") or "",
        },
        allowed_metrics=_allowed_metrics(level, synchronized),
    )
    case.segment_sha256 = _segment_hash(audio, sample_rate, start, end)
    if detection["speech_contaminated"]:
        case.status = "REJECTED_SPEECH_CONTAMINATED"
        case.rejection_reason = "speech detector or human review rejected segment"
    return case


def _finish_receipt(
    vehicle_id: str,
    cases: list[ReferenceCase],
    unavailable: list[dict[str, Any]],
    source_audio: list[dict[str, Any]],
    *,
    human_confirmation_applied: bool,
) -> dict[str, Any]:
    case_dicts = [case.to_dict() for case in cases]
    summary = summarize_reference_cases(case_dicts)
    return {
        "schema": CASESET_SCHEMA,
        "vehicle_id": vehicle_id,
        "reference_evidence_level": effective_caseset_evidence(case_dicts),
        "source_audio": source_audio,
        "cases": case_dicts,
        "scenario_unavailable": unavailable,
        **summary,
        "valid_reference_count": summary["selection_reference_count"],
        "cleanliness_receipt": {
            "detector": "s12_stage_y_speech_band_heuristic_v2",
            "human_confirmation_applied": human_confirmation_applied,
            "minimum_engine_to_speech_ratio_db": ENGINE_TO_SPEECH_RATIO_REJECT_DB,
            "rejected_scenarios": [case.scenario for case in cases if case.status != "BOUND"],
            "note": (
                "R2/R3 never becomes R1; order metrics require synchronized RPM. "
                "Multiple windows from one recording count once."
            ),
        },
        "scope": (
            "relative engineering review only; no OEM likeness, calibration, "
            "Profile Freeze, or automatic tuning authority"
        ),
    }


def build_reference_caseset(
    vehicle_id: str,
    manifest_path: str | Path,
    audio_dir: str | Path,
    *,
    human_speech_confirmations: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build cases from the legacy vehicle manifest without evidence promotion."""
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    record = manifest["vehicles"][vehicle_id]
    media = record["external_media"]
    video_id = media.get("video_id")
    if not video_id:
        raise ValueError(f"{vehicle_id} has no external media binding")
    audio_path = Path(audio_dir) / f"{video_id}.wav"
    digest = hashlib.sha256(audio_path.read_bytes()).hexdigest()
    if digest.lower() != str(media["sha256"]).lower():
        raise ValueError(f"{vehicle_id} reference audio SHA mismatch: {audio_path}")
    audio, sample_rate = read_wav_mono(audio_path)
    speech_confirmations = dict(human_speech_confirmations or {})
    human_note = speech_confirmations.get(vehicle_id)

    source_record = {
        **record,
        **media,
        "external_media": media,
        "audio_path": str(audio_path),
        "audio_sha256": digest,
        "source_url": media.get("source_url"),
        "extraction": media.get("extraction"),
        "rights_status": record.get("rights_status", "UNVERIFIED_PUBLIC_VIDEO"),
        "source_level": record.get("source_level", "R3"),
        "risk": (record.get("recording") or {}).get("risk", ""),
    }
    segment_windows = {
        name: _parse_window(segment.get("intent", ""))
        for name, segment in record["segments"].items()
    }
    cases: list[ReferenceCase] = []
    unavailable: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        segment_name = _SEGMENT_MAP[scenario]
        window = segment_windows.get(segment_name)
        if window is None:
            unavailable.append({
                "scenario": scenario,
                "status": "SCENARIO_REFERENCE_UNAVAILABLE",
                "reason": f"no annotated {segment_name} window",
            })
            continue
        start, end = window
        end = min(end, audio.size / sample_rate)
        if end - start < 1.0:
            unavailable.append({
                "scenario": scenario,
                "status": "SCENARIO_REFERENCE_UNAVAILABLE",
                "reason": "bounded window shorter than one second",
            })
            continue
        cases.append(_build_case(
            vehicle_id=vehicle_id,
            scenario=scenario,
            audio_path=audio_path,
            audio_sha256=digest,
            audio=audio,
            sample_rate=sample_rate,
            start=start,
            end=end,
            source_record=source_record,
            human_note=human_note,
        ))
    return _finish_receipt(
        vehicle_id,
        cases,
        unavailable,
        [{
            "source_id": source_identity(source_record)["source_id"],
            "audio_path": str(audio_path),
            "audio_sha256": digest,
            "sample_rate": sample_rate,
            "duration_s": audio.size / sample_rate,
            "evidence_governance": classify_reference_evidence(source_record),
        }],
        human_confirmation_applied=bool(human_note),
    )


def build_reference_caseset_from_registry(
    vehicle_id: str,
    registry_path: str | Path,
    *,
    human_speech_confirmations: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build cases from a canonical registry containing external audio pointers."""
    registry = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    if isinstance(registry, list):
        records = registry
    elif isinstance(registry.get("records"), list):
        records = registry["records"]
    else:
        vehicle = (registry.get("vehicles") or {}).get(vehicle_id, {})
        records = vehicle.get("records") or vehicle.get("references") or []
    selected = [dict(record) for record in records if str(record.get("vehicle_id")) == vehicle_id]
    if not selected:
        raise ValueError(f"canonical registry has no records for {vehicle_id}")

    human_note = (human_speech_confirmations or {}).get(vehicle_id)
    cases: list[ReferenceCase] = []
    unavailable: list[dict[str, Any]] = []
    source_audio: list[dict[str, Any]] = []
    for record in selected:
        scenario = str(record.get("scenario") or "")
        if scenario not in SCENARIOS:
            unavailable.append({
                "recording_id": record.get("recording_id"),
                "status": "SCENARIO_REFERENCE_UNAVAILABLE",
                "reason": f"unsupported or missing scenario: {scenario!r}",
            })
            continue
        audio_path = Path(str(record.get("audio_path") or ""))
        if not audio_path.is_file():
            raise ValueError(f"external reference file missing: {audio_path}")
        digest = hashlib.sha256(audio_path.read_bytes()).hexdigest()
        expected = str(record.get("audio_sha256") or record.get("sha256") or "")
        if expected and digest.lower() != expected.lower():
            raise ValueError(f"reference audio SHA mismatch: {audio_path}")
        audio, sample_rate = read_wav_mono(audio_path)
        start = float(record.get("start_s", 0.0))
        end = float(record.get("end_s", audio.size / sample_rate))
        end = min(end, audio.size / sample_rate)
        if end <= start:
            raise ValueError(f"invalid reference window: {audio_path}")
        record = {**record, "audio_path": str(audio_path), "audio_sha256": digest}
        case = _build_case(
            vehicle_id=vehicle_id,
            scenario=scenario,
            audio_path=audio_path,
            audio_sha256=digest,
            audio=audio,
            sample_rate=sample_rate,
            start=start,
            end=end,
            source_record=record,
            human_note=human_note,
        )
        cases.append(case)
        identity = source_identity(record)
        source_audio.append({
            **identity,
            "audio_path": str(audio_path),
            "sample_rate": sample_rate,
            "duration_s": audio.size / sample_rate,
            "evidence_governance": classify_reference_evidence(record),
        })
    return _finish_receipt(
        vehicle_id,
        cases,
        unavailable,
        source_audio,
        human_confirmation_applied=bool(human_note),
    )


def load_case_segment_audio(
    case: dict[str, Any],
    *,
    target_sample_rate: int | None = None,
) -> tuple[np.ndarray, int]:
    """Load one bound segment and optionally resample it deterministically."""
    if case["status"] != "BOUND":
        raise ValueError(f"reference case is not bound: {case['scenario']} / {case['status']}")
    audio, sample_rate = read_wav_mono(case["audio_path"])
    start = int(round(float(case["start_s"]) * sample_rate))
    end = int(round(float(case["end_s"]) * sample_rate))
    segment = audio[start:end]
    if target_sample_rate is not None and target_sample_rate != sample_rate:
        segment = _linear_resample(segment, sample_rate, target_sample_rate)
        sample_rate = int(target_sample_rate)
    return segment, sample_rate


__all__ = [
    "CASESET_SCHEMA",
    "SCENARIOS",
    "ReferenceCase",
    "build_reference_caseset",
    "build_reference_caseset_from_registry",
    "detect_speech",
    "load_case_segment_audio",
    "read_wav_mono",
]
