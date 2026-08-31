"""Fail-closed Stage-E candidate profile contract."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

BASE_COMMIT = "4e363c66b92e51848a35700650ee1464925c479a"
STAGE_C_BASE_COMMIT = "a5d048145c29b20d687376c0b73226bc4a2435c7"
SCHEMA_VERSION = "s12-stage-e-candidate-profile-1"
ANCHOR_IDS = ("ferrari_458", "hellcat", "rx7_fd")
TOP_LEVEL = {"schema_version", "candidate_id", "vehicle_id", "base_commit", "parent_candidate_id", "status", "hypothesis", "reference_target", "canonical_trace_version", "source", "idle", "afterfire", "shift", "loudness", "locked_layers", "provenance"}
SECTION_KEYS = {
    "source": {"pulse_width_scale", "bank_phase_offset_deg", "metallic_decay_scale", "high_rpm_growth_scale", "blower_gain_scale", "blower_boost_mix", "boost_attack_s", "boost_release_s", "rotary_phase_offset_deg", "rotary_pulse_width_scale", "primary_spool_tau_s", "secondary_spool_tau_s", "blow_off_gain_scale", "blow_off_release_s", "turbo_gain_scale"},
    "idle": {"variation", "jitter_ms", "mechanical_texture"},
    "afterfire": {"gain_scale"},
    "shift": {"impact_scale", "recovery_scale"},
}


@dataclass(frozen=True)
class StageECandidateProfile:
    payload: Mapping[str, Any]
    path: Path | None = None

    @property
    def vehicle_id(self) -> str:
        return str(self.payload["vehicle_id"])

    @property
    def candidate_id(self) -> str:
        return str(self.payload["candidate_id"])

    def parameter(self, section: str, name: str, default: float) -> float:
        entry = self.payload.get(section, {}).get(name)
        return float(default if entry is None else entry["value"])

    def section_values(self, section: str) -> dict[str, float]:
        return {name: self.parameter(section, name, 0.0) for name in self.payload.get(section, {})}

    def with_parameter(self, section: str, name: str, value: float) -> "StageECandidateProfile":
        payload = deepcopy(self.payload)
        if section not in SECTION_KEYS or name not in SECTION_KEYS[section]:
            raise ValueError(f"unknown Stage-E parameter: {section}.{name}")
        payload[section][name]["value"] = float(value)
        _validate_payload(payload)
        return StageECandidateProfile(payload, self.path)


def load_stage_e_candidate(path: str | Path) -> StageECandidateProfile:
    candidate_path = Path(path)
    payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    _validate_payload(payload)
    package_root = candidate_path.parents[2] if len(candidate_path.parents) > 2 else None
    if package_root is not None:
        reference_path = package_root / str(payload["reference_target"]["path"])
        if reference_path.is_file() and reference_sha256(reference_path) != payload["reference_target"]["sha256"]:
            raise ValueError("reference target sha256 does not match candidate contract")
    return StageECandidateProfile(payload, candidate_path)


def _validate_payload(payload: Any) -> None:
    if not isinstance(payload, Mapping):
        raise ValueError("candidate profile must be an object")
    if set(payload) != TOP_LEVEL:
        raise ValueError(f"candidate profile keys mismatch: unknown={sorted(set(payload) - TOP_LEVEL)} missing={sorted(TOP_LEVEL - set(payload))}")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported Stage-E schema_version")
    if payload["vehicle_id"] not in ANCHOR_IDS:
        raise ValueError("unsupported Stage-E vehicle_id")
    if payload["base_commit"] != BASE_COMMIT:
        raise ValueError("candidate base_commit does not match Stage-E baseline")
    if payload["status"] != "Candidate":
        raise ValueError("Stage-E status must be Candidate")
    if not isinstance(payload["candidate_id"], str) or not payload["candidate_id"]:
        raise ValueError("candidate_id must be non-empty")
    if payload["parent_candidate_id"] is None or not isinstance(payload["parent_candidate_id"], str):
        raise ValueError("Stage-E candidates must name a parent candidate")
    reference = payload["reference_target"]
    if not isinstance(reference, Mapping) or set(reference) != {"path", "sha256", "eligible_states"}:
        raise ValueError("reference_target contract is incomplete")
    if not isinstance(reference["sha256"], str) or len(reference["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in reference["sha256"].lower()):
        raise ValueError("reference_target sha256 must be hexadecimal")
    for section, allowed in SECTION_KEYS.items():
        value = payload[section]
        if not isinstance(value, Mapping) or set(value) - allowed:
            raise ValueError(f"unknown {section} override")
        for name, parameter in value.items():
            _validate_parameter(section, name, parameter)
    loudness = payload["loudness"]
    if loudness != {"target_lufs": -16.0, "peak_limit_dbfs": -1.5, "whole_cycle_gain_only": True, "transient_peak_shaper": loudness.get("transient_peak_shaper") if isinstance(loudness, Mapping) else None}:
        if not isinstance(loudness, Mapping) or loudness.get("target_lufs") != -16.0 or loudness.get("peak_limit_dbfs") != -1.5 or loudness.get("whole_cycle_gain_only") is not True:
            raise ValueError("formal loudness policy is frozen")
    if not isinstance(payload["locked_layers"], Mapping) or any(payload["locked_layers"].get(k, {}).get("unchanged") is not True for k in ("low_frequency_body", "rumble", "pre_ptr_eq", "frozen_ptr")):
        raise ValueError("locked Stage-C layers must remain unchanged")
    provenance = payload["provenance"]
    if not isinstance(provenance, Mapping) or provenance.get("source_level") != "C" or provenance.get("source") != "synthetic" or provenance.get("calibration") != "uncalibrated" or provenance.get("claim") != "not OEM reproduction":
        raise ValueError("candidate provenance must remain C/synthetic/uncalibrated/not OEM")


def _validate_parameter(section: str, name: str, parameter: Any) -> None:
    required = {"value", "unit", "range", "source_level", "source", "source_scope", "verification_state"}
    if not isinstance(parameter, Mapping) or set(parameter) != required:
        raise ValueError(f"{section}.{name} provenance record is incomplete")
    value, bounds = parameter["value"], parameter["range"]
    if not isinstance(value, (int, float)) or not isinstance(bounds, list) or len(bounds) != 2 or not all(isinstance(x, (int, float)) for x in bounds) or not bounds[0] < bounds[1] or not bounds[0] <= value <= bounds[1]:
        raise ValueError(f"{section}.{name} value/range is invalid")
    if parameter["source_level"] != "C" or parameter["source"] != "synthetic" or not all(isinstance(parameter[k], str) and parameter[k] for k in ("unit", "source_scope", "verification_state")):
        raise ValueError(f"{section}.{name} provenance is invalid")


def reference_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
