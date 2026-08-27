"""Versioned synthetic block-boundary click acceptance contract."""

from __future__ import annotations

from typing import Any, Mapping


DEFAULT_CLICK_GATE: dict[str, Any] = {
    "contract_version": "s12.stage_w.click_gate.v1",
    "threshold": 0.35,
    "definition": "block_boundary_only",
    "scope": "synthetic_stage_w_source_and_post_ptr_outputs",
    "provenance": "bounded_synthetic_engineering_acceptance_threshold",
}


def click_gate_contract(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    supplied = dict(config.get("click_gate", {})) if isinstance(config, Mapping) and isinstance(config.get("click_gate"), Mapping) else {}
    result = dict(DEFAULT_CLICK_GATE)
    result.update(supplied)
    result["threshold"] = float(result["threshold"])
    if result["threshold"] <= 0.0:
        raise ValueError("click gate threshold must be positive")
    return result


__all__ = ["DEFAULT_CLICK_GATE", "click_gate_contract"]
