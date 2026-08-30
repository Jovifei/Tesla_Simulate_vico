"""Strict JSON contracts for the clean-room event-domain source."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

CONFIG_ROOT = Path(__file__).resolve().parent / "configs"
_PARAMETER_KEYS = {"value", "unit", "range", "source_level", "source", "verification_state"}
_TOP_LEVEL_KEYS = {
    "schema", "vehicle_id", "architecture", "cylinder_or_rotor_count", "bank_count", "bank_angle_deg",
    "cycle_definition", "event_phase_deg", "bank_assignment", "firing_order_evidence", "crank_inertia",
    "friction_model", "idle_target_rpm", "idle_governor", "combustion_event", "blowdown_event",
    "cycle_variation", "per_path_primary_length_m", "per_path_attenuation", "collector_assignment",
    "collector_length_m", "collector_loss", "gas_temperature_model", "intake_model", "forced_induction",
    "afterfire", "transfer_ir", "runtime_limits", "provenance", "asset_checksums",
    "crankpin_geometry", "rotor_geometry", "timbre_map", "bank_phase_offsets_version", "bank_phase_offsets_deg",
    "click_gate",
    "rotary_event_width_scale", "rotary_event_gain_scale", "housing_gain_scale", "housing_decay_scale",
    "housing_order_mix", "primary_spool_tau", "secondary_spool_tau", "blow_off_gain", "blow_off_decay",
    "timbre_mixes", "exhaust_waveguide", "monitor_policy", "attack_shaping",
    "require_fitted_timbre_map",
    "fitted_timbre_map",
}


def load_config(vehicle_id: str) -> dict[str, Any]:
    path = CONFIG_ROOT / f"{vehicle_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"unknown event-domain config: {vehicle_id}")
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("architecture") == "rotary_wankel":
        defaults_path = CONFIG_ROOT.parent / "rotary_parameter_defaults.json"
        defaults = json.loads(defaults_path.read_text(encoding="utf-8"))
        for key, value in defaults.items():
            config.setdefault(key, value)
    afterfire = config.setdefault("afterfire", {})
    afterfire.setdefault("ignition_delay_s", parameter(0.004, "s", [0.001, 0.25], source="synthetic afterfire delay", verification_state="synthetic_assumption"))
    afterfire.setdefault("event_location", parameter("primary", "label", "primary|bank_collector|central_collector", source="synthetic afterfire location", verification_state="synthetic_assumption"))
    count = int(config["cylinder_or_rotor_count"]["value"])
    bank_count = int(config["bank_count"]["value"])
    config.setdefault("bank_phase_offsets_version", "s12.stage_w.bank_phase_offsets.v1")
    config.setdefault("bank_phase_offsets_deg", parameter([0.0] * bank_count, "deg", [-180.0, 180.0], source="synthetic declared bank phase geometry", verification_state="synthetic_assumption"))
    if config.get("architecture") == "piston":
        config.setdefault("crankpin_geometry", parameter([0.0] * count, "deg", [0, 720], source="synthetic crankpin geometry", verification_state="synthetic_assumption"))
    else:
        config.setdefault("rotor_geometry", parameter(list(config["event_phase_deg"]["value"]), "eccentric_shaft_deg", [0, 1080], source="synthetic rotor geometry", verification_state="synthetic_assumption"))
    return validate_config(config)


def parameter(value: Any, unit: str, value_range: Any, source: str = "synthetic", verification_state: str = "synthetic_assumption") -> dict[str, Any]:
    return {"value": value, "unit": unit, "range": value_range, "source_level": "C", "source": source, "verification_state": verification_state}


def unwrap(config: Mapping[str, Any], path: str) -> Any:
    node: Any = config
    for part in path.split("."):
        node = node[part]
    return node["value"] if isinstance(node, Mapping) and "value" in node else node


def flatten_parameters(node: Mapping[str, Any], prefix: str = "") -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping) and "value" in value:
            result[path] = value
        elif isinstance(value, Mapping):
            result.update(flatten_parameters(value, path))
    return result


def validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(config, Mapping):
        raise ValueError("config must be an object")
    config = copy.deepcopy(dict(config))
    bank_count = int(config.get("bank_count", {}).get("value", 0)) if isinstance(config.get("bank_count"), Mapping) else 0
    config.setdefault("bank_phase_offsets_version", "s12.stage_w.bank_phase_offsets.v1")
    config.setdefault("bank_phase_offsets_deg", parameter([0.0] * bank_count, "deg", [-180.0, 180.0], source="synthetic declared bank phase geometry", verification_state="synthetic_assumption"))
    unknown = set(config) - _TOP_LEVEL_KEYS
    if unknown:
        raise ValueError(f"unknown config fields: {sorted(unknown)}")
    for key in ("schema", "vehicle_id", "architecture"):
        if not isinstance(config.get(key), str) or not config[key]:
            raise ValueError(f"{key} must be a non-empty string")
    if config["schema"] != "s12.event_domain_v1":
        raise ValueError("unsupported event-domain schema")
    if config["architecture"] not in {"piston", "rotary_wankel"}:
        raise ValueError("architecture must be piston or rotary_wankel")
    if config.get("bank_phase_offsets_version") != "s12.stage_w.bank_phase_offsets.v1":
        raise ValueError("unsupported bank phase offset schema")
    for path, node in flatten_parameters(config).items():
        if set(node) != _PARAMETER_KEYS:
            raise ValueError(f"parameter {path} has incomplete provenance or unknown fields")
        if node["source_level"] not in {"A", "B", "C"}:
            raise ValueError(f"parameter {path} has invalid source_level")
        if not isinstance(node["source"], str) or not node["source"]:
            raise ValueError(f"parameter {path} has no source")
        if node["verification_state"] not in {"verified", "synthetic_assumption", "pending"}:
            raise ValueError(f"parameter {path} has invalid verification_state")
    count = int(unwrap(config, "cylinder_or_rotor_count"))
    bank_count = int(unwrap(config, "bank_count"))
    if count <= 0 or bank_count <= 0:
        raise ValueError("cylinder/rotor and bank counts must be positive")
    phases = list(unwrap(config, "event_phase_deg"))
    if len(phases) != count:
        raise ValueError("event_phase_deg length must equal cylinder_or_rotor_count")
    if config["architecture"] == "piston":
        geometry = list(unwrap(config, "crankpin_geometry")) if "crankpin_geometry" in config else [0.0] * count
        if len(geometry) != count or not all(isinstance(value, (int, float)) and not isinstance(value, bool) and __import__("math").isfinite(float(value)) for value in geometry):
            raise ValueError("crankpin_geometry must contain one finite offset per cylinder")
    else:
        geometry = list(unwrap(config, "rotor_geometry")) if "rotor_geometry" in config else phases
        if len(geometry) != count or not all(isinstance(value, (int, float)) and __import__("math").isfinite(float(value)) for value in geometry):
            raise ValueError("rotor_geometry must contain one finite offset per rotor")
    assignment = list(unwrap(config, "bank_assignment"))
    if len(assignment) != count or any(int(x) < 0 or int(x) >= bank_count for x in assignment):
        raise ValueError("bank_assignment must cover each entity")
    bank_offsets = list(unwrap(config, "bank_phase_offsets_deg"))
    if len(bank_offsets) != bank_count or any(not isinstance(x, (int, float)) or isinstance(x, bool) or not __import__("math").isfinite(float(x)) or not -180.0 <= float(x) <= 180.0 for x in bank_offsets):
        raise ValueError("bank_phase_offsets_deg must contain one finite bounded offset per bank")
    lengths = list(unwrap(config, "per_path_primary_length_m"))
    attenuations = list(unwrap(config, "per_path_attenuation"))
    if len(lengths) != count or len(attenuations) != count:
        raise ValueError("per-path arrays must equal cylinder_or_rotor_count")
    if config["architecture"] == "piston":
        order = list(unwrap(config, "firing_order_evidence"))
        if sorted(int(x) for x in order) != list(range(1, count + 1)):
            raise ValueError("firing_order_evidence must be a permutation of all entities")
    elif unwrap(config, "cycle_definition") not in {"rotary_360", "rotary_1080"}:
        raise ValueError("rotary config must declare a rotary cycle definition")
    return copy.deepcopy(dict(config))
