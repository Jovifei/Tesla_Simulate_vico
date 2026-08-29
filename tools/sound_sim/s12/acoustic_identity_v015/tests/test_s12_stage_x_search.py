"""Stage X tests: parameter reachability, search utilities, engineering gate, R1 fixture."""

from __future__ import annotations

import json

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_x import engineering_gate as eg
from tools.sound_sim.s12.acoustic_identity_v015.stage_x import formal_gate_fixture as fgf
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.candidate_search import refine_overrides, sobol_overrides
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.search_parameters import (
    PARAMETER_NOT_REACHABLE,
    PARAMETER_REACHABLE,
    apply_parameters,
    hellcat_search_parameters,
)


def _good_record(**overrides) -> dict:
    record = {
        "finite": True,
        "clipping_samples": 0,
        "click_ok": True,
        "overrides": {"attack_mix_120_400": 0.2},
        "comparison": {
            "improvement_fraction": 0.22,
            "dimension_median_relative_error": {
                "low_frequency_body": -0.30,
                "120_400_pressure_attack": -0.25,
                "mid_band_congestion": -0.10,
                "mechanical_texture": -0.15,
                "synthetic_artifact": -0.05,
                "dynamic_range": 0.02,
            },
        },
    }
    record.update(overrides)
    return record


def test_every_parameter_has_probe_protocol() -> None:
    parameters = hellcat_search_parameters()
    assert len(parameters) == 27
    for item in parameters:
        assert item.scenes, item.name
        assert item.stem in {"post_ptr", "monitor"}, item.name
        assert item.architecture in {"P2H", "P3", "P5"}, item.name


def test_apply_parameters_mutates_and_validates() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config, validate_config

    parameters = hellcat_search_parameters()
    base = load_config("hellcat_v1")
    overrides = {item.name: item.baseline for item in parameters}
    merged = apply_parameters(base, overrides, parameters)
    validated = validate_config(merged)  # must pass strict provenance validation
    assert validated["vehicle_id"] == base["vehicle_id"]
    with pytest.raises(KeyError):
        apply_parameters(base, {"not_a_parameter": 1.0}, parameters)


def test_sobol_and_refine_stay_in_bounds() -> None:
    parameters = hellcat_search_parameters()
    coarse = sobol_overrides(parameters, 8, seed=11)
    assert len(coarse) == 8
    for row in coarse:
        for item in parameters:
            assert item.baseline - item.delta - 1e-9 <= row[item.name] <= item.baseline + item.delta + 1e-9
    center = {item.name: item.baseline for item in parameters}
    refined = refine_overrides(parameters, center, 6, seed=12)
    for row in refined:
        for item in parameters:
            assert item.baseline - item.delta <= row[item.name] <= item.baseline + item.delta


def test_engineering_gate_eligible_on_strong_record() -> None:
    gate = eg.evaluate_engineering_preselection(
        _good_record(),
        architecture="P3",
        valid_reference_count=4,
        reference_evidence_level="R2_AUDIO_DIAGNOSTIC",
        monitor_idle_rms=0.01,
    )
    assert gate["hard_gates_passed"] is True
    assert gate["eligibility"]["selection_eligible"] is True
    assert gate["status"] == "R2_ENGINEERING_PRESELECTION"


def test_engineering_gate_fail_closed_paths() -> None:
    weak = _good_record(comparison={"improvement_fraction": 0.05, "dimension_median_relative_error": {}})
    gate = eg.evaluate_engineering_preselection(weak, architecture="P3", valid_reference_count=1, reference_evidence_level="NONE", monitor_idle_rms=None)
    assert gate["eligibility"]["selection_eligible"] is False
    assert gate["status"] == "NO_R2_ENGINEERING_CANDIDATE_IMPROVED"
    assert "VALID_REFERENCE_COUNT_LT_2" in gate["eligibility"]["blocking_reasons"]
    assert "MEDIAN_IMPROVEMENT_BELOW_15PCT" in gate["eligibility"]["blocking_reasons"]
    clipped = _good_record(clipping_samples=3)
    gate2 = eg.evaluate_engineering_preselection(clipped, architecture="P3", valid_reference_count=4, reference_evidence_level="R2_AUDIO_DIAGNOSTIC", monitor_idle_rms=0.01)
    assert gate2["hard_gates_passed"] is False
    assert gate2["eligibility"]["selection_eligible"] is False


def test_r1_fixture_pipeline_is_ready_but_fail_closed(tmp_path) -> None:
    receipt = fgf.generate_synthetic_r1_fixture(tmp_path)
    assert receipt["fixture"] is True
    for marker in fgf.FIXTURE_MARKERS:
        assert marker in str(receipt)
    order = fgf.export_matlab_order_input([fgf.FormalReferenceCase(**{**case, "uncertainty": {}}) if False else _case_from_dict(case) for case in receipt["cases"]], tmp_path / "order_input.json")
    assert order["order_metric_status"] == "QUALIFIED_WITH_SYNCHRONIZED_RPM"
    result = fgf.evaluate_formal_selection(receipt, {"P3": 0.42, "P2H": 0.10}, human_confirmation=False)
    assert result["all_checks_pass"] is True
    assert result["selected_architecture"] is None
    assert result["formal_selection_status"] == "FORMAL_SELECTION_READY_NOT_RUN"
    assert result["profile_candidate_gate"]["opened"] is False
    assert result["real_status"]["status"] == "FORMAL_R1_REFERENCE_MISSING"


def _case_from_dict(payload: dict) -> fgf.FormalReferenceCase:
    return fgf.FormalReferenceCase(
        scenario=payload["scenario"],
        audio_path=payload["audio_path"],
        audio_sha256=payload["audio_sha256"],
        evidence_level=payload["evidence_level"],
        rights_status=payload["rights_status"],
        sample_rate=payload["sample_rate"],
        start_s=payload["start_s"],
        end_s=payload["end_s"],
        microphone_position=payload["microphone_position"],
        agc_post_processing=payload["agc_post_processing"],
        rpm_trace=payload["rpm_trace"],
        load_trace=payload["load_trace"],
        gear_trace=payload["gear_trace"],
        time_coverage_s=payload["time_coverage_s"],
        uncertainty=payload.get("uncertainty", {}),
    )


def test_review_package_validator_fail_closed(tmp_path) -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_x.review_package import validate_review_package

    assert validate_review_package(tmp_path) == ["package_manifest.json missing"]
    manifest_dir = tmp_path / "partial"
    manifest_dir.mkdir()
    (manifest_dir / "package_manifest.json").write_text(json.dumps({"schema": "s12.stage_x.review_package.v1", "boundary": "", "files": {"a.wav": "0" * 64}, "scenarios": {}}), encoding="utf-8")
    errors = validate_review_package(manifest_dir)
    assert any("missing file" in error for error in errors)
    assert any("boundary not displayed" in error for error in errors)


def test_loudness_match_preserves_spectrum() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_x.review_package import _loudness_match

    t = np.arange(48000) / 48000
    reference = np.column_stack([np.sin(2 * np.pi * 100 * t), np.sin(2 * np.pi * 100 * t)]) * 0.4
    candidate = np.column_stack([np.sin(2 * np.pi * 100 * t), np.sin(2 * np.pi * 100 * t)]) * 0.1
    matched = _loudness_match(candidate, reference)
    assert abs(float(np.sqrt(np.mean(np.square(matched.mean(axis=1))))) - float(np.sqrt(np.mean(np.square(reference.mean(axis=1)))))) < 1e-9
