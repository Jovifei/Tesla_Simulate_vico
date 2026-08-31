from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path

import numpy as np
import pytest

from tools.sound_sim.s12.real_reference import (
    MATLAB_R1_FUNCTIONS,
    StageRExecutionContractError,
    build_r1_execution_plan,
    prepare_r1_matlab_inputs,
    run_r2_limited_comparison,
    write_r2_outputs,
)
from tools.sound_sim.s12.real_reference.qualification import ReferenceQualificationError
import tools.sound_sim.s12.real_reference.stage_r_execute as stage_r_execute


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
    record["audio"] = {"codec": "PCM", "sample_rate_hz": 48_000}
    record["recording_id"] = "ferrari_r1_authorised_fixture"
    record["reference_id"] = "q:ferrari_r1_authorised_fixture"
    record["provenance"] = {
        "legal_permission": "CONFIRMED",
        "rights_evidence": "https://example.com/r1-license",
        "source_url": "https://example.com/original-audio-receipt",
        "source_kind": "controlled_raw_audio",
        "raw_audio_confirmed": True,
        "stock_identity": "VERIFIED_EXACT_TRIM",
        "stock_exhaust_confirmation": "CONFIRMED_STOCK",
        "microphone_perspective": "EXTERIOR_REAR",
        "recording_device_agc": "DOCUMENTED_NO_AGC",
    }
    record["analysis_contract"] = {
        "rpm_state_status": "SYNCED",
        "load_throttle_status": "SYNCED",
        "gear_shift_status": "SYNCED",
    }
    return record


def _write_r1_state(root: Path, frame_count: int, sample_rate_hz: int = 48_000) -> str:
    root.mkdir(parents=True, exist_ok=True)
    time_s = np.arange(frame_count, dtype=np.float64) / sample_rate_hz
    rpm = np.linspace(1_000.0, 4_000.0, frame_count, dtype=np.float64)
    load = np.full(frame_count, 0.65, dtype=np.float64)
    throttle = np.full(frame_count, 0.8, dtype=np.float64)
    gear = np.where(time_s < time_s[-1] / 2.0, 2.0, 3.0)
    shift_event = np.concatenate(([0.0], (np.diff(gear) != 0).astype(np.float64)))
    (root / "rpm.csv").write_text(
        "time_s,rpm\n" + "\n".join(f"{time:.17g},{value:.17g}" for time, value in zip(time_s, rpm)) + "\n",
        encoding="utf-8",
    )
    (root / "load_throttle.csv").write_text(
        "time_s,load,throttle\n" + "\n".join(
            f"{time:.17g},{load_value:.17g},{throttle_value:.17g}"
            for time, load_value, throttle_value in zip(time_s, load, throttle)
        ) + "\n",
        encoding="utf-8",
    )
    (root / "gear_shift.csv").write_text(
        "time_s,gear,shift_event\n" + "\n".join(
            f"{time:.17g},{gear_value:.17g},{shift_value:.17g}"
            for time, gear_value, shift_value in zip(time_s, gear, shift_event)
        ) + "\n",
        encoding="utf-8",
    )
    state, _ = stage_r_execute._load_state_bundle(
        {
            "trace_root": str(root),
            "rpm_trace_path": "rpm.csv",
            "load_throttle_trace_path": "load_throttle.csv",
            "gear_shift_trace_path": "gear_shift.csv",
        },
        frame_count=frame_count,
        sample_rate_hz=sample_rate_hz,
        fallback_root=root,
    )
    return stage_r_execute._trace_sha256(state)


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


def test_r2_runner_accepts_case_insensitive_manifest_sha(tmp_path: Path) -> None:
    t = np.arange(16_384) / 48_000.0
    reference_path = tmp_path / "reference.wav"
    candidate_path = tmp_path / "candidate.wav"
    reference_sha = _write_pcm16(reference_path, 48_000, np.sin(2 * np.pi * 240 * t))
    _write_pcm16(candidate_path, 48_000, np.sin(2 * np.pi * 240 * t))
    result = run_r2_limited_comparison(
        _r2_record(reference_path, reference_sha.upper()),
        candidate_path,
        candidate_meta={
            "vehicle_id": "ferrari_458",
            "scenario": "acceleration",
            "candidate_id": "candidate:case-insensitive-sha",
        },
    )
    assert result["status"] == "R2_LIMITED_COMPARISON_COMPLETE"


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
    assert plan["input_preparation"]["function"] == "prepare_r1_matlab_inputs"
    assert plan["matlab_entrypoints"]["manual_desktop_only"] is True
    assert plan["order_hard_gate"] is True
    assert plan["automatic_tuning_authority"] == "WITHHELD_UNTIL_STAGE_S_HUMAN_FEEDBACK_AND_HARD_GATES"


