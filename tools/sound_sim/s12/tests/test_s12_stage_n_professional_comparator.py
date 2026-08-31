from __future__ import annotations

import csv
import hashlib
import json
import wave
from pathlib import Path

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_comparator.listening.webmushra_export import (
    RATING_DIMENSIONS,
    apply_chinese_webmushra_patch,
    export_webmushra_study,
)
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
    recommend_parameter_adjustments,
    tool_record,
    validate_tool_record,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_n.run_stage_n import (
    _prepare_feedback_closure,
    _validated_fixture_import_matches_binding,
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
    assert manifest["loop_range_policy"] == "participant_settable_full_clip_default"
    assert manifest["future_candidate_policy"] == "INACTIVE_NOT_GENERATED_NO_SOURCE_CHANGE_AUTHORIZED"
    assert (package / "configs" / "s12-stage-n.yaml").is_file()
    assert (package / "results" / ".gitkeep").is_file()
    assert "--lss-input" in (package / "LOCAL_WEBMUSHRA_SETUP.md").read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        export_webmushra_study(package, [], upstream_receipt={})
    versioned = tmp_path / "study-v2"
    export_webmushra_study(
        versioned,
        [{"anonymous_id": "V01", "vehicle_id": "hellcat", "scenario": "acceleration", "parent": parent, "candidate": candidate}],
        upstream_receipt={"tool": "webMUSHRA", "version": "fixture"},
        study_id="s12-stage-n-webmushra-v2",
    )
    assert (versioned / "configs" / "s12-stage-n-webmushra-v2.yaml").is_file()
    versioned_config = (versioned / "configs" / "s12-stage-n-webmushra-v2.yaml").read_text(encoding="utf-8")
    assert "testId: s12-stage-n-webmushra-v2" in versioned_config
    assert "configs/s12-stage-n-webmushra-v2/audio/V01/" in versioned_config
    binding = json.loads((package / "webmushra_package_manifest.json").read_text(encoding="utf-8"))
    assert "identity_guess" in binding["required_result_columns"]
    assert "identity_guess" in (package / "configs" / "s12-stage-n.yaml").read_text(encoding="utf-8")
    result = package / "results" / "fixture.csv"
    with result.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=binding["required_result_columns"])
        writer.writeheader()
        row = {
            "listener_id": "fixture-not-human",
            "anonymous_id": "V01",
            "package_manifest_sha256": binding["package_manifest_sha256"],
            "candidate_sha256": binding["trials"]["V01"]["candidate_sha256"],
            "identity_guess": "hellcat",
        }
        row.update({dimension: "50" for dimension in binding["required_result_columns"] if dimension not in row})
        writer.writerow(row)
    receipt = import_webmushra_results(result, binding)
    assert receipt["status"] == "FIXTURE_IMPORT_ONLY_NOT_HUMAN_FEEDBACK"
    assert receipt["accepted_rows"] == 1
    assert receipt["human_feedback_available"] is False
    row["identity_guess"] = "unknown_vehicle"
    with result.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=binding["required_result_columns"])
        writer.writeheader()
        writer.writerow(row)
    rejected_identity = import_webmushra_results(result, binding)
    assert rejected_identity["accepted_rows"] == 0
    assert rejected_identity["errors"] == [{"line": 2, "reason": "identity_guess_not_in_study_vehicle_set"}]
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
    assert _validated_fixture_import_matches_binding(raw_receipt, binding) is True
    stale = {**raw_receipt, "rows": [{**raw_receipt["rows"][0], "package_manifest_sha256": "0" * 64}]}
    assert _validated_fixture_import_matches_binding(stale, binding) is False
    lss = package / "results" / "lss.csv"
    with lss.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["session_test_id", "listener_id", "trial_id", "stimuli_rating", "stimuli", "rating_time"],
        )
        writer.writeheader()
        for dimension in (*RATING_DIMENSIONS, "identity_guess"):
            writer.writerow({
                "session_test_id": binding["test_id"],
                "listener_id": "fixture-webmushra",
                "trial_id": f"V01_{dimension}",
                "stimuli_rating": "hellcat" if dimension == "identity_guess" else "50",
                "stimuli": "stage_m_candidate",
                "rating_time": "1.0",
            })
    combined_receipt = import_webmushra_results(raw, binding, lss_csv=lss)
    assert combined_receipt["source_format"] == "webmushra_raw_mushra_and_lss_csv"
    assert combined_receipt["accepted_rows"] == 1
    assert combined_receipt["rows"] == [{
        "listener_id": "fixture-webmushra",
        "anonymous_id": "V01",
        "package_manifest_sha256": binding["package_manifest_sha256"],
        "candidate_sha256": binding["trials"]["V01"]["candidate_sha256"],
        "identity_guess": "hellcat",
        **{dimension: "50" for dimension in RATING_DIMENSIONS},
    }]
    bad_lss = package / "results" / "bad_lss.csv"
    bad_lss.write_text(lss.read_text(encoding="utf-8").replace(",hellcat,stage_m_candidate,", ",unknown_vehicle,stage_m_candidate,"), encoding="utf-8")
    rejected_combined = import_webmushra_results(raw, binding, lss_csv=bad_lss)
    assert rejected_combined["accepted_rows"] == 0
    assert any(error["reason"] == "identity_guess_not_in_study_vehicle_set" for error in rejected_combined["errors"])


