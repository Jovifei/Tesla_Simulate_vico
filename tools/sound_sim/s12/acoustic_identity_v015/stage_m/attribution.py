"""Scenario-level, fail-closed Stage-M automatic-gate attribution."""
from __future__ import annotations

from collections.abc import Mapping


VEHICLE_SOURCE_LABELS = {
    "ferrari_458": "stage_k/round2_remaining_sources.py Ferrari 458 named shift_recovery_boom source/trace",
    "hellcat": "independent Stage-L Hellcat v9 diagnostic package",
    "rx7_fd": "stage_k/round2_remaining_sources.py RX-7 FD named blow_off source/trace",
    "supra_jza80": "stage_k/round2_remaining_sources.py Supra JZA80 named spool_release source/trace",
    "aventador_lp700": "stage_k/round2_remaining_sources.py Aventador LP700 named V12 re-engagement source/trace",
    "c63_w204": "stage_k/round2_propagation.py C63 named closed_throttle_tail source/trace",
    "gtr_r35": "stage_k/round2_propagation.py GT-R named wastegate source/trace",
    "lfa": "stage_k/round2_propagation.py LFA named lfa_shift_exhaust_reengagement source/trace",
}

SCENARIOS = ("idle", "acceleration", "shift", "afterfire")
CATEGORY_DEFINITIONS = {
    "A": "candidate actually worsened",
    "B": "reference window misalignment",
    "C": "reference recording operating condition mismatch",
    "D": "R2 recording unsuitable for an absolute gate",
    "E": "source/final-PCM domain mixing",
    "F": "loudness copy used in raw analysis",
    "G": "reference extractor and comparator method mismatch",
    "H": "parameter unreachable for the selected metric",
    "I": "event-qualification logic failure",
    "J": "actual state regression",
    "K": "metric cannot represent the human target",
}


def _event(source_metrics: Mapping[str, object]) -> Mapping[str, object]:
    event = source_metrics.get("event", {})
    return event if isinstance(event, Mapping) else {}


def _candidate_actual_for_scenario(source_metrics: Mapping[str, object], scenario: str, comparison: Mapping[str, object]) -> object:
    if scenario in {"idle", "acceleration"}:
        return {
            "kind": "candidate_source_summary",
            "bands_db": source_metrics.get("bands_db"),
            "spectral_distance": source_metrics.get("spectral_distance"),
            "internal_full_cycle_log_spectral_distance": comparison.get("spectral", {}).get("log_distance"),
        }
    if scenario == "shift":
        return {"kind": "candidate_actual_named_event", "event": _event(source_metrics)}
    return {
        "kind": "candidate_actual_named_lift_or_afterfire",
        "afterfire": source_metrics.get("afterfire"),
        "event": _event(source_metrics),
    }


def _category_assessment(vehicle_id: str, scenario: str, source_metrics: Mapping[str, object], target_segment: Mapping[str, object] | None) -> dict[str, dict[str, object]]:
    event_qualification = _event(source_metrics).get("qualification", {})
    event_qualification = event_qualification if isinstance(event_qualification, Mapping) else {}
    ferrari_failure = vehicle_id == "ferrari_458" and scenario == "shift" and event_qualification.get("eligible") is False
    lfa_resolved = vehicle_id == "lfa" and scenario == "shift" and event_qualification.get("eligible") is True and event_qualification.get("wrong_condition_event_count") == 0
    return {
        "A": {"state": "not_proven", "reason": "no comparable external raw waveform/window exists"},
        "B": {"state": "unassessable", "reason": "external raw window and RPM trace are unavailable"},
        "C": {"state": "confirmed", "reason": "reference target is B/R2 microphone/AGC/configuration dependent without a bound operating-condition trace"},
        "D": {"state": "confirmed", "reason": "relative extracted summary cannot support an absolute automated gate"},
        "E": {"state": "not_observed", "reason": "M2 domain audit keeps source, final PCM, and review paths separate"},
        "F": {"state": "not_observed", "reason": "comparator rejects loudness-matched audition signals for raw analysis"},
        "G": {"state": "confirmed", "reason": "reference targets expose four aggregated bands while Stage-M comparator uses eight bands and lacks source waveform/STFT settings"},
        "H": {"state": "confirmed", "reason": "no parameter can be ranked against a legally usable, scenario/RPM-bound target"},
        "I": {"state": "confirmed", "reason": f"actual named event is ineligible: {event_qualification}"} if ferrari_failure else ({"state": "resolved", "reason": "actual ASG re-engagement has 3 events and 0 wrong-condition events"} if lfa_resolved else {"state": "not_observed", "reason": "actual named-event receipt does not show an eligibility failure for this scenario"}),
        "J": {"state": "not_observed", "reason": "available receipt does not establish a state-regression breach"},
        "K": {"state": "confirmed", "reason": "no Jovi named listening result exists to connect the R2 scalar target to human identity/realism"},
    }


