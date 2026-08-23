"""Executable Stage U mappings from dashboard abstractions to Track-S renderer controls."""
from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_g.candidate_profiles import (
    StageGCandidateProfile,
    _validate_payload,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_g.render_candidate import render_stage_g_candidate


class StageUReachabilityError(ValueError):
    """Raised when a Stage U abstract parameter cannot become a real override."""


_STAGE_U_PARAMETERS = {
    "ferrari_458": ("metallic_gain_scale", "mid_carrier_gain_scale", "metallic_texture_mix"),
    "hellcat": ("blower_intake_balance", "intake_gain_scale", "pressure_attack_gain_scale"),
    "rx7_fd": ("housing_gain_scale", "turbo_gain_scale", "turbine_gain_scale", "rotary_amplitude_scale", "housing_order_weight_scale"),
}
_TARGET_STEMS = {
    "ferrari_458": {
        "metallic_gain_scale": ("metallic",),
        "mid_carrier_gain_scale": ("left_bank", "right_bank"),
        "metallic_texture_mix": ("metallic",),
    },
    "hellcat": {
        "blower_intake_balance": ("blower", "intake"),
        "intake_gain_scale": ("intake",),
        "pressure_attack_gain_scale": ("pressure_attack",),
    },
    "rx7_fd": {
        "housing_gain_scale": ("rotor_housing",),
        "turbo_gain_scale": ("turbo",),
        "turbine_gain_scale": ("turbine",),
        "rotary_amplitude_scale": ("rotary",),
        "housing_order_weight_scale": ("rotor_housing",),
    },
}
_RANGES = {
    "metallic_gain_scale": (10.0 ** (-6.0 / 20.0), 10.0 ** (6.0 / 20.0), "ratio", "metallic_envelope"),
    "mid_carrier_gain_scale": (10.0 ** (-6.0 / 20.0), 10.0 ** (6.0 / 20.0), "ratio", "mid_carrier_balance"),
    "metallic_texture_mix": (0.0, 1.0, "fraction_0_1", "upper_metallic_texture"),
    "blower_intake_balance": (-0.25, 0.25, "balance_minus1_to1", "blower_vs_intake"),
    "intake_gain_scale": (10.0 ** (-6.0 / 20.0), 10.0 ** (6.0 / 20.0), "ratio", "mid_band_intake_pressure"),
    "pressure_attack_gain_scale": (10.0 ** (-6.0 / 20.0), 10.0 ** (6.0 / 20.0), "ratio", "pressure_attack_stem"),
    "housing_gain_scale": (10.0 ** (-6.0 / 20.0), 10.0 ** (6.0 / 20.0), "ratio", "rotor_housing_level"),
    "turbo_gain_scale": (10.0 ** (-6.0 / 20.0), 10.0 ** (6.0 / 20.0), "ratio", "turbo_band_level"),
    "turbine_gain_scale": (10.0 ** (-6.0 / 20.0), 10.0 ** (6.0 / 20.0), "ratio", "turbine_band_level"),
    "rotary_amplitude_scale": (0.80, 1.20, "ratio", "rotary_amplitude"),
    "housing_order_weight_scale": (0.70, 1.30, "ratio", "housing_order_distribution"),
}


def _db_to_ratio(value: float) -> float:
    return float(10.0 ** (float(value) / 20.0))


def dashboard_values_to_source(vehicle_id: str, values: Mapping[str, float]) -> dict[str, float]:
    """Map the prior Dashboard grids to concrete renderer source overrides."""

    if vehicle_id == "ferrari_458":
        required = {"metallic_envelope_db", "mid_band_balance_db", "texture_mix"}
        if set(values) != required:
            raise StageUReachabilityError("Ferrari Stage U values must be metallic_envelope_db/mid_band_balance_db/texture_mix")
        return {
            "metallic_gain_scale": _db_to_ratio(float(values["metallic_envelope_db"])),
            "mid_carrier_gain_scale": _db_to_ratio(float(values["mid_band_balance_db"])),
            "metallic_texture_mix": float(values["texture_mix"]),
        }
    if vehicle_id == "hellcat":
        required = {"blower_intake_balance", "mid_band_pressure_db", "pressure_attack_db"}
        if set(values) != required:
            raise StageUReachabilityError("Hellcat Stage U values must be blower_intake_balance/mid_band_pressure_db/pressure_attack_db")
        return {
            "blower_intake_balance": float(values["blower_intake_balance"]),
            "intake_gain_scale": _db_to_ratio(float(values["mid_band_pressure_db"])),
            "pressure_attack_gain_scale": _db_to_ratio(float(values["pressure_attack_db"])),
        }
    if vehicle_id == "rx7_fd":
        required = {"housing_peak_db", "turbo_band_balance_db", "broadband_mix"}
        if set(values) != required:
            raise StageUReachabilityError("RX-7 Stage U values must be housing_peak_db/turbo_band_balance_db/broadband_mix")
        mix = float(values["broadband_mix"])
        turbo = _db_to_ratio(float(values["turbo_band_balance_db"]))
        return {
            "housing_gain_scale": _db_to_ratio(float(values["housing_peak_db"])),
            "turbo_gain_scale": turbo,
            "turbine_gain_scale": 1.0 / turbo,
            "rotary_amplitude_scale": 0.80 + 0.40 * mix,
            "housing_order_weight_scale": 0.70 + 0.60 * mix,
        }
    raise StageUReachabilityError(f"unsupported Stage U vehicle: {vehicle_id}")


def _source_entry(name: str, value: float) -> dict[str, Any]:
    low, high, unit, scope = _RANGES[name]
    if not low <= value <= high:
        raise StageUReachabilityError(f"mapped source parameter out of range: {name}={value}")
    return {
        "value": float(value),
        "unit": unit,
        "range": [low, high],
        "source_level": "C",
        "source": "synthetic",
        "source_scope": f"stage_u_{scope}",
        "verification_state": "candidate_assumption",
    }


def _read_profile(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StageUReachabilityError(f"cannot read Stage-G candidate: {path}") from exc
    _validate_payload(payload)
    return payload


def build_stage_u_candidate(profile_path: Path, candidate_id: str, dashboard_values: Mapping[str, float]) -> tuple[StageGCandidateProfile, dict[str, Any]]:
    """Create a strict Stage-G compatible candidate using only real source controls."""

    payload = deepcopy(_read_profile(Path(profile_path)))
    vehicle_id = str(payload["vehicle_id"])
    source_values = dashboard_values_to_source(vehicle_id, dashboard_values)
    parent_candidate_id = str(payload["candidate_id"])
    payload["candidate_id"] = str(candidate_id)
    payload["parent_candidate_id"] = parent_candidate_id
    payload["hypothesis"] = f"Stage U executable {vehicle_id} source mapping; all values must pass per-parameter reachability before grid rendering."
    # The legacy name only represented amplitude.  It remains readable in old
    # receipts but is intentionally not accepted in any new Stage-U profile.
    if vehicle_id == "rx7_fd":
        payload["source"].pop("rotary_pulse_width_scale", None)
    for name, value in source_values.items():
        payload["source"][name] = _source_entry(name, value)
    _validate_payload(payload)
    mapping = {
        "schema_version": "s12-stage-u-source-mapping-v1",
        "vehicle_id": vehicle_id,
        "candidate_id": str(candidate_id),
        "parent_candidate_id": parent_candidate_id,
        "parameter_group": {
            "ferrari_458": "metallic_high_order_envelope_mid_band",
            "hellcat": "pressure_attack_blower_intake_balance",
            "rx7_fd": "rotary_housing_turbo_distribution",
        }[vehicle_id],
        "dashboard_values": dict(dashboard_values),
        "source_values": source_values,
        "legacy_rotary_pulse_width_scale": "REJECTED_FOR_STAGE_U_GRID" if vehicle_id == "rx7_fd" else "NOT_APPLICABLE",
    }
    return StageGCandidateProfile(payload, Path(profile_path)), mapping


def _energy(render: Any, stem: str) -> float:
    values = np.asarray(render.stems.get(stem, np.zeros_like(render.pressure)), dtype=np.float64)
    return float(np.sum(np.square(values)))


def _triplet(candidate: StageGCandidateProfile, name: str) -> tuple[StageGCandidateProfile, StageGCandidateProfile, StageGCandidateProfile]:
    entry = candidate.payload["source"][name]
    baseline = float(entry["value"])
    low, high = (float(entry["range"][0]), float(entry["range"][1]))
    delta = max((high - low) * 0.10, 1e-5)
    minus = candidate.with_parameter("source", name, max(low, baseline - delta))
    plus = candidate.with_parameter("source", name, min(high, baseline + delta))
    return minus, candidate, plus


def _direction_ok(name: str, minus: Any, baseline: Any, plus: Any, targets: tuple[str, ...]) -> bool:
    if name == "blower_intake_balance":
        return _energy(plus, "blower") > _energy(baseline, "blower") > _energy(minus, "blower") and _energy(plus, "intake") < _energy(baseline, "intake") < _energy(minus, "intake")
    values = [sum(_energy(render, stem) for stem in targets) for render in (minus, baseline, plus)]
    return values[0] < values[1] < values[2]


def probe_candidate_reachability(candidate: StageGCandidateProfile, trace: VehicleStateTrace, *, non_target_limit: float = 0.75) -> dict[str, Any]:
    """Run required -delta/baseline/+delta evidence for Stage-U source controls."""

    trace.validate()
    controls = [name for name in _STAGE_U_PARAMETERS[candidate.vehicle_id] if name in candidate.payload["source"]]
    if not controls:
        raise StageUReachabilityError("PARAMETER_NOT_REACHABLE: candidate contains no Stage-U controls")
    baseline_render = render_stage_g_candidate(candidate.vehicle_id, trace, candidate)
    usage = baseline_render.diagnostics.get("candidate_parameter_usage", {})
    consumed = set(usage.get("consumed", ()))
    rows: list[dict[str, Any]] = []
    all_stems = tuple(baseline_render.stems)
    for name in controls:
        minus_candidate, _, plus_candidate = _triplet(candidate, name)
        minus_render = render_stage_g_candidate(candidate.vehicle_id, trace, minus_candidate)
        plus_render = render_stage_g_candidate(candidate.vehicle_id, trace, plus_candidate)
        targets = _TARGET_STEMS[candidate.vehicle_id][name]
        target_changed = any(abs(_energy(plus_render, stem) - _energy(minus_render, stem)) > 1e-9 for stem in targets)
        direction_ok = _direction_ok(name, minus_render, baseline_render, plus_render, targets)
        non_targets = [stem for stem in all_stems if stem not in targets]
        relative_non_target = max(
            (abs(_energy(plus_render, stem) - _energy(minus_render, stem)) / max(_energy(baseline_render, stem), 1e-12) for stem in non_targets),
            default=0.0,
        )
        rows.append({
            "parameter_id": f"source.{name}",
            "requested": f"source.{name}" in candidate.requested_parameters(),
            "consumed": f"source.{name}" in consumed,
            "target_stems": list(targets),
            "target_changed": target_changed,
            "direction_ok": direction_ok,
            "non_target_max_relative_change": relative_non_target,
            "non_target_bounded": relative_non_target <= non_target_limit,
            "triplet": {
                "minus": minus_candidate.parameter("source", name),
                "baseline": candidate.parameter("source", name),
                "plus": plus_candidate.parameter("source", name),
            },
        })
    unused = sorted(row["parameter_id"] for row in rows if not row["consumed"])
    passed = all(row["requested"] and row["consumed"] and row["target_changed"] and row["direction_ok"] and row["non_target_bounded"] for row in rows)
    return {
        "schema_version": "s12-stage-u-parameter-reachability-v1",
        "status": "PARAMETER_REACHABILITY_PASS" if passed else "PARAMETER_NOT_REACHABLE",
        "vehicle_id": candidate.vehicle_id,
        "candidate_id": candidate.candidate_id,
        "unused": unused,
        "non_target_limit": non_target_limit,
        "parameters": rows,
    }


__all__ = ["StageUReachabilityError", "build_stage_u_candidate", "dashboard_values_to_source", "probe_candidate_reachability"]
