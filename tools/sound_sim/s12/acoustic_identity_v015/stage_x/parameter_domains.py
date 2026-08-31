"""Domain-aware sampling for Stage X/Y acoustic search parameters.

The original Sobol search treated every control as an unconstrained float.
This module makes categorical controls discrete and clamps physical time/gain
controls before they reach the renderer.
"""

from __future__ import annotations

from typing import Any

import numpy as np

DOMAIN_SCHEMA = "s12.stage_y.parameter_domains.v1"

_CATEGORICAL: dict[str, tuple[float, ...]] = {
    "waveguide_reflection": (0.0, 1.0),
    "afterfire_location_mix": (0.0, 1.0),
}

_BOUNDS: dict[str, tuple[float, float]] = {
    "combustion_event_energy": (0.05, 1.50),
    "combustion_rise_time": (0.0002, 0.0200),
    "combustion_decay_time": (0.0020, 0.1200),
    "cycle_variation": (0.0, 0.35),
    "crank_inertia": (0.02, 2.0),
    "idle_governor": (0.0, 1.0),
    "primary_length_spread": (0.20, 2.50),
    "primary_attenuation_spread": (0.20, 2.50),
    "waveguide_loss": (0.0, 0.50),
    "collector_loss": (0.10, 1.00),
    "attack_mix_120_400": (0.0, 2.0),
    "timbre_map_order_weights": (0.0, 4.0),
    "blower_sideband_mix": (0.0, 4.0),
    "blower_broadband_mix": (0.0, 4.0),
    "blower_casing_mix": (0.0, 4.0),
    "intake_mix": (0.0, 1.5),
    "boost_attack": (0.0, 2.0),
    "boost_release": (0.0, 5.0),
    "bypass_threshold": (0.02, 1.0),
    "afterfire_reservoir_rate": (0.0, 2.0),
    "afterfire_ignition_delay": (0.0, 0.25),
    "afterfire_energy": (0.0, 0.50),
    "monitor_attack": (0.001, 2.0),
    "monitor_release": (0.001, 10.0),
    "monitor_max_makeup": (0.0, 24.0),
}


def parameter_domain(name: str, baseline: float, delta: float) -> dict[str, Any]:
    """Describe one search domain in a machine-readable form."""
    if name in _CATEGORICAL:
        return {
            "schema": DOMAIN_SCHEMA,
            "name": name,
            "kind": "categorical",
            "choices": list(_CATEGORICAL[name]),
        }
    requested = (float(baseline) - float(delta), float(baseline) + float(delta))
    configured = _BOUNDS.get(name, requested)
    lo = max(requested[0], configured[0])
    hi = min(requested[1], configured[1])
    if hi < lo:
        lo, hi = configured
    return {
        "schema": DOMAIN_SCHEMA,
        "name": name,
        "kind": "continuous",
        "lower": float(lo),
        "upper": float(hi),
    }


def sanitize_value(name: str, value: float) -> float:
    """Clamp or quantize one renderer-facing search value."""
    numeric = float(value)
    if not np.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    if name in _CATEGORICAL:
        choices = np.asarray(_CATEGORICAL[name], dtype=np.float64)
        return float(choices[int(np.argmin(np.abs(choices - numeric)))])
    if name in _BOUNDS:
        lo, hi = _BOUNDS[name]
        return float(np.clip(numeric, lo, hi))
    return numeric


def sample_value(item: Any, coordinate: float) -> float:
    """Map a Sobol coordinate in [0, 1] to one valid parameter value."""
    coordinate = float(np.clip(coordinate, 0.0, 1.0))
    domain = parameter_domain(item.name, item.baseline, item.delta)
    if domain["kind"] == "categorical":
        choices = domain["choices"]
        index = min(int(np.floor(coordinate * len(choices))), len(choices) - 1)
        return float(choices[index])
    return sanitize_value(
        item.name,
        domain["lower"] + coordinate * (domain["upper"] - domain["lower"]),
    )


def refine_value(item: Any, center: float, coordinate: float, shrink: float) -> float:
    """Sample a local bounded value while preserving discrete domains."""
    if item.name in _CATEGORICAL:
        return sample_value(item, coordinate)
    span = float(item.delta) * float(shrink)
    value = float(center) + (2.0 * float(coordinate) - 1.0) * span
    return sanitize_value(item.name, value)


def sanitize_overrides(overrides: dict[str, float]) -> dict[str, float]:
    """Return a deterministic, renderer-safe copy of an override mapping."""
    return {name: sanitize_value(name, value) for name, value in overrides.items()}


def validate_parameter_set(parameters: list[Any]) -> dict[str, Any]:
    """Describe invalid or degenerate domains without rendering audio."""
    errors: list[str] = []
    domains: list[dict[str, Any]] = []
    for item in parameters:
        domain = parameter_domain(item.name, item.baseline, item.delta)
        domains.append(domain)
        if domain["kind"] == "continuous" and domain["upper"] <= domain["lower"]:
            errors.append(f"{item.name}: non-positive continuous span")
        if domain["kind"] == "categorical" and len(set(domain["choices"])) < 2:
            errors.append(f"{item.name}: fewer than two categorical choices")
    return {
        "schema": DOMAIN_SCHEMA,
        "parameter_count": len(parameters),
        "domains": domains,
        "errors": errors,
        "passed": not errors,
    }


__all__ = [
    "DOMAIN_SCHEMA",
    "parameter_domain",
    "refine_value",
    "sample_value",
    "sanitize_overrides",
    "sanitize_value",
    "validate_parameter_set",
]
