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
PARENT_CANDIDATE_ID = "hellcat_stage_k_v7"
PARENT_CANDIDATE_PATH = "targets/stage_k_candidates/hellcat_candidate_v7.json"
PARENT_CANDIDATE_SHA256 = "b730090daa6274c9e6501e9cdf6894ea00f8ccfff535af3f887ec00721d6d358"
REFERENCE_TARGET_PATH = "reference_database/hellcat_reference_targets.json"
REFERENCE_TARGET_SHA256 = "84030e8204fe228fddb604ca0190869d3fee34ac41e3e693c90fb1ecaad72eff"

TOP_LEVEL = {
    "schema_version", "candidate_id", "vehicle_id", "base_commit",
    "parent_candidate_id", "parent_candidate_path", "parent_candidate_sha256",
    "status", "hypothesis", "reference_target", "feedback_receipt", "crank_clock",
    "combustion_and_blowdown", "supercharger_intake", "shift_and_load_transient",
    "operating_level", "afterfire", "loudness", "locked_layers", "provenance",
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
_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[5]
_FEEDBACK_PATH = "tasks/reports/runtime/s12-stage-l-hellcat-calibration-v1/stage_l_jovi_feedback_intake.json"
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
        return tuple(
            f"{section}.{name}"
            for section in PARAMETER_SECTIONS
            for name in sorted(self.payload[section])
        )

    def with_parameter(self, section: str, name: str, value: float) -> "StageLCandidateProfile":
        if section not in PARAMETER_KEYS or name not in self.payload.get(section, {}):
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
    if _sha256(parent) != PARENT_CANDIDATE_SHA256:
        raise ValueError("parent candidate SHA-256 does not match Stage-L lineage")
    if _sha256(reference) != REFERENCE_TARGET_SHA256:
        raise ValueError("reference target SHA-256 does not match Stage-L candidate")
    feedback_path = (_REPO_ROOT / payload["feedback_receipt"]["named_text_feedback_path"]).resolve()
    try:
        feedback_path.relative_to(_REPO_ROOT)
    except ValueError as exc:
        raise ValueError("named text feedback path escapes repository") from exc
    if _sha256(feedback_path) != _EXPECTED_FEEDBACK["named_text_feedback_sha256"]:
        raise ValueError("named text feedback SHA-256 does not match Stage-L receipt")
    return StageLCandidateProfile(payload, candidate_path)


def _validate_payload(payload: Any) -> None:
    if not isinstance(payload, Mapping) or set(payload) != TOP_LEVEL:
        raise ValueError("Stage-L candidate top-level keys mismatch")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported Stage-L schema_version")
    if payload.get("vehicle_id") != "hellcat":
        raise ValueError("Stage-L vehicle_id must be hellcat")
    if payload.get("base_commit") != BASE_COMMIT:
        raise ValueError("candidate base_commit does not match Stage-L baseline")
    if payload.get("status") != "Candidate":
        raise ValueError("Stage-L status must be Candidate")
    if payload.get("parent_candidate_id") != PARENT_CANDIDATE_ID or payload.get("parent_candidate_path") != PARENT_CANDIDATE_PATH:
        raise ValueError("parent candidate mapping does not match Stage-L Hellcat lineage")
    if str(payload.get("parent_candidate_sha256", "")).lower() != PARENT_CANDIDATE_SHA256:
        raise ValueError("parent candidate SHA-256 does not match Stage-L lineage")
    for key in ("candidate_id", "hypothesis"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ValueError(f"{key} must be a non-empty string")
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
    _validate_crank_clock(payload.get("crank_clock"))
    for section in PARAMETER_SECTIONS:
        value = payload.get(section)
        if not isinstance(value, Mapping) or set(value) != PARAMETER_KEYS[section]:
            raise ValueError(f"{section} public parameter keys mismatch")
        for name, record in value.items():
            _validate_parameter(f"{section}.{name}", record)
    _validate_loudness(payload.get("loudness"))
    _validate_locked_layers(payload.get("locked_layers"))
    _validate_provenance(payload.get("provenance"))


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


def _validate_provenance(value: Any) -> None:
    keys = {"source_level", "source", "calibration", "claim", "parent_status", "official_facts"}
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError("candidate provenance is incomplete")
    if value["source_level"] != "C" or value["source"] != "synthetic" or value["calibration"] != "uncalibrated" or value["claim"] != "Hellcat-inspired; not OEM reproduction" or value["parent_status"] != "STAGE_K_CANDIDATE_PARENT":
        raise ValueError("candidate provenance must remain C/synthetic/uncalibrated/not OEM")
    facts = value["official_facts"]
    if not isinstance(facts, Mapping) or set(facts) != _OFFICIAL_FACT_KEYS:
        raise ValueError("provenance official_facts keys mismatch")
    if facts["supercharger_drive_ratio"] != 2.36 or facts["published_max_supercharger_rpm"] != 14600 or facts["engine_configuration"] != "90-degree V8":
        raise ValueError("provenance official_facts values mismatch")


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
    "BASE_COMMIT", "PARAMETER_KEYS", "PARAMETER_SECTIONS", "PARENT_CANDIDATE_ID",
    "PARENT_CANDIDATE_PATH", "PARENT_CANDIDATE_SHA256", "SCHEMA_VERSION", "TOP_LEVEL",
    "StageLCandidateProfile", "load_stage_l_candidate",
)
