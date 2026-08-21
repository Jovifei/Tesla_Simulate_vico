"""Executable audit of the existing Round-2 qualification path."""
from __future__ import annotations

from collections.abc import Mapping

ROUND2_SOURCE_FILES = (
    "stage_k/candidate_search.py",
    "scripts/qualify_stage_k_candidates.py",
    "round2_propagation.py",
    "round2_legacy_anchors.py",
    "round2_remaining_sources.py",
    "round2_package.py",
    "round2_remaining_package.py",
)


def audit_qualification_callgraph() -> dict[str, object]:
    return {
        "nodes": [
            "candidate_grid", "renderer_source_overlay", "source_metrics", "final_pcm_metrics", "reference_distance",
            "hard_gates", "state_regression", "candidate_search", "selected_candidate", "review_package", "status_manifest",
        ],
        "edges": [
            ["candidate_grid", "renderer_source_overlay"], ["renderer_source_overlay", "source_metrics"],
            ["renderer_source_overlay", "final_pcm_metrics"], ["source_metrics", "hard_gates"],
            ["final_pcm_metrics", "hard_gates"], ["reference_distance", "candidate_search"],
            ["hard_gates", "candidate_search"], ["state_regression", "candidate_search"],
            ["candidate_search", "selected_candidate"], ["selected_candidate", "review_package"], ["review_package", "status_manifest"],
        ],
        "source_files": list(ROUND2_SOURCE_FILES),
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
        "idle_bytes": {"origin": "actual final-PCM bytes", "trace_bound": True, "domain": "final_pcm", "hard_gate": True},
        "low_band": {"origin": "actual source arrays", "trace_bound": True, "domain": "source", "hard_gate": True},
        "high_band": {"origin": "actual source arrays", "trace_bound": True, "domain": "source", "hard_gate": True},
        "spectral_distance": {"origin": "actual candidate/parent arrays", "trace_bound": True, "domain": "source", "hard_gate": True},
        "clock_coherence": {"origin": "actual induction arrays and crank trace", "trace_bound": True, "domain": "source", "hard_gate": True},
        "ridge_continuity": {"origin": "probe metrics", "trace_bound": True, "domain": "source", "hard_gate": True},
        "state_availability": {"origin": "trace-derived windows", "trace_bound": True, "domain": "trace", "hard_gate": True},
        "pressure_accounting": {"origin": "actual primitive stems", "trace_bound": False, "domain": "source", "hard_gate": True},
        "pcm_health": {"origin": "final PCM array", "trace_bound": False, "domain": "final_pcm", "hard_gate": True},
        "isolation": {"origin": "non-target render/hash regression", "trace_bound": False, "domain": "final_pcm", "hard_gate": True},
        "reference_distance": {"origin": "caller metric only", "trace_bound": False, "domain": "unbound", "hard_gate": False},
    }
    return {"schema_version": "s12-stage-m-gate-source-matrix-2", "audited_source_files": list(ROUND2_SOURCE_FILES), "gates": rows, "qualification_defect": "reference_distance_is_not_a_required_round2_hard_gate"}


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
