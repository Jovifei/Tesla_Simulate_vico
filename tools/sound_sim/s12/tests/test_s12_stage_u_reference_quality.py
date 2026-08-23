from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.io import wavfile

from tools.sound_sim.s12.real_reference.stage_u_reference_quality import (
    ReferenceQualityError,
    silero_vad_segments,
    validate_reference_quality,
)
from tools.sound_sim.s12.real_reference.stage_u_silero_vad_runner import _load_wav


def _write_audio(path: Path) -> str:
    wavfile.write(path, 48_000, (0.1 * np.sin(np.linspace(0.0, 800.0, 96_000))).astype(np.float32))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(path: Path, scenario: str = "full_pull", candidate_audio_id: str = "candidate-full-pull") -> dict[str, object]:
    return {
        "reference_id": path.stem,
        "reference_path": str(path),
        "reference_sha256": _write_audio(path),
        "vehicle_id": "rx7_fd",
        "scenario": scenario,
        "matching_trace_scenario": scenario,
        "candidate_audio_id": candidate_audio_id,
        "microphone_uncertainty": "EXTERIOR_EXHAUST_AGC_UNKNOWN",
        "manual_contamination_review": "NOT_REVIEWED",
    }


def test_reference_quality_rejects_continuous_speech(tmp_path: Path) -> None:
    record = _record(tmp_path / "speech.wav")
    result = validate_reference_quality([record], vad=lambda *_: [(0.2, 1.7)])
    assert result[0]["status"] == "REFERENCE_SPEECH_CONTAMINATED"
    assert result[0]["grid_eligible"] is False


def test_reference_quality_rejects_wrong_scenario_mapping(tmp_path: Path) -> None:
    record = _record(tmp_path / "wrong_scene.wav")
    record["matching_trace_scenario"] = "idle"
    result = validate_reference_quality([record], vad=lambda *_: [])
    assert result[0]["status"] == "SCENARIO_NOT_COMPARABLE"
    assert result[0]["grid_eligible"] is False


def test_reference_quality_rejects_candidate_reuse_across_scenarios(tmp_path: Path) -> None:
    first = _record(tmp_path / "pull.wav", "full_pull", "shared-candidate")
    second = _record(tmp_path / "idle.wav", "idle", "shared-candidate")
    result = validate_reference_quality([first, second], vad=lambda *_: [])
    assert {row["status"] for row in result} == {"CANDIDATE_SCENARIO_REUSE_FORBIDDEN"}


def test_reference_quality_accepts_clean_sha_bound_same_scenario_record(tmp_path: Path) -> None:
    record = _record(tmp_path / "clean.wav")
    result = validate_reference_quality([record], vad=lambda *_: [])
    assert result[0]["status"] == "REFERENCE_QUALITY_PASS"
    assert result[0]["grid_eligible"] is True
    assert result[0]["duration_s"] == pytest.approx(2.0)


def test_reference_quality_refuses_bad_sha(tmp_path: Path) -> None:
    record = _record(tmp_path / "bad_sha.wav")
    record["reference_sha256"] = "0" * 64
    with pytest.raises(ReferenceQualityError, match="SHA"):
        validate_reference_quality([record], vad=lambda *_: [])


def test_silero_vad_adapter_parses_seconds_and_rejects_bad_runner_output(tmp_path: Path) -> None:
    path = tmp_path / "vad.wav"
    _write_audio(path)
    output = silero_vad_segments(
        path,
        Path("silero-python.exe"),
        command_runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout='[{"start_s": 0.25, "end_s": 1.50}]', stderr=""),
    )
    assert output == [(0.25, 1.50)]
    with pytest.raises(ReferenceQualityError, match="Silero"):
        silero_vad_segments(
            path,
            Path("silero-python.exe"),
            command_runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="", stderr="model failure"),
        )


def test_silero_runner_reads_pcm_wav_without_torchaudio_loader(tmp_path: Path) -> None:
    path = tmp_path / "pcm.wav"
    _write_audio(path)
    signal, sample_rate_hz = _load_wav(path)
    assert sample_rate_hz == 48_000
    assert signal.ndim == 1
    assert signal.size == 96_000
