"""Fail-closed per-vehicle Stage-M attribution."""
from __future__ import annotations

from collections.abc import Mapping


VEHICLE_SOURCE_LABELS = {
    "ferrari_458": "round2_remaining_sources.py Ferrari 458 source/trace",
    "hellcat": "independent Stage-L Hellcat v9 diagnostic package",
    "rx7_fd": "round2_remaining_sources.py RX-7 FD source/trace",
    "supra_jza80": "round2_remaining_sources.py Supra JZA80 source/trace",
    "aventador_lp700": "round2_remaining_sources.py Aventador LP700 source/trace",
    "c63_w204": "round2_propagation.py C63 bark/body source/trace",
    "gtr_r35": "round2_propagation.py GT-R twin-turbo/V6 source/trace",
    "lfa": "round2_propagation.py LFA ASG/V10 source/trace",
}


def attribute_vehicle_failure(vehicle_id: str, comparison: Mapping[str, object] | None, *, scenario: str) -> dict[str, object]:
    """Return a complete record without fabricating an unavailable reference target."""

    if vehicle_id not in VEHICLE_SOURCE_LABELS:
        raise ValueError(f"unknown vehicle: {vehicle_id}")
    comparison = comparison or {}
    spectral = comparison.get("spectral", {}) if isinstance(comparison, Mapping) else {}
    uncertainty = comparison.get("uncertainty", {}) if isinstance(comparison, Mapping) else {}
    external_missing = not comparison or bool(uncertainty.get("external_reference_missing", True))
    categories = ["C", "D", "G", "K"]
    if vehicle_id in {"c63_w204", "gtr_r35"}:
        categories.insert(0, "B")
    if vehicle_id == "lfa":
        categories.append("I")
    if vehicle_id == "hellcat":
        categories.append("J")
    internal_delta = spectral.get("log_distance") if isinstance(spectral, Mapping) else None
    return {
        "vehicle_id": vehicle_id,
        "scenario": scenario,
        "target": None,
        "parent_actual": {"kind": "synthetic_parent_internal_baseline", "value": 0.0 if internal_delta is not None else None},
        "candidate_actual": {"kind": "synthetic_candidate_internal_delta", "value": internal_delta},
        "parent_error": None,
        "candidate_error": None,
        "improvement": None,
        "hard_gate": False,
        "failure_category": categories,
        "evidence": {
            "source": VEHICLE_SOURCE_LABELS[vehicle_id],
            "comparison_kind": comparison.get("comparison_kind", "no_formal_pcm_pair"),
            "external_reference_missing": external_missing,
            "internal_log_spectral_distance": internal_delta,
            "not_a_real_reference_deterioration_claim": True,
        },
        "parameter_reachability": {"reachable": False, "reason": "no legally usable, scenario/RPM-bound external target"},
        "recommended_action": "do not auto-tune against R2; obtain legally usable, state/RPM-bound reference or Jovi named feedback",
        "uncertainty": "external_reference_unavailable; no target/error/improvement asserted",
    }
