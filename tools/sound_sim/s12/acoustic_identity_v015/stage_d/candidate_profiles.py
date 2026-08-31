"""Strict, synthetic Stage-D candidate profile contract."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

BASE_COMMIT = "a5d048145c29b20d687376c0b73226bc4a2435c7"
SCHEMA_VERSION = "s12-stage-d-candidate-profile-1"
ANCHOR_IDS = ("ferrari_458", "hellcat", "rx7_fd")
_TOP_LEVEL = {
    "schema_version", "candidate_id", "vehicle_id", "base_commit", "parent_candidate_id", "status",
    "hypothesis", "reference_target", "canonical_trace_version", "source", "idle", "afterfire",
    "shift", "loudness", "locked_layers", "provenance",
}
_SECTION_KEYS = {
    "source": {
        "pulse_width_scale", "bank_phase_offset_deg", "metallic_mid_gain_scale", "metallic_upper_gain_scale",
        "metallic_decay_scale", "high_rpm_growth_scale", "blower_gain_scale", "blower_boost_mix",
        "boost_attack_s", "boost_release_s", "bypass_release_s", "rotary_phase_offset_deg",
        "rotary_pulse_width_scale", "primary_spool_tau_s", "secondary_spool_tau_s", "blow_off_gain_scale",
        "blow_off_release_s", "turbo_gain_scale",
    },
    "idle": {"variation", "jitter_ms", "combustion_gain_scale", "mechanical_texture", "mechanical_texture_scale"},
    "afterfire": {"gain_scale", "min_rpm", "cluster_stride", "low_hz", "high_hz", "stereo"},
    "shift": {"impact_scale", "recovery_scale", "jerk_s", "recovery_hz"},
}
_REQUIRED_PROVENANCE = {"source_level", "source", "calibration", "claim"}


@dataclass(frozen=True)
class StageDCandidateProfile:
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
        if entry is None:
            return float(default)
        if not isinstance(entry, Mapping) or "value" not in entry:
            raise ValueError(f"{section}.{name} must be a parameter record")
        return float(entry["value"])

    def scalar(self, section: str, name: str, default: float) -> float:
        entry = self.payload.get(section, {}).get(name, default)
        return float(entry)


def load_stage_d_candidate(path: str | Path) -> StageDCandidateProfile:
    candidate_path = Path(path)
    with candidate_path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    _validate_payload(payload)
    return StageDCandidateProfile(payload=payload, path=candidate_path)


def _validate_payload(payload: Any) -> None:
    if not isinstance(payload, Mapping):
        raise ValueError("candidate profile must be an object")
    unknown = set(payload) - _TOP_LEVEL
    missing = _TOP_LEVEL - set(payload)
    if unknown:
        raise ValueError(f"unknown candidate profile fields: {sorted(unknown)}")
    if missing:
        raise ValueError(f"missing candidate profile fields: {sorted(missing)}")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported Stage-D candidate schema_version")
    if payload["vehicle_id"] not in ANCHOR_IDS:
        raise ValueError(f"unsupported Stage-D vehicle_id: {payload['vehicle_id']!r}")
    if payload["base_commit"] != BASE_COMMIT:
        raise ValueError("candidate base_commit does not match Stage-C baseline")
    if payload["status"] != "Candidate":
        raise ValueError("Stage-D profile status must be Candidate")
    if not isinstance(payload["candidate_id"], str) or not payload["candidate_id"]:
        raise ValueError("candidate_id must be non-empty")
    if payload["parent_candidate_id"] is not None and not isinstance(payload["parent_candidate_id"], str):
        raise ValueError("parent_candidate_id must be null or a string")
    reference = payload["reference_target"]
    if not isinstance(reference, Mapping) or set(reference) != {"path", "sha256", "eligible_states"}:
        raise ValueError("reference_target must contain path, sha256, eligible_states")
    if not isinstance(reference["path"], str) or len(reference["sha256"]) != 64:
        raise ValueError("reference_target path and sha256 are required")
    if any(character not in "0123456789abcdef" for character in reference["sha256"].lower()):
        raise ValueError("reference_target sha256 must be hexadecimal")
    if not isinstance(reference["eligible_states"], list) or not reference["eligible_states"]:
        raise ValueError("reference_target eligible_states must be non-empty")
    for section, allowed in _SECTION_KEYS.items():
        value = payload[section]
        if not isinstance(value, Mapping):
            raise ValueError(f"{section} must be an object")
        unknown_section = set(value) - allowed
        if unknown_section:
            raise ValueError(f"unknown {section} fields: {sorted(unknown_section)}")
        for name, parameter in value.items():
            _validate_parameter(section, name, parameter)
    loudness = payload["loudness"]
    if not isinstance(loudness, Mapping) or set(loudness) != {"target_lufs", "peak_limit_dbfs", "whole_cycle_gain_only", "transient_peak_shaper"}:
        raise ValueError("loudness must contain the fixed manager contract and transient_peak_shaper")
    if loudness["target_lufs"] != -16.0 or loudness["peak_limit_dbfs"] != -1.5 or loudness["whole_cycle_gain_only"] is not True:
        raise ValueError("Stage-D loudness manager policy is frozen at -16 LUFS / -1.5 dBFS / one gain")
    shaper = loudness["transient_peak_shaper"]
    if not isinstance(shaper, Mapping) or set(shaper) != {"enabled", "attack_ms", "release_ms", "max_reduction_db"}:
        raise ValueError("transient_peak_shaper contract is incomplete")
    for key in ("attack_ms", "release_ms", "max_reduction_db"):
        if not isinstance(shaper[key], (int, float)) or not 0.0 <= float(shaper[key]) <= 100.0:
            raise ValueError(f"invalid transient_peak_shaper.{key}")
    if not isinstance(shaper["enabled"], bool):
        raise ValueError("transient_peak_shaper.enabled must be boolean")
    if not isinstance(payload["locked_layers"], Mapping):
        raise ValueError("locked_layers must be an object")
    for layer in ("low_frequency_body", "rumble", "pre_ptr_eq", "frozen_ptr"):
        value = payload["locked_layers"].get(layer)
        if not isinstance(value, Mapping) or value.get("unchanged") is not True:
            raise ValueError(f"locked layer {layer} must be marked unchanged")
    provenance = payload["provenance"]
    if not isinstance(provenance, Mapping) or set(provenance) != _REQUIRED_PROVENANCE:
        raise ValueError("provenance contract is incomplete")
    if provenance["source_level"] != "C" or provenance["source"] != "synthetic" or provenance["calibration"] != "uncalibrated":
        raise ValueError("candidate provenance must remain C/synthetic/uncalibrated")
    if provenance["claim"] != "not OEM reproduction":
        raise ValueError("candidate claim must remain not OEM reproduction")


def _validate_parameter(section: str, name: str, parameter: Any) -> None:
    if not isinstance(parameter, Mapping):
        raise ValueError(f"{section}.{name} must be a parameter record")
    expected = {"value", "unit", "range", "source_level", "source", "source_scope", "verification_state"}
    if set(parameter) != expected:
        raise ValueError(f"{section}.{name} provenance record is incomplete")
    value = parameter["value"]
    bounds = parameter["range"]
    if not isinstance(value, (int, float)) or not isinstance(bounds, list) or len(bounds) != 2:
        raise ValueError(f"{section}.{name} value/range is invalid")
    if not all(isinstance(item, (int, float)) for item in bounds) or not bounds[0] < bounds[1] or not bounds[0] <= value <= bounds[1]:
        raise ValueError(f"{section}.{name} value is outside range")
    if not all(isinstance(parameter[key], str) and parameter[key] for key in ("unit", "source_scope", "verification_state")):
        raise ValueError(f"{section}.{name} unit/source_scope/verification_state is invalid")
    if parameter["source_level"] != "C" or parameter["source"] != "synthetic":
        raise ValueError(f"{section}.{name} must be C/synthetic")
