from __future__ import annotations

from pathlib import Path

import pytest

from tools.sound_sim.s12.real_reference.url_intake import (
    UrlIntakeError,
    build_video_record,
    validate_source_url,
)


def _probe(codec_name: str = "opus") -> dict:
    return {
        "streams": [
            {
                "codec_type": "audio",
                "codec_name": codec_name,
                "sample_rate": "48000",
                "channels": 1,
                "duration": "8.0",
            }
        ],
        "format": {"duration": "8.0"},
    }


def _files(tmp_path: Path) -> tuple[Path, Path]:
    video = tmp_path / "source.webm"
    wav = tmp_path / "source.analysis.wav"
    video.write_bytes(b"video")
    wav.write_bytes(b"pcm")
    return video, wav


def test_validate_source_url_rejects_non_http_and_credentials() -> None:
    assert validate_source_url("https://example.com/video") == "https://example.com/video"
    with pytest.raises(UrlIntakeError):
        validate_source_url("file:///C:/video.webm")
    with pytest.raises(UrlIntakeError):
        validate_source_url("https://user:password@example.com/video")


def test_url_without_rights_or_identity_is_r3(tmp_path: Path) -> None:
    video, wav = _files(tmp_path)
    record = build_video_record(
        source_url="https://example.com/video",
        video_path=video,
        wav_path=wav,
        probe=_probe(),
    )
    assert record["evidence"]["level"] == "R3"
    assert record["evidence"]["r1_eligible"] is False
    assert record["evidence"]["r2_eligible"] is False
    assert record["evidence"]["automatic_tuning_eligible"] is False


def test_confirmed_rights_vehicle_and_scenario_are_r2_only_without_state(tmp_path: Path) -> None:
    video, wav = _files(tmp_path)
    record = build_video_record(
        source_url="https://example.com/video",
        video_path=video,
        wav_path=wav,
        probe=_probe(),
        vehicle_id="ferrari_458",
        scenario="acceleration",
        legal_permission="CONFIRMED",
        rights_evidence="https://example.com/license",
    )
    assert record["evidence"]["level"] == "R2"
    assert record["evidence"]["r2_eligible"] is True
    assert record["evidence"]["r1_eligible"] is False
    assert record["analysis_contract"]["rpm_state_status"] == "MISSING_RPM_STATE"


def test_complete_contract_can_reach_r1_gate_only_with_raw_audio_receipt(tmp_path: Path) -> None:
    video, wav = _files(tmp_path)
    record = build_video_record(
        source_url="https://example.com/video",
        video_path=video,
        wav_path=wav,
        probe=_probe(codec_name="pcm_s24le"),
        vehicle_id="ferrari_458",
        scenario="full_pull",
        legal_permission="CONFIRMED",
        rights_evidence="https://example.com/license",
        stock_identity="VERIFIED_EXACT_TRIM",
        microphone_perspective="EXTERIOR_REAR",
        recording_device_agc="DOCUMENTED_NO_AGC",
        state_contract={
            "rpm_state_status": "SYNCED",
            "load_throttle_status": "SYNCED",
            "gear_shift_status": "SYNCED",
            "trace_paths": {"rpm": "rpm.csv", "load_throttle": "load.csv", "gear_shift": "gear.csv"},
        },
        raw_audio_confirmed=True,
    )
    assert record["evidence"]["level"] == "R1"
    assert record["evidence"]["r1_eligible"] is True
    assert record["evidence"]["automatic_tuning_eligible"] is False