def attribute_vehicle_failure(
    vehicle_id: str,
    comparison: Mapping[str, object] | None,
    *,
    scenario: str,
    source_metrics: Mapping[str, object] | None = None,
    target_segment: Mapping[str, object] | None = None,
    package_status: str = "PARTIAL / AUTOMATED_GATE_FAIL / UNQUALIFIED_DIAGNOSTIC_ONLY",
) -> dict[str, object]:
    """Emit all requested fields without turning a relative R2 summary into a target waveform."""

    if vehicle_id not in VEHICLE_SOURCE_LABELS:
        raise ValueError(f"unknown vehicle: {vehicle_id}")
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario: {scenario}")
    comparison = comparison or {}
    source_metrics = source_metrics or {}
    assessment = _category_assessment(vehicle_id, scenario, source_metrics, target_segment)
    confirmed = [code for code, row in assessment.items() if row["state"] == "confirmed"]
    event = _event(source_metrics)
    target = None if target_segment is None else {
        "kind": "B_R2_relative_feature_summary_not_raw_reference",
        "values": target_segment,
        "usable_for_absolute_gate": False,
    }
    legacy_note = None
    if vehicle_id in {"c63_w204", "gtr_r35"}:
        legacy_note = "Historical large negative reference-distance reports are not reproduced as deterioration: the raw reference window/RPM trace and extractor contract are unavailable; categories B/C/D/G/K prevent blind tuning."
    return {
        "vehicle_id": vehicle_id,
        "scenario": scenario,
        "target": target,
        "parent_actual": None,
        "candidate_actual": _candidate_actual_for_scenario(source_metrics, scenario, comparison),
        "parent_error": None,
        "candidate_error": None,
        "improvement": None,
        "hard_gate": False,
        "hard_gate_evidence": {"package_status": package_status, "reason": "automatic gate did not pass; no real-reference gate is eligible"},
        "failure_category": confirmed,
        "category_assessment": assessment,
        "evidence": {
            "named_source": VEHICLE_SOURCE_LABELS[vehicle_id],
            "source_metrics": source_metrics,
            "comparison_kind": comparison.get("comparison_kind", "no_formal_pcm_pair"),
            "external_reference_missing": comparison.get("uncertainty", {}).get("external_reference_missing", True),
            "legacy_negative_reference_distance_diagnosis": legacy_note,
        },
        "parameter_reachability": {"reachable": False, "reason": "no legally usable, scenario/RPM-bound external target"},
        "recommended_action": "withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback",
        "uncertainty": "B/R2 relative reference summary only; no raw external waveform, matching window, RPM trace, or microphone/setup contract",
    }


def build_eight_vehicle_attribution(
    comparisons: Mapping[str, Mapping[str, object]],
    source_metrics: Mapping[str, Mapping[str, object]],
    target_segments: Mapping[str, Mapping[str, Mapping[str, object]]],
    package_status: Mapping[str, str],
) -> list[dict[str, object]]:
    records = []
    for vehicle_id in VEHICLE_SOURCE_LABELS:
        for scenario in SCENARIOS:
            records.append(attribute_vehicle_failure(
                vehicle_id,
                comparisons.get(vehicle_id),
                scenario=scenario,
                source_metrics=source_metrics.get(vehicle_id),
                target_segment=target_segments.get(vehicle_id, {}).get(scenario),
                package_status=package_status.get(vehicle_id, "PARTIAL / AUTOMATED_GATE_FAIL / UNQUALIFIED_DIAGNOSTIC_ONLY"),
            ))
    return records
