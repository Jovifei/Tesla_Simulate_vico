from __future__ import annotations

from tools.sound_sim.s12.real_reference.professional_diagnosis import (
    build_bounded_candidate_results,
    build_plain_language_diagnosis,
    build_r2_diagnostic_plan,
)


def _pair(vehicle_id: str, pair_id: str) -> dict:
    bands = {name: {"reference_share": 0.1, "candidate_share": 0.1, "delta": 0.0} for name in ("20_60", "60_120", "120_250", "250_400", "400_1000", "1000_4000", "4000_5500", "5500_12000")}
    if vehicle_id == "ferrari_458":
        bands["120_250"]["delta"] = -0.2
        bands["250_400"]["delta"] = -0.2
        bands["1000_4000"]["delta"] = 0.4
        bands["4000_5500"]["delta"] = -0.1
    elif vehicle_id == "hellcat":
        bands["60_120"]["delta"] = 0.2
        bands["120_250"]["delta"] = -0.2
        bands["250_400"]["delta"] = -0.2
        bands["400_1000"]["delta"] = 0.1
    else:
        bands["60_120"]["delta"] = -0.1
        bands["120_250"]["delta"] = 0.7
        bands["400_1000"]["delta"] = -0.3
        bands["1000_4000"]["delta"] = -0.1
    return {
        "pair_id": pair_id,
        "file_id": pair_id + "-reference-vs-candidate",
        "vehicle_id": vehicle_id,
        "scenario": "scenario_candidate_peak",
        "reference_class": "R3",
        "reference_sha256": "a" * 64,
        "candidate_sha256": "b" * 64,
        "window": {"start_s": 0.0, "duration_s": 5.0},
        "microphone_uncertainty": "UNKNOWN_PUBLIC_VIDEO_CAPTURE",
        "order": {"status": "ORDER_COMPARISON_NOT_QUALIFIED"},
        "matlab": {"tool_domain": "Professional MATLAB", "delta": {"roughness_asper": -0.05}},
        "mosqito": {"tool_domain": "Professional MoSQITo", "delta": {"roughness_asper": -0.05}},
        "legacy_proxy": {"tool_domain": "Legacy Proxy", "bands": bands, "transient": {"crest_factor": 0.1}},
    }


def test_plain_language_diagnosis_has_three_anchor_vehicle_sections_without_similarity_percent() -> None:
    metrics = {"pairs": [_pair("ferrari_458", "ferrari_01"), _pair("hellcat", "hellcat_01"), _pair("rx7_fd", "rx7_01")]}
    diagnosis = build_plain_language_diagnosis(metrics)
    assert {row["vehicle_id"] for row in diagnosis["vehicles"]} == {"ferrari_458", "hellcat", "rx7_fd"}
    text = " ".join(item["diagnosis_zh"] for row in diagnosis["vehicles"] for item in row["items"])
    assert "120–400Hz" in text
    assert "120–250Hz" in text
    assert "相似度" not in text
    assert diagnosis["overall_status"] == "R2_DIAGNOSTIC_ONLY_NO_TOTAL_SIMILARITY"


def test_r2_plan_has_one_parameter_group_per_anchor_and_at_most_64_specs() -> None:
    metrics = {"pairs": [_pair("ferrari_458", "ferrari_01"), _pair("hellcat", "hellcat_01"), _pair("rx7_fd", "rx7_01")]}
    plan = build_r2_diagnostic_plan(metrics)
    assert len(plan["anchors"]) == 3
    assert {row["parameter_group"] for row in plan["anchors"]} == {
        "metallic_high_order_envelope_mid_band",
        "pressure_attack_blower_intake_balance",
        "rotary_housing_turbo_distribution",
    }
    assert all(row["candidate_spec_count"] <= 64 for row in plan["anchors"])
    assert plan["automatic_tuning_eligible"] is False


def test_candidate_results_are_specs_only_until_jovi_review() -> None:
    metrics = {"pairs": [_pair("ferrari_458", "ferrari_01"), _pair("hellcat", "hellcat_01"), _pair("rx7_fd", "rx7_01")]}
    results = build_bounded_candidate_results(build_r2_diagnostic_plan(metrics))
    assert results["status"] == "WAITING_FOR_JOVI_GUIDED_REVIEW"
    assert all(anchor["evaluated_count"] == 0 for anchor in results["anchors"])
    assert all(anchor["candidate_spec_count"] <= 64 for anchor in results["anchors"])
    assert results["profile_candidate_ready"] is False
    assert results["objective_before_after_claim"] == "NOT_CLAIMED"
