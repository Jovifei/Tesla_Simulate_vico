"""Strict Stage-I Hellcat whine-voicing candidate contract."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping


BASE_COMMIT = "6ee4b1a4a7e3925dd4ca2baf206c98ea76e697d2"
SCHEMA_VERSION = "s12-stage-i-hellcat-candidate-profile-1"
ANCHOR_IDS = ("ferrari_458", "hellcat", "rx7_fd")
TOP_LEVEL = {
    "schema_version",
    "candidate_id",
    "vehicle_id",
    "base_commit",
    "parent_candidate_id",
    "status",
    "hypothesis",
    "reference_target",
    "canonical_trace_version",
    "source",
    "idle",
    "afterfire",
    "shift",
    "loudness",
    "locked_layers",
    "provenance",
}
SOURCE_KEYS = {
    "blower_gain_scale",
    "blower_boost_mix",
    "lobe_family_mix",
    "upper_family_tilt_db",
    "sideband_depth",
    "phase_ripple_depth",
    "order_cluster_spread_ratio",
    "intake_voicing_mix",
    "boost_attack_s",
    "boost_release_s",
    "bypass_release_gain",
    "bypass_pitch_fall_ratio",
    "bypass_decay_s",
}
COMMON_KEYS = {
    "idle": set(),
    "afterfire": {"gain_scale"},
    "shift": {"impact_scale", "recovery_scale"},
}
REQUIRED_STATES = ["idle", "acceleration", "afterfire"]


@dataclass(frozen=True)
class StageICandidateProfile:
    payload: Mapping[str, Any]
    path: Path | None = None

    @property
    def vehicle_id(self) -> str:
        return str(self.payload["vehicle_id"])

    @property
    def candidate_id(self) -> str:
        return str(self.payload["candidate_id"])

    @property
    def parent_candidate_id(self) -> str:
        return str(self.payload["parent_candidate_id"])

    @property
    def base_commit(self) -> str:
        return str(self.payload["base_commit"])

    @property
    def status(self) -> str:
        return str(self.payload["status"])

    def parameter(self, section: str, name: str, default: float = 0.0) -> float:
        target: Mapping[str, Any] = self.payload.get(section, {})
        if section == "loudness":
            target = target.get("transient_peak_shaper", {})
        entry = target.get(name)
        if entry is None:
            return float(default)
        return float(entry["value"] if isinstance(entry, Mapping) else entry)

    def section_values(self, section: str) -> dict[str, float]:
        return {
            name: self.parameter(section, name)
            for name in self.payload.get(section, {})
        }

    def requested_parameters(self) -> tuple[str, ...]:
        names: list[str] = []
        for section in ("source", "idle", "afterfire", "shift"):
            names.extend(
                f"{section}.{name}" for name in self.payload.get(section, {})
            )
        shaper = self.payload["loudness"]["transient_peak_shaper"]
        if shaper["enabled"]:
            names.extend(
                f"loudness.transient_peak_shaper.{name}"
                for name in ("attack_ms", "release_ms", "max_reduction_db")
            )
        return tuple(names)

    def with_parameter(
        self, section: str, name: str, value: float
    ) -> "StageICandidateProfile":
        payload = deepcopy(self.payload)
        target: Any = payload.get(section, {})
        if section == "loudness":
            target = payload["loudness"]["transient_peak_shaper"]
        entry = target.get(name)
        if not isinstance(entry, Mapping) or "value" not in entry:
            raise ValueError(f"unknown Stage-I parameter: {section}.{name}")
        entry["value"] = float(value)
        _validate_payload(payload)
        return StageICandidateProfile(payload, self.path)


def load_stage_i_candidate(path: str | Path) -> StageICandidateProfile:
    candidate_path = Path(path).resolve()
    payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    _validate_payload(payload)
    reference_path = candidate_path.parents[2] / str(payload["reference_target"]["path"])
    if not reference_path.is_file():
        raise ValueError(f"reference target is missing: {reference_path}")
    if reference_sha256(reference_path) != payload["reference_target"]["sha256"]:
        raise ValueError("reference target SHA-256 does not match Stage-I contract")
    return StageICandidateProfile(payload, candidate_path)


def _validate_payload(payload: Any) -> None:
    if not isinstance(payload, Mapping) or set(payload) != TOP_LEVEL:
        raise ValueError("Stage-I candidate top-level keys mismatch")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported Stage-I schema_version")
    if payload["vehicle_id"] != "hellcat":
        raise ValueError("Stage-I candidate only supports hellcat")
    if payload["base_commit"] != BASE_COMMIT:
        raise ValueError("candidate base_commit does not match Stage-I baseline")
    if payload["status"] != "Candidate":
        raise ValueError("Stage-I status must be Candidate")
    for name in (
        "candidate_id",
        "parent_candidate_id",
        "hypothesis",
        "canonical_trace_version",
    ):
        if not isinstance(payload.get(name), str) or not payload[name]:
            raise ValueError(f"{name} must be non-empty")
    reference = payload["reference_target"]
    if not isinstance(reference, Mapping) or set(reference) != {
        "path",
        "sha256",
        "eligible_states",
    }:
        raise ValueError("reference target contract is incomplete")
    if reference["eligible_states"] != REQUIRED_STATES:
        raise ValueError("reference eligible_states must be idle/acceleration/afterfire")
    sha = reference["sha256"]
    if (
        not isinstance(reference["path"], str)
        or not reference["path"]
        or not isinstance(sha, str)
        or len(sha) != 64
        or any(char not in "0123456789abcdef" for char in sha.lower())
    ):
        raise ValueError("reference target path/SHA-256 is invalid")
    for section in ("source", "idle", "afterfire", "shift"):
        values = payload[section]
        if not isinstance(values, Mapping):
            raise ValueError(f"{section} must be an object")
        allowed = SOURCE_KEYS if section == "source" else COMMON_KEYS[section]
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"unknown Stage-I {section} override: {sorted(unknown)}")
        if section == "source" and set(values) != SOURCE_KEYS:
            raise ValueError("Stage-I source exact-key contract mismatch")
        for name, entry in values.items():
            _validate_parameter(f"{section}.{name}", entry)
    _validate_loudness(payload["loudness"])
    locked = payload["locked_layers"]
    if not isinstance(locked, Mapping) or any(
        locked.get(name, {}).get("unchanged") is not True
        for name in ("low_frequency_body", "rumble", "pre_ptr_eq", "frozen_ptr")
    ):
        raise ValueError("Stage-C shared layers must remain locked")
    provenance = payload["provenance"]
    if (
        not isinstance(provenance, Mapping)
        or provenance.get("source_level") != "C"
        or provenance.get("source") != "synthetic"
        or provenance.get("calibration") != "uncalibrated"
        or provenance.get("claim") != "not OEM reproduction"
    ):
        raise ValueError("Stage-I provenance must remain C/synthetic/uncalibrated/not OEM")


def _validate_loudness(loudness: Any) -> None:
    required = {
        "target_lufs",
        "peak_limit_dbfs",
        "whole_cycle_gain_only",
        "transient_peak_shaper",
    }
    if not isinstance(loudness, Mapping) or set(loudness) != required:
        raise ValueError("Stage-I loudness policy is incomplete")
    if (
        loudness["target_lufs"] != -16.0
        or loudness["peak_limit_dbfs"] != -1.5
        or loudness["whole_cycle_gain_only"] is not True
    ):
        raise ValueError("formal loudness policy is frozen")
    shaper = loudness["transient_peak_shaper"]
    if not isinstance(shaper, Mapping) or set(shaper) != {
        "enabled",
        "attack_ms",
        "release_ms",
        "max_reduction_db",
    } or not isinstance(shaper["enabled"], bool):
        raise ValueError("transient peak shaper contract is incomplete")
    for name in ("attack_ms", "release_ms", "max_reduction_db"):
        _validate_parameter(f"loudness.transient_peak_shaper.{name}", shaper[name])


def _validate_parameter(name: str, entry: Any) -> None:
    required = {
        "value",
        "unit",
        "range",
        "source_level",
        "source",
        "source_scope",
        "verification_state",
    }
    if not isinstance(entry, Mapping) or set(entry) != required:
        raise ValueError(f"{name} provenance record is incomplete")
    is_number = lambda value: (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )
    bounds = entry["range"]
    if (
        not is_number(entry["value"])
        or not isinstance(bounds, list)
        or len(bounds) != 2
        or not all(is_number(value) for value in bounds)
        or not bounds[0] < bounds[1]
        or not bounds[0] <= entry["value"] <= bounds[1]
    ):
        raise ValueError(f"{name} value/range is invalid")
    if (
        entry["source_level"] != "C"
        or entry["source"] != "synthetic"
        or entry["verification_state"] != "candidate_assumption"
        or not all(
            isinstance(entry[key], str) and entry[key]
            for key in ("unit", "source_scope")
        )
    ):
        raise ValueError(f"{name} provenance is invalid")


def reference_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


__all__ = (
    "ANCHOR_IDS",
    "BASE_COMMIT",
    "SCHEMA_VERSION",
    "SOURCE_KEYS",
    "StageICandidateProfile",
    "load_stage_i_candidate",
    "reference_sha256",
)