def test_webmushra_export_is_chinese_and_patch_is_idempotent(tmp_path: Path) -> None:
    parent = tmp_path / "parent.wav"
    candidate = tmp_path / "candidate.wav"
    _write_wav(parent, 220.0)
    _write_wav(candidate, 440.0)
    package = tmp_path / "study"
    export_webmushra_study(
        package,
        [{"anonymous_id": "V01", "vehicle_id": "hellcat", "scenario": "full_cycle", "parent": parent, "candidate": candidate}],
        upstream_receipt={"tool": "webMUSHRA", "version": "fixture"},
    )
    config = (package / "configs" / "s12-stage-n.yaml").read_text(encoding="utf-8")
    assert "language: zh" in config
    assert "真实声浪对比与调音听审" in config
    assert "Playback level" not in config
    assert "Rate the" not in config
    assert "听者编号" in config
    patch_file = package / "webmushra_zh_cn_nls.js"
    assert "nls['zh']" in patch_file.read_text(encoding="utf-8")

    checkout = tmp_path / "webmushra"
    (checkout / "lib" / "webmushra" / "nls").mkdir(parents=True)
    (checkout / "index.html").write_text(
        '<script src="lib/webmushra/nls/nls.js"></script>\n', encoding="utf-8"
    )
    first = apply_chinese_webmushra_patch(checkout, patch_file)
    second = apply_chinese_webmushra_patch(checkout, patch_file)
    assert first["index_updated"] is True
    assert second["index_updated"] is False
    index = (checkout / "index.html").read_text(encoding="utf-8")
    assert index.count("s12_stage_s_zh_cn.js") == 1


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
    project = {"status": "EXECUTED_ON_PROJECT_DATA", "vehicles": {"hellcat": {"metrics": {"results": {"loudness_sone": 1.0}}}}}
    project_result = build_unified_results(stage_m, human_feedback=None, mosqito_project=project)
    psycho = project_result["vehicles"]["hellcat"]["full_cycle"]["psychoacoustic_residual"]
    assert psycho["status"] == "CANDIDATE_METRICS_AVAILABLE_REFERENCE_COMPARISON_BLOCKED"
    assert psycho["residual"] is None
    stage_m["vehicles"]["hellcat"]["scenario_metrics"] = {
        "idle": "not_evaluated_without_idle_window",
        "acceleration": "not_evaluated_without_rpm_load_window",
        "lift_afterfire": "not_evaluated_without_lift_window",
        "shift": "not_evaluated_without_shift_window",
    }
    scenario_result = build_unified_results(stage_m, human_feedback=None)
    assert set(scenario_result["vehicles"]["hellcat"]) == {"full_cycle", "idle", "acceleration", "lift_afterfire", "shift"}
    assert scenario_result["vehicles"]["hellcat"]["shift"]["order_identity"]["status"] == "ORDER_COMPARISON_NOT_QUALIFIED"


