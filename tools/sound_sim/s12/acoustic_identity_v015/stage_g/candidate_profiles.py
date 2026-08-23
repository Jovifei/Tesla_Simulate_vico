"""Strict Stage-G candidate contract for the three anchor vehicles."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

BASE_COMMIT = "e38fe62f423b1fb220e9daedf5f4ef291bcc5849"
SCHEMA_VERSION = "s12-stage-g-candidate-profile-1"
ANCHOR_IDS = ("ferrari_458", "hellcat", "rx7_fd")
TOP_LEVEL = {
    "schema_version", "candidate_id", "vehicle_id", "base_commit", "parent_candidate_id", "status",
    "hypothesis", "reference_target", "canonical_trace_version", "source", "idle", "afterfire",
    "shift", "loudness", "locked_layers", "provenance",
}
COMMON_KEYS = {
    "idle": {"variation", "jitter_ms", "mechanical_texture"},
    "afterfire": {"gain_scale"},
    "shift": {"impact_scale", "recovery_scale"},
}
SOURCE_KEYS = {
    "ferrari_458": {"pulse_width_scale", "bank_phase_offset_deg", "metallic_decay_scale", "high_rpm_growth_scale", "metallic_gain_scale", "mid_carrier_gain_scale", "metallic_texture_mix"},
    "hellcat": {"blower_gain_scale", "blower_boost_mix", "boost_attack_s", "boost_release_s", "blower_intake_balance", "intake_gain_scale", "pressure_attack_gain_scale"},
    # ``rotary_pulse_width_scale`` is retained only so historical Stage-G v4
    # receipts can be reopened.  New Stage-U grids must use the semantic
    # ``rotary_amplitude_scale`` and one or more housing controls instead.
    "rx7_fd": {"rotary_phase_offset_deg", "rotary_pulse_width_scale", "rotary_amplitude_scale", "housing_gain_scale", "housing_decay_scale", "housing_order_weight_scale", "turbo_gain_scale", "turbine_gain_scale", "primary_spool_tau_s", "secondary_spool_tau_s", "boost_attack_s", "boost_release_s", "blow_off_gain_scale", "blow_off_release_s"},
}
ELIGIBLE_STATES = ("idle", "acceleration", "afterfire")


@dataclass(frozen=True)
class StageGCandidateProfile:
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

    def parameter(self, section: str, name: str, default: float = 0.0) -> float:
        section_payload: Mapping[str, Any] = self.payload.get(section, {})
        if section == "loudness":
            section_payload = section_payload.get("transient_peak_shaper", {})
        value = section_payload.get(name)
        if value is None:
            return float(default)
        return float(value["value"] if isinstance(value, Mapping) and "value" in value else value)

    def section_values(self, section: str) -> dict[str, float]:
        return {name: self.parameter(section, name) for name in self.payload.get(section, {})}

    def requested_parameters(self) -> tuple[str, ...]:
        names: list[str] = []
        for section in ("source", "idle", "afterfire", "shift"):
            names.extend(f"{section}.{name}" for name in self.payload.get(section, {}))
        shaper = self.payload["loudness"]["transient_peak_shaper"]
        if shaper.get("enabled", False):
            names.extend(f"loudness.transient_peak_shaper.{name}" for name in ("attack_ms", "release_ms", "max_reduction_db"))
        return tuple(names)

    def with_parameter(self, section: str, name: str, value: float) -> "StageGCandidateProfile":
        payload = deepcopy(self.payload)
        target: Any = payload.get(section, {})
        if section == "loudness":
            target = payload["loudness"]["transient_peak_shaper"]
        entry = target.get(name)
        if not isinstance(entry, Mapping) or "value" not in entry:
            raise ValueError(f"unknown Stage-G parameter: {section}.{name}")
        entry["value"] = float(value)
        _validate_payload(payload)
        return StageGCandidateProfile(payload, self.path)


def load_stage_g_candidate(path: str | Path) -> StageGCandidateProfile:
    candidate_path = Path(path).resolve()
    payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    _validate_payload(payload)
    reference_path = candidate_path.parents[2] / str(payload["reference_target"]["path"])
    if not reference_path.is_file():
        raise ValueError(f"reference target SHA-256 cannot be checked; file is missing: {reference_path}")
    actual = reference_sha256(reference_path)
    if actual != payload["reference_target"]["sha256"]:
        raise ValueError("reference target SHA-256 does not match candidate contract")
    return StageGCandidateProfile(payload, candidate_path)


def _validate_payload(payload: Any) -> None:
    if not isinstance(payload, Mapping) or set(payload) != TOP_LEVEL:
        raise ValueError("Stage-G candidate top-level keys mismatch")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported Stage-G schema_version")
    vehicle_id = payload.get("vehicle_id")
    if vehicle_id not in ANCHOR_IDS:
        raise ValueError("unsupported Stage-G vehicle_id")
    if payload.get("base_commit") != BASE_COMMIT:
        raise ValueError("candidate base_commit does not match Stage-G baseline")
    if payload.get("status") != "Candidate":
        raise ValueError("Stage-G status must be Candidate")
    for key in ("candidate_id", "parent_candidate_id", "hypothesis", "canonical_trace_version"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ValueError(f"{key} must be a non-empty string")
    reference = payload.get("reference_target")
    if not isinstance(reference, Mapping) or set(reference) != {"path", "sha256", "eligible_states"}:
        raise ValueError("reference_target contract is incomplete")
    if not isinstance(reference["path"], str) or not reference["path"]:
        raise ValueError("reference target path must be non-empty")
    if not isinstance(reference["sha256"], str) or len(reference["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in reference["sha256"].lower()):
        raise ValueError("reference target sha256 must be hexadecimal")
    if reference["eligible_states"] != list(ELIGIBLE_STATES):
        raise ValueError("reference eligible_states must be idle/acceleration/afterfire")
    for section in ("source", "idle", "afterfire", "shift"):
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
    locked = payload.get("locked_layers")
    if not isinstance(locked, Mapping) or any(locked.get(key, {}).get("unchanged") is not True for key in ("low_frequency_body", "rumble", "pre_ptr_eq", "frozen_ptr")):
        raise ValueError("locked Stage-C layers must remain unchanged")
    provenance = payload.get("provenance")
    if not isinstance(provenance, Mapping) or provenance.get("source_level") != "C" or provenance.get("source") != "synthetic" or provenance.get("calibration") != "uncalibrated" or provenance.get("claim") != "not OEM reproduction":
        raise ValueError("candidate provenance must remain C/synthetic/uncalibrated/not OEM")


def _validate_loudness(loudness: Any) -> None:
    required = {"target_lufs", "peak_limit_dbfs", "whole_cycle_gain_only", "transient_peak_shaper"}
    if not isinstance(loudness, Mapping) or set(loudness) != required:
        raise ValueError("formal loudness policy is incomplete")
    if loudness["target_lufs"] != -16.0 or loudness["peak_limit_dbfs"] != -1.5 or loudness["whole_cycle_gain_only"] is not True:
        raise ValueError("formal loudness policy is frozen")
    shaper = loudness["transient_peak_shaper"]
    if not isinstance(shaper, Mapping) or set(shaper) != {"enabled", "attack_ms", "release_ms", "max_reduction_db"} or not isinstance(shaper["enabled"], bool):
        raise ValueError("transient shaper contract is incomplete")
    for name in ("attack_ms", "release_ms", "max_reduction_db"):
        _validate_parameter(f"loudness.transient_peak_shaper.{name}", shaper[name])


def _validate_parameter(name: str, parameter: Any) -> None:
    required = {"value", "unit", "range", "source_level", "source", "source_scope", "verification_state"}
    if not isinstance(parameter, Mapping) or set(parameter) != required:
        raise ValueError(f"{name} provenance record is incomplete")
    value = parameter["value"]
    bounds = parameter["range"]
    valid_number = lambda item: isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(float(item))
    if not valid_number(value) or not isinstance(bounds, list) or len(bounds) != 2 or not all(valid_number(item) for item in bounds) or not bounds[0] < bounds[1] or not bounds[0] <= value <= bounds[1]:
        raise ValueError(f"{name} value/range is invalid")
    if parameter["source_level"] != "C" or parameter["source"] != "synthetic" or parameter["verification_state"] != "candidate_assumption" or not all(isinstance(parameter[key], str) and parameter[key] for key in ("unit", "source_scope")):
        raise ValueError(f"{name} provenance is invalid")


def reference_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


__all__ = ("ANCHOR_IDS", "BASE_COMMIT", "ELIGIBLE_STATES", "SCHEMA_VERSION", "StageGCandidateProfile", "load_stage_g_candidate", "reference_sha256")
