"""Stage X scenario-bound reference case set.

One reference case per bake-off scenario with evidence level, rights,
cleanliness and trace metadata. A single raw ndarray never represents a
whole vehicle. Speech-contaminated segments are rejected fail-closed.
"""

from __future__ import annotations

import hashlib
import json
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

CASESET_SCHEMA = "s12.stage_x.reference_case_set.v1"
CASE_SCHEMA = "s12.stage_x.reference_case.v1"

SCENARIOS = ("hot_idle", "steady_low", "steady_mid", "steady_high", "tip_in", "full_pull", "shift", "lift", "afterfire", "idle_return")

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


def read_wav_mono(path: str | Path) -> tuple[np.ndarray, int]:
    """Read a PCM WAV as float64 mono (-1..1) plus its sample rate."""
    with wave.open(str(path), "rb") as handle:
        sample_rate = handle.getframerate()
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        if width != 2:
            raise ValueError(f"only 16-bit PCM WAV is supported: {path}")
        frames = np.frombuffer(handle.readframes(handle.getnframes()), dtype="<i2").astype(np.float64) / 32768.0
    if channels > 1:
        frames = frames.reshape(-1, channels).mean(axis=1)
    return frames, int(sample_rate)


def _stft_magnitude(audio: np.ndarray, frame: int = 2048, hop: int = 512) -> tuple[np.ndarray, int]:
    window = np.hanning(frame)
    count = 1 + max(0, (audio.size - frame) // hop)
    if count < 2:
        raise ValueError("audio too short for speech analysis")
    spectra = np.stack([np.abs(np.fft.rfft(audio[i * hop : i * hop + frame] * window)) for i in range(count)])
    return spectra, hop


def detect_speech(audio: np.ndarray, sample_rate: int) -> dict[str, Any]:
    """Deterministic Silero-equivalent heuristic speech detector.

    Combines speech-band energy dominance with syllabic (2-8 Hz) envelope
    modulation of the speech band. Engine sound is dominated by low-order
    energy below 300 Hz and by shaft-locked modulation, not syllabic bursts.
    """
    spectra, hop = _stft_magnitude(audio)
    freqs = np.fft.rfftfreq(2048, 1.0 / sample_rate)
    band = spectra[:, (freqs >= ANALYSIS_LO_HZ) & (freqs <= ANALYSIS_HI_HZ)]
    speech = spectra[:, (freqs >= SPEECH_BAND_LO_HZ) & (freqs <= SPEECH_BAND_HI_HZ)]
    low = spectra[:, (freqs >= ANALYSIS_LO_HZ) & (freqs < SPEECH_BAND_LO_HZ)]
    high = spectra[:, (freqs > SPEECH_BAND_HI_HZ) & (freqs <= ANALYSIS_HI_HZ)]
    total_power = float(np.sum(band**2)) + 1e-12
    speech_ratio = float(np.sum(speech**2)) / total_power
    engine_power = float(np.sum(low**2) + np.sum(high**2))
    engine_to_speech_ratio_db = 10.0 * np.log10(max(engine_power, 1e-12) / max(float(np.sum(speech**2)), 1e-12))
    envelope = np.sqrt(np.mean(speech**2, axis=1))
    envelope_mean = float(np.mean(envelope))
    modulation_depth = float(np.std(envelope) / envelope_mean) if envelope_mean > 1e-9 else 0.0
    if envelope.size >= 16 and modulation_depth > 1e-6:
        modulation = np.abs(np.fft.rfft((envelope - envelope_mean) * np.hanning(envelope.size)))
        mod_freqs = np.fft.rfftfreq(envelope.size, d=hop / sample_rate)
        syllabic_ratio = float(np.sum(modulation[(mod_freqs >= SYLLABIC_LO_HZ) & (mod_freqs <= SYLLABIC_HI_HZ)] ** 2) / (np.sum(modulation**2) + 1e-15))
    else:
        syllabic_ratio = 0.0
    band_score = float(np.clip(speech_ratio / 0.50, 0.0, 1.0))
    syllabic_score = float(np.clip(modulation_depth / 0.40, 0.0, 1.0) * np.clip(syllabic_ratio / 0.30, 0.0, 1.0))
    probability = float(np.clip(0.5 * band_score + 0.5 * syllabic_score, 0.0, 1.0))
    contaminated = bool(probability >= SPEECH_PROB_REJECT or engine_to_speech_ratio_db < ENGINE_TO_SPEECH_RATIO_REJECT_DB)
    return {
        "detector": "s12_stage_x_speech_band_heuristic_v1",
        "speech_band_energy_ratio": speech_ratio,
        "modulation_depth": modulation_depth,
        "syllabic_modulation_ratio": syllabic_ratio,
        "engine_to_speech_ratio_db": engine_to_speech_ratio_db,
        "speech_probability": probability,
        "speech_contaminated": bool(contaminated),
        "thresholds": {
            "speech_probability_reject": SPEECH_PROB_REJECT,
            "engine_to_speech_ratio_reject_db": ENGINE_TO_SPEECH_RATIO_REJECT_DB,
        },
    }


def _cleanest_subwindow(audio: np.ndarray, sample_rate: int, start: float, end: float, *, min_duration_s: float = 4.0, step_s: float = 2.0) -> tuple[tuple[float, float], dict[str, Any]] | None:
    """Scan the annotated window for the cleanest passing sub-window.

    Keeps the manifest bounds authoritative while excluding narration or
    music pockets. Returns None when no sub-window passes the detector.
    """
    duration = end - start
    if duration <= min_duration_s:
        detection = detect_speech(audio[int(start * sample_rate) : int(end * sample_rate)], sample_rate)
        return ((start, end), detection) if not detection["speech_contaminated"] else None
    candidates: list[tuple[float, dict[str, Any]]] = []
    offset = 0.0
    while offset + min_duration_s <= duration + 1e-9:
        sub_start = start + offset
        sub_end = sub_start + min_duration_s
        detection = detect_speech(audio[int(sub_start * sample_rate) : int(sub_end * sample_rate)], sample_rate)
        if not detection["speech_contaminated"]:
            candidates.append((offset, detection))
        offset += step_s
    if not candidates:
        return None
    offset, detection = min(candidates, key=lambda item: item[1]["speech_probability"])
    return (start + offset, start + offset + min_duration_s), detection


def _segment_hash(path: Path, start: float, end: float) -> str:
    digest = hashlib.sha256()
    digest.update(str(path).encode("utf-8"))
    digest.update(f"{start:.3f}:{end:.3f}".encode("utf-8"))
    return digest.hexdigest()


# scenario -> manifest segment name ("__none__" = no legal binding window)
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
    """Extract the first 'a-b s' window from a manifest segment intent string."""
    digits: list[float] = []
    token = ""
    for char in intent:
        if char.isdigit() or char == ".":
            token += char
        elif token:
            digits.append(float(token))
            token = ""
            if len(digits) == 2:
                break
        elif char == "-":
            continue
    if len(digits) < 2 or digits[1] <= digits[0]:
        return None
    return digits[0], digits[1]


def build_reference_caseset(vehicle_id: str, manifest_path: str | Path, audio_dir: str | Path, *, human_speech_confirmations: dict[str, str] | None = None) -> dict[str, Any]:
    """Bind every scenario to an independent reference case from the R2 manifest."""
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    record = manifest["vehicles"][vehicle_id]
    media = record["external_media"]
    if not media.get("video_id"):
        raise ValueError(f"{vehicle_id} has no external R2 media binding")
    audio_path = Path(audio_dir) / f"{media['video_id']}.wav"
    digest = hashlib.sha256(audio_path.read_bytes()).hexdigest()
    if digest != media["sha256"]:
        raise ValueError(f"{vehicle_id} reference audio SHA mismatch: {audio_path}")
    audio, sample_rate = read_wav_mono(audio_path)
    speech_confirmations = dict(human_speech_confirmations or {})
    cases: list[ReferenceCase] = []
    unavailable: list[dict[str, Any]] = []
    segment_windows = {name: _parse_window(segment.get("intent", "")) for name, segment in record["segments"].items()}
    for scenario in SCENARIOS:
        segment_name = _SEGMENT_MAP[scenario]
        window = segment_windows.get(segment_name)
        if window is None:
            unavailable.append({"scenario": scenario, "status": "SCENARIO_REFERENCE_UNAVAILABLE", "reason": f"no annotated {segment_name} window"})
            continue
        start, end = window
        end = min(end, audio.size / sample_rate)
        segment_audio = audio[int(start * sample_rate) : int(end * sample_rate)]
        detection = detect_speech(segment_audio, sample_rate)
        if detection["speech_contaminated"]:
            refined = _cleanest_subwindow(audio, sample_rate, start, end)
            if refined is not None:
                (start, end), detection = refined
                detection["subwindow_refined"] = True
        human_note = speech_confirmations.get(vehicle_id)
        if human_note:
            detection["human_review"] = human_note
            detection["speech_contaminated"] = True
        allowed = ["raw_dynamic", "loudness_matched_timbre"]
        case = ReferenceCase(
            vehicle_id=vehicle_id,
            scenario=scenario,
            reference_id=f"{vehicle_id}:{media['video_id']}:{segment_name}:{start:.1f}-{end:.1f}",
            audio_path=str(audio_path),
            audio_sha256=digest,
            evidence_level="R2_AUDIO_DIAGNOSTIC",
            rights_status="R2_RELATIVE_REVIEW_ONLY",
            sample_rate=sample_rate,
            start_s=start,
            end_s=end,
            microphone_position="UNVERIFIED",
            agc_post_processing="UNKNOWN_AGC_POSSIBLE",
            speech_music_contamination=detection,
            rpm_trace=None,
            load_trace=None,
            gear_trace=None,
            uncertainty={
                "rpm_synchronised": False,
                "stock_state_verified": False,
                "agc_verified": False,
                "notes": record["recording"].get("risk", ""),
            },
            allowed_metrics=allowed,
        )
        case.segment_sha256 = _segment_hash(audio_path, start, end)
        if detection["speech_contaminated"]:
            case.status = "REJECTED_SPEECH_CONTAMINATED"
            case.rejection_reason = "speech detector above reject threshold" + (" plus human confirmation" if human_note else "")
        cases.append(case)
    clean = [case for case in cases if case.status == "BOUND"]
    receipt = {
        "schema": CASESET_SCHEMA,
        "vehicle_id": vehicle_id,
        "reference_evidence_level": "R2_AUDIO_DIAGNOSTIC",
        "source_audio": [
            {
                "reference_id_base": f"{vehicle_id}:{media['video_id']}",
                "audio_path": str(audio_path),
                "audio_sha256": digest,
                "sample_rate": sample_rate,
                "duration_s": audio.size / sample_rate,
            }
        ],
        "cases": [case.to_dict() for case in cases],
        "scenario_unavailable": unavailable,
        "bound_scenario_count": len(clean),
        "valid_reference_count": len(clean),
        "cleanliness_receipt": {
            "detector": "s12_stage_x_speech_band_heuristic_v1",
            "human_confirmation_applied": bool(speech_confirmations.get(vehicle_id)),
            "minimum_engine_to_speech_ratio_db": ENGINE_TO_SPEECH_RATIO_REJECT_DB,
            "rejected_scenarios": [case.scenario for case in cases if case.status != "BOUND"],
            "note": "R2 segments are never promoted to R1; RPM traces absent so order metrics stay NOT_QUALIFIED",
        },
        "scope": "synthetic analysis of third-party R2 media for relative review only; not OEM reproduction",
    }
    return receipt


def load_case_segment_audio(case: dict[str, Any]) -> tuple[np.ndarray, int]:
    """Load the bounded segment audio for one bound reference case."""
    if case["status"] != "BOUND":
        raise ValueError(f"reference case is not bound: {case['scenario']} / {case['status']}")
    audio, sample_rate = read_wav_mono(case["audio_path"])
    start = int(case["start_s"] * sample_rate)
    end = int(case["end_s"] * sample_rate)
    return audio[start:end], sample_rate


__all__ = [
    "CASESET_SCHEMA",
    "SCENARIOS",
    "ReferenceCase",
    "build_reference_caseset",
    "detect_speech",
    "load_case_segment_audio",
    "read_wav_mono",
]
