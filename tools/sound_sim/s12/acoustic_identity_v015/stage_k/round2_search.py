"""Bounded, fail-closed coordinate search for the three-car Round-2 pass."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .round2_propagation import ROUND2_PARAMETER_GRIDS, ROUND2_VEHICLES


ROUND2_PROBES = (
    "shift_whine_balance_10s",
    "sustained_high_load_10s",
    "lift_afterfire_10s",
)
REQUIRED_FULL_GATES = (
    "idle_bytes",
    "low_band",
    "high_band",
    "spectral_distance",
    "clock_coherence",
    "ridge_continuity",
    "state_availability",
    "pressure_accounting",
    "pcm_health",
    "isolation",
)
MAX_FULL_SNAPSHOTS = 9


def rank_round2_snapshots(
    snapshots: Sequence[Mapping[str, object]],
    vehicle_id: str,
) -> list[Mapping[str, object]]:
    """Return only measured, complete-gate snapshots in deterministic order."""

    if vehicle_id not in ROUND2_VEHICLES:
        raise ValueError(f"unsupported Round-2 vehicle_id: {vehicle_id!r}")
    accepted: list[Mapping[str, object]] = []
    for snapshot in snapshots:
        if not isinstance(snapshot, Mapping):
            continue
        metrics = snapshot.get("metrics")
        parameters = snapshot.get("parameters")
        candidate_id = snapshot.get("candidate_id")
        probes = snapshot.get("probe_results")
        if not isinstance(metrics, Mapping) or not isinstance(parameters, Mapping) or not isinstance(candidate_id, str) or not candidate_id:
            continue
        if not isinstance(probes, Mapping) or set(probes) != set(ROUND2_PROBES):
            continue
        gates = metrics.get("hard_gates")
        if not isinstance(gates, Mapping) or set(gates) != set(REQUIRED_FULL_GATES):
            continue
        if any(type(value) is not bool for value in gates.values()) or not all(gates.values()):
            continue
        if any(not isinstance(value, Mapping) or value.get("measured") is not True for value in probes.values()):
            continue
        accepted.append(snapshot)

    def sort_key(snapshot: Mapping[str, object]) -> tuple[float, float, float, float, str, str]:
        metrics = snapshot["metrics"]
        parameters = snapshot["parameters"]
        assert isinstance(metrics, Mapping) and isinstance(parameters, Mapping)
        return (
            _finite_number(metrics.get("user_feedback_error"), math.inf),
            _finite_number(metrics.get("reference_distance"), math.inf),
            _finite_number(metrics.get("relative_v2_delta"), math.inf),
            _finite_number(metrics.get("relative_seed_delta"), math.inf),
            _canonical(parameters),
            str(snapshot["candidate_id"]),
        )

    return sorted(accepted, key=sort_key)


def run_round2_coordinate_search(
    vehicle_id: str,
    seed_parameters: Mapping[str, float],
    evaluate_probe: Callable[[dict[str, float]], Mapping[str, object]],
) -> dict[str, object]:
    """Run low/seed/high probes sequentially, retaining compact records only."""

    if vehicle_id not in ROUND2_VEHICLES:
        raise ValueError(f"unsupported Round-2 vehicle_id: {vehicle_id!r}")
    grid = ROUND2_PARAMETER_GRIDS[vehicle_id]
    if set(seed_parameters) != set(grid):
        raise ValueError("Round-2 seed parameter keys mismatch")
    current = {name: _grid_value(value, grid[name]) for name, value in seed_parameters.items()}
    snapshots: list[Mapping[str, object]] = []
    step_results: list[dict[str, object]] = []
    for parameter_name, bounds in grid.items():
        trials: list[Mapping[str, object]] = []
        for label, value in zip(("low", "seed", "high"), bounds):
            parameters = dict(current)
            parameters[parameter_name] = float(value)
            record = evaluate_probe(parameters)
            if not isinstance(record, Mapping):
                raise ValueError("Round-2 probe evaluator must return a mapping")
            if "parameters" not in record:
                record = {**record, "parameters": parameters}
            trials.append(record)
            snapshots.append(record)
        ranked = rank_round2_snapshots(trials, vehicle_id)
        winner = ranked[0] if ranked else trials[1]
        winner_parameters = winner.get("parameters")
        if not isinstance(winner_parameters, Mapping):
            raise ValueError("Round-2 winner is missing parameters")
        current = {name: float(value) for name, value in winner_parameters.items()}
        step_results.append(
            {
                "parameter": parameter_name,
                "winner_id": str(winner.get("candidate_id", "")),
                "hard_gates_pass": bool(ranked),
                "trial_ids": [str(trial.get("candidate_id", "")) for trial in trials],
            }
        )
    ranked_all = rank_round2_snapshots(snapshots, vehicle_id)
    return {
        "vehicle_id": vehicle_id,
        "probe_names": list(ROUND2_PROBES),
        "parameter_order": list(grid),
        "snapshots": snapshots,
        "step_results": step_results,
        "best_snapshot": ranked_all[0] if ranked_all else snapshots[-1],
        "qualified_snapshot_count": min(len(ranked_all), MAX_FULL_SNAPSHOTS),
        "status": "QUALIFIED_PROBE_POOL" if ranked_all else "BEST_DIAGNOSTIC_ONLY",
    }


def _grid_value(value: object, bounds: tuple[float, float, float]) -> float:
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < bounds[0] or numeric > bounds[2]:
        raise ValueError("Round-2 seed parameter is outside its bounded grid")
    return numeric


def _finite_number(value: object, default: float) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        return float(value)
    return default


def _canonical(value: object) -> str:
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Round-2 parameters must be deterministic JSON") from exc


__all__ = (
    "MAX_FULL_SNAPSHOTS",
    "REQUIRED_FULL_GATES",
    "ROUND2_PROBES",
    "rank_round2_snapshots",
    "run_round2_coordinate_search",
)