def test_stage_n_feedback_closure_module_is_available() -> None:
    import importlib.util

    assert importlib.util.find_spec("tools.sound_sim.s12.acoustic_identity_v015.stage_n.feedback_closure") is not None


def _stage_n_feedback_inputs() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    binding = {
        "package_manifest_sha256": "m" * 64,
        "trials": {
            "V01": {"vehicle_id": "hellcat", "scenario": "full_cycle", "candidate_sha256": "a" * 64},
            "V02": {"vehicle_id": "lfa", "scenario": "full_cycle", "candidate_sha256": "b" * 64},
        },
    }
    receipt = {
        "status": "IMPORTED_JOVI_FEEDBACK_PENDING_REVIEW",
        "accepted_rows": 2,
        "rejected_rows": 0,
        "rows": [
            {"listener_id": "Jovi", "anonymous_id": "V01", "package_manifest_sha256": "m" * 64, "candidate_sha256": "a" * 64, "identity_guess": "hellcat", "realism": "75"},
            {"listener_id": "Jovi", "anonymous_id": "V02", "package_manifest_sha256": "m" * 64, "candidate_sha256": "b" * 64, "identity_guess": "hellcat", "realism": "50"},
        ],
    }
    comparator = {"vehicles": {"hellcat": {"full_cycle": {"spectral_residual": 0.1}}, "lfa": {"full_cycle": {"spectral_residual": 0.2}}}}
    return binding, receipt, comparator


def test_feedback_closure_refuses_unconfirmed_listener_claim() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_n.feedback_closure import prepare_feedback_closure

    binding, receipt, comparator = _stage_n_feedback_inputs()
    closure = prepare_feedback_closure(receipt, binding, comparator, confirmed_by_jovi=False)
    assert closure["status"] == "WAITING_FOR_JOVI_HUMAN_FEEDBACK"
    assert closure["human_feedback_available"] is False


def test_publisher_feedback_flow_requires_explicit_confirmation(tmp_path: Path) -> None:
    binding, receipt, comparator = _stage_n_feedback_inputs()
    waiting = _prepare_feedback_closure(None, binding, comparator, confirmed_by_jovi=False)
    assert waiting["status"] == "WAITING_FOR_JOVI_HUMAN_FEEDBACK"
    receipt_path = tmp_path / "jovi_import.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    confirmed = _prepare_feedback_closure(receipt_path, binding, comparator, confirmed_by_jovi=True)
    assert confirmed["status"] == "CONFIRMED_JOVI_FEEDBACK_IMPORTED"


def test_feedback_closure_confirms_bound_rows_and_builds_identity_confusion_matrix() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_n.feedback_closure import prepare_feedback_closure

    binding, receipt, comparator = _stage_n_feedback_inputs()
    closure = prepare_feedback_closure(receipt, binding, comparator, confirmed_by_jovi=True)
    assert closure["status"] == "CONFIRMED_JOVI_FEEDBACK_IMPORTED"
    assert closure["human_feedback_available"] is True
    assert closure["identity_confusion_matrix"]["hellcat"]["hellcat"] == 1
    assert closure["identity_confusion_matrix"]["lfa"]["hellcat"] == 1
    assert closure["objective_residual_bindings"]["lfa"]["full_cycle"]["spectral_residual"] == 0.2


