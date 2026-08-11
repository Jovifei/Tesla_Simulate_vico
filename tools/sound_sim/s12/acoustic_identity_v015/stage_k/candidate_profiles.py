"""Fail-closed Stage-K candidate lineage and parameter contract.

Stage K is a Track-S repair layer.  It deliberately has its own schema and
baseline binding so a candidate cannot silently become a Stage-J or Stage-I
profile by changing a filename.  All numeric records remain synthetic
assumptions; no field in this module is an OEM calibration claim.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping


BASE_COMMIT = "b78b6c3031269eae1a0b917ce7bbaaed2af81c76"
SCHEMA_VERSION = "s12-stage-k-candidate-profile-1"
SCHEMA_VERSION_ALIASES = {
    SCHEMA_VERSION,
    "s12-stage-k-hellcat-candidate-profile-1",
    "s12-stage-k-c63_w204-candidate-profile-1",
    "s12-stage-k-gtr_r35-candidate-profile-1",
    "s12-stage-k-lfa-candidate-profile-1",
}
STAGE_K_VEHICLES = ("hellcat", "c63_w204", "gtr_r35", "lfa")
ELIGIBLE_STATES = ("idle", "acceleration", "afterfire")

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]

TOP_LEVEL = {
    "schema_version",
    "candidate_id",
    "vehicle_id",
    "base_commit",
    "parent_candidate_id",
    "parent_candidate_path",
    "parent_candidate_sha256",
    "status",
    "hypothesis",
    "reference_target",
    "canonical_trace_version",
    "source",
    "operating_level",
    "idle",
    "afterfire",
    "shift_or_transient",
    "loudness",
    "locked_layers",
    "provenance",
}

PARENT_MAPPING = {
    "hellcat": {
        "path": "targets/stage_i_candidates/Hellcat_candidate_v6_C_SofterMechanical.json",
        "candidate_id": "hellcat_stage_i_v6_c_softer_mechanical",
        "status": "UNQUALIFIED_DIAGNOSTIC_PARENT",
    },
    "c63_w204": {
        "path": "targets/stage_j_candidates/c63_w204_candidate_v1.json",
        "candidate_id": "c63_w204_stage_j_v1",
        "status": "STAGE_J_CANDIDATE_PARENT",
    },
    "gtr_r35": {
        "path": "targets/stage_j_candidates/gtr_r35_candidate_v1.json",
        "candidate_id": "gtr_r35_stage_j_v1",
        "status": "STAGE_J_CANDIDATE_PARENT",
    },
    "lfa": {
        "path": "targets/stage_j_candidates/lfa_candidate_v1.json",
        "candidate_id": "lfa_stage_j_v1",
        "status": "STAGE_J_CANDIDATE_PARENT",
    },
}

REFERENCE_MAPPING = {
    "hellcat": "reference_database/hellcat_reference_targets.json",
    "c63_w204": "reference_database/c63_w204_reference_targets.json",
    "gtr_r35": "reference_database/gtr_r35_reference_targets.json",
    "lfa": "reference_database/lfa_reference_targets.json",
}

# These are the public Stage-K keys.  In particular, C63's old
# ``bark_resonance_scale`` and Hellcat's implicit ``sideband_depth`` are not
# accepted: their meanings were ambiguous and their use produced invalid
# tuning knobs in prior stages.
SOURCE_KEYS = {
    "hellcat": {
        "blower_gain_scale",
        "blower_boost_mix",
        "upper_family_tilt_db",
        "cluster_spread_ratio",
        "sideband_main_ratio",
        "intake_voicing_mix",
        "boost_attack_10_90_s",
        "boost_release_90_10_s",
        "bypass_release_gain",
        "bypass_decay_90_10_s",
    },
    "c63_w204": {
        "bank_phase_offset_deg",
        "pulse_width_scale",
        "bark_primary_order",
        "bark_upper_partial_mix",
        "bark_decay_ms",
        "mechanical_upper_tilt_db",
        "high_rpm_compression",
        "mechanical_texture_scale",
        "high_rpm_growth_scale",
    },
    "gtr_r35": {
        "bank_phase_offset_deg",
        "pulse_width_scale",
        "primary_spool_tau_s",
        "secondary_spool_tau_s",
        "boost_attack_s",
        "boost_release_s",
        "turbo_whistle_mix",
        "turbo_a_inertia_s",
        "turbo_b_inertia_s",
        "shaft_detune_ratio",
        "shaft_bpf_order",
        "intake_duct_mix",
        "bov_release_gain",
        "bov_release_s",
        "wastegate_gain_scale",
    },
    "lfa": {
        "pulse_width_scale",
        "phase_offset_deg",
        "order_family_mix",
        "intake_resonance_scale",
        "metallic_texture_scale",
        "high_rpm_growth_scale",
    },
}

COMMON_KEYS = {
    "operating_level": {
        "low_load_gain_db",
        "high_load_gain_db",
        "blend_load_low",
        "blend_load_high",
        "smoothing_s",
    },
    "idle": {"variation", "jitter_ms", "mechanical_texture"},
    "afterfire": {"gain_scale"},
    "shift_or_transient": {
        "impact_scale",
        "recovery_scale",
        "shift_interruption_s",
        "shift_min_gain",
        "reengagement_decay_s",
        "intake_reopen_gain",
        "lift_high_order_decay_s",
        "overrun_gain",
    },
}

_LOCKED_LAYER_KEYS = ("low_frequency_body", "rumble", "pre_ptr_eq", "frozen_ptr")
_OPTIONAL_LOCKED_LAYER_KEYS = ("formal_loudness_manager",)


@dataclass(frozen=True)
class StageKCandidateProfile:
    """Immutable, validated Stage-K candidate payload."""

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

    @property
    def reference_target(self) -> Mapping[str, Any]:
        return self.payload["reference_target"]

    @property
    def parent_status(self) -> str:
        return str(self.payload.get("provenance", {}).get("parent_status", ""))

    def parameter(self, section: str, name: str, default: float = 0.0) -> float:
        section_payload = self.payload.get(section, {})
        value = section_payload.get(name) if isinstance(section_payload, Mapping) else None
        if value is None:
            return float(default)
        return float(value["value"] if isinstance(value, Mapping) and "value" in value else value)

    def section_values(self, section: str) -> dict[str, float]:
        value = self.payload.get(section, {})
        if not isinstance(value, Mapping):
            return {}
        return {name: self.parameter(section, name) for name in value}

    def requested_parameters(self) -> tuple[str, ...]:
        names: list[str] = []
        for section in ("source", "operating_level", "idle", "afterfire", "shift_or_transient"):
            names.extend(f"{section}.{name}" for name in self.payload.get(section, {}))
        return tuple(names)

    def with_parameter(self, section: str, name: str, value: float) -> "StageKCandidateProfile":
        payload = deepcopy(self.payload)
        target = payload.get(section)
        if not isinstance(target, Mapping) or name not in target:
            raise ValueError(f"unknown Stage-K parameter: {section}.{name}")
        entry = target[name]
        if not isinstance(entry, Mapping) or "value" not in entry:
            raise ValueError(f"unknown Stage-K parameter: {section}.{name}")
        entry["value"] = float(value)
        _validate_payload(payload)
        return StageKCandidateProfile(payload, self.path)


def load_stage_k_candidate(path: str | Path) -> StageKCandidateProfile:
    """Load and bind one candidate to this checkout's parent/reference files."""

    candidate_path = Path(path).resolve()
    try:
        payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read Stage-K candidate: {candidate_path}") from exc
    _validate_payload(payload)
    vehicle_id = payload["vehicle_id"]
    reference_path = _package_file(payload["reference_target"]["path"])
    parent_path = _package_file(payload["parent_candidate_path"])
    if not reference_path.is_file():
        raise ValueError(f"reference target is missing: {reference_path}")
    if not parent_path.is_file():
        raise ValueError(f"parent candidate is missing: {parent_path}")
    expected_reference = reference_sha256(reference_path)
    if expected_reference.lower() != payload["reference_target"]["sha256"].lower():
        raise ValueError("reference target SHA-256 does not match Stage-K candidate")
    expected_parent = reference_sha256(parent_path)
    if expected_parent.lower() != payload["parent_candidate_sha256"].lower():
        raise ValueError("parent candidate SHA-256 does not match Stage-K candidate")
    parent_payload = _read_json(parent_path)
    expected_parent_id = PARENT_MAPPING[vehicle_id]["candidate_id"]
    if _lineage_token(parent_payload.get("candidate_id", "")) != _lineage_token(expected_parent_id):
        raise ValueError("parent candidate identity does not match Stage-K vehicle mapping")
    return StageKCandidateProfile(payload, candidate_path)


