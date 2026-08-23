from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path

import pytest

from tools.sound_sim.s12.real_reference.r1_pilot import (
    R1PilotValidationError,
    run_r1_pilot_preflight,
    validate_rights_scope,
    validate_sha256_manifest,
    validate_state_sync,
)


def _write_wav(path: Path, duration_s: float = 1.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8_000)
        handle.writeframes(b"\x00\x00" * int(8_000 * duration_s))


def _base_spec() -> dict:
    return {
        "schema_version": "s12.stage_q.r1_pilot_spec.v1",
        "recording_id": "hellcat_full_pull_01",
        "vehicle_id": "hellcat",
        "scenario": "full_pull",
        "audio_path": "raw/raw_audio.wav",
        "source_url": "https://example.invalid/owner-receipt",
        "rights_path": "rights.json",
        "exact_vehicle_trim": "Dodge Challenger SRT Hellcat 2015 stock",
        "stock_exhaust_confirmation": "CONFIRMED_STOCK",
        "microphone_position": "EXHAUST_REAR",
        "recording_device_agc": "DOCUMENTED_NO_AGC",
        "raw_audio_confirmed": True,
        "raw_media_stored_outside_git": True,
        "state": {
            "trace_root": "state",
            "rpm_trace_path": "rpm.csv",
            "load_throttle_trace_path": "load_throttle.csv",
            "gear_shift_trace_path": "gear_shift.csv",
            "time_window": {"start_s": 0.0, "end_s": 1.0},
            "units": {
                "time_s": "s",
                "rpm": "rpm",
                "load": "fraction_0_1",
                "throttle": "fraction_0_1",
                "gear": "integer_index",
                "shift_event": "0_or_1",
            },
        },
    }


def _write_state(root: Path, *, nonmonotonic: bool = False) -> None:
    state = root / "state"
    state.mkdir(parents=True, exist_ok=True)
    times = [0.0, 0.5, 1.0]
    if nonmonotonic:
        times = [0.0, 0.7, 0.6]
    (state / "rpm.csv").write_text("time_s,rpm\n" + "\n".join(f"{t},{1000 + i * 500}" for i, t in enumerate(times)) + "\n", encoding="utf-8")
    (state / "load_throttle.csv").write_text("time_s,load,throttle\n" + "\n".join(f"{t},0.5,0.8" for t in times) + "\n", encoding="utf-8")
    (state / "gear_shift.csv").write_text("time_s,gear,shift_event\n" + "\n".join(f"{t},2,{1 if i == 1 else 0}" for i, t in enumerate(times)) + "\n", encoding="utf-8")


def _write_rights(root: Path, allowed_uses: list[str] | None = None) -> None:
    (root / "rights.json").write_text(json.dumps({
        "schema_version": "s12.stage_q.r1_rights_scope.v1",
        "permission_status": "CONFIRMED",
        "source_holder": "Owner",
        "source_url": "https://example.invalid/receipt",
        "license_identifier": "OWNER-RECEIPT-01",
        "allowed_uses": allowed_uses or ["local_analysis", "derived_features", "comparison", "human_audition", "bounded_tuning"],
        "raw_media_git_policy": "EXTERNAL_ONLY",
        "raw_redistribution": "FORBIDDEN",
    }, ensure_ascii=False), encoding="utf-8")


def test_rights_scope_rejects_ordinary_sfx_only_permission(tmp_path: Path) -> None:
    _write_rights(tmp_path, ["personal_playback"])
    with pytest.raises(R1PilotValidationError, match="allowed_uses"):
        validate_rights_scope(tmp_path, _base_spec())


def test_rights_scope_requires_manual_review_for_pdf(tmp_path: Path) -> None:
    (tmp_path / "rights.pdf").write_bytes(b"pdf placeholder")
    spec = _base_spec()
    spec["rights_path"] = "rights.pdf"
    result = validate_rights_scope(tmp_path, spec)
    assert result["status"] == "MANUAL_REVIEW_REQUIRED"
    assert result["r1_rights_ready"] is False


def test_sha_manifest_rejects_placeholder_or_mismatch(tmp_path: Path) -> None:
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "raw_audio.wav").write_bytes(b"audio")
    (tmp_path / "sha256.txt").write_text("0" * 64 + "  raw/raw_audio.wav\n", encoding="utf-8")
    with pytest.raises(R1PilotValidationError, match="SHA-256"):
        validate_sha256_manifest(tmp_path, ["raw/raw_audio.wav"])


def test_state_sync_accepts_timestamped_covering_traces(tmp_path: Path) -> None:
    _write_wav(tmp_path / "raw" / "raw_audio.wav")
    _write_state(tmp_path)
    result = validate_state_sync(tmp_path, _base_spec())
    assert result["status"] == "PASS"
    assert result["synchronization"] == "timestamp_bound_state_traces"
    assert result["time_window"] == {"start_s": 0.0, "end_s": 1.0}


def test_state_sync_rejects_nonmonotonic_trace(tmp_path: Path) -> None:
    _write_wav(tmp_path / "raw" / "raw_audio.wav")
    _write_state(tmp_path, nonmonotonic=True)
    with pytest.raises(R1PilotValidationError, match="strictly increasing"):
        validate_state_sync(tmp_path, _base_spec())


def test_empty_pilot_is_waiting_not_ready(tmp_path: Path) -> None:
    result = run_r1_pilot_preflight(tmp_path, "hellcat_full_pull_01", tmp_path / "out")
    assert result["status"] == "WAITING_FOR_R1_PILOT_DELIVERY"
    assert result["r1_pilot_ready"] is False
    assert result["automatic_tuning_eligible"] is False
    assert result["missing_files"]


def test_complete_pilot_preflight_is_r1_ready_but_does_not_tune(tmp_path: Path) -> None:
    recording_id = "hellcat_full_pull_01"
    root = tmp_path / "pilot" / recording_id
    spec = _base_spec()
    _write_wav(root / "raw" / "raw_audio.wav")
    _write_state(root)
    _write_rights(root)
    (root / "spec.json").parent.mkdir(parents=True, exist_ok=True)
    (root / "spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    required = ["raw/raw_audio.wav", "rights.json", "spec.json", "state/rpm.csv", "state/load_throttle.csv", "state/gear_shift.csv"]
    (root / "sha256.txt").write_text(
        "\n".join(f"{hashlib.sha256((root / path).read_bytes()).hexdigest()}  {path}" for path in required) + "\n",
        encoding="utf-8",
    )
    result = run_r1_pilot_preflight(tmp_path / "pilot", recording_id, tmp_path / "out")
    assert result["status"] == "R1_PILOT_READY"
    assert result["r1_pilot_ready"] is True
    assert result["automatic_tuning_eligible"] is False
    assert result["profile_candidate_ready"] is False
    assert next(g for g in result["gates"] if g["name"] == "raw_audio_intake")["status"] == "PASS"
