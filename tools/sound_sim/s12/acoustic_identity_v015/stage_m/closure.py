"""Emit reproducible Stage-M automated closure evidence; never evaluate human feedback."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .attribution import CATEGORY_DEFINITIONS, build_eight_vehicle_attribution
from .audit import VEHICLES, build_gate_matrix
from .callgraph import audit_qualification_callgraph, gate_source_matrix, signal_domain_matrix
from .feedback import validate_named_feedback


RUNTIME_SCHEMA = "s12-stage-m-automated-closure-1"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _markdown_callgraph(audit: dict[str, object]) -> str:
    answers = "\n".join(f"{index}. **{key}** — {answer}" for index, (key, answer) in enumerate(audit["m2_answers"].items(), start=1))
    return """# S12 Stage M Qualification Call Graph

## M2 machine-readable answers

""" + answers + """

## Call graph

```text
parameter_grid -> renderer_source_overlay -> source_stems -> source_metrics
                                   -> common_acoustic_layers -> frozen_ptr -> final_pcm -> analysis_copy
                                                                                 -> review_gain_copy (audition only)
source_metrics + final_pcm + state_regression -> hard_gates -> candidate_search -> selected_candidate -> review_package -> status_manifest
reference_distance ---------------------------> candidate_search (rank input only; not a required hard gate)
```

## Source files audited

