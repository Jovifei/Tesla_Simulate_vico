"""Versioned synthetic block-boundary click acceptance contract."""

from __future__ import annotations

from typing import Any, Mapping
import numpy as np


DEFAULT_CLICK_GATE: dict[str, Any] = {
    "contract_version": "s12.stage_w.click_gate.v1",
    "threshold": 0.35,
    "definition": "block_boundary_only",
    "scope": "synthetic_stage_w_raw_post_ptr_monitor_outputs",
    "provenance": "bounded_synthetic_engineering_acceptance_threshold",
}


def click_gate_contract(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    supplied = dict(config.get("click_gate", {})) if isinstance(config, Mapping) and isinstance(config.get("click_gate"), Mapping) else {}
    result = dict(DEFAULT_CLICK_GATE)
    result.update(supplied)
    for key in ("contract_version", "definition", "scope", "provenance"):
        if result[key] != DEFAULT_CLICK_GATE[key]:
            raise ValueError(f"click gate {key} does not match the versioned contract")
    result["threshold"] = float(result["threshold"])
    if not np.isfinite(result["threshold"]) or result["threshold"] <= 0.0:
        raise ValueError("click gate threshold must be positive")
    return result


def block_boundary_click_metrics(audio: np.ndarray, block_size: int = 960, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    values = np.asarray(audio, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2 or values.shape[0] == 0 or block_size <= 0 or not np.all(np.isfinite(values)):
        raise ValueError("click metrics require finite nonempty stereo audio")
    starts = np.arange(0, values.shape[0], int(block_size), dtype=np.int64)
    boundary_starts = starts[1:]
    jumps = values[boundary_starts] - values[boundary_starts - 1] if boundary_starts.size else np.zeros((0, 2), dtype=np.float64)
    contract = click_gate_contract(config)
    maximum = float(np.max(np.abs(jumps))) if jumps.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(jumps))))
    return {"max_boundary_jump": maximum, "normalized_rms_boundary": rms / max(float(np.sqrt(np.mean(np.square(values)))), 1.0e-12), **contract, "passed": maximum <= contract["threshold"]}


__all__ = ["DEFAULT_CLICK_GATE", "block_boundary_click_metrics", "click_gate_contract"]