def test_parameter_recommendations_require_confirmed_feedback_and_preserve_source_boundary() -> None:
    unified = {
        "vehicles": {"hellcat": {"full_cycle": {"spectral_residual": 0.1}}},
        "human_feedback_import": {
            "status": "CONFIRMED_JOVI_FEEDBACK_IMPORTED",
            "human_scores_by_vehicle": {"hellcat": [{"low_frequency_weight": "25", "realism": "50"}]},
            "identity_confusion_matrix": {"hellcat": {"hellcat": 1}},
            "objective_residual_bindings": {"hellcat": {"full_cycle": {"spectral_residual": 0.1}}},
        },
    }
    recommendations = recommend_parameter_adjustments(unified)
    recommendation = recommendations["recommendations"][0]
    assert recommendation["metric_residual"] == {"spectral_residual": 0.1, "low_frequency_weight": 25.0}
    assert recommendation["parameter_group"] == "pressure/body resonance (60-120 Hz local band)"
    assert recommendation["direction"].startswith("increase local")
    assert recommendation["no_source_change"] is True


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
    assert "if ~isfolder(outputDirectory)" in order
    assert "measureOrderStability(orderMap, orderAxis, expectedOrders, 0.08)" in order
    assert "tracked_amplitude_relative_variation_observation" in order
    assert "rpmtrack(" not in order
    exporter = (matlab / "s12_export_matlab_comparator_result.m").read_text(encoding="utf-8")
    assert exporter.index("movefile(temporaryPath, jsonPath, 'f');") < exporter.index("clear cleanup")
    for function in ("acousticLoudness", "acousticSharpness", "acousticRoughness", "acousticFluctuation", "acousticToneToNoiseRatio", "acousticProminenceRatio"):
        assert function in psycho
    assert "acousticRoughness(signal, sampleRateHz)" in psycho
    assert "acousticFluctuation(signal, sampleRateHz)" in psycho
    assert "signal = signal(:);" in psycho
    assert "setdiff(fieldnames(fixture), {'sample_rate_hz'}, 'stable')" in psycho
    assert "values.prominent_tone.prominence_ratio_db > values.base.prominence_ratio_db" in psycho


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
    psycho_runner = Path("tools/sound_sim/s12/acoustic_comparator/matlab/s12_stage_n_run_psychoacoustic_analysis.m").read_text(encoding="utf-8")
    assert "s12_psychoacoustic_analysis(struct('mode', 'fixture')" in psycho_runner
    assert "signal_pcm24" in psycho_runner
    assert "matlab_psychoacoustic_session_receipt" in psycho_runner


def test_mosqito_adapter_is_real_call_path_not_proxy() -> None:
    adapter = Path("tools/sound_sim/s12/acoustic_comparator/psychoacoustics/mosqito_adapter.py").read_text(encoding="utf-8")
    for function in ("loudness_zwst", "sharpness_din_st", "roughness_dw", "tnr_ecma_st", "pr_ecma_st"):
        assert function in adapter
    assert "proxy_metrics" not in adapter
    assert "--project-input-root" in adapter
    assert "--shared-fixture-root" in adapter
    assert "shared_fixture_suite" in adapter
    assert 'prominent["tone_to_noise_prominent"]' in adapter
    assert "MATLAB input SHA mismatch" in adapter


def test_shared_fixture_matlab_runner_and_publisher_contract_exist() -> None:
    matlab = Path("tools/sound_sim/s12/acoustic_comparator/matlab")
    shared_runner = matlab / "s12_stage_n_run_shared_psychoacoustic_fixture.m"
    assert shared_runner.is_file()
    runner = Path("tools/sound_sim/s12/acoustic_identity_v015/stage_n/run_stage_n.py").read_text(encoding="utf-8")
    assert "--shared-fixture-root" in runner
    assert "--matlab-shared-psychoacoustic-receipt" in runner
    assert "--mosqito-shared-fixture-receipt" in runner
    assert "stage_n_parameter_recommendations.json" in runner
