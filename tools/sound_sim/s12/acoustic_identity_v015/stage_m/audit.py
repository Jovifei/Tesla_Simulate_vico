"""Fail-closed Stage-M qualification evidence helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

VEHICLES = ("ferrari_458", "hellcat", "rx7_fd", "supra_jza80", "aventador_lp700", "c63_w204", "gtr_r35", "lfa")
QUALIFICATION_STATUSES = frozenset(("DIAGNOSTIC_ONLY", "AUTOMATED_PASS_HUMAN_PENDING", "HUMAN_FAIL_REPAIR_REQUIRED", "PROFILE_CANDIDATE", "PROFILE_FREEZE_READY"))
REQUIRED_FEEDBACK_FIELDS = frozenset(("listener_id", "playback_device", "windows_volume", "playback_endpoint", "vehicle_id", "scenario", "baseline_file", "candidate_file", "identity_score", "realism_score", "low_frequency_score", "mechanical_score", "shift_score", "afterfire_score", "artifact_score", "preference", "notes"))

def audit_qualification_callgraph() -> dict[str, object]:
    return {
        "nodes": ["candidate_grid", "renderer_source_overlay", "source_metrics", "final_pcm_metrics", "reference_distance", "hard_gates", "state_regression", "candidate_search", "selected_candidate", "review_package", "status_manifest"],
        "findings": {
            "hard_gates": "candidate_search consumes caller-supplied metrics.hard_gates",
            "reference_distance": "candidate_search deliberately does not recompute or require reference distance",
            "event_evidence": "Round-2 modules measure named event arrays against trace windows",
            "review_gain": "package manifests label comfort as static post-PCM copy separate from formal PCM",
            "qualification": "diagnostic packages remain intentionally buildable when automatic gates fail",
        },
        "fail_closed": {"reference_distance_enters_hard_gate": False, "selection_without_supplied_gates": False},
    }


def gate_source_matrix() -> dict[str, object]:
    """Return the authoritative Stage-M audit of the Round-2 selection path."""

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
    return {"schema_version": "s12-stage-m-gate-source-matrix-1", "gates": rows, "qualification_defect": "reference_distance_is_not_a_required_round2_hard_gate"}


def signal_domain_matrix() -> dict[str, object]:
    return {
        "formal_pcm": {"analysis_allowed": True, "audition_allowed": True, "pipeline": ["frozen_ptr", "edge_fade", "one_fixed_whole_cycle_gain", "pcm24"]},
        "comfort_review_copy": {"analysis_allowed": False, "audition_allowed": True, "gain": "one static post-PCM 1.25x requested gain, headroom limited"},
        "source_stems": {"analysis_allowed": True, "audition_allowed": False, "restriction": "must not be presented as final PCM reference distance"},
        "reference_recording": {"analysis_allowed": "only when provenance, scenario, RPM and window contracts are bound", "audition_allowed": True},
    }

def validate_named_feedback(rows: Sequence[Mapping[str, object]], known_file_ids: set[str]) -> dict[str, object]:
    if not rows:
        return {"accepted": False, "reason": "WAITING_FOR_JOVI_NAMED_REVIEW", "content_read": False, "human_pass": False}
    seen: set[tuple[str, str]] = set()
    for row in rows:
        missing = REQUIRED_FEEDBACK_FIELDS - set(row)
        if missing:
            raise ValueError(f"feedback missing required fields: {sorted(missing)}")
        vehicle = row["vehicle_id"]
        candidate = row["candidate_file"]
        if not isinstance(vehicle, str) or vehicle not in VEHICLES:
            raise ValueError("unknown vehicle")
        if not isinstance(candidate, str) or candidate not in known_file_ids:
            raise ValueError("unknown candidate file")
        key = (str(row["listener_id"]), candidate)
        if key in seen:
            raise ValueError("duplicate feedback response")
        seen.add(key)
        for field in ("identity_score", "realism_score", "low_frequency_score", "mechanical_score", "shift_score", "afterfire_score", "artifact_score", "preference"):
            if row[field] in ("", None):
                raise ValueError(f"blank feedback field: {field}")
    return {"accepted": True, "content_read": True, "human_pass": False, "reason": "VALID_NAMED_FEEDBACK_REQUIRES_REVIEW"}

def build_gate_matrix(automatic: Mapping[str, bool], feedback: Mapping[str, object]) -> dict[str, str]:
    result: dict[str, str] = {}
    for vehicle in VEHICLES:
        if automatic.get(vehicle) is not True:
            result[vehicle] = "DIAGNOSTIC_ONLY"
        elif feedback.get("accepted") is not True:
            result[vehicle] = "AUTOMATED_PASS_HUMAN_PENDING"
        else:
            result[vehicle] = "PROFILE_CANDIDATE"
    return result
