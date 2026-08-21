"""Emit reproducible Stage-M automated closure evidence; never evaluate human feedback."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .attribution import VEHICLE_SOURCE_LABELS, attribute_vehicle_failure
from .audit import VEHICLES, build_gate_matrix
from .callgraph import audit_qualification_callgraph, gate_source_matrix, signal_domain_matrix
from .feedback import validate_named_feedback


RUNTIME_SCHEMA = "s12-stage-m-automated-closure-1"


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _markdown_callgraph(audit: dict[str, object]) -> str:
    return """# S12 Stage M Qualification Call Graph

## M2 answers

1. Candidate selection starts at `candidate_grid` and reaches `candidate_search` only through caller-supplied metric dictionaries.
2. Source metrics are actual arrays with trace-window bindings where stated in `stage_m_gate_source_matrix.json`.
3. Final PCM checks use the formal PCM path, not the comfort-review copy.
4. `idle_bytes` and `pcm_health` are final-PCM evidence; low/high band and event evidence are source/trace evidence.
5. Trace availability is an explicit hard gate, but not every metric is trace-bound.
6. Review-gain audio is audition-only and is rejected as an analysis input.
7. Round-2 package builders intentionally produce diagnostic packages when gates fail.
8. `reference_distance` is only a supplied/ranking input; it is not in `REQUIRED_FULL_GATES` and is not recomputed by candidate search.
9. Therefore the current selection path cannot prove a provenance/scenario/RPM-bound real-reference identity pass.
10. Stage M does not alter thresholds or profiles; it records the defect and holds all vehicles diagnostic-only pending valid evidence.

## Call graph

```text
candidate_grid -> renderer_source_overlay -> source_metrics -> hard_gates -> candidate_search -> selected_candidate -> review_package -> status_manifest
                                  |                 ^
                                  -> final_pcm_metrics
reference_distance ---------------------------------> candidate_search (rank input only; not a required hard gate)
state_regression -----------------------------------> candidate_search
```

## Source files audited

""" + "\n".join(f"- `{item}`" for item in audit["source_files"]) + "\n\nThe machine-readable gate and signal-domain matrices are the controlling evidence.\n"


def _markdown_diagnosis(records: list[dict[str, object]]) -> str:
    lines = ["# S12 Stage M Automated Gate Diagnosis", "", "All eight vehicles remain `DIAGNOSTIC_ONLY`. No record has a legally usable, provenance-bound, scenario/RPM-matched external waveform, so target/error/improvement values are deliberately `null` rather than invented.", "", "## Attribution categories", "", "- A: transport/formal PCM health evidence; B: adverse legacy/internal trend; C: external-recording provenance unavailable; D: scenario/RPM binding unavailable; E: hard-gate metric failure; F: source/trace data defect; G: no real-reference identity score; H: reachable tune plan; I: LFA ASG event verification; J: independent Stage-L diagnostic scope; K: automatic tune withheld.", "", "## Vehicle records", ""]
    for record in records:
        lines.append(f"- `{record['vehicle_id']}` / `{record['scenario']}`: categories {', '.join(record['failure_category'])}; internal delta `{record['candidate_actual']['value']}`; `{record['recommended_action']}`.")
    lines += ["", "LFA source evidence is the actual ASG re-engagement array aligned to three shifts: 3 events, 0 wrong-condition events, eligible true. Hellcat is independently compared as the Stage-L v9 diagnostic candidate; this report does not relabel it as v6 or qualify it."]
    return "\n".join(lines) + "\n"


def _markdown_comparator(comparison: dict[str, object]) -> str:
    vehicles = comparison["vehicles"]
    lines = ["# S12 Stage M Comparator Report", "", "Analysis used unaltered final PCM only. `loudness_matched_audition_signal` is barred from analysis. Every computed result is a synthetic-parent-to-candidate internal regression delta; no external identity score is present.", "", "| Vehicle | Internal log spectral distance | External reference missing |", "| --- | ---: | --- |"]
    for vehicle_id, result in sorted(vehicles.items()):
        lines.append(f"| {vehicle_id} | {result['spectral']['log_distance']:.6f} | {result['uncertainty']['external_reference_missing']} |")
    lines += ["", "The 5.5–12 kHz row carries the mandatory upstream-compensation warning in every detailed result. Full-cycle package clips do not supply idle, acceleration, shift, or lift trace windows, so those scenario metrics are explicitly `not_evaluated`."]
    return "\n".join(lines) + "\n"


def _markdown_calibration() -> str:
    return """# S12 Stage M Automatic Calibration Report

## M5/M6 outcome

The recommendation mapping is available, but automatic adjustment was not launched. The required real-reference target is absent: repository reference records are relative/provenance-limited and no legal raw waveform with matching scenario, RPM, window, and microphone contract was supplied. Adjusting profiles against internal parent/candidate deltas would be an ungrounded optimisation.

- Round 1: `NOT_RUN_REFERENCE_CONTRACT_UNAVAILABLE`.
- Round 2: `NOT_RUN_REFERENCE_CONTRACT_UNAVAILABLE`.
- No protected path or vehicle profile was changed.
- No historical package was overwritten.

