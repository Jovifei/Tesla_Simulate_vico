"""Fail-closed Stage-L Hellcat candidate lineage and parameter contract."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping


BASE_COMMIT = "bf653c6f7a3779314d9891aaa801b29a4874db40"
SCHEMA_VERSION = "s12-stage-l-hellcat-candidate-profile-1"
SCHEMA_VERSION_V2 = "s12-stage-l-hellcat-candidate-profile-2"
PARENT_CANDIDATE_ID = "hellcat_stage_k_v7"
PARENT_CANDIDATE_PATH = "targets/stage_k_candidates/hellcat_candidate_v7.json"
PARENT_CANDIDATE_SHA256 = "b730090daa6274c9e6501e9cdf6894ea00f8ccfff535af3f887ec00721d6d358"
V2_PARENT_CANDIDATE_ID = "hellcat_stage_l_v8"
V2_PARENT_CANDIDATE_PATH = "targets/stage_l_candidates/hellcat_candidate_v8.json"
V2_PARENT_CANDIDATE_SHA256 = "18903081a45d9263d65db86f8ce93557ea3ad69905d204c04a66205c0fdd046c"
REFERENCE_TARGET_PATH = "reference_database/hellcat_reference_targets.json"
REFERENCE_TARGET_SHA256 = "84030e8204fe228fddb604ca0190869d3fee34ac41e3e693c90fb1ecaad72eff"

TOP_LEVEL = {
    "schema_version", "candidate_id", "vehicle_id", "base_commit",
    "parent_candidate_id", "parent_candidate_path", "parent_candidate_sha256",
    "status", "hypothesis", "reference_target", "feedback_receipt", "crank_clock",
    "combustion_and_blowdown", "supercharger_intake", "shift_and_load_transient",
    "operating_level", "afterfire", "loudness", "locked_layers", "provenance",
}
TOP_LEVEL_V2 = {
    "schema_version", "candidate_id", "vehicle_id", "base_commit",
    "parent_candidate_id", "parent_candidate_path", "parent_candidate_sha256",
    "status", "hypothesis", "reference_target", "feedback_receipt",
    "round2_feedback_receipt", "crank_clock", "combustion_and_blowdown",
    "supercharger_intake", "afterfire", "loudness", "locked_layers", "provenance",
}
PARAMETER_SECTIONS = (
    "combustion_and_blowdown", "supercharger_intake", "shift_and_load_transient",
    "operating_level", "afterfire",
)
PARAMETER_KEYS = {
    "combustion_and_blowdown": {
        "cylinder_strength_variation", "bank_amplitude_asymmetry", "blowdown_attack_ms",
        "blowdown_fast_decay_ms", "blowdown_slow_decay_ms", "blowdown_slow_weight",
        "low_frequency_blowdown_gain", "structure_shock_mix",
        "torque_ripple_modulation_depth", "xpipe_cross_coupling", "xpipe_delay_ms",
    },
    "supercharger_intake": {
        "aero_family_order_ratio", "aero_harmonic_mix", "aero_cluster_spread_ratio",
        "gear_family_order_ratio", "gear_to_aero_ratio", "torque_ripple_to_gear_depth",
        "intake_transfer_mix", "casing_transfer_mix", "boost_attack_10_90_s",
        "boost_release_90_10_s", "bypass_release_gain", "bypass_decay_90_10_s",
    },
    "shift_and_load_transient": {
        "shift_interruption_s", "shift_min_exhaust_gain", "shift_min_sc_gain",
        "reengagement_decay_s", "sc_drive_modulation_depth", "tip_in_blowdown_gain",
    },
    "operating_level": {
        "low_load_gain_db", "high_load_gain_db", "blend_load_low", "blend_load_high", "smoothing_s",
    },
    "afterfire": {"gain_scale"},
}
PARAMETER_SECTIONS_V2 = (
    "combustion_and_blowdown", "supercharger_intake", "afterfire",
)
PARAMETER_KEYS_V2 = {
    "combustion_and_blowdown": {
        "acceleration_blowdown_body_gain", "low_frequency_blowdown_gain",
        "structure_shock_mix", "torque_ripple_modulation_depth",
    },
    "supercharger_intake": {
        "combustion_ripple_to_aero_depth", "high_load_whine_knee",
        "high_load_whine_post_knee_slope",
    },
    "afterfire": {
        "minimum_rpm", "residual_energy_gain", "event_energy_threshold",
        "body_mix", "bright_mix", "decay_90_10_s",
    },
}
_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[5]
_L0_RECEIPT_ROOT = _REPO_ROOT / "tasks" / "reports" / "runtime" / "s12-stage-l-hellcat-calibration-v1"
_L0_EVIDENCE_RECEIPT_PATH = _L0_RECEIPT_ROOT / "stage_l_stage_k_evidence_receipt.json"
_L0_FEEDBACK_RECEIPT_PATH = _L0_RECEIPT_ROOT / "stage_l_jovi_feedback_intake.json"
_L0_EVIDENCE_RECEIPT_SHA256 = "963cbb02afe3cc67deb49f31c2bb5fe5b5a9667e9d02916d8690d004f1519cec"
_L0_FEEDBACK_RECEIPT_SHA256 = "0f8e55cd4020d43e23b773d3844057444fda8fab5efa4b0b779e892fc976ca70"
_FEEDBACK_PATH = "tasks/reports/runtime/s12-stage-l-hellcat-calibration-v1/stage_l_jovi_feedback_intake.json"
_ROUND2_FEEDBACK_PATH = "tasks/reports/runtime/s12-stage-l-hellcat-round2/round2_feedback_receipt.json"
_ROUND2_FEEDBACK_RECEIPT_PATH = _REPO_ROOT / _ROUND2_FEEDBACK_PATH
_ROUND2_FEEDBACK_RECEIPT_SHA256 = "ec9a80980715744dd7ca6dff766314e821e6dd375747d002189c5a2c2fe337bc"
_ROUND2_FEEDBACK_KEYS = {
    "path", "sha256", "feedback_scope", "human_pass", "csv_content_read",
}
_EXPECTED_ROUND2_FEEDBACK = {
    "path": _ROUND2_FEEDBACK_PATH,
    "sha256": _ROUND2_FEEDBACK_RECEIPT_SHA256,
    "feedback_scope": "named_round2_engineering_direction",
    "human_pass": False,
    "csv_content_read": False,
}
_FEEDBACK_KEYS = {
    "stage_k_package_sha256", "formal_template_sha256", "formal_template_status",
    "nested_copy_sha256", "nested_copy_status", "named_text_feedback_path",
    "named_text_feedback_sha256", "feedback_scope", "human_pass",
}
_EXPECTED_FEEDBACK = {
    "stage_k_package_sha256": "d81bc9e77276bf6066c73bf3444239800067f1a1545f43460061c37bd88fdeef",
    "formal_template_sha256": "de55eb154e05530f2905aa0cfc5c247ee7d6f81158119cb2a8fe2535e60f374e",
    "formal_template_status": "UNSUBMITTED_TEMPLATE",
    "nested_copy_sha256": "88f9636511233c04014b848bdc4a9c2cb49b188d23f964bbf3c337c1783faf95",
    "nested_copy_status": "INVALID_UNBOUND_DIAGNOSTIC_COPY",
    "named_text_feedback_path": _FEEDBACK_PATH,
    "named_text_feedback_sha256": "0f8e55cd4020d43e23b773d3844057444fda8fab5efa4b0b779e892fc976ca70",
    "feedback_scope": "named_engineering_direction",
    "human_pass": False,
}
_OFFICIAL_FACT_KEYS = {
    "engine_displacement_l", "engine_configuration", "supercharger_type",
    "supercharger_drive_ratio", "published_max_supercharger_rpm",
    "published_max_boost_psi", "provenance_note",
}
_EXPECTED_OFFICIAL_FACTS = {
    "engine_displacement_l": 6.2,
    "engine_configuration": "90-degree V8",
    "supercharger_type": "twin-screw",
    "supercharger_drive_ratio": 2.36,
    "published_max_supercharger_rpm": 14600,
    "published_max_boost_psi": 11.6,
    "provenance_note": "Hardware context only; no rotor pocket count, timing gear tooth count, SPL, or synthetic timbre amplitude is asserted as official.",
}
_OFFICIAL_FACT_KEYS_V2 = _OFFICIAL_FACT_KEYS - {"published_max_boost_psi"}
_EXPECTED_OFFICIAL_FACTS_V2 = {
    "engine_displacement_l": 6.2,
    "engine_configuration": "HEMI V8",
    "supercharger_type": "twin-screw",
    "supercharger_drive_ratio": 2.36,
    "published_max_supercharger_rpm": 14600,
    "provenance_note": "Hardware context only; no rotor geometry, OEM SPL, or factory afterfire calibration is asserted.",
}


@dataclass(frozen=True)
class StageLCandidateProfile:
    payload: Mapping[str, Any]
    path: Path | None = None

    @property
    def vehicle_id(self) -> str:
        return str(self.payload["vehicle_id"])

    @property
    def candidate_id(self) -> str:
        return str(self.payload["candidate_id"])

    @property
    def status(self) -> str:
        return str(self.payload["status"])

    def parameter(self, section: str, name: str, default: float = 0.0) -> float:
        section_payload = self.payload.get(section, {})
        record = section_payload.get(name) if isinstance(section_payload, Mapping) else None
        if record is None:
            return float(default)
        return float(record["value"])

    def requested_parameters(self) -> tuple[str, ...]:
        sections, _ = _parameter_contract(self.payload)
        return tuple(
            f"{section}.{name}"
            for section in sections
            for name in sorted(self.payload[section])
        )

    def with_parameter(self, section: str, name: str, value: float) -> "StageLCandidateProfile":
        _, parameter_keys = _parameter_contract(self.payload)
        if section not in parameter_keys or name not in self.payload.get(section, {}):
            raise ValueError(f"unknown Stage-L parameter: {section}.{name}")
        payload = deepcopy(self.payload)
        payload[section][name]["value"] = float(value)
        _validate_payload(payload)
        return StageLCandidateProfile(payload, self.path)


def load_stage_l_candidate(path: str | Path) -> StageLCandidateProfile:
    candidate_path = Path(path).resolve()
    try:
        payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read Stage-L candidate: {candidate_path}") from exc
    _validate_payload(payload)
    parent = _package_file(payload["parent_candidate_path"])
    reference = _package_file(payload["reference_target"]["path"])
    expected_parent_sha = (
        V2_PARENT_CANDIDATE_SHA256
        if payload["schema_version"] == SCHEMA_VERSION_V2
        else PARENT_CANDIDATE_SHA256
    )
    if _sha256(parent) != expected_parent_sha:
        raise ValueError("parent candidate SHA-256 does not match Stage-L lineage")
    if _sha256(reference) != REFERENCE_TARGET_SHA256:
        raise ValueError("reference target SHA-256 does not match Stage-L candidate")
    l0_feedback = _load_l0_feedback_bindings()
    if dict(payload["feedback_receipt"]) != l0_feedback:
        raise ValueError("candidate feedback_receipt does not match validated repository L0 receipts")
    if _sha256(_L0_FEEDBACK_RECEIPT_PATH) != l0_feedback["named_text_feedback_sha256"]:
        raise ValueError("named text feedback SHA-256 does not match Stage-L receipt")
    if payload["schema_version"] == SCHEMA_VERSION_V2:
        _validate_round2_feedback_binding(payload["round2_feedback_receipt"])
    return StageLCandidateProfile(payload, candidate_path)


def _validate_payload(payload: Any) -> None:
    if not isinstance(payload, Mapping):
        raise ValueError("Stage-L candidate must be an object")
    schema_version = payload.get("schema_version")
    if schema_version == SCHEMA_VERSION:
        top_level = TOP_LEVEL
    elif schema_version == SCHEMA_VERSION_V2:
        top_level = TOP_LEVEL_V2
    else:
        raise ValueError("unsupported Stage-L schema_version")
    if set(payload) != top_level:
        raise ValueError("Stage-L candidate top-level keys mismatch")
    if payload.get("vehicle_id") != "hellcat":
        raise ValueError("Stage-L vehicle_id must be hellcat")
    if payload.get("base_commit") != BASE_COMMIT:
        raise ValueError("candidate base_commit does not match Stage-L baseline")
    if payload.get("status") != "Candidate":
        raise ValueError("Stage-L status must be Candidate")
    expected_parent = (
        (V2_PARENT_CANDIDATE_ID, V2_PARENT_CANDIDATE_PATH, V2_PARENT_CANDIDATE_SHA256)
        if schema_version == SCHEMA_VERSION_V2
        else (PARENT_CANDIDATE_ID, PARENT_CANDIDATE_PATH, PARENT_CANDIDATE_SHA256)
    )
    if payload.get("parent_candidate_id") != expected_parent[0] or payload.get("parent_candidate_path") != expected_parent[1]:
        raise ValueError("parent candidate mapping does not match Stage-L Hellcat lineage")
    if str(payload.get("parent_candidate_sha256", "")).lower() != expected_parent[2]:
        raise ValueError("parent candidate SHA-256 does not match Stage-L lineage")
    for key in ("candidate_id", "hypothesis"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ValueError(f"{key} must be a non-empty string")
    if schema_version == SCHEMA_VERSION_V2 and payload["candidate_id"] != "hellcat_stage_l_v9":
        raise ValueError("schema v2 candidate_id must be hellcat_stage_l_v9")
    reference = payload.get("reference_target")
    if not isinstance(reference, Mapping) or set(reference) != {"path", "sha256", "eligible_states"}:
        raise ValueError("reference_target contract is incomplete")
    if reference["path"] != REFERENCE_TARGET_PATH or str(reference["sha256"]).lower() != REFERENCE_TARGET_SHA256:
        raise ValueError("reference target is not the frozen Hellcat target")
    if reference["eligible_states"] != ["idle", "acceleration", "afterfire"]:
        raise ValueError("reference eligible_states are frozen")
    feedback = payload.get("feedback_receipt")
    if not isinstance(feedback, Mapping) or set(feedback) != _FEEDBACK_KEYS:
        raise ValueError("feedback_receipt contract is incomplete")
    for key, expected in _EXPECTED_FEEDBACK.items():
        actual = feedback.get(key)
        if isinstance(expected, str) and key.endswith("sha256"):
            actual = str(actual).lower()
        if actual != expected:
            raise ValueError(f"feedback_receipt {key} does not match frozen input")
    if schema_version == SCHEMA_VERSION_V2:
        round2_feedback = payload.get("round2_feedback_receipt")
        if not isinstance(round2_feedback, Mapping) or set(round2_feedback) != _ROUND2_FEEDBACK_KEYS:
            raise ValueError("round2_feedback_receipt contract is incomplete")
        for key, expected in _EXPECTED_ROUND2_FEEDBACK.items():
            actual = round2_feedback.get(key)
            if key == "sha256":
                actual = str(actual).lower()
            if actual != expected:
                raise ValueError(f"round2_feedback_receipt {key} does not match frozen input")
    _validate_crank_clock(payload.get("crank_clock"))
    sections, parameter_keys = _parameter_contract(payload)
    for section in sections:
        value = payload.get(section)
        if not isinstance(value, Mapping) or set(value) != parameter_keys[section]:
            raise ValueError(f"{section} public parameter keys mismatch")
        for name, record in value.items():
            _validate_parameter(f"{section}.{name}", record)
    _validate_loudness(payload.get("loudness"))
    _validate_locked_layers(payload.get("locked_layers"))
    _validate_provenance(payload.get("provenance"), schema_version)


def _parameter_contract(
    payload: Mapping[str, Any],
) -> tuple[tuple[str, ...], Mapping[str, set[str]]]:
    if payload.get("schema_version") == SCHEMA_VERSION:
        return PARAMETER_SECTIONS, PARAMETER_KEYS
    if payload.get("schema_version") == SCHEMA_VERSION_V2:
        return PARAMETER_SECTIONS_V2, PARAMETER_KEYS_V2
    raise ValueError("unsupported Stage-L schema_version")


def _validate_round2_feedback_binding(value: Mapping[str, Any]) -> None:
    if _sha256(_ROUND2_FEEDBACK_RECEIPT_PATH) != value["sha256"]:
        raise ValueError("Round-2 feedback receipt SHA-256 mismatch")
    receipt = _load_l0_receipt(
        _ROUND2_FEEDBACK_RECEIPT_PATH,
        _ROUND2_FEEDBACK_RECEIPT_SHA256,
        "Round-2 text feedback",
    )
    expected_windows = {
        "v8_byte_freeze": [0.0, 8.0],
        "third_shift_whine_balance": [24.0, 26.0],
        "sustained_high_load": [26.0, 36.0],
        "afterfire": [36.0, 46.0],
    }
    claims = receipt.get("claims")
    if (
        receipt.get("schema_version") != "s12-stage-l-hellcat-round2-feedback-receipt-1"
        or receipt.get("receipt_status") != "TEXT_ONLY_ENGINEERING_DIRECTION"
        or receipt.get("feedback_scope") != "named_round2_engineering_direction"
        or receipt.get("windows_s") != expected_windows
        or not isinstance(claims, list)
        or len(claims) != 3
        or not all(isinstance(claim, str) and claim for claim in claims)
        or receipt.get("human_pass") is not False
        or receipt.get("csv_content_read") is not False
        or receipt.get("qualification_status") != "PARTIAL / AUTOMATED_GATE_FAIL / UNQUALIFIED_DIAGNOSTIC_ONLY"
    ):
        raise ValueError("Round-2 feedback receipt contract mismatch")


def _validate_crank_clock(value: Any) -> None:
    keys = {"firing_order", "bank_pattern", "events_per_revolution", "cycle_revolutions", "scope"}
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError("crank_clock contract is incomplete")
    if value["firing_order"] != [1, 8, 4, 3, 6, 5, 7, 2] or value["bank_pattern"] != ["left", "right", "left", "right", "right", "left", "right", "left"]:
        raise ValueError("crank_clock firing order or bank pattern is not frozen")
    if value["events_per_revolution"] != 4.0 or value["cycle_revolutions"] != 2.0 or value["scope"] != "architecture_contract":
        raise ValueError("crank_clock architecture contract is invalid")


def _validate_parameter(name: str, value: Any) -> None:
    required = {"value", "unit", "range", "source_level", "source", "source_scope", "verification_state"}
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError(f"{name} provenance record is incomplete")
    finite_number = lambda item: isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(float(item))
    bounds = value["range"]
    if not finite_number(value["value"]) or not isinstance(bounds, list) or len(bounds) != 2 or not all(finite_number(item) for item in bounds) or not bounds[0] < bounds[1] or not bounds[0] <= value["value"] <= bounds[1]:
        raise ValueError(f"{name} value/range is invalid")
    if value["source_level"] != "C" or value["source"] != "synthetic" or value["verification_state"] != "candidate_assumption":
        raise ValueError(f"{name} provenance must remain C/synthetic/candidate_assumption")
    if not isinstance(value["unit"], str) or not isinstance(value["source_scope"], str) or not value["source_scope"]:
        raise ValueError(f"{name} unit/source_scope is invalid")


def _validate_loudness(value: Any) -> None:
    expected = {"target_lufs": -16.0, "peak_limit_dbfs": -1.5, "whole_cycle_gain_only": True}
    if value != expected:
        raise ValueError("formal loudness policy is frozen")


def _validate_locked_layers(value: Any) -> None:
    names = {"low_frequency_body", "rumble", "pre_ptr_eq", "frozen_ptr", "formal_loudness_manager", "reference_target"}
    if not isinstance(value, Mapping) or set(value) != names:
        raise ValueError("locked Stage-L layers are incomplete")
    for name, record in value.items():
        if not isinstance(record, Mapping) or set(record) != {"unchanged", "fingerprint"} or record["unchanged"] is not True or not isinstance(record["fingerprint"], str) or not record["fingerprint"]:
            raise ValueError(f"locked layer {name} must remain unchanged")


def _validate_provenance(value: Any, schema_version: str = SCHEMA_VERSION) -> None:
    keys = {"source_level", "source", "calibration", "claim", "parent_status", "official_facts"}
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError("candidate provenance is incomplete")
    parent_status = "STAGE_L_V8_BASELINE" if schema_version == SCHEMA_VERSION_V2 else "STAGE_K_CANDIDATE_PARENT"
    if value["source_level"] != "C" or value["source"] != "synthetic" or value["calibration"] != "uncalibrated" or value["claim"] != "Hellcat-inspired; not OEM reproduction" or value["parent_status"] != parent_status:
        raise ValueError("candidate provenance must remain C/synthetic/uncalibrated/not OEM")
    facts = value["official_facts"]
    fact_keys = _OFFICIAL_FACT_KEYS_V2 if schema_version == SCHEMA_VERSION_V2 else _OFFICIAL_FACT_KEYS
    expected_facts = _EXPECTED_OFFICIAL_FACTS_V2 if schema_version == SCHEMA_VERSION_V2 else _EXPECTED_OFFICIAL_FACTS
    if not isinstance(facts, Mapping) or set(facts) != fact_keys:
        raise ValueError("provenance official_facts keys mismatch")
    if dict(facts) != expected_facts:
        raise ValueError("provenance official_facts values mismatch")


def _load_l0_feedback_bindings() -> dict[str, object]:
    """Validate frozen repository L0 receipts and return the candidate binding."""
    evidence = _load_l0_receipt(
        _L0_EVIDENCE_RECEIPT_PATH, _L0_EVIDENCE_RECEIPT_SHA256, "Stage-K evidence",
    )
    feedback = _load_l0_receipt(
        _L0_FEEDBACK_RECEIPT_PATH, _L0_FEEDBACK_RECEIPT_SHA256, "named feedback",
    )
    if evidence.get("schema_version") != "s12-stage-l-stage-k-evidence-receipt-1" or evidence.get("receipt_status") != "FROZEN":
        raise ValueError("L0 Stage-K evidence receipt status/schema mismatch")
    bootstrap = evidence.get("stage_l_bootstrap")
    package = evidence.get("stage_k_package")
    if not isinstance(bootstrap, Mapping) or bootstrap.get("stage_k_pre_bootstrap_head") != BASE_COMMIT:
        raise ValueError("L0 Stage-K evidence baseline mismatch")
    expected_package = {
        "package_id": "S12_Stage_K_Named_Review_v1",
        "package_root": r"E:\Tesla_speed\review_packages\s12-stage-k-four-vehicle-perceptual-repair-v1",
        "automatic_gate_status": "PARTIAL / AUTOMATED_GATE_FAIL",
        "named_review_status": "WAITING_FOR_JOVI_STAGE_K_NAMED_REVIEW",
        "sealed_key_read": False,
        "provenance": "synthetic; uncalibrated; Hellcat-inspired; not OEM reproduction",
    }
    if package != expected_package:
        raise ValueError("L0 Stage-K package receipt values mismatch")
    artifacts = evidence.get("frozen_artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("L0 Stage-K frozen artifacts are missing")
    by_name = {item.get("name"): item for item in artifacts if isinstance(item, Mapping)}
    candidate_artifact = by_name.get("hellcat_candidate_v7.json")
    package_artifact = by_name.get("S12_Stage_K_Named_Review.zip")
    if not isinstance(candidate_artifact, Mapping) or (
        str(candidate_artifact.get("sha256", "")).lower() != PARENT_CANDIDATE_SHA256
        or str(candidate_artifact.get("expected_sha256", "")).lower() != PARENT_CANDIDATE_SHA256
        or candidate_artifact.get("sha256_match") is not True
    ):
        raise ValueError("L0 Stage-K candidate artifact binding mismatch")
    package_sha = str(_EXPECTED_FEEDBACK["stage_k_package_sha256"])
    if not isinstance(package_artifact, Mapping) or (
        str(package_artifact.get("sha256", "")).lower() != package_sha
        or str(package_artifact.get("expected_sha256", "")).lower() != package_sha
        or package_artifact.get("sha256_match") is not True
        or package_artifact.get("sha256sums_binding") != "NOT_LISTED"
    ):
        raise ValueError("L0 Stage-K package archive binding mismatch")
    if feedback.get("schema_version") != "s12-stage-l-jovi-feedback-intake-1":
        raise ValueError("L0 named feedback receipt schema mismatch")
    if feedback.get("feedback_scope") != "named_engineering_direction" or feedback.get("human_pass") is not False or feedback.get("human_result_status") != "NOT_A_FORMAL_HUMAN_SCORE":
        raise ValueError("L0 named feedback status mismatch")
    bindings = feedback.get("stage_k_bindings")
    if not isinstance(bindings, Mapping) or (
        bindings.get("package_id") != "S12_Stage_K_Named_Review_v1"
        or str(bindings.get("package_zip_sha256", "")).lower() != package_sha
        or str(bindings.get("hellcat_candidate_sha256", "")).lower() != PARENT_CANDIDATE_SHA256
    ):
        raise ValueError("L0 named feedback Stage-K binding mismatch")
    csv_inputs = feedback.get("csv_inputs")
    if not isinstance(csv_inputs, Mapping):
        raise ValueError("L0 named feedback CSV inputs are missing")
    formal = csv_inputs.get("formal_stage_k_csv")
    nested = csv_inputs.get("nested_same_name_csv")
    if not isinstance(formal, Mapping) or (
        str(formal.get("sha256", "")).lower() != _EXPECTED_FEEDBACK["formal_template_sha256"]
        or formal.get("sha256sums_binding") != "BOUND"
        or formal.get("row_count") != 24
        or formal.get("filled_score_row_count") != 0
        or formal.get("out_of_range_score_count") != 0
        or formal.get("legal_conclusion") != "UNSUBMITTED_TEMPLATE"
        or formal.get("eligible_as_formal_human_feedback") is not False
        or feedback.get("formal_stage_k_csv_status") != "UNSUBMITTED_TEMPLATE"
    ):
        raise ValueError("L0 formal feedback component values mismatch")
    if not isinstance(nested, Mapping) or (
        str(nested.get("sha256", "")).lower() != _EXPECTED_FEEDBACK["nested_copy_sha256"]
        or nested.get("sha256sums_binding") != "NOT_BOUND"
        or nested.get("row_count") != 24
        or nested.get("filled_score_row_count") != 24
        or nested.get("literal_zero_score_count") != 6
        or nested.get("legal_conclusion") != "INVALID_UNBOUND_DIAGNOSTIC_COPY"
        or nested.get("eligible_as_formal_human_feedback") is not False
        or feedback.get("nested_csv_status") != "INVALID_UNBOUND_DIAGNOSTIC_COPY"
    ):
        raise ValueError("L0 nested feedback component values mismatch")
    return dict(_EXPECTED_FEEDBACK)


def _load_l0_receipt(path: Path, expected_sha256: str, label: str) -> Mapping[str, Any]:
    if _sha256(path) != expected_sha256:
        raise ValueError(f"L0 {label} receipt SHA-256 mismatch")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read L0 {label} receipt") from exc
    if not isinstance(value, Mapping):
        raise ValueError(f"L0 {label} receipt must be an object")
    return value


def _package_file(relative_path: str) -> Path:
    path = (_PACKAGE_ROOT / relative_path).resolve()
    try:
        path.relative_to(_PACKAGE_ROOT)
    except ValueError as exc:
        raise ValueError("candidate path escapes acoustic_identity_v015 package") from exc
    if not path.is_file():
        raise ValueError(f"candidate-bound file is missing: {path}")
    return path


def _sha256(path: str | Path) -> str:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError(f"cannot hash candidate-bound file: {path}") from exc


__all__ = (
    "BASE_COMMIT", "PARAMETER_KEYS", "PARAMETER_KEYS_V2", "PARAMETER_SECTIONS",
    "PARAMETER_SECTIONS_V2", "PARENT_CANDIDATE_ID", "PARENT_CANDIDATE_PATH",
    "PARENT_CANDIDATE_SHA256", "SCHEMA_VERSION", "SCHEMA_VERSION_V2", "TOP_LEVEL",
    "TOP_LEVEL_V2",
    "StageLCandidateProfile", "load_stage_l_candidate",
)
