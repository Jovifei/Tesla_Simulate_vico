"""Small deterministic bounded search for Stage-K diagnostic candidates."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import json
import math
from typing import Any


MAX_CANDIDATES = 64


def select_stage_k_candidate(
    candidates: Sequence[Mapping[str, object]],
    parent_metrics: Mapping[str, object] | None = None,
    vehicle_id: str | None = None,
) -> Mapping[str, object]:
    """Select one candidate using fixed gates and stable tie-breaks.

    Candidates are records containing ``candidate_id``, ``parameters`` and
    ``metrics``.  Records failing a supplied hard gate or a state-regression
    limit are discarded before vehicle metric error, parameter distance and
    canonical JSON order are compared.  Reference-distance is deliberately
    not recomputed here; a caller may include its result in ``metrics`` as an
    additional hard gate.
    """

    if len(candidates) > MAX_CANDIDATES:
        raise ValueError(f"Stage-K bounded search accepts at most {MAX_CANDIDATES} candidates")
    if not candidates:
        raise ValueError("Stage-K search requires at least one candidate")
    parent = parent_metrics or {}
    seen: set[str] = set()
    accepted: list[Mapping[str, object]] = []
    for candidate in candidates:
        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ValueError("each candidate requires a non-empty candidate_id")
        if candidate_id in seen:
            raise ValueError(f"duplicate candidate_id {candidate_id!r}")
        seen.add(candidate_id)
        parameters = candidate.get("parameters")
        metrics = candidate.get("metrics")
        if not isinstance(parameters, Mapping) or not isinstance(metrics, Mapping):
            raise ValueError(f"candidate {candidate_id!r} requires parameters and metrics mappings")
        gates = _candidate_gates(metrics, vehicle_id)
        if not all(gates.values()):
            continue
        if not _state_regression_ok(metrics, parent):
            continue
        accepted.append(candidate)
    if not accepted:
        raise ValueError("no Stage-K candidates pass hard gates")

    def rank(candidate: Mapping[str, object]) -> tuple[float, float, float, str, str]:
        metrics = candidate["metrics"]
        parameters = candidate["parameters"]
        assert isinstance(metrics, Mapping)
        assert isinstance(parameters, Mapping)
        vehicle_error = _vehicle_error(metrics, vehicle_id)
        delta = _parameter_delta(parameters, parent.get("parameters", {}))
        return (
            vehicle_error,
            delta,
            _state_regression_score(metrics),
            _canonical(parameters),
            str(candidate["candidate_id"]),
        )

    return min(accepted, key=rank)


def bounded_stage_k_search(
    parameter_candidates: Sequence[Mapping[str, object]],
    evaluate: Callable[[Mapping[str, object]], Mapping[str, object]],
    parent_metrics: Mapping[str, object] | None = None,
    vehicle_id: str | None = None,
    *,
    max_candidates: int = MAX_CANDIDATES,
) -> Mapping[str, object]:
    """Evaluate a bounded parameter sequence one render/record at a time.

    The callback is invoked in input order and its returned record is retained
    only as the compact metrics/parameter mapping needed by selection.  The
    function never stores a ``SourceRender`` and therefore cannot accumulate
    full-length audio renders during a search.
    """

    if len(parameter_candidates) > max_candidates or max_candidates > MAX_CANDIDATES:
        raise ValueError(f"Stage-K bounded search accepts at most {MAX_CANDIDATES} candidates")
    records: list[Mapping[str, object]] = []
    for parameters in parameter_candidates:
        record = evaluate(parameters)
        if not isinstance(record, Mapping):
            raise ValueError("candidate evaluator must return a mapping")
        records.append(record)
    return select_stage_k_candidate(records, parent_metrics, vehicle_id)


def candidate_rank_key(
    candidate: Mapping[str, object],
    parent_metrics: Mapping[str, object] | None = None,
    vehicle_id: str | None = None,
) -> tuple[float, float, float, str, str]:
    """Expose the stable ordering key for reports and reproducibility tests."""

    metrics = candidate.get("metrics", {})
    parameters = candidate.get("parameters", {})
    if not isinstance(metrics, Mapping) or not isinstance(parameters, Mapping):
        raise ValueError("candidate requires metrics and parameters mappings")
    return (
        _vehicle_error(metrics, vehicle_id),
        _parameter_delta(parameters, (parent_metrics or {}).get("parameters", {})),
        _state_regression_score(metrics),
        _canonical(parameters),
        str(candidate.get("candidate_id", "")),
    )


def _candidate_gates(metrics: Mapping[str, object], vehicle_id: str | None) -> dict[str, bool]:
    supplied = metrics.get("hard_gates")
    if supplied is not None and not isinstance(supplied, Mapping):
        return {"hard_gates": False}
    gates = {str(name): value is True for name, value in supplied.items()} if isinstance(supplied, Mapping) else {}
    if not gates:
        # A record without explicit gates is not evidence of a passing gate.
        return {"hard_gates": False}
    gates["all_pass"] = all(gates.values())
    # Vehicle-specific guardrails remain explicit if metrics provide them.
    if vehicle_id == "hellcat":
        gates["hellcat_correlation"] = _number(metrics.get("blower_load_correlation", metrics.get("vehicle_metrics", {}).get("blower_load_correlation") if isinstance(metrics.get("vehicle_metrics"), Mapping) else None), 0.0) >= 0.82
    return gates


def _state_regression_ok(metrics: Mapping[str, object], parent: Mapping[str, object]) -> bool:
    regression = metrics.get("state_regression")
    if regression is None:
        return True
    if not isinstance(regression, Mapping):
        return False
    return all(abs(_number(value, 100.0)) <= 0.10 for value in regression.values())


def _state_regression_score(metrics: Mapping[str, object]) -> float:
    regression = metrics.get("state_regression")
    if not isinstance(regression, Mapping):
        return 0.0
    return float(sum(abs(_number(value, 100.0)) for value in regression.values()))


def _vehicle_error(metrics: Mapping[str, object], vehicle_id: str | None) -> float:
    value = metrics.get("vehicle_error")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        return abs(float(value))
    nested = metrics.get("vehicle_metrics")
    if isinstance(nested, Mapping):
        value = nested.get("vehicle_error")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
            return abs(float(value))
    # No target error is an unknown metric, not an accidental advantage.
    return float("inf")


def _parameter_delta(parameters: Mapping[str, object], parent: object) -> float:
    baseline = parent if isinstance(parent, Mapping) else {}
    keys = set(parameters) | set(baseline)
    total = 0.0
    for key in keys:
        current = parameters.get(key)
        previous = baseline.get(key)
        if isinstance(current, Mapping) and "value" in current:
            current = current["value"]
        if isinstance(previous, Mapping) and "value" in previous:
            previous = previous["value"]
        total += abs(_number(current, 0.0) - _number(previous, 0.0))
    return total


def _canonical(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("candidate parameters must be deterministic JSON values") from exc


def _number(value: object, default: float) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        return float(value)
    return float(default)


__all__ = (
    "MAX_CANDIDATES",
    "bounded_stage_k_search",
    "candidate_rank_key",
    "select_stage_k_candidate",
    "select_stage_k_candidates",
)

select_stage_k_candidates = select_stage_k_candidate
