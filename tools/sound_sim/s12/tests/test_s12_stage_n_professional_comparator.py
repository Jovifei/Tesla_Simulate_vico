from __future__ import annotations

import csv
import hashlib
import json
import wave
from pathlib import Path

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_comparator.listening.webmushra_export import export_webmushra_study
from tools.sound_sim.s12.acoustic_comparator.listening.webmushra_import import import_webmushra_results
from tools.sound_sim.s12.acoustic_comparator.perceptual.visqol_adapter import validate_visqol_request
from tools.sound_sim.s12.acoustic_identity_v015.stage_n.matlab_inputs import (
    CandidateBinding,
    _stage_k_trace_sha256,
    _stage_l_trace_sha256,
    _state_codes,
)
from tools.sound_sim.s12.acoustic_identity_v015.render_drive_cycle_v10 import build_drive_cycle_trace
from tools.sound_sim.s12.acoustic_identity_v015.stage_n.toolchain import (
    TOOL_STATUSES,
    build_unified_results,
    tool_record,
    validate_tool_record,
)


def _write_wav(path: Path, frequency_hz: float) -> None:
    sample_rate_hz = 8_000
    time = np.arange(sample_rate_hz, dtype=np.float64) / sample_rate_hz
    pcm = np.rint(np.sin(2.0 * np.pi * frequency_hz * time) * 0.2 * 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate_hz)
        handle.writeframes(pcm.tobytes())


def test_tool_statuses_are_closed_and_validated_requires_real_fixture() -> None:
    assert TOOL_STATUSES == {
        "RESEARCHED_ONLY",
        "ADAPTER_IMPLEMENTED",
        "EXECUTED_ON_FIXTURE",
        "EXECUTED_ON_PROJECT_DATA",
        "VALIDATED",
        "BLOCKED",
        "OPTIONAL_NOT_INSTALLED",
    }
    invalid = tool_record("MoSQITo", status="VALIDATED", actually_invoked=False, fixture_validated=True)
    with pytest.raises(ValueError, match="VALIDATED"):
        validate_tool_record(invalid)
    valid = tool_record(
        "MoSQITo",
        version="1.2.1",
        status="VALIDATED",
        actually_invoked=True,
        fixture_validated=True,
        output_artifact="mosqito_validation.json",
    )
    validate_tool_record(valid)


def test_visqol_rejects_non_official_or_cross_scope_requests(tmp_path: Path) -> None:
    official = tmp_path / "google-visqol"
    official.mkdir()
    (official / ".git").mkdir()
    (official / "WORKSPACE").write_text("workspace(name = 'visqol')\n", encoding="utf-8")
    binary = official / "bazel-bin" / "visqol.exe"
    binary.parent.mkdir()
    binary.write_bytes(b"fixture")
    request = {
        "checkout": str(official),
        "binary": str(binary),
        "commit": "abc123",
        "source_sha256": "a" * 64,
        "reference": {"vehicle_id": "hellcat", "scenario": "acceleration", "state_trace_sha256": "b" * 64, "role": "synthetic"},
        "degraded": {"vehicle_id": "hellcat", "scenario": "acceleration", "state_trace_sha256": "b" * 64, "role": "synthetic"},
    }
    accepted = validate_visqol_request(request)
    assert accepted["allowed"] is True
    request["degraded"] = {**request["degraded"], "scenario": "idle"}
    rejected = validate_visqol_request(request)
    assert rejected["allowed"] is False
    assert "scenario" in rejected["reason"]


def test_webmushra_export_is_non_destructive_and_import_binds_manifest_sha(tmp_path: Path) -> None:
    parent = tmp_path / "parent.wav"
    candidate = tmp_path / "candidate.wav"
    _write_wav(parent, 220.0)
    _write_wav(candidate, 440.0)
    package = tmp_path / "study"
    manifest = export_webmushra_study(
        package,
        [{"anonymous_id": "V01", "vehicle_id": "hellcat", "scenario": "acceleration", "parent": parent, "candidate": candidate}],
        upstream_receipt={"tool": "webMUSHRA", "version": "fixture", "license": "external"},
    )
    assert manifest["hidden_reference_policy"] == "synthetic_parent_not_real_reference"
    assert (package / "configs" / "s12-stage-n.yaml").is_file()
    assert (package / "results" / ".gitkeep").is_file()
    with pytest.raises(FileExistsError):
        export_webmushra_study(package, [], upstream_receipt={})
    binding = json.loads((package / "webmushra_package_manifest.json").read_text(encoding="utf-8"))
    result = package / "results" / "fixture.csv"
    with result.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=binding["required_result_columns"])
        writer.writeheader()
        row = {
            "listener_id": "fixture-not-human",
            "anonymous_id": "V01",
            "package_manifest_sha256": binding["package_manifest_sha256"],
            "candidate_sha256": binding["trials"]["V01"]["candidate_sha256"],
        }
        row.update({dimension: "50" for dimension in binding["required_result_columns"] if dimension not in row})
        writer.writerow(row)
    receipt = import_webmushra_results(result, binding)
    assert receipt["status"] == "FIXTURE_IMPORT_ONLY_NOT_HUMAN_FEEDBACK"
    assert receipt["accepted_rows"] == 1
    assert receipt["human_feedback_available"] is False
    raw = package / "results" / "mushra.csv"
    raw.write_text(
        "session_test_id,listener_id,session_uuid,trial_id,rating_stimulus,rating_score,rating_time,rating_comment\n"
        "s12-stage-n-webmushra-v1,fixture-webmushra,uuid,V01,stage_m_candidate,75,1.0,fixture\n",
        encoding="utf-8",
    )
    raw_receipt = import_webmushra_results(raw, binding)
    assert raw_receipt["source_format"] == "webmushra_raw_mushra_csv"
    assert raw_receipt["accepted_rows"] == 1
    assert raw_receipt["human_feedback_available"] is False


