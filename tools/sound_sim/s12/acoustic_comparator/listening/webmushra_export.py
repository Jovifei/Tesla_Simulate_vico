"""Export non-destructive, upstream-compatible webMUSHRA study packages."""
from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np

from . import loudness_matched_audition


RATING_DIMENSIONS = (
    "vehicle_identity",
    "realism",
    "low_frequency_weight",
    "mechanical_character",
    "idle_life",
    "acceleration_aggression",
    "shift_realism",
    "afterfire_naturalness",
    "synthetic_artifact_freedom",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as handle:
        frames = handle.readframes(handle.getnframes())
        channels, width, rate = handle.getnchannels(), handle.getsampwidth(), handle.getframerate()
    if channels not in {1, 2} or width not in {1, 2, 3, 4}:
        raise ValueError(f"unsupported WAV layout: {path}")
    raw = np.frombuffer(frames, dtype=np.uint8)
    if width == 1:
        value = (raw.astype(np.float64) - 128.0) / 128.0
    elif width == 2:
        value = np.frombuffer(frames, dtype="<i2").astype(np.float64) / (1 << 15)
    elif width == 3:
        packed = raw.reshape(-1, 3)
        value = packed[:, 0].astype(np.int32) | (packed[:, 1].astype(np.int32) << 8) | (packed[:, 2].astype(np.int32) << 16)
        value = np.where(value & 0x800000, value - (1 << 24), value).astype(np.float64) / (1 << 23)
    else:
        value = np.frombuffer(frames, dtype="<i4").astype(np.float64) / (1 << 31)
    return value.reshape(-1, channels), rate


def _write_wav(path: Path, signal: np.ndarray, rate: int) -> None:
    value = np.clip(np.asarray(signal, dtype=np.float64), -1.0, 1.0 - 1.0 / (1 << 15))
    if value.ndim == 1:
        value = value[:, None]
    pcm = np.rint(value * ((1 << 15) - 1)).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(value.shape[1])
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm.tobytes())


def _audition_copy(source: Path, destination: Path) -> dict[str, object]:
    signal, rate = _read_wav(source)
    copy, level = loudness_matched_audition(signal)
    _write_wav(destination, copy, rate)
    return {"source_sha256": _sha256(source), "audition_sha256": _sha256(destination), "sample_rate_hz": rate, **level}


def _low_quality_anchor(source: Path, destination: Path) -> dict[str, object]:
    signal, rate = _read_wav(source)
    coarse = np.repeat(signal[::4], 4, axis=0)[: signal.shape[0]]
    copy, level = loudness_matched_audition(coarse)
    _write_wav(destination, copy, rate)
    return {"method": "four_sample_zero_order_hold_low_quality_anchor", "sha256": _sha256(destination), "sample_rate_hz": rate, **level}


def _yaml(trials: Mapping[str, Mapping[str, object]]) -> str:
    lines = [
        "testname: S12 Stage N professional comparator",
        "testId: s12-stage-n-webmushra-v1",
        "bufferSize: 2048",
        "stopOnErrors: true",
        "showButtonPreviousPage: true",
        "remoteService: service/write.php",
        "pages:",
        "  - type: volume",
        "    id: playback-level",
        "    name: Playback level",
        "    content: Use the documented endpoint. This study has a synthetic parent hidden reference; it is not an external vehicle recording.",
        f"    stimulus: {next(iter(trials.values()))['volume_path']}",
        "    defaultVolume: 0.5",
    ]
    for anonymous_id, trial in trials.items():
        lines.extend([
            "  - type: mushra",
            f"    id: {anonymous_id}",
            f"    name: {anonymous_id} {trial['scenario']}",
            "    content: Rate the anonymous stimuli. Looping is permitted. Scores remain unqualified until a SHA-bound Jovi submission is imported.",
            "    showWaveform: false",
            "    enableLooping: true",
            "    strict: true",
            f"    reference: {trial['reference_path']}",
            "    stimuli:",
            f"      stage_k_parent: {trial['parent_path']}",
            f"      stage_m_candidate: {trial['candidate_path']}",
            f"      low_quality_anchor: {trial['anchor_path']}",
        ])
        for dimension in RATING_DIMENSIONS:
            lines.extend([
                "  - type: likert_single_stimulus",
                f"    id: {anonymous_id}_{dimension}",
                f"    name: {anonymous_id} {dimension}",
                f"    content: Rate the Stage-M candidate for {dimension.replace('_', ' ')}. This response is SHA-bound but not a human qualification until Jovi submits it.",
                "    mustRate: true",
                "    stimuli:",
                f"      stage_m_candidate: {trial['candidate_path']}",
                "    response:",
                "      - value: 0",
                "        label: 0",
                "      - value: 25",
                "        label: 25",
                "      - value: 50",
                "        label: 50",
                "      - value: 75",
                "        label: 75",
                "      - value: 100",
                "        label: 100",
            ])
    lines.extend([
        "  - type: finish",
        "    name: Submit results",
        "    content: Results are written by the local webMUSHRA PHP service. Export them with the package binding before any Stage-N feedback import.",
        "    showResults: false",
        "    showErrors: true",
        "    writeResults: true",
        "    questionnaire:",
        "      - type: text",
        "        label: Listener ID",
        "        name: listener_id",
        "        optional: false",
    ])
    return "\n".join(lines) + "\n"


