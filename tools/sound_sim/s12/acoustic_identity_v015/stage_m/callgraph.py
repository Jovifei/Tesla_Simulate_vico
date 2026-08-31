"""Executable audit of the existing Round-2 qualification path."""
from __future__ import annotations

from collections.abc import Mapping

ROUND2_SOURCE_FILES = (
    "stage_k/candidate_search.py",
    "scripts/qualify_stage_k_candidates.py",
    "stage_k/round2_propagation.py",
    "stage_k/round2_legacy_anchors.py",
    "stage_k/round2_remaining_sources.py",
    "stage_k/round2_package.py",
    "stage_k/round2_remaining_package.py",
)

M2_ANSWERS = {
    "hard_gate_data_source": "The ten REQUIRED_FULL_GATES are caller-supplied metrics: source-array, trace, final-PCM and isolation checks. reference_distance is not among them.",
    "actual_arrays_and_trace": "Named event and band metrics originate in actual source arrays; event eligibility is bound to trace windows. pressure_accounting and PCM/isolation checks have their stated non-trace origins.",
    "domain_mixing": "Source, final-PCM and audition domains are separately labeled. Stage M rejects diagnostic/review/unbound sources as hard-gate evidence.",
    "formal_vs_review_copy": "Formal PCM follows frozen_ptr -> edge_fade -> fixed whole-cycle gain -> PCM24. The 1.25x comfort/review copy is post-PCM audition-only.",
    "reference_distance_hard_gate": "No. reference_distance is neither recomputed by candidate_search nor required by REQUIRED_FULL_GATES; it is a post-gate rank input.",
    "diagnostic_package_on_failure": "Round-2 package builders intentionally serialize transport-valid diagnostic evidence when automatic gates fail, preserving investigation without declaring qualification.",
    "best_failing_candidate": "Yes for diagnostics only: run_round2_coordinate_search returns snapshots[-1] as BEST_DIAGNOSTIC_ONLY when no qualified snapshot exists. rank_round2_snapshots never calls it qualified.",
    "baseline_candidate_trace_window_rate_chain": "Package receipts bind each vehicle's formal parent/candidate to one canonical trace SHA and 48 kHz PCM chain; no raw external recording/window exists to prove an external-reference equivalence.",
    "loudness_copy_raw_analysis": "No. loudness_matched_audition_signal is forbidden by the comparator and signal-domain matrix for raw band, loudness, and transient analysis.",
    "named_events_actual_stems": "Yes. The R2 receipts cite actual named source arrays plus trace alignment; e.g. LFA lfa_shift_exhaust_reengagement, Ferrari shift_recovery_boom, RX-7 blow_off, Supra spool_release and Aventador V12 re-engagement.",
}


def audit_qualification_callgraph() -> dict[str, object]:
    return {
        "nodes": [
            "parameter_grid", "renderer_source_overlay", "source_stems", "source_metrics", "common_acoustic_layers", "frozen_ptr",
            "final_pcm", "analysis_copy", "review_gain_copy", "reference_distance", "hard_gates", "state_regression",
            "candidate_search", "selected_candidate", "review_package", "status_manifest",
        ],
        "edges": [
            ["parameter_grid", "renderer_source_overlay"], ["renderer_source_overlay", "source_stems"],
            ["source_stems", "source_metrics"], ["source_stems", "common_acoustic_layers"],
            ["common_acoustic_layers", "frozen_ptr"], ["frozen_ptr", "final_pcm"], ["final_pcm", "analysis_copy"],
            ["final_pcm", "review_gain_copy"], ["source_metrics", "hard_gates"], ["final_pcm", "hard_gates"],
            ["reference_distance", "candidate_search"],
            ["hard_gates", "candidate_search"], ["state_regression", "candidate_search"],
            ["candidate_search", "selected_candidate"], ["selected_candidate", "review_package"], ["review_package", "status_manifest"],
        ],
        "source_files": list(ROUND2_SOURCE_FILES),
        "m2_answers": M2_ANSWERS,
        "findings": {
            "hard_gates": "candidate_search consumes caller-supplied metrics.hard_gates; round2_search requires the ten REQUIRED_FULL_GATES.",
            "reference_distance": "round2_search uses reference_distance as a post-gate rank input; candidate_search does not recompute or require it.",
            "event_evidence": "Round-2 modules measure named event arrays against trace windows.",
            "review_gain": "package manifests label comfort as static post-PCM copy separate from formal PCM.",
            "qualification": "diagnostic packages remain intentionally buildable when automatic gates fail.",
        },
        "fail_closed": {"reference_distance_enters_hard_gate": False, "selection_without_supplied_gates": False},
    }


