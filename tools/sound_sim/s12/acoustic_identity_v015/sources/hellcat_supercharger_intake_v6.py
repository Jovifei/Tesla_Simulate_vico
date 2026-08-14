"""Round-2 high-load refinement of the Stage-L Hellcat intake source.

The v6 source delegates all v8/v5 source construction, then changes only the
aero path above the configured high-load knee.  It remains a deterministic,
C-level synthetic source and never contributes to an exhaust stem.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib

import numpy as np

from ..contracts import SourceRender
from ..stage_l.crank_clock import HellcatCrankClock
from .hellcat_supercharger_intake_v5 import render_hellcat_supercharger_intake_v5


_PARAMETERS = {
    "combustion_ripple_to_aero_depth",
    "high_load_whine_knee",
    "high_load_whine_post_knee_slope",
}
_V8_OVERRIDES = {
    "aero_family_order_ratio": 5.0,
    "aero_harmonic_mix": 0.24,
    "aero_cluster_spread_ratio": 0.018,
    "gear_family_order_ratio": 10.0,
    "gear_to_aero_ratio": 0.10,
    "torque_ripple_to_gear_depth": 0.10,
    "intake_transfer_mix": 0.36,
    "casing_transfer_mix": 0.14,
    "boost_attack_10_90_s": 0.075,
    "boost_release_90_10_s": 0.24,
    "bypass_release_gain": 0.10,
    "bypass_decay_90_10_s": 0.16,
}
_CONTRIBUTORS = ("sc_intake_radiated", "sc_casing_radiated", "sc_bypass_release")


def render_hellcat_supercharger_intake_v6(
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    clock: HellcatCrankClock,
    sample_rate_hz: int,
    overrides: Mapping[str, float],
) -> SourceRender:
    """Render v5 exactly below the knee and refine its aero path above it."""
    values = _validate_overrides(overrides)
    base = render_hellcat_supercharger_intake_v5(
        rpm, load, throttle, clock, sample_rate_hz, _V8_OVERRIDES
    )
    load_array = np.clip(np.asarray(load, dtype=np.float64), 0.0, 1.0)
    throttle_array = np.clip(np.asarray(throttle, dtype=np.float64), 0.0, 1.0)
    high_load_control = np.minimum(load_array, throttle_array)
    knee = values["high_load_whine_knee"]
    normalized = np.clip((high_load_control - knee) / (1.0 - knee), 0.0, 1.0)
    blend = normalized * normalized * (3.0 - 2.0 * normalized)
    attenuation = 1.0 - values["high_load_whine_post_knee_slope"] * blend

    ripple = 2.0 * np.asarray(clock.torque_ripple_envelope, dtype=np.float64) - 1.0
    above_knee = blend > 0.0
    if np.any(above_knee):
        ripple = ripple - float(np.mean(ripple[above_knee]))
        ripple_rms = _rms(ripple[above_knee])
        unit_rms_ripple = ripple / ripple_rms if ripple_rms > 1.0e-15 else np.zeros_like(ripple)
    else:
        unit_rms_ripple = np.zeros_like(ripple)
    ripple_factor = 1.0 + values["combustion_ripple_to_aero_depth"] * blend * unit_rms_ripple
    aero_factor = attenuation * ripple_factor

    stems = {name: np.asarray(stem, dtype=np.float64).copy() for name, stem in base.stems.items()}
    for name in ("sc_aero_raw", "sc_intake_radiated"):
        stems[name] *= aero_factor[:, None]
    pressure = sum(
        (stems[name] for name in _CONTRIBUTORS),
        np.zeros_like(base.pressure),
    )
    stems["supercharger_intake"] = pressure.copy()

    below_knee = high_load_control <= knee
    below_knee_identical = np.array_equal(pressure[below_knee], base.pressure[below_knee]) and all(
        np.array_equal(stems[name][below_knee], base.stems[name][below_knee])
        for name in base.stems
    )
    aero_delta = stems["sc_intake_radiated"] - base.stems["sc_intake_radiated"]
    ripple_only_delta = (
        base.stems["sc_intake_radiated"]
        * attenuation[:, None]
        * (ripple_factor[:, None] - 1.0)
    )
    active_conditions = {
        "combustion_ripple_to_aero_depth": _energy(ripple_only_delta) > 1.0e-24,
        "high_load_whine_knee": _energy(aero_delta) > 1.0e-24,
        "high_load_whine_post_knee_slope": _energy(
            base.stems["sc_intake_radiated"] * (attenuation[:, None] - 1.0)
        ) > 1.0e-24,
    }
    active = sorted(name for name, used in active_conditions.items() if used)
    inactive = sorted(_PARAMETERS - set(active))
    diagnostics = dict(base.diagnostics)
    diagnostics.update({
        "source_version": "hellcat_supercharger_intake_v6",
        "v8_source_baseline": "hellcat_supercharger_intake_v5",
        "below_knee_v5_byte_identical": bool(below_knee_identical),
        "high_load_control": "minimum_of_existing_trace_load_and_throttle",
        "high_load_whine_knee": knee,
        "high_load_blend_peak": float(np.max(blend)) if blend.size else 0.0,
        "high_load_whine_attenuation_min": float(np.min(attenuation)) if attenuation.size else 1.0,
        "monotonic_high_load_whine_attenuation": _is_monotonic_by_control(
            high_load_control, attenuation
        ),
        "shared_clock_torque_ripple_modulation": True,
        "torque_ripple_clock_object_id": id(clock),
        "torque_ripple_zero_mean": float(np.mean(unit_rms_ripple[above_knee])) if np.any(above_knee) else 0.0,
        "torque_ripple_unit_rms": _rms(unit_rms_ripple[above_knee]),
        "torque_ripple_sha256": _array_sha256(unit_rms_ripple),
        "random_source": False,
        "fixed_hz_oscillator": False,
        "gear_or_bypass_change": False,
        "exhaust_contributor": False,
        "parameter_effect_energy": {
            "combustion_ripple_to_aero_depth": _energy(ripple_only_delta),
            "high_load_whine_knee": _energy(aero_delta),
            "high_load_whine_post_knee_slope": _energy(
                base.stems["sc_intake_radiated"] * (attenuation[:, None] - 1.0)
            ),
        },
        "candidate_source_overrides": dict(values),
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
        raise ValueError("v6 supercharger overrides must contain the exact Round-2 parameter set")
    values = {name: float(value) for name, value in overrides.items()}
    if any(not np.isfinite(value) for value in values.values()):
        raise ValueError("v6 supercharger overrides must be finite")
    if not 0.0 <= values["combustion_ripple_to_aero_depth"] <= 1.0:
        raise ValueError("combustion_ripple_to_aero_depth must be within [0, 1]")
    if not 0.0 < values["high_load_whine_knee"] < 1.0:
        raise ValueError("high_load_whine_knee must be within (0, 1)")
    if not 0.0 <= values["high_load_whine_post_knee_slope"] <= 1.0:
        raise ValueError("high_load_whine_post_knee_slope must be within [0, 1]")
    return values


def _is_monotonic_by_control(control: np.ndarray, attenuation: np.ndarray) -> bool:
    if control.size < 2:
        return True
    order = np.argsort(control, kind="stable")
    return bool(np.all(np.diff(attenuation[order]) <= 1.0e-15))


def _array_sha256(value: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(value, dtype="<f8").tobytes(order="C")).hexdigest()


def _rms(value: np.ndarray) -> float:
    array = np.asarray(value, dtype=np.float64)
    return float(np.sqrt(np.mean(np.square(array)))) if array.size else 0.0


def _energy(value: np.ndarray) -> float:
    return float(np.sum(np.square(np.asarray(value, dtype=np.float64))))


__all__ = ("render_hellcat_supercharger_intake_v6",)