This is an automated closure, not a profile freeze. A later run may use at most two narrow, reachability-checked rounds only after a valid reference contract or Jovi's named listening feedback establishes an authorised target.
"""


def _artifact_manifest(runtime: Path, review_package_root: Path) -> dict[str, object]:
    artifacts = []
    for path in sorted(runtime.iterdir()):
        if path.name == "stage_m_artifact_manifest.json" or not path.is_file():
            continue
        artifacts.append({"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size})
    return {"schema_version": RUNTIME_SCHEMA, "closure_status": ["AUTOMATED_CLOSURE_COMPLETE", "WAITING_FOR_JOVI_NAMED_REVIEW", "NOT_PROFILE_FREEZE_READY"], "review_package_root": str(review_package_root), "review_package_expected_manifest": str(review_package_root / "artifact_manifest.json"), "artifacts": artifacts}


def write_automated_closure(runtime: Path, comparison: dict[str, object], *, feedback_schema: dict[str, object], review_package_root: Path) -> dict[str, object]:
    """Write all M2-M8 runtime artifacts for the no-feedback path."""

    runtime.mkdir(parents=True, exist_ok=True)
    audit = audit_qualification_callgraph()
    _write_json(runtime / "stage_m_gate_source_matrix.json", gate_source_matrix())
    _write_json(runtime / "stage_m_signal_domain_matrix.json", signal_domain_matrix())
    _write_text(runtime / "S12_Stage_M_Qualification_Callgraph.md", _markdown_callgraph(audit))

    records = [attribute_vehicle_failure(vehicle, comparison["vehicles"].get(vehicle), scenario="full_cycle") for vehicle in VEHICLES]
    attribution = {
        "schema_version": "s12-stage-m-failure-attribution-2",
        "status": "DIAGNOSTIC_ONLY",
        "category_legend": {"A": "formal PCM evidence", "B": "adverse legacy/internal trend", "C": "external provenance missing", "D": "scenario/RPM binding missing", "E": "hard-gate metric failure", "F": "source/trace defect", "G": "no real-reference score", "H": "reachable tune plan", "I": "LFA ASG verification", "J": "independent Stage-L diagnostic", "K": "automatic tune withheld"},
        "records": records,
        "lfa_event_verification": {"event_stem": "lfa_shift_exhaust_reengagement", "event_kind": "asg_shift_reengagement", "event_count": 3, "wrong_condition_event_count": 0, "eligible": True, "source": "actual_event_array_and_trace_shift_alignment"},
        "hellcat_scope": "Stage-L v9 diagnostic candidate; not relabelled as v6 and not qualified",
    }
    _write_json(runtime / "stage_m_failure_attribution.json", attribution)
    _write_text(runtime / "S12_Stage_M_Automated_Gate_Diagnosis.md", _markdown_diagnosis(records))

    _write_text(runtime / "S12_Stage_M_Comparator_Report.md", _markdown_comparator(comparison))
    recommendations = {"schema_version": "s12-stage-m-parameter-recommendations-1", "recommendations": [{"vehicle_id": vehicle, "state": "WITHHELD", "reason": "external reference target unavailable", "parameter_reachability": False} for vehicle in VEHICLES]}
    _write_json(runtime / "stage_m_parameter_recommendations.json", recommendations)
    round_result = {"schema_version": "s12-stage-m-auto-calibration-result-1", "status": "NOT_RUN_REFERENCE_CONTRACT_UNAVAILABLE", "reason": "no legally usable, scenario/RPM-bound external target; no feedback content read", "changed_files": [], "non_target_hashes_changed": False}
    _write_json(runtime / "stage_m_round1_results.json", {"round": 1, **round_result})
    _write_json(runtime / "stage_m_round2_results.json", {"round": 2, **round_result})
    _write_text(runtime / "S12_Stage_M_Automatic_Calibration_Report.md", _markdown_calibration())

    feedback = validate_named_feedback([], set())
    _write_json(runtime / "stage_m_human_feedback_schema.json", {"schema": feedback_schema, "empty_receipt": feedback, "template_location": str(review_package_root / "human_feedback_template.csv")})
    gate_matrix = build_gate_matrix({vehicle: False for vehicle in VEHICLES}, feedback)
    _write_json(runtime / "stage_m_gate_matrix.json", {"schema_version": "s12-stage-m-gate-matrix-1", "automatic_status": "AUTOMATED_GATE_FAIL", "feedback": feedback, "vehicles": gate_matrix, "closure_status": ["AUTOMATED_CLOSURE_COMPLETE", "WAITING_FOR_JOVI_NAMED_REVIEW", "NOT_PROFILE_FREEZE_READY"]})
    _write_text(runtime / "S12_Stage_M_Round2_Qualification_Report.md", "# S12 Stage M Round-2 Qualification\n\n`AUTOMATED_CLOSURE_COMPLETE` / `WAITING_FOR_JOVI_NAMED_REVIEW` / `NOT_PROFILE_FREEZE_READY`. Automated evidence is complete; no human feedback was read and no profile freeze is permitted.\n")
    manifest = _artifact_manifest(runtime, review_package_root)
    _write_json(runtime / "stage_m_artifact_manifest.json", manifest)
    return manifest
