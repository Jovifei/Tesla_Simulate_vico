"""Stage X two-layer architecture selection contract.

Layer 1 — engineering preselection: data-driven, R2/clean-R3/Jovi-feedback
supported, produces a listenable preferred candidate. Never approved profile.
Layer 2 — formal selection: R1-only, rights-bound, scenario-synchronised.
Stays null until a legal R1 reference set exists.
"""

from __future__ import annotations

from typing import Any

ENGINEERING_SCHEMA = "s12.stage_x.engineering_preselection.v1"
FORMAL_SCHEMA = "s12.stage_x.formal_selection.v1"
CONTRACT_SCHEMA = "s12.stage_x.selection_contract.v1"

ENGINEERING_STATUSES = {
    "NOT_ATTEMPTED",
    "R2_ENGINEERING_PRESELECTION",
    "NO_R2_ENGINEERING_CANDIDATE_IMPROVED",
    "MODEL_REDESIGN_REQUIRED",
    "NO_VALID_REFERENCE",
}
FORMAL_STATUSES = {
    "FORMAL_R1_REFERENCE_MISSING",
    "FORMAL_SELECTION_READY_NOT_RUN",
    "FORMAL_SELECTION_PASS",
    "FORMAL_SELECTION_FAIL",
}
ENGINEERING_EVIDENCE_LEVELS = {"NONE", "R2_R3_DIAGNOSTIC", "R2_AUDIO_DIAGNOSTIC"}
FORMAL_EVIDENCE_LEVEL = "R1_REQUIRED"

_FORBIDDEN_ENGINEERING_CLAIMS = {"APPROVED_PROFILE", "PROFILE_FREEZE", "OEM_MATCH", "HUMAN_PASS", "CALIBRATED"}


def empty_engineering_preselection() -> dict[str, Any]:
    return {
        "schema": ENGINEERING_SCHEMA,
        "architecture": None,
        "evidence_level": "NONE",
        "status": "NOT_ATTEMPTED",
        "objective": {},
        "human_feedback": {},
        "limitations": [],
        "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
    }


def empty_formal_selection() -> dict[str, Any]:
    return {
        "schema": FORMAL_SCHEMA,
        "architecture": None,
        "evidence_level": FORMAL_EVIDENCE_LEVEL,
        "status": "FORMAL_R1_REFERENCE_MISSING",
        "required_inputs": [
            "rights_status=CLEARED",
            "synchronized_rpm_load_gear_trace",
            "scenario_bound_reference_audio",
            "microphone_and_agc_receipt",
            "human_confirmation",
        ],
        "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
    }


def build_selection_contract(engineering: dict[str, Any] | None = None, formal: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = {
        "schema": CONTRACT_SCHEMA,
        "engineering_preselection": dict(empty_engineering_preselection()),
        "formal_selection": dict(empty_formal_selection()),
        "separation_policy": {
            "engineering_gate_inputs": ["R2", "clean_R3", "jovi_feedback", "parent_candidate_metrics", "internal_ablation", "runtime_hard_gates"],
            "engineering_gate_forbidden_outputs": sorted(_FORBIDDEN_ENGINEERING_CLAIMS),
            "formal_gate_inputs": ["R1_audio", "rights", "synchronized_rpm_load_gear", "scenario_binding", "human_confirmation"],
            "missing_r1_blocks": ["formal_selection", "profile_freeze", "productization"],
            "missing_r1_does_not_block": ["engineering_preselection", "candidate_render", "parent_candidate_comparison", "audition_package", "diagnostic_migration", "r1_pipeline_fixture_validation"],
        },
        "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
    }
    if engineering is not None:
        contract["engineering_preselection"] = validate_engineering(engineering)
    if formal is not None:
        contract["formal_selection"] = validate_formal(formal)
    return contract


def validate_engineering(record: dict[str, Any]) -> dict[str, Any]:
    merged = dict(empty_engineering_preselection())
    merged.update({key: record[key] for key in record if key in merged})
    if merged["status"] not in ENGINEERING_STATUSES:
        raise ValueError(f"unknown engineering status: {merged['status']}")
    if merged["evidence_level"] not in ENGINEERING_EVIDENCE_LEVELS:
        raise ValueError(f"unknown engineering evidence level: {merged['evidence_level']}")
    if merged["architecture"] is not None and merged["evidence_level"] == "NONE":
        raise ValueError("an engineering architecture requires an evidence level")
    text = " ".join(str(value) for value in (merged["status"], merged["evidence_level"], *merged["limitations"]))
    for claim in _FORBIDDEN_ENGINEERING_CLAIMS:
        if claim.lower() in text.lower():
            raise ValueError(f"engineering preselection must not claim {claim}")
    return merged


def validate_formal(record: dict[str, Any]) -> dict[str, Any]:
    merged = dict(empty_formal_selection())
    merged.update({key: record[key] for key in record if key in merged})
    if merged["status"] not in FORMAL_STATUSES:
        raise ValueError(f"unknown formal status: {merged['status']}")
    if merged["architecture"] is not None and merged["evidence_level"] != FORMAL_EVIDENCE_LEVEL:
        raise ValueError("formal selection requires R1 evidence level")
    if merged["architecture"] is not None and merged["status"] != "FORMAL_SELECTION_PASS":
        raise ValueError("formal architecture requires FORMAL_SELECTION_PASS")
    return merged


def evaluate_selection_eligibility(
    *,
    hard_gates_passed: bool,
    valid_reference_count: int,
    median_improvement_fraction: float | None,
    reference_evidence_level: str,
) -> dict[str, Any]:
    """Data-driven engineering eligibility. No unconditional False anywhere."""
    reasons: list[str] = []
    if not hard_gates_passed:
        reasons.append("HARD_GATES_FAILED")
    if valid_reference_count < 2:
        reasons.append("VALID_REFERENCE_COUNT_LT_2")
    if median_improvement_fraction is None:
        reasons.append("MEDIAN_OBJECTIVE_UNAVAILABLE")
    elif median_improvement_fraction < 0.15:
        reasons.append("MEDIAN_IMPROVEMENT_BELOW_15PCT")
    if reference_evidence_level not in {"R2_R3_DIAGNOSTIC", "R2_AUDIO_DIAGNOSTIC"}:
        reasons.append("REFERENCE_EVIDENCE_LEVEL_UNSUPPORTED")
    eligible = not reasons
    return {
        "schema": "s12.stage_x.selection_eligibility.v1",
        "selection_eligible": eligible,
        "blocking_reasons": reasons,
        "inputs": {
            "hard_gates_passed": hard_gates_passed,
            "valid_reference_count": valid_reference_count,
            "median_improvement_fraction": median_improvement_fraction,
            "reference_evidence_level": reference_evidence_level,
        },
        "scope": "engineering preselection only; formal R1 selection is a separate gate",
    }


__all__ = [
    "CONTRACT_SCHEMA",
    "ENGINEERING_SCHEMA",
    "FORMAL_SCHEMA",
    "build_selection_contract",
    "empty_engineering_preselection",
    "empty_formal_selection",
    "evaluate_selection_eligibility",
    "validate_engineering",
    "validate_formal",
]