def gate_source_matrix() -> dict[str, object]:
    rows = {
        "idle_bytes": {"origin": "actual final-PCM bytes", "actual_array": True, "trace_bound": True, "domain": "final_pcm", "hard_gate": True, "review_copy_allowed": False},
        "low_band": {"origin": "actual source arrays", "actual_array": True, "trace_bound": True, "domain": "source", "hard_gate": True, "review_copy_allowed": False},
        "high_band": {"origin": "actual source arrays", "actual_array": True, "trace_bound": True, "domain": "source", "hard_gate": True, "review_copy_allowed": False},
        "spectral_distance": {"origin": "actual candidate/parent arrays", "actual_array": True, "trace_bound": True, "domain": "source", "hard_gate": True, "review_copy_allowed": False},
        "clock_coherence": {"origin": "actual induction arrays and crank trace", "actual_array": True, "trace_bound": True, "domain": "source", "hard_gate": True, "review_copy_allowed": False},
        "ridge_continuity": {"origin": "probe metrics", "actual_array": True, "trace_bound": True, "domain": "source", "hard_gate": True, "review_copy_allowed": False},
        "state_availability": {"origin": "trace-derived windows", "actual_array": True, "trace_bound": True, "domain": "trace", "hard_gate": True, "review_copy_allowed": False},
        "pressure_accounting": {"origin": "actual primitive stems", "actual_array": True, "trace_bound": False, "domain": "source", "hard_gate": True, "review_copy_allowed": False},
        "pcm_health": {"origin": "final PCM array", "actual_array": True, "trace_bound": False, "domain": "final_pcm", "hard_gate": True, "review_copy_allowed": False},
        "isolation": {"origin": "non-target render/hash regression", "actual_array": True, "trace_bound": False, "domain": "final_pcm", "hard_gate": True, "review_copy_allowed": False},
        "reference_distance": {"origin": "caller metric only", "actual_array": False, "trace_bound": False, "domain": "unbound", "hard_gate": False, "review_copy_allowed": False},
    }
    return {"schema_version": "s12-stage-m-gate-source-matrix-3", "audited_source_files": list(ROUND2_SOURCE_FILES), "m2_answers": M2_ANSWERS, "gates": rows, "qualification_defect": "reference_distance_is_not_a_required_round2_hard_gate"}


def signal_domain_matrix() -> dict[str, object]:
    matrix = {
        "unaltered_analysis_signal": {"analysis_allowed": True, "audition_allowed": False, "pipeline": ["formal_final_pcm", "channel_fold_down", "dc_removal"]},
        "loudness_matched_audition_signal": {"analysis_allowed": False, "audition_allowed": True, "gain": "static post-PCM gain/headroom policy"},
        "source_stems": {"analysis_allowed": True, "audition_allowed": False, "restriction": "must not be presented as final PCM reference distance"},
        "reference_recording": {"analysis_allowed": "only when provenance, scenario, RPM and window contracts are bound", "audition_allowed": True},
    }
    matrix["comfort_review_copy"] = matrix["loudness_matched_audition_signal"]
    return matrix


def validate_gate_origin(gate: Mapping[str, object]) -> None:
    """Refuse diagnostic/review/unbound evidence as a hard-gate input."""

    if gate.get("domain") in {"diagnostic", "loudness_matched_audition_signal", "unbound"}:
        raise ValueError("hard gate cannot use diagnostic, review, or unbound evidence")
    if gate.get("trace_bound") is not True and gate.get("name") in {"state_availability", "event_timing", "reference_distance"}:
        raise ValueError("state/event/reference gate requires bound trace/window evidence")