def test_r1_plan_rejects_unqualified_reference(tmp_path: Path) -> None:
    reference_path = tmp_path / "reference.wav"
    reference_sha = _write_pcm16(reference_path, 48_000, np.zeros(16_384))
    record = _r2_record(reference_path, reference_sha)
    with pytest.raises(ReferenceQualificationError, match="not R1-eligible"):
        build_r1_execution_plan(record, {"vehicle_id": "ferrari_458", "scenario": "acceleration"})


def test_r1_input_preparation_binds_audio_state_and_matlab_receipts(tmp_path: Path) -> None:
    frame_count = 4_096
    sample_rate_hz = 48_000
    t = np.arange(frame_count) / sample_rate_hz
    reference_path = tmp_path / "reference.wav"
    candidate_path = tmp_path / "candidate.wav"
    reference_sha = _write_pcm16(reference_path, sample_rate_hz, np.sin(2 * np.pi * 240 * t))
    candidate_sha = _write_pcm16(candidate_path, sample_rate_hz, np.sin(2 * np.pi * 250 * t))
    reference_state_root = tmp_path / "reference_state"
    candidate_state_root = tmp_path / "candidate_state"
    reference_state_sha = _write_r1_state(reference_state_root, frame_count, sample_rate_hz)
    candidate_state_sha = _write_r1_state(candidate_state_root, frame_count, sample_rate_hz)
    window = {"start_s": 0.0, "end_s": (frame_count - 1) / sample_rate_hz}
    record = _r1_record(reference_path, reference_sha)
    record["time_window"] = window
    record["state_bindings"] = {
        "trace_root": str(reference_state_root),
        "rpm_trace_path": "rpm.csv",
        "load_throttle_trace_path": "load_throttle.csv",
        "gear_shift_trace_path": "gear_shift.csv",
        "trace_sha256": reference_state_sha,
    }
    candidate_meta = {
        "vehicle_id": "ferrari_458",
        "scenario": "acceleration",
        "candidate_id": "candidate:r1-input-fixture",
        "candidate_sha256": candidate_sha,
        "state_trace_sha256": candidate_state_sha,
        "trace_root": str(candidate_state_root),
        "rpm_trace_path": "rpm.csv",
        "load_throttle_trace_path": "load_throttle.csv",
        "gear_shift_trace_path": "gear_shift.csv",
        "time_window": window,
    }
    output_root = tmp_path / "r1-matlab-inputs"
    manifest = prepare_r1_matlab_inputs(
        record,
        candidate_path,
        candidate_meta=candidate_meta,
        output_root=output_root,
    )
    assert manifest["schema_version"] == "s12-stage-r1-matlab-inputs-v1"
    assert manifest["status"] == "READY_FOR_MANUAL_MATLAB_EXECUTION"
    assert manifest["automatic_tuning_eligible"] is False
    assert manifest["matlab_entrypoints"]["manual_desktop_only"] is True
    assert manifest["inputs"]["reference"]["source_wav_sha256"] == reference_sha
    assert manifest["inputs"]["candidate"]["source_wav_sha256"] == candidate_sha
    assert (output_root / "input_manifest.json").is_file()
    assert (output_root / "reference.mat").is_file()
    assert (output_root / "candidate.mat").is_file()
    from scipy.io import loadmat

    reference_mat = loadmat(output_root / "reference.mat")
    assert reference_mat["signal_pcm24"].shape == (frame_count, 2)
    assert reference_mat["rpm"].reshape(-1).size == frame_count
    assert reference_mat["state_trace"].reshape(-1).size == frame_count
    assert json.loads((output_root / "input_manifest.json").read_text(encoding="utf-8"))["inputs"]["candidate"]["mat_sha256"] == manifest["inputs"]["candidate"]["mat_sha256"]


