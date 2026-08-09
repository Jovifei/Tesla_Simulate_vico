"""Offline semantic contract for S12 v1.2 synthetic source profiles.

This complements the JSON Schema with range containment and topology checks
that draft-2020-12 JSON Schema cannot express across sibling fields.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema


class SourceProfileContractError(ValueError):
    """Raised when a source profile is structurally valid but semantically unsafe."""


_ROOT = Path(__file__).resolve().parent
_SCHEMA_PATH = _ROOT / "schemas" / "source_profile_v12.schema.json"


def validate_source_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Validate provenance ranges, event topology, and order-surface semantics."""
    try:
        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(profile)
    except (OSError, json.JSONDecodeError, jsonschema.ValidationError) as error:
        raise SourceProfileContractError(str(error)) from error

    _validate_parameter_tree(profile)
    _validate_scalar_render_parameters(profile)
    _validate_topology(profile["source"])
    _validate_order_surface(profile["source"]["order_surface"])
    return profile


def _validate_parameter_tree(value: Any) -> None:
    if isinstance(value, dict):
        if "value" in value:
            _validate_parameter_range(value)
        for child in value.values():
            _validate_parameter_tree(child)
    elif isinstance(value, list):
        for child in value:
            _validate_parameter_tree(child)


def _validate_parameter_range(parameter: dict[str, Any]) -> None:
    recorded_value = parameter["value"]
    recorded_range = parameter["range"]
    if _is_number(recorded_value) or _is_numeric_list(recorded_value):
        if not _is_numeric_list(recorded_range) or len(recorded_range) < 2:
            raise SourceProfileContractError("numeric parameter range must be a finite numeric vector")
        lower = min(recorded_range)
        upper = max(recorded_range)
        values = [recorded_value] if _is_number(recorded_value) else recorded_value
        if any(number < lower or number > upper for number in values):
            raise SourceProfileContractError("numeric parameter value lies outside its declared range")
    elif isinstance(recorded_value, str):
        if not isinstance(recorded_range, list) or not all(isinstance(item, str) for item in recorded_range):
            raise SourceProfileContractError("enum parameter range must contain text values")
        if recorded_value not in recorded_range:
            raise SourceProfileContractError("enum parameter value lies outside its declared range")
    else:
        raise SourceProfileContractError("unsupported parameter value type")


def _validate_scalar_render_parameters(profile: dict[str, Any]) -> None:
    """Keep Python preflight scalar semantics aligned with MATLAB scalarNumber."""
    source = profile["source"]
    _require_scalar_numbers(source, (
        "cylinders", "rotor_count", "chambers_per_rotor", "shaft_turns_per_rotor_turn",
        "pulse_sharpness", "combustion_gain", "intake_gain", "induction_gain",
        "mechanical_gain", "flow_gain",
    ))
    _require_scalar_numbers(profile["transient"], (
        "acceleration_attack_gain", "lift_decay_gain",
    ))
    _require_scalar_numbers(profile["gearbox"], (
        "torque_cut_gain", "shift_bark_gain",
    ))
    _require_scalar_numbers(profile["afterfire"], (
        "upshift_bark_gain", "downshift_blip_pop_gain", "overrun_crackle_gain",
    ))
    for entry in source["order_surface"]:
        _require_scalar_numbers(entry, ("order",))


def _require_scalar_numbers(container: dict[str, Any], fields: tuple[str, ...]) -> None:
    for field in fields:
        if not _is_number(_value(container, field)):
            raise SourceProfileContractError(f"{field} must be one finite scalar number")


def _validate_topology(source: dict[str, Any]) -> None:
    kind = _value(source, "engine_kind")
    layout = _value(source, "layout")
    cylinders = _value(source, "cylinders")
    rotor_count = _value(source, "rotor_count")
    chambers = _value(source, "chambers_per_rotor")
    shaft_turns = _value(source, "shaft_turns_per_rotor_turn")
    firing_order = _value(source, "firing_order")
    phases = _value(source, "firing_phases_deg")
    bank_map = _value(source, "bank_map")

    if kind == "piston":
        if not isinstance(cylinders, int) or cylinders < 1 or layout not in {"inline", "V"}:
            raise SourceProfileContractError("piston profile must declare an inline or V cylinder count")
        if rotor_count != 0 or chambers != 0:
            raise SourceProfileContractError("piston profile may not declare rotary geometry")
        count = cylinders
    elif kind == "rotary":
        if (cylinders != 0 or layout != "rotary" or rotor_count != 2
                or chambers != 3 or shaft_turns != 3):
            raise SourceProfileContractError("v1.2 rotary profile requires the two-rotor, three-chamber topology")
        count = rotor_count
    else:
        raise SourceProfileContractError("unsupported engine kind")

    if not all(isinstance(values, list) and len(values) == count for values in (firing_order, phases, bank_map)):
        raise SourceProfileContractError("event arrays must match the declared cylinder or rotor count")
    if firing_order != sorted(range(1, count + 1), key=lambda event_id: phases[event_id - 1]):
        raise SourceProfileContractError("firing order must be the ascending 720-degree event map")
    if len(set(phases)) != count or any(not _is_number(phase) or phase < 0 or phase >= 720 for phase in phases):
        raise SourceProfileContractError("event phases must be unique values in [0, 720)")
    if any(bank not in {-1, 0, 1} for bank in bank_map):
        raise SourceProfileContractError("bank map may contain only -1, 0, or +1")
    if kind == "piston" and layout == "V" and not (-1 in bank_map and 1 in bank_map):
        raise SourceProfileContractError("V layout requires both independently routed banks")
    if kind == "piston" and layout == "inline" and any(bank != 0 for bank in bank_map):
        raise SourceProfileContractError("inline layout must use the centered bank map")
    if kind == "rotary" and sorted(bank_map) != [-1, 1]:
        raise SourceProfileContractError("two-rotor topology requires one event per routed bank")


def _validate_order_surface(entries: list[dict[str, Any]]) -> None:
    for entry in entries:
        order = _value(entry, "order")
        nodes = _value(entry, "rpm_nodes")
        low = _value(entry, "low_load_gains")
        high = _value(entry, "high_load_gains")
        phase = _value(entry, "phase_rad")
        if not _is_number(order) or not 0.5 <= order <= 18:
            raise SourceProfileContractError("order surface order must lie in [0.5, 18]")
        if not isinstance(nodes, list) or len(nodes) < 2 or any(right <= left for left, right in zip(nodes, nodes[1:])):
            raise SourceProfileContractError("order surface RPM nodes must be strictly increasing")
        if any(not isinstance(values, list) or len(values) != len(nodes) for values in (low, high, phase)):
            raise SourceProfileContractError("order surface vectors must share RPM-node length")
        if any(gain < 0 or gain > 1 for gain in [*low, *high]) or any(abs(angle) > 3.141593 for angle in phase):
            raise SourceProfileContractError("order surface gain or phase is outside the fixed contract")


def _value(container: dict[str, Any], field: str) -> Any:
    return container[field]["value"]


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and float("-inf") < value < float("inf")


def _is_numeric_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_is_number(item) for item in value)
