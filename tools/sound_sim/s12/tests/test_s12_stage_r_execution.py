from __future__ import annotations

import hashlib
import wave
from pathlib import Path

import numpy as np
import pytest

from tools.sound_sim.s12.real_reference import (
    MATLAB_R1_FUNCTIONS,
    StageRExecutionContractError,
    build_r1_execution_plan,
    run_r2_limited_comparison,
    write_r2_outputs,
)
from tools.sound_sim.s12.real_reference.qualification import ReferenceQualificationError


def _write_pcm16(path: Path, sample_rate_hz: int, signal: np.ndarray) -> str:
    values = np.clip(np.asarray(signal, dtype=np.float64), -1.0, 1.0)
    pcm = np.round(values * 32767.0).astype("<i2").tobytes()
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate_hz)
        stream.writeframes(pcm)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _r2_record(path: Path, sha256: str, *, sample_rate_hz: int = 48_000) -> dict[str, object]:
    return {
        "recording_id": "ferrari_r2_authorised_fixture",
        "reference_id": "q:ferrari_r2_authorised_fixture",
        "vehicle_id": "ferrari_458",
        "scenario": "acceleration",
        "file_present": True,
        "external_path": str(path),
        "sha256": sha256,
        "audio": {"sample_rate_hz": sample_rate_hz},
        "provenance": {"legal_permission": "CONFIRMED"},
    }


def _r1_record(path: Path, sha256: str) -> dict[str, object]:
    record = _r2_record(path, sha256)
    record["recording_id"] = "ferrari_r1_authorised_fixture"
    record["reference_id"] = "q:ferrari_r1_authorised_fixture"
    record["provenance"] = {
        "legal_permission": "CONFIRMED",
        "stock_identity": "VERIFIED_EXACT_TRIM",
        "microphone_perspective": "EXTERIOR_REAR",
        "recording_device_agc": "DOCUMENTED_NO_AGC",
    }
    record["analysis_contract"] = {
        "rpm_state_status": "SYNCED",
        "load_throttle_status": "SYNCED",
        "gear_shift_status": "SYNCED",
    }
    return record


def test_r2_runner_rejects_current_unqualified_reference(tmp_path: Path) -> None:
    wav_path = tmp_path / "reference.wav"
    sha256 = _write_pcm16(wav_path, 48_000, np.sin(np.linspace(0, 50, 16_384)))
    record = _r2_record(wav_path, sha256)
    record["provenance"] = {"legal_permission": "UNVERIFIED"}
    with pytest.raises(ReferenceQualificationError, match="not R2-eligible"):
        run_r2_limited_comparison(record, wav_path)


def test_r2_runner_emits_relative_only_report_and_no_recommendations(tmp_path: Path) -> None:
    t = np.arange(16_384) / 48_000.0
    reference_path = tmp_path / "reference.wav"
    candidate_path = tmp_path / "candidate.wav"
    reference_sha = _write_pcm16(reference_path, 48_000, np.sin(2 * np.pi * 240 * t))
    _write_pcm16(candidate_path, 48_000, np.sin(2 * np.pi * 260 * t))
    result = run_r2_limited_comparison(
        _r2_record(reference_path, reference_sha),
        candidate_path,
        candidate_meta={
            "vehicle_id": "ferrari_458",
            "scenario": "acceleration",
            "candidate_id": "candidate:fixture",
            "source_commit": "fixture-source-sha",
        },
    )
    assert result["status"] == "R2_LIMITED_COMPARISON_COMPLETE"
    assert result["comparison_scope"] == "relative_digital_domain_only"
    assert result["uncertainty"]["digital_domain_relative_only"] is True
    assert result["uncertainty"]["identity_score_available"] is False
    assert result["order"]["used_for_gate"] is False
    assert result["automatic_tuning_eligible"] is False
    assert result["parameter_recommendations"] == []
    assert result["difference_report"]["human_score"] is None

    outputs = write_r2_outputs(result, tmp_path / "out")
    assert outputs["result"].is_file()
    report = outputs["report"].read_text(encoding="utf-8")
    assert "有限真实声浪差异报告" in report
    assert "没有同步 RPM/state" in report


def test_r2_runner_rejects_implicit_resampling(tmp_path: Path) -> None:
    t = np.arange(16_384) / 48_000.0
    reference_path = tmp_path / "reference.wav"
    candidate_path = tmp_path / "candidate.wav"
    reference_sha = _write_pcm16(reference_path, 48_000, np.sin(2 * np.pi * 240 * t))
    _write_pcm16(candidate_path, 44_100, np.sin(2 * np.pi * 260 * t))
    with pytest.raises(StageRExecutionContractError, match="sample-rate mismatch"):
        run_r2_limited_comparison(
            _r2_record(reference_path, reference_sha),
            candidate_path,
            candidate_meta={
                "vehicle_id": "ferrari_458",
                "scenario": "acceleration",
                "candidate_id": "candidate:sample-rate-mismatch",
            },
        )


def test_r1_plan_is_ready_only_when_all_state_contracts_are_present(tmp_path: Path) -> None:
    reference_path = tmp_path / "reference.wav"
    reference_sha = _write_pcm16(reference_path, 48_000, np.zeros(16_384))
    record = _r1_record(reference_path, reference_sha)
    candidate_meta = {
        "vehicle_id": "ferrari_458",
        "scenario": "acceleration",
        "candidate_id": "candidate:r1-fixture",
        "candidate_sha256": "b" * 64,
        "state_trace_sha256": "c" * 64,
        "rpm_trace_path": "state/rpm.csv",
        "load_throttle_trace_path": "state/load_throttle.csv",
        "gear_shift_trace_path": "state/gear_shift.csv",
    }
    plan = build_r1_execution_plan(record, candidate_meta)
    assert plan["status"] == "READY_FOR_R1_MATLAB_EXECUTION"
    assert set(MATLAB_R1_FUNCTIONS).issubset(plan["matlab_required_functions"])
    assert plan["order_hard_gate"] is True
    assert plan["automatic_tuning_authority"] == "WITHHELD_UNTIL_STAGE_S_HUMAN_FEEDBACK_AND_HARD_GATES"


def test_r1_plan_rejects_unqualified_reference(tmp_path: Path) -> None:
    reference_path = tmp_path / "reference.wav"
    reference_sha = _write_pcm16(reference_path, 48_000, np.zeros(16_384))
    record = _r2_record(reference_path, reference_sha)
    with pytest.raises(ReferenceQualificationError, match="not R1-eligible"):
        build_r1_execution_plan(record, {"vehicle_id": "ferrari_458", "scenario": "acceleration"})