def _validate_payload(payload: Any) -> None:
    if not isinstance(payload, Mapping) or set(payload) != TOP_LEVEL:
        raise ValueError("Stage-K candidate top-level keys mismatch")
    if payload.get("schema_version") not in SCHEMA_VERSION_ALIASES:
        raise ValueError("unsupported Stage-K schema_version")
    vehicle_id = payload.get("vehicle_id")
    if vehicle_id not in STAGE_K_VEHICLES:
        raise ValueError("unsupported Stage-K vehicle_id")
    if payload.get("base_commit") != BASE_COMMIT:
        raise ValueError("candidate base_commit does not match Stage-K baseline")
    if payload.get("status") != "Candidate":
        raise ValueError("Stage-K status must be Candidate")
    for key in ("candidate_id", "parent_candidate_id", "parent_candidate_path", "hypothesis", "canonical_trace_version"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ValueError(f"{key} must be a non-empty string")
    parent = PARENT_MAPPING[vehicle_id]
    if _lineage_token(payload["parent_candidate_id"]) != _lineage_token(parent["candidate_id"]) or payload["parent_candidate_path"] != parent["path"]:
        raise ValueError("parent candidate mapping does not match Stage-K vehicle")
    _validate_sha("parent_candidate_sha256", payload.get("parent_candidate_sha256"))

    reference = payload.get("reference_target")
    if not isinstance(reference, Mapping) or set(reference) != {"path", "sha256", "eligible_states"}:
        raise ValueError("reference_target contract is incomplete")
    if reference["path"] != REFERENCE_MAPPING[vehicle_id]:
        raise ValueError("reference target path does not match Stage-K vehicle")
    _validate_sha("reference target sha256", reference.get("sha256"))
    if reference["eligible_states"] != list(ELIGIBLE_STATES):
        raise ValueError("reference eligible_states must be idle/acceleration/afterfire")

    for section in ("source", "operating_level", "idle", "afterfire", "shift_or_transient"):
        value = payload.get(section)
        if not isinstance(value, Mapping):
            raise ValueError(f"{section} must be an object")
        allowed = SOURCE_KEYS[vehicle_id] if section == "source" else COMMON_KEYS[section]
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown {section} override: {sorted(unknown)}")
        for name, parameter in value.items():
            _validate_parameter(f"{section}.{name}", parameter)
    _validate_loudness(payload.get("loudness"))
    _validate_locked_layers(payload.get("locked_layers"))
    provenance = payload.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError("candidate provenance is incomplete")
    required_provenance = {"source_level", "source", "calibration", "claim"}
    if not required_provenance.issubset(provenance):
        raise ValueError("candidate provenance is incomplete")
    claim = provenance.get("claim")
    if provenance.get("source_level") != "C" or provenance.get("source") != "synthetic" or provenance.get("calibration") != "uncalibrated" or not isinstance(claim, str) or not claim.endswith("not OEM reproduction"):
        raise ValueError("candidate provenance must remain C/synthetic/uncalibrated/not OEM")
    if provenance.get("parent_status") != parent["status"]:
        raise ValueError("candidate provenance parent_status does not match Stage-K parent mapping")


def _validate_loudness(value: Any) -> None:
    required = {"target_lufs", "peak_limit_dbfs", "whole_cycle_gain_only"}
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError("formal loudness policy is incomplete")
    if value["target_lufs"] != -16.0 or value["peak_limit_dbfs"] != -1.5 or value["whole_cycle_gain_only"] is not True:
        raise ValueError("formal loudness policy is frozen")


def _validate_locked_layers(value: Any) -> None:
    allowed = set(_LOCKED_LAYER_KEYS) | set(_OPTIONAL_LOCKED_LAYER_KEYS)
    if not isinstance(value, Mapping) or not set(_LOCKED_LAYER_KEYS).issubset(value) or set(value) - allowed:
        raise ValueError("locked Stage-C layers are incomplete")
    for name in tuple(_LOCKED_LAYER_KEYS) + tuple(_OPTIONAL_LOCKED_LAYER_KEYS):
        if name not in value:
            continue
        entry = value[name]
        if not isinstance(entry, Mapping) or set(entry) != {"unchanged", "fingerprint"} or entry["unchanged"] is not True or not isinstance(entry["fingerprint"], str) or not entry["fingerprint"]:
            raise ValueError(f"locked layer {name} must remain unchanged")


def _validate_parameter(name: str, value: Any) -> None:
    required = {"value", "unit", "range", "source_level", "source", "source_scope", "verification_state"}
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError(f"{name} provenance record is incomplete")
    number = lambda item: isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(float(item))
    bounds = value["range"]
    if not number(value["value"]) or not isinstance(bounds, list) or len(bounds) != 2 or not all(number(item) for item in bounds) or not bounds[0] < bounds[1] or not bounds[0] <= value["value"] <= bounds[1]:
        raise ValueError(f"{name} value/range is invalid")
    if value["source_level"] != "C" or value["source"] != "synthetic" or value["verification_state"] != "candidate_assumption" or not all(isinstance(value[key], str) and value[key] for key in ("unit", "source_scope")):
        raise ValueError(f"{name} provenance is invalid")


def _validate_sha(label: str, value: Any) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value.lower()):
        raise ValueError(f"{label} must be a hexadecimal SHA-256")


def _lineage_token(value: Any) -> str:
    """Compare historical candidate IDs without cosmetic case/separator drift."""

    return "".join(char for char in str(value).casefold() if char.isalnum())


def _package_file(relative_path: str) -> Path:
    candidate = (_PACKAGE_ROOT / relative_path).resolve()
    try:
        candidate.relative_to(_PACKAGE_ROOT)
    except ValueError as exc:
        raise ValueError("candidate path escapes acoustic_identity_v015 package") from exc
    return candidate


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read parent candidate: {path}") from exc
    if not isinstance(value, Mapping):
        raise ValueError(f"parent candidate is not a JSON object: {path}")
    return value


def reference_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


__all__ = (
    "BASE_COMMIT",
    "COMMON_KEYS",
    "ELIGIBLE_STATES",
    "PARENT_MAPPING",
    "REFERENCE_MAPPING",
    "SCHEMA_VERSION",
    "SOURCE_KEYS",
    "STAGE_K_VEHICLES",
    "StageKCandidateProfile",
    "load_stage_k_candidate",
    "reference_sha256",
)