def export_webmushra_study(destination: Path, trials: Iterable[Mapping[str, object]], *, upstream_receipt: Mapping[str, object]) -> dict[str, object]:
    """Create a new study directory and never overwrite a populated one."""

    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing webMUSHRA study: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    config_dir = destination / "configs"
    results_dir = destination / "results"
    audio_dir = destination / "audio"
    config_dir.mkdir()
    results_dir.mkdir()
    audio_dir.mkdir()
    results_dir.joinpath(".gitkeep").write_text("webMUSHRA result export destination\n", encoding="utf-8", newline="\n")
    records: dict[str, dict[str, object]] = {}
    for trial in trials:
        anonymous_id = str(trial["anonymous_id"])
        if anonymous_id in records:
            raise ValueError(f"duplicate anonymous id: {anonymous_id}")
        parent, candidate = Path(str(trial["parent"])), Path(str(trial["candidate"]))
        if not parent.is_file() or not candidate.is_file():
            raise FileNotFoundError("parent and candidate WAV files are required")
        folder = audio_dir / anonymous_id
        folder.mkdir()
        reference = folder / "reference_synthetic_parent.wav"
        parent_copy = folder / "stage_k_parent.wav"
        candidate_copy = folder / "stage_m_candidate.wav"
        anchor = folder / "low_quality_anchor.wav"
        reference_receipt = _audition_copy(parent, reference)
        parent_receipt = _audition_copy(parent, parent_copy)
        candidate_receipt = _audition_copy(candidate, candidate_copy)
        anchor_receipt = _low_quality_anchor(candidate, anchor)
        records[anonymous_id] = {
            "anonymous_id": anonymous_id,
            "vehicle_id": str(trial["vehicle_id"]),
            "scenario": str(trial["scenario"]),
            "reference_role": "synthetic_parent_not_real_reference",
            "future_candidate": {"status": "NOT_GENERATED", "reason": "no source change is authorized on comparator branch"},
            "reference_path": f"configs/s12-stage-n/audio/{anonymous_id}/{reference.name}",
            "parent_path": f"configs/s12-stage-n/audio/{anonymous_id}/{parent_copy.name}",
            "candidate_path": f"configs/s12-stage-n/audio/{anonymous_id}/{candidate_copy.name}",
            "anchor_path": f"configs/s12-stage-n/audio/{anonymous_id}/{anchor.name}",
            "volume_path": f"configs/s12-stage-n/audio/{anonymous_id}/{reference.name}",
            "candidate_sha256": candidate_receipt["audition_sha256"],
            "audition_receipts": {"reference": reference_receipt, "parent": parent_receipt, "candidate": candidate_receipt, "anchor": anchor_receipt},
        }
    if not records:
        raise ValueError("at least one listening trial is required")
    yaml_path = config_dir / "s12-stage-n.yaml"
    yaml_path.write_text(_yaml(records), encoding="utf-8", newline="\n")
    study = {
        "schema_version": "s12-stage-n-webmushra-study-1",
        "tool": "webMUSHRA",
        "upstream_receipt": dict(upstream_receipt),
        "hidden_reference_policy": "synthetic_parent_not_real_reference",
        "rating_dimensions": list(RATING_DIMENSIONS),
        "looping": True,
        "fade_policy": "webMUSHRA sample-accurate switching; no analysis signal is used for audition",
        "trials": records,
    }
    study_path = destination / "study_manifest.json"
    study_path.write_text(json.dumps(study, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    binding = {
        "schema_version": "s12-stage-n-webmushra-package-binding-1",
        "test_id": "s12-stage-n-webmushra-v1",
        "package_manifest_sha256": _sha256(study_path),
        "trials": {key: {"candidate_sha256": value["candidate_sha256"], "vehicle_id": value["vehicle_id"], "scenario": value["scenario"]} for key, value in records.items()},
        "required_result_columns": ["listener_id", "anonymous_id", "package_manifest_sha256", "candidate_sha256", *RATING_DIMENSIONS],
        "result_policy": "fixture imports and raw external rows are not human feedback until explicitly submitted by Jovi",
    }
    (destination / "webmushra_package_manifest.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (destination / "LOCAL_WEBMUSHRA_SETUP.md").write_text(
        "# Local Stage-N webMUSHRA setup\n\n"
        "This study uses the official external webMUSHRA checkout; its source is not copied into this repository. The hidden reference is a synthetic parent, not a real vehicle recording.\n\n"
        "1. Copy `configs/s12-stage-n.yaml` to `<webMUSHRA>/configs/s12-stage-n.yaml`.\n"
        "2. Copy this package's `audio/` directory to `<webMUSHRA>/configs/s12-stage-n/audio/`.\n"
        "3. From the external checkout run `docker compose up --build`.\n"
        "4. Open `http://127.0.0.1:8000/?config=s12-stage-n.yaml` in Chrome. Results appear under `<webMUSHRA>/results/s12-stage-n-webmushra-v1/mushra.csv`.\n"
        "5. Normalize the exported result with the SHA/file-ID binding before calling `webmushra_import.py`. No fixture or browser result is human qualification until Jovi submits it.\n",
        encoding="utf-8", newline="\n",
    )
    return study
