"""Round-2 high-load deltas over the Stage-L v8 cross-plane source."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib

import numpy as np

from ..contracts import SourceRender
from .hellcat_crossplane_combustion_v2 import render_hellcat_crossplane_combustion_v2


_PARAMETERS = {
    "acceleration_blowdown_body_gain",
    "low_frequency_blowdown_gain",
    "structure_shock_mix",
    "torque_ripple_modulation_depth",
}
_V8_OVERRIDES = {
    "cylinder_strength_variation": 0.16,
    "bank_amplitude_asymmetry": 0.05,
    "blowdown_attack_ms": 0.45,
    "blowdown_fast_decay_ms": 2.0,
    "blowdown_slow_decay_ms": 6.5,
    "blowdown_slow_weight": 0.28,
    "low_frequency_blowdown_gain": 1.12,
    "structure_shock_mix": 0.10,
    "torque_ripple_modulation_depth": 0.11,
    "xpipe_cross_coupling": 0.14,
    "xpipe_delay_ms": 0.65,
}
_CONTRIBUTORS = (
    "hemi_exhaust_left",
    "hemi_exhaust_right",
    "hemi_blowdown_body",
    "hemi_structure_shock",
    "hemi_mechanical_torque_ripple",
)
_HIGH_LOAD_BLEND_START = 0.75
_HIGH_LOAD_BLEND_FULL = 0.90


def render_hellcat_crossplane_combustion_v3(
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    clock: object,
    sample_rate_hz: int,
    overrides: Mapping[str, float],
) -> SourceRender:
    """Apply the four v9 deltas only through a smooth high-load trace blend."""
    values = _validate_overrides(overrides)
    baseline = render_hellcat_crossplane_combustion_v2(
        rpm, load, throttle, clock, sample_rate_hz, _V8_OVERRIDES
    )
    load_array = np.asarray(load, dtype=np.float64)
    throttle_array = np.asarray(throttle, dtype=np.float64)
    high_load_control = np.minimum(load_array, throttle_array)
    normalized = np.clip(
        (high_load_control - _HIGH_LOAD_BLEND_START)
        / (_HIGH_LOAD_BLEND_FULL - _HIGH_LOAD_BLEND_START),
        0.0,
        1.0,
    )
    blend = normalized * normalized * (3.0 - 2.0 * normalized)

    stems = {
        name: np.asarray(stem, dtype=np.float64).copy()
        for name, stem in baseline.stems.items()
    }
    body_target = (
        values["acceleration_blowdown_body_gain"]
        * values["low_frequency_blowdown_gain"]
        / _V8_OVERRIDES["low_frequency_blowdown_gain"]
    )
    stems["hemi_blowdown_body"] *= (1.0 + blend * (body_target - 1.0))[:, None]
    structure_target = values["structure_shock_mix"] / _V8_OVERRIDES["structure_shock_mix"]
    stems["hemi_structure_shock"] *= (1.0 + blend * (structure_target - 1.0))[:, None]
    torque_target = (
        values["torque_ripple_modulation_depth"]
        / _V8_OVERRIDES["torque_ripple_modulation_depth"]
    )
    stems["hemi_mechanical_torque_ripple"] *= (
        1.0 + blend * (torque_target - 1.0)
    )[:, None]

    pressure = sum(
        (stems[name] for name in _CONTRIBUTORS),
        np.zeros_like(baseline.pressure),
    )
    stems["hemi_exhaust"] = stems["hemi_exhaust_left"] + stems["hemi_exhaust_right"]
    stems["hemi_combustion_and_blowdown"] = pressure.copy()

    zero_blend = blend == 0.0
    zero_blend_identical = np.array_equal(
        pressure[zero_blend], baseline.pressure[zero_blend]
    ) and all(
        np.array_equal(stems[name][zero_blend], baseline.stems[name][zero_blend])
        for name in baseline.stems
    )
    whole_render_identical = np.array_equal(pressure, baseline.pressure) and all(
        np.array_equal(stems[name], baseline.stems[name]) for name in baseline.stems
    )
    parameter_effect_energy = {
        "acceleration_blowdown_body_gain": _energy(
            baseline.stems["hemi_blowdown_body"]
            * (blend * (values["acceleration_blowdown_body_gain"] - 1.0))[:, None]
        ),
        "low_frequency_blowdown_gain": _energy(
            baseline.stems["hemi_blowdown_body"]
            * (
                blend
                * (
                    values["low_frequency_blowdown_gain"]
                    / _V8_OVERRIDES["low_frequency_blowdown_gain"]
                    - 1.0
                )
            )[:, None]
        ),
        "structure_shock_mix": _energy(
            stems["hemi_structure_shock"] - baseline.stems["hemi_structure_shock"]
        ),
        "torque_ripple_modulation_depth": _energy(
            stems["hemi_mechanical_torque_ripple"]
            - baseline.stems["hemi_mechanical_torque_ripple"]
        ),
    }
    active = sorted(
        name for name, energy in parameter_effect_energy.items() if energy > 1.0e-24
    )
    inactive = sorted(_PARAMETERS - set(active))
    diagnostics = dict(baseline.diagnostics)
    diagnostics.update({
        "source_version": "hellcat_crossplane_combustion_v3",
        "v8_source_baseline": "hellcat_crossplane_combustion_v2",
        "high_load_control": "minimum_of_existing_trace_load_and_throttle",
        "high_load_blend_start": _HIGH_LOAD_BLEND_START,
        "high_load_blend_full": _HIGH_LOAD_BLEND_FULL,
        "high_load_blend_peak": float(np.max(blend)) if blend.size else 0.0,
        "high_load_blend_sha256": _array_sha256(blend),
        "zero_blend_v8_byte_identical": bool(zero_blend_identical),
        "v8_baseline_byte_identical": bool(whole_render_identical),
        "pressure_rebuilt_from_actual_contributors_once": True,
        "aggregates_rebuilt_after_v9_deltas": True,
        "parameter_effect_energy": parameter_effect_energy,
        "candidate_source_overrides": dict(values),
        "parameter_affected_stems": {
            "acceleration_blowdown_body_gain": ["hemi_blowdown_body"],
            "low_frequency_blowdown_gain": ["hemi_blowdown_body"],
            "structure_shock_mix": ["hemi_structure_shock"],
            "torque_ripple_modulation_depth": ["hemi_mechanical_torque_ripple"],
        },
        "candidate_parameter_usage": {
            "requested": sorted(_PARAMETERS),
            "read": sorted(_PARAMETERS),
            "configured": sorted(_PARAMETERS),
            "active": active,
            "inactive": inactive,
            "unused": [],
        },
    })
    return SourceRender(pressure=pressure, stems=stems, diagnostics=diagnostics).validate()


def _validate_overrides(overrides: Mapping[str, float]) -> dict[str, float]:
    if not isinstance(overrides, Mapping) or set(overrides) != _PARAMETERS:
        raise ValueError("v3 combustion overrides must contain the exact Round-2 parameter set")
    values = {name: float(value) for name, value in overrides.items()}
    if any(not np.isfinite(value) for value in values.values()):
        raise ValueError("v3 combustion overrides must be finite")
    if values["acceleration_blowdown_body_gain"] <= 0.0:
        raise ValueError("acceleration_blowdown_body_gain must be positive")
    for name in (
        "low_frequency_blowdown_gain",
        "structure_shock_mix",
        "torque_ripple_modulation_depth",
    ):
        if values[name] < 0.0:
            raise ValueError(f"{name} must be non-negative")
    return values


def _array_sha256(value: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(value, dtype="<f8").tobytes(order="C")).hexdigest()


def _energy(value: np.ndarray) -> float:
    return float(np.sum(np.square(np.asarray(value, dtype=np.float64))))


__all__ = ("render_hellcat_crossplane_combustion_v3",)
