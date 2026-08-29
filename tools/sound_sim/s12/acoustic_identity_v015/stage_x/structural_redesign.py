"""Stage X structural redesign between engineering search rounds.

When round-1 soft gates fail, analyze dimension medians, patch the base
config structure, and re-center the searchable parameter box before round 2.
"""

from __future__ import annotations

import copy
from dataclasses import replace
from typing import Any

from ..event_domain.config_schema import load_config, parameter
from .multi_reference_comparator import DIMENSIONS
from .search_parameters import SearchParameter, hellcat_search_parameters

REDESIGN_SCHEMA = "s12.stage_x.structural_redesign.v1"
KEY_DIMENSIONS = ("low_frequency_body", "120_400_pressure_attack", "mid_band_congestion", "synthetic_artifact")


def analyze_failure_dimensions(preselection_summary: dict[str, Any]) -> dict[str, Any]:
    """Pick the best round-1 architecture and list failing dimensions."""
    ranking = preselection_summary.get("architecture_ranking") or []
    preselections = preselection_summary.get("preselections") or {}
    best_arch = ranking[0] if ranking else None
    gate = preselections.get(best_arch, {}) if best_arch else {}
    medians = gate.get("dimension_median_relative_error") or {}
    failing = {
        name: float(medians[name])
        for name in DIMENSIONS
        if name in medians and name != "runtime_cost" and float(medians[name]) > 0.05
    }
    key_failures = {name: failing[name] for name in KEY_DIMENSIONS if name in failing}
    return {
        "schema": REDESIGN_SCHEMA,
        "best_architecture": best_arch,
        "best_objective": gate.get("objective"),
        "best_overrides": gate.get("best_overrides"),
        "failing_dimensions": failing,
        "key_failures": key_failures,
        "redesign_required": not bool(preselection_summary.get("selected_engineering_architecture")),
    }


def apply_structural_config_patches(base_config: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    """Config-level structural tweaks targeting round-1 failure modes."""
    config = copy.deepcopy(base_config)
    failures = set(analysis.get("key_failures", {}))
    attack = config.setdefault("attack_shaping", {})
    if "120_400_pressure_attack" in failures or "low_frequency_body" in failures:
        attack["band_120_400_mix"] = parameter(0.18, "gain", "stage x structural redesign", source="stage_x_round2", verification_state="synthetic_assumption")
    mixes = config.setdefault("timbre_mixes", {})
    if "synthetic_artifact" in failures or "mid_band_congestion" in failures:
        mixes["order_weights"] = parameter([0.75, 0.75, 1.0, 0.85], "vector", "stage x structural redesign", source="stage_x_round2", verification_state="synthetic_assumption")
        mixes["sideband_mix"] = parameter(0.82, "gain", "stage x structural redesign", source="stage_x_round2", verification_state="synthetic_assumption")
    monitor = config.setdefault("monitor_policy", {})
    monitor["attack_s"] = parameter(0.08, "s", "stage x structural redesign", source="stage_x_round2", verification_state="synthetic_assumption")
    monitor["release_s"] = parameter(0.95, "s", "stage x structural redesign", source="stage_x_round2", verification_state="synthetic_assumption")
    monitor["max_makeup_db"] = parameter(7.5, "dB", "stage x structural redesign", source="stage_x_round2", verification_state="synthetic_assumption")
    return config


def redesign_search_parameters(
    parameters: list[SearchParameter],
    best_overrides: dict[str, float] | None,
    analysis: dict[str, Any],
) -> list[SearchParameter]:
    """Re-center baselines on round-1 best and widen deltas on failing axes."""
    if not best_overrides:
        return list(parameters)
    failures = analysis.get("key_failures", {})
    redesigned: list[SearchParameter] = []
    widen = {
        "low_frequency_body": ("combustion_event_energy", "combustion_decay_time", "primary_length_spread"),
        "120_400_pressure_attack": ("attack_mix_120_400", "combustion_rise_time"),
        "mid_band_congestion": ("collector_loss", "intake_mix"),
        "synthetic_artifact": ("timbre_map_order_weights", "cycle_variation"),
    }
    widen_names = {name for dim, names in widen.items() if dim in failures for name in names}
    for item in parameters:
        baseline = float(best_overrides.get(item.name, item.baseline))
        delta = item.delta * (1.35 if item.name in widen_names else 1.0)
        redesigned.append(replace(item, baseline=baseline, delta=delta))
    return redesigned


def build_round2_plan(preselection_summary: dict[str, Any]) -> dict[str, Any]:
    """Full round-2 plan: analysis + patched config + redesigned parameters."""
    analysis = analyze_failure_dimensions(preselection_summary)
    base_config = apply_structural_config_patches(load_config("hellcat_v1"), analysis)
    parameters = redesign_search_parameters(hellcat_search_parameters(), analysis.get("best_overrides"), analysis)
    return {
        "analysis": analysis,
        "architecture": analysis["best_architecture"] or "P3",
        "base_config": base_config,
        "parameters": parameters,
        "coarse_count": 32,
        "refine_count": 16,
        "seed": 8676309,
    }


__all__ = [
    "REDESIGN_SCHEMA",
    "analyze_failure_dimensions",
    "apply_structural_config_patches",
    "build_round2_plan",
    "redesign_search_parameters",
]