def test_unified_result_keeps_missing_reference_order_not_qualified() -> None:
    stage_m = {
        "vehicles": {
            "hellcat": {
                "comparison_kind": "synthetic_parent_to_candidate_internal_regression_only",
                "spectral": {"log_distance": 0.2},
                "order": {"comparison": {"status": "not_evaluated_without_rpm_trace"}},
                "uncertainty": {"external_reference_missing": True},
            }
        }
    }
    result = build_unified_results(stage_m, human_feedback=None)
    hellcat = result["vehicles"]["hellcat"]["full_cycle"]
    assert hellcat["order_identity"]["status"] == "ORDER_COMPARISON_NOT_QUALIFIED"
    assert hellcat["human_score"] is None
    assert result["no_truth_percentage"] is True


def test_matlab_adapters_name_real_functions_and_never_estimate_missing_rpm() -> None:
    matlab = Path("tools/sound_sim/s12/acoustic_comparator/matlab")
    order = (matlab / "s12_order_analysis.m").read_text(encoding="utf-8")
    psycho = (matlab / "s12_psychoacoustic_analysis.m").read_text(encoding="utf-8")
    for function in ("rpmordermap", "rpmfreqmap", "orderspectrum", "ordertrack"):
        assert function in order
    assert "REFERENCE_RPM_UNAVAILABLE" in order
    assert "ORDER_COMPARISON_NOT_QUALIFIED" in order
    assert "EXECUTED_ON_PROJECT_DATA" in order
    assert "signal_pcm24" in order
    assert "rpmtrack(" not in order
    for function in ("acousticLoudness", "acousticSharpness", "acousticRoughness", "acousticFluctuation", "acousticToneToNoiseRatio", "acousticProminenceRatio"):
        assert function in psycho


def test_matlab_project_input_trace_hashes_and_manual_runner_contract() -> None:
    trace = build_drive_cycle_trace("hellcat", 60.0)
    assert _stage_k_trace_sha256(trace) != _stage_l_trace_sha256(trace)
    states = _state_codes(trace.time_s)
    assert states.dtype == np.uint8
    assert set(np.unique(states)) == {0, 1, 2, 3, 4, 5}
    binding = CandidateBinding(
        vehicle_id="hellcat",
        source_package="fixture",
        candidate_path="candidate.wav",
        candidate_sha256="a" * 64,
        trace_sha256=_stage_l_trace_sha256(trace),
        trace_hash_kind="stage_l_json_time_rpm_load_throttle",
        frame_count=trace.time_s.size,
        raw_pcm24=b"fixture",
    )
    assert binding.trace_sha256 == "7a1f057a191ed4dc85f5fcbc2750d3dc1a8662031ecc21388ea2aea2d9b92d9f"
    runner = Path("tools/sound_sim/s12/acoustic_comparator/matlab/s12_stage_n_run_order_analysis.m").read_text(encoding="utf-8")
    assert "s12_order_analysis(struct('mode', 'fixture')" in runner
    assert "s12:StageN:OutputExists" in runner
    assert "REFERENCE_RPM_UNAVAILABLE" in runner


def test_mosqito_adapter_is_real_call_path_not_proxy() -> None:
    adapter = Path("tools/sound_sim/s12/acoustic_comparator/psychoacoustics/mosqito_adapter.py").read_text(encoding="utf-8")
    for function in ("loudness_zwst", "sharpness_din_st", "roughness_dw", "tnr_ecma_st", "pr_ecma_st"):
        assert function in adapter
    assert "proxy_metrics" not in adapter