def test_r1_input_preparation_rejects_state_audio_frame_mismatch(tmp_path: Path) -> None:
    frame_count = 1_024
    sample_rate_hz = 48_000
    t = np.arange(frame_count) / sample_rate_hz
    reference_path = tmp_path / "reference.wav"
    candidate_path = tmp_path / "candidate.wav"
    reference_sha = _write_pcm16(reference_path, sample_rate_hz, np.sin(2 * np.pi * 240 * t))
    candidate_sha = _write_pcm16(candidate_path, sample_rate_hz, np.sin(2 * np.pi * 250 * t))
    reference_state_root = tmp_path / "reference_state"
    candidate_state_root = tmp_path / "candidate_state"
    reference_state_sha = _write_r1_state(reference_state_root, frame_count, sample_rate_hz)
    candidate_state_sha = _write_r1_state(candidate_state_root, frame_count - 1, sample_rate_hz)
    window = {"start_s": 0.0, "end_s": (frame_count - 1) / sample_rate_hz}
    record = _r1_record(reference_path, reference_sha)
    record.update(
        {
            "time_window": window,
            "state_bindings": {
                "trace_root": str(reference_state_root),
                "rpm_trace_path": "rpm.csv",
                "load_throttle_trace_path": "load_throttle.csv",
                "gear_shift_trace_path": "gear_shift.csv",
                "trace_sha256": reference_state_sha,
            },
        }
    )
    candidate_meta = {
        "vehicle_id": "ferrari_458",
        "scenario": "acceleration",
        "candidate_id": "candidate:r1-mismatch-fixture",
        "candidate_sha256": candidate_sha,
        "state_trace_sha256": candidate_state_sha,
        "trace_root": str(candidate_state_root),
        "rpm_trace_path": "rpm.csv",
        "load_throttle_trace_path": "load_throttle.csv",
        "gear_shift_trace_path": "gear_shift.csv",
        "time_window": window,
    }
    with pytest.raises(StageRExecutionContractError, match="sample count mismatch"):
        prepare_r1_matlab_inputs(
            record,
            candidate_path,
            candidate_meta=candidate_meta,
            output_root=tmp_path / "r1-matlab-inputs-mismatch",
        )


def test_r1_state_bundle_resamples_timestamped_lower_rate_telemetry(tmp_path: Path) -> None:
    frame_count = 4_800
    sample_rate_hz = 48_000
    root = tmp_path / "low-rate-state"
    root.mkdir()
    (root / "rpm.csv").write_text(
        "time_s,rpm\n0,1000\n0.05,2000\n0.099,3000\n",
        encoding="utf-8",
    )
    (root / "load_throttle.csv").write_text(
        "time_s,load,throttle\n0,0.2,0.3\n0.05,0.6,0.8\n0.099,0.9,1.0\n",
        encoding="utf-8",
    )
    (root / "gear_shift.csv").write_text(
        "time_s,gear,shift_event\n0,2,0\n0.05,2,0\n0.099,3,1\n",
        encoding="utf-8",
    )
    bundle, meta = stage_r_execute._load_state_bundle(
        {
            "trace_root": str(root),
            "rpm_trace_path": "rpm.csv",
            "load_throttle_trace_path": "load_throttle.csv",
            "gear_shift_trace_path": "gear_shift.csv",
            "time_window": {"start_s": 0.0, "end_s": 0.099},
        },
        frame_count=frame_count,
        sample_rate_hz=sample_rate_hz,
        fallback_root=root,
    )
    assert bundle["rpm"].size == frame_count
    assert bundle["load"].size == frame_count
    assert bundle["gear"].size == frame_count
    assert bundle["rpm"][0] == pytest.approx(1000.0)
    assert bundle["rpm"][-1] == pytest.approx(3000.0)
    assert set(np.unique(bundle["gear"])) <= {2.0, 3.0}
    assert meta["resampling"] == "timestamp_interpolation_to_audio_sample_grid"
