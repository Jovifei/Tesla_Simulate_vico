"""Strict, vehicle-specific Stage-F candidate profile contract."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

BASE_COMMIT = "3c2c891b469adc7a507870c71ee94319e7125226"
SCHEMA_VERSION = "s12-stage-f-candidate-profile-1"
ANCHOR_IDS = ("ferrari_458", "hellcat", "rx7_fd")
TOP_LEVEL = {"schema_version", "candidate_id", "vehicle_id", "base_commit", "parent_candidate_id", "status", "hypothesis", "reference_target", "canonical_trace_version", "source", "idle", "afterfire", "shift", "loudness", "locked_layers", "provenance"}
COMMON = {"afterfire": {"gain_scale"}, "shift": {"impact_scale", "recovery_scale"}, "idle": {"variation", "jitter_ms", "mechanical_texture"}}
SOURCE = {
    "ferrari_458": {"pulse_width_scale", "bank_phase_offset_deg", "metallic_decay_scale", "high_rpm_growth_scale"},
    "hellcat": {"blower_gain_scale", "blower_boost_mix", "boost_attack_s", "boost_release_s"},
    "rx7_fd": {"rotary_phase_offset_deg", "rotary_pulse_width_scale", "primary_spool_tau_s", "secondary_spool_tau_s", "boost_attack_s", "boost_release_s", "blow_off_gain_scale", "blow_off_release_s"},
}


@dataclass(frozen=True)
class StageFCandidateProfile:
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
    def base_commit(self) -> str:
        return str(self.payload["base_commit"])

    def parameter(self, section: str, name: str, default: float) -> float:
        section_payload = self.payload.get(section, {})
        if section == "loudness":
            section_payload = section_payload.get("transient_peak_shaper", {})
        entry = section_payload.get(name)
        if entry is None:
            return float(default)
        if isinstance(entry, Mapping) and "value" in entry:
            return float(entry["value"])
        return float(entry)

    def section_values(self, section: str) -> dict[str, float]:
        return {name: self.parameter(section, name, 0.0) for name in self.payload.get(section, {})}

    def with_parameter(self, section: str, name: str, value: float) -> "StageFCandidateProfile":
        payload = deepcopy(self.payload)
        if section == "loudness":
            entry = payload["loudness"]["transient_peak_shaper"].get(name)
        else:
            entry = payload.get(section, {}).get(name)
        if not isinstance(entry, Mapping) or "value" not in entry:
            raise ValueError(f"unknown Stage-F parameter: {section}.{name}")
        entry["value"] = float(value)
        _validate_payload(payload)
        return StageFCandidateProfile(payload, self.path)

    def requested_parameters(self) -> tuple[str, ...]:
        names = []
        for section in ("source", "idle", "afterfire", "shift"):
            names.extend(f"{section}.{name}" for name in self.payload.get(section, {}))
        shaper = self.payload["loudness"]["transient_peak_shaper"]
        if shaper.get("enabled", False):
            names.extend(f"loudness.transient_peak_shaper.{name}" for name in ("attack_ms", "release_ms", "max_reduction_db"))
        return tuple(names)


def load_stage_f_candidate(path: str | Path) -> StageFCandidateProfile:
    candidate_path = Path(path)
    payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    _validate_payload(payload)
    reference = candidate_path.parents[2] / str(payload["reference_target"]["path"])
    if reference.is_file() and reference_sha256(reference) != payload["reference_target"]["sha256"]:
        raise ValueError("reference target sha256 does not match candidate contract")
    return StageFCandidateProfile(payload, candidate_path)


def _validate_payload(payload: Any) -> None:
    if not isinstance(payload, Mapping) or set(payload) != TOP_LEVEL:
        raise ValueError("Stage-F candidate top-level keys mismatch")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported Stage-F schema_version")
    vehicle_id = payload.get("vehicle_id")
    if vehicle_id not in ANCHOR_IDS:
        raise ValueError("unsupported Stage-F vehicle_id")
    if payload.get("base_commit") != BASE_COMMIT:
        raise ValueError("candidate base_commit does not match Stage-F baseline")
    if payload.get("status") != "Candidate":
        raise ValueError("Stage-F status must be Candidate")
    if not isinstance(payload.get("candidate_id"), str) or not payload["candidate_id"]:
        raise ValueError("candidate_id must be non-empty")
    if not isinstance(payload.get("parent_candidate_id"), str) or not payload["parent_candidate_id"]:
        raise ValueError("parent_candidate_id must be non-empty")
    reference = payload.get("reference_target")
    if not isinstance(reference, Mapping) or set(reference) != {"path", "sha256", "eligible_states"}:
        raise ValueError("reference_target contract is incomplete")
    if not isinstance(reference["eligible_states"], list) or not reference["eligible_states"]:
        raise ValueError("reference eligible_states must be non-empty")
    if not isinstance(reference["sha256"], str) or len(reference["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in reference["sha256"].lower()):
        raise ValueError("reference target sha256 must be hexadecimal")
    allowed_source = SOURCE[vehicle_id]
    for section in ("source", "idle", "afterfire", "shift"):
        value = payload.get(section)
        if not isinstance(value, Mapping):
            raise ValueError(f"{section} must be an object")
        allowed = allowed_source if section == "source" else COMMON[section]
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown {section} override: {sorted(unknown)}")
        for name, parameter in value.items():
            _validate_parameter(f"{section}.{name}", parameter)
    _validate_loudness(payload["loudness"])
    locked = payload["locked_layers"]
    if not isinstance(locked, Mapping) or any(locked.get(k, {}).get("unchanged") is not True for k in ("low_frequency_body", "rumble", "pre_ptr_eq", "frozen_ptr")):
        raise ValueError("locked Stage-C layers must remain unchanged")
    provenance = payload["provenance"]
    if not isinstance(provenance, Mapping) or provenance.get("source_level") != "C" or provenance.get("source") != "synthetic" or provenance.get("calibration") != "uncalibrated" or provenance.get("claim") != "not OEM reproduction":
        raise ValueError("candidate provenance must remain C/synthetic/uncalibrated/not OEM")


def _validate_loudness(loudness: Any) -> None:
    required = {"target_lufs", "peak_limit_dbfs", "whole_cycle_gain_only", "transient_peak_shaper"}
    if not isinstance(loudness, Mapping) or set(loudness) != required:
        raise ValueError("formal loudness policy is incomplete")
    if loudness["target_lufs"] != -16.0 or loudness["peak_limit_dbfs"] != -1.5 or loudness["whole_cycle_gain_only"] is not True:
        raise ValueError("formal loudness policy is frozen")
    shaper = loudness["transient_peak_shaper"]
    if not isinstance(shaper, Mapping) or set(shaper) != {"enabled", "attack_ms", "release_ms", "max_reduction_db"}:
        raise ValueError("transient peak shaper contract is incomplete")
    if not isinstance(shaper["enabled"], bool):
        raise ValueError("transient shaper enabled must be boolean")
    for name in ("attack_ms", "release_ms", "max_reduction_db"):
        _validate_parameter(f"loudness.transient_peak_shaper.{name}", shaper[name])


def _validate_parameter(name: str, parameter: Any) -> None:
    required = {"value", "unit", "range", "source_level", "source", "source_scope", "verification_state"}
    if not isinstance(parameter, Mapping) or set(parameter) != required:
        raise ValueError(f"{name} provenance record is incomplete")
    value, bounds = parameter["value"], parameter["range"]
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)) or not isinstance(bounds, list) or len(bounds) != 2 or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x)) for x in bounds) or not bounds[0] < bounds[1] or not bounds[0] <= value <= bounds[1]:
        raise ValueError(f"{name} value/range is invalid")
    if parameter["source_level"] != "C" or parameter["source"] != "synthetic" or not all(isinstance(parameter[k], str) and parameter[k] for k in ("unit", "source_scope", "verification_state")):
        raise ValueError(f"{name} provenance is invalid")


def reference_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