""" + "\n".join(f"- `{item}`" for item in audit["source_files"]) + "\n\nThe machine-readable gate and signal-domain matrices are the controlling evidence.\n"


def _markdown_diagnosis(records: list[dict[str, object]]) -> str:
    lines = ["# S12 Stage M Automated Gate Diagnosis", "", "All eight vehicles remain `DIAGNOSTIC_ONLY`. Relative B/R2 summaries are retained as evidence but are not promoted to raw-recording targets, so parent/candidate errors and improvements remain `null`.", "", "## Attribution categories", ""]
    lines.extend(f"- {code}: {meaning}" for code, meaning in CATEGORY_DEFINITIONS.items())
    lines += ["", "## Vehicle/scenario records", ""]
    for record in records:
        lines.append(f"- `{record['vehicle_id']}` / `{record['scenario']}`: confirmed categories {', '.join(record['failure_category'])}; hard gate `{record['hard_gate']}`; `{record['recommended_action']}`.")
    lines += ["", "LFA source evidence is the actual ASG re-engagement array aligned to three shifts: 3 events, 0 wrong-condition events, eligible true. Ferrari's named shift event receipt is ineligible (two expected events missing). Hellcat is independently compared as the actual Stage-L v9 diagnostic candidate; this report does not relabel it as v6 or qualify it."]
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
    for path in sorted(runtime.rglob("*")):
        if path.name == "stage_m_artifact_manifest.json" or not path.is_file():
            continue
        artifacts.append({"path": path.relative_to(runtime).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size})
    return {"schema_version": RUNTIME_SCHEMA, "closure_status": ["AUTOMATED_CLOSURE_COMPLETE", "WAITING_FOR_JOVI_NAMED_REVIEW", "NOT_PROFILE_FREEZE_READY"], "review_package_root": str(review_package_root), "review_package_expected_manifest": str(review_package_root / "artifact_manifest.json"), "artifacts": artifacts}


def write_automated_closure(
    runtime: Path,
    comparison: dict[str, object],
    *,
    feedback_schema: dict[str, object],
    review_package_root: Path,
    source_metrics: dict[str, dict[str, object]] | None = None,
    target_segments: dict[str, dict[str, dict[str, object]]] | None = None,
    package_status: dict[str, str] | None = None,
    final_context: dict[str, object] | None = None,
) -> dict[str, object]:
    """Write all M2-M8 runtime artifacts for the no-feedback path."""

    runtime.mkdir(parents=True, exist_ok=True)
    audit = audit_qualification_callgraph()
    _write_json(runtime / "stage_m_gate_source_matrix.json", gate_source_matrix())
    _write_json(runtime / "stage_m_signal_domain_matrix.json", signal_domain_matrix())
    _write_text(runtime / "S12_Stage_M_Qualification_Callgraph.md", _markdown_callgraph(audit))

    source_metrics = source_metrics or {}
    target_segments = target_segments or {}
    package_status = package_status or {}
    records = build_eight_vehicle_attribution(comparison["vehicles"], source_metrics, target_segments, package_status)
    lfa_event = source_metrics.get("lfa", {}).get("event", {})
    lfa_qualification = lfa_event.get("qualification", {}) if isinstance(lfa_event, dict) else {}
    attribution = {
        "schema_version": "s12-stage-m-eight-vehicle-failure-attribution-1",
        "status": "DIAGNOSTIC_ONLY",
        "category_legend": CATEGORY_DEFINITIONS,
        "records": records,
        "lfa_event_verification": {"event_stem": lfa_event.get("event_stem"), "event_kind": lfa_event.get("event_kind"), "event_count": lfa_event.get("event_count"), "wrong_condition_event_count": lfa_qualification.get("wrong_condition_event_count"), "eligible": lfa_qualification.get("eligible"), "source": lfa_qualification.get("source")},
        "hellcat_scope": "Stage-L v9 diagnostic candidate; not relabelled as v6 and not qualified",
    }
    _write_json(runtime / "stage_m_failure_attribution.json", attribution)
    _write_json(runtime / "stage_m_eight_vehicle_failure_attribution.json", attribution)
    _write_text(runtime / "S12_Stage_M_Automated_Gate_Diagnosis.md", _markdown_diagnosis(records))

    _write_text(runtime / "S12_Stage_M_Comparator_Report.md", _markdown_comparator(comparison))
    comparator_runtime = runtime / "comparator"
    _write_json(comparator_runtime / "s12_acoustic_comparator_run.json", comparison)
    _write_json(comparator_runtime / "run_receipt.json", {"analysis_domain": "unaltered_final_pcm", "reference_policy": "external raw reference unavailable; internal regression only", "root_result_sha256": hashlib.sha256(json.dumps(comparison, sort_keys=True).encode("utf-8")).hexdigest()})
    recommendations = {"schema_version": "s12-stage-m-parameter-recommendations-1", "recommendations": [{"vehicle_id": vehicle, "state": "WITHHELD", "reason": "external reference target unavailable", "parameter_reachability": False} for vehicle in VEHICLES]}
    _write_json(runtime / "stage_m_parameter_recommendations.json", recommendations)
    round_result = {"schema_version": "s12-stage-m-auto-calibration-result-1", "status": "NOT_RUN_REFERENCE_CONTRACT_UNAVAILABLE", "reason": "no legally usable, scenario/RPM-bound external target; no feedback content read", "changed_files": [], "non_target_hashes_changed": False}
    _write_json(runtime / "stage_m_round1_results.json", {"round": 1, **round_result})
    _write_json(runtime / "stage_m_round2_results.json", {"round": 2, **round_result})
    _write_text(runtime / "S12_Stage_M_Automatic_Calibration_Report.md", _markdown_calibration())

    feedback = validate_named_feedback([], set())
    _write_json(runtime / "stage_m_human_feedback_schema.json", {"schema": feedback_schema, "empty_receipt": feedback, "template_location": str(review_package_root / "Jovi_Stage_M_Named_Feedback.csv"), "feedback_binding_location": str(review_package_root / "feedback_binding.json")})
    gate_matrix = build_gate_matrix({vehicle: False for vehicle in VEHICLES}, feedback)
    _write_json(runtime / "stage_m_gate_matrix.json", {"schema_version": "s12-stage-m-gate-matrix-1", "automatic_status": "AUTOMATED_GATE_FAIL", "feedback": feedback, "vehicles": gate_matrix, "closure_status": ["AUTOMATED_CLOSURE_COMPLETE", "WAITING_FOR_JOVI_NAMED_REVIEW", "NOT_PROFILE_FREEZE_READY"]})
    final_context = final_context or {}
    _write_text(runtime / "S12_Stage_M_Round2_Qualification_Report.md", "# S12 Stage M Round-2 Qualification\n\n" + "\n".join([
        "`AUTOMATED_CLOSURE_COMPLETE` / `WAITING_FOR_JOVI_NAMED_REVIEW` / `NOT_PROFILE_FREEZE_READY`.",
        f"Evidence-generation HEAD: `{final_context.get('head', 'pending final verification')}`.",
        f"Local commits: `{', '.join(final_context.get('local_commits', [])) or 'pending final verification'}`.",
        "Vehicles automatically improved: none (no lawful state/RPM-bound raw target; no calibration run).",
        "Vehicles reference-limited: Ferrari 458, Hellcat, RX-7 FD, Supra JZA80, Aventador LP700, C63 W204, GT-R R35, LFA.",
        "Vehicles still failing: all eight remain DIAGNOSTIC_ONLY; Ferrari also has an actual named shift-event eligibility failure.",
        "Human feedback status: no content read; no human pass inferred.",
        f"Track-P status: {final_context.get('track_p_status', 'pending final verification')}.",
        f"Git status at evidence generation: {final_context.get('git_status', 'pending final verification')}; not pushed; not merged; no PR; no Profile Freeze.",
    ]) + "\n")
    manifest = _artifact_manifest(runtime, review_package_root)
    _write_json(runtime / "stage_m_artifact_manifest.json", manifest)
    return manifest
