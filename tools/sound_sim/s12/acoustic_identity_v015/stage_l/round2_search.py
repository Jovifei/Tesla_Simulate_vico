"""Deterministic bounded coordinate search for Stage-L Round-2 diagnostics.

The search owns no renderer and writes no candidate file.  A caller supplies a
short-probe evaluator; each candidate snapshot is passed through the three
fixed ten-second probes in order and released before the next call.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
import math


DIAGNOSTIC_STATUS = "PARTIAL / AUTOMATED_GATE_FAIL / UNQUALIFIED_DIAGNOSTIC_ONLY"
MAX_FULL_RENDER_CANDIDATES = 9

ROUND2_PROBES = (
    {"probe_id": "shift_whine_balance", "duration_s": 10.0},
    {"probe_id": "sustained_high_load", "duration_s": 10.0},
    {"probe_id": "lift_afterfire", "duration_s": 10.0},
)

ROUND2_PARAMETER_GRID = (
    ("supercharger_intake.combustion_ripple_to_aero_depth", (0.04, 0.09, 0.16)),
    ("supercharger_intake.high_load_whine_knee", (0.20, 0.30, 0.40)),
    ("supercharger_intake.high_load_whine_post_knee_slope", (0.45, 0.65, 0.85)),
    ("combustion_and_blowdown.acceleration_blowdown_body_gain", (1.00, 1.35, 1.60)),
    ("combustion_and_blowdown.low_frequency_blowdown_gain", (1.20, 1.28, 1.35)),
    ("combustion_and_blowdown.structure_shock_mix", (0.10, 0.13, 0.16)),
    ("combustion_and_blowdown.torque_ripple_modulation_depth", (0.11, 0.14, 0.17)),
    ("afterfire.minimum_rpm", (2800.0, 3300.0, 4200.0)),
    ("afterfire.residual_energy_gain", (0.55, 0.85, 1.25)),
    ("afterfire.event_energy_threshold", (0.20, 0.35, 0.50)),
    ("afterfire.body_mix", (0.55, 0.68, 0.80)),
    ("afterfire.bright_mix", (0.10, 0.20, 0.30)),
    ("afterfire.decay_90_10_s", (0.025, 0.045, 0.070)),
)

REQUIRED_FULL_GATES = (
    "full_mix_crest",
    "low_band",
    "mid_band",
    "roughness",
    "afterfire",
)


def run_round2_coordinate_search(
    seed_profile: Mapping[str, object],
    evaluate_probe: Callable[[dict[str, object], dict[str, object]], Mapping[str, object]],
) -> dict[str, object]:
    """Run low/seed/high coordinate probes and return an unqualified shortlist."""

    if not isinstance(seed_profile, Mapping):
        raise TypeError("seed_profile must be a mapping")
    if not callable(evaluate_probe):
        raise TypeError("evaluate_probe must be callable")

    original_seed = deepcopy(dict(seed_profile))
    _validate_seed_profile(original_seed)
    current_winner = deepcopy(original_seed)
    evaluated: list[dict[str, object]] = []
    short_pass_pool: list[dict[str, object]] = []
    observed_residency_max = 0

    for coordinate_index, (parameter_path, values) in enumerate(ROUND2_PARAMETER_GRID, start=1):
        coordinate_records: list[dict[str, object]] = []
        for choice_index, (choice_name, value) in enumerate(
            zip(("low", "seed", "high"), values, strict=True)
        ):
            candidate_id = f"round2-{coordinate_index:02d}-{choice_index}-{choice_name}"
            snapshot = deepcopy(current_winner)
            _set_parameter(snapshot, parameter_path, value)
            snapshot["candidate_id"] = candidate_id
            record = _evaluate_snapshot(
                candidate_id,
                snapshot,
                original_seed,
                evaluate_probe,
            )
            coordinate_records.append(record)
            evaluated.append(record)
            observed_residency_max = max(
                observed_residency_max,
                int(record["source_render_residency_max"]),
            )
            if record["hard_gates_pass"] is True:
                short_pass_pool.append(deepcopy(record))

        promoted = rank_round2_snapshots(coordinate_records)[0]
        current_winner = deepcopy(promoted["profile_snapshot"])

    ranked_pool = rank_round2_snapshots(short_pass_pool)
    full_render_shortlist = deepcopy(ranked_pool[:MAX_FULL_RENDER_CANDIDATES])
    ranked_all = rank_round2_snapshots(evaluated)
    best_diagnostic = None
    if not ranked_pool and ranked_all:
        best_diagnostic = {
            "artifact_id": "best_diagnostic_v9",
            **deepcopy(ranked_all[0]),
        }

    return {
        "schema_version": "s12-stage-l-round2-search-1",
        "status": DIAGNOSTIC_STATUS,
        "probe_sequence": deepcopy(ROUND2_PROBES),
        "parameter_count": len(ROUND2_PARAMETER_GRID),
        "evaluated_candidate_count": len(evaluated),
        "evaluated": deepcopy(evaluated),
        "short_pass_pool": deepcopy(ranked_pool),
        "full_render_shortlist": full_render_shortlist,
        "max_full_render_candidates": MAX_FULL_RENDER_CANDIDATES,
        "best_diagnostic_v9": best_diagnostic,
        "selected_candidate_id": None,
        "current_winner_profile": deepcopy(current_winner),
        "seed_profile_mutated": dict(seed_profile) != original_seed,
        "candidate_file_update_performed": False,
        "qualification_upgrade_performed": False,
        "full_render_residency_evidence": {
            "contract": "one SourceRender resident at a time",
            "observed_max": observed_residency_max,
            "passes": observed_residency_max <= 1,
        },
    }


def rank_round2_snapshots(
    snapshots: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Rank snapshots by the frozen Round-2 ordering contract."""

    copied: list[dict[str, object]] = []
    for snapshot in snapshots:
        if not isinstance(snapshot, Mapping):
            raise TypeError("each Round-2 snapshot must be a mapping")
        copied.append(deepcopy(dict(snapshot)))
    return sorted(copied, key=_rank_key)


def _evaluate_snapshot(
    candidate_id: str,
    snapshot: dict[str, object],
    seed_profile: Mapping[str, object],
    evaluate_probe: Callable[[dict[str, object], dict[str, object]], Mapping[str, object]],
) -> dict[str, object]:
    probe_evidence: list[dict[str, object]] = []
    errors: list[str] = []
    for probe in ROUND2_PROBES:
        try:
            raw = evaluate_probe(deepcopy(snapshot), deepcopy(probe))
        except Exception as exc:  # A failed render is failed evidence, never a pass.
            raw = {}
            errors.append(f"{probe['probe_id']}: {type(exc).__name__}: {exc}")
        probe_evidence.append(_normalize_probe_evidence(raw, probe))

    hard_gates = {
        gate: all(bool(item["full_gates"][gate]) for item in probe_evidence)
        for gate in REQUIRED_FULL_GATES
    }
    residency_max = max(int(item["source_render_residency_max"]) for item in probe_evidence)
    hard_gates["one_render_residency"] = residency_max <= 1
    feedback_error = _mean_or_none(item["feedback_error"] for item in probe_evidence)
    reference_distance = _mean_or_none(
        item["frozen_reference_distance"] for item in probe_evidence
    )
    return {
        "candidate_id": candidate_id,
        "profile_snapshot": deepcopy(snapshot),
        "probe_evidence": probe_evidence,
        "evaluation_errors": errors,
        "hard_gates": hard_gates,
        "hard_gates_pass": all(hard_gates.values()),
        "feedback_error": feedback_error,
        "frozen_reference_distance": reference_distance,
        "shared_v9_parameter_delta": _parameter_delta(snapshot, seed_profile),
        "source_render_residency_max": residency_max,
    }


def _normalize_probe_evidence(
    value: object,
    probe: Mapping[str, object],
) -> dict[str, object]:
    evidence = value if isinstance(value, Mapping) else {}
    supplied_gates = evidence.get("full_gates")
    exact_gate_schema = (
        isinstance(supplied_gates, Mapping)
        and set(supplied_gates) == set(REQUIRED_FULL_GATES)
        and all(type(supplied_gates[name]) is bool for name in REQUIRED_FULL_GATES)
    )
    full_gates = {
        name: bool(exact_gate_schema and supplied_gates[name] is True)
        for name in REQUIRED_FULL_GATES
    }
    residency = evidence.get("source_render_residency_max")
    if isinstance(residency, bool) or not isinstance(residency, int) or residency < 0:
        residency = 2
    return {
        "probe_id": probe["probe_id"],
        "duration_s": probe["duration_s"],
        "full_gates": full_gates,
        "feedback_error": _finite_or_none(evidence.get("feedback_error")),
        "frozen_reference_distance": _finite_or_none(
            evidence.get("frozen_reference_distance")
        ),
        "source_render_residency_max": residency,
    }


def _validate_seed_profile(profile: Mapping[str, object]) -> None:
    for parameter_path, _ in ROUND2_PARAMETER_GRID:
        section, name = parameter_path.split(".", 1)
        section_value = profile.get(section)
        if not isinstance(section_value, Mapping) or name not in section_value:
            raise ValueError(f"seed_profile is missing {parameter_path}")
        if _finite_or_none(section_value[name]) is None:
            raise ValueError(f"seed_profile parameter {parameter_path} must be finite")


def _set_parameter(profile: dict[str, object], parameter_path: str, value: float) -> None:
    section, name = parameter_path.split(".", 1)
    section_value = profile.get(section)
    if not isinstance(section_value, dict):
        raise ValueError(f"profile section {section!r} must be a mutable mapping copy")
    section_value[name] = value


def _parameter_delta(
    profile: Mapping[str, object],
    seed_profile: Mapping[str, object],
) -> float:
    total = 0.0
    for parameter_path, (low, _, high) in ROUND2_PARAMETER_GRID:
        section, name = parameter_path.split(".", 1)
        value = float(profile[section][name])
        seed = float(seed_profile[section][name])
        total += abs(value - seed) / (high - low)
    return total


def _rank_key(snapshot: Mapping[str, object]) -> tuple[int, float, float, float, str]:
    hard_pass = _measured_hard_gates_pass(snapshot)
    return (
        0 if hard_pass else 1,
        _rank_number(snapshot.get("feedback_error")),
        _rank_number(snapshot.get("frozen_reference_distance")),
        _rank_number(snapshot.get("shared_v9_parameter_delta")),
        str(snapshot.get("candidate_id", "")),
    )


def _measured_hard_gates_pass(snapshot: Mapping[str, object]) -> bool:
    gates = snapshot.get("hard_gates")
    if snapshot.get("hard_gates_pass") is not True or not isinstance(gates, Mapping):
        return False
    required = set(REQUIRED_FULL_GATES)
    if set(gates) not in (required, required | {"one_render_residency"}):
        return False
    return all(type(value) is bool and value is True for value in gates.values())


def _rank_number(value: object) -> float:
    finite = _finite_or_none(value)
    return finite if finite is not None else math.inf


def _finite_or_none(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number >= 0.0 else None


def _mean_or_none(values: Iterable[object]) -> float | None:
    finite = [_finite_or_none(value) for value in values]
    if not finite or any(value is None for value in finite):
        return None
    return float(sum(value for value in finite if value is not None) / len(finite))


__all__ = (
    "DIAGNOSTIC_STATUS",
    "MAX_FULL_RENDER_CANDIDATES",
    "REQUIRED_FULL_GATES",
    "ROUND2_PARAMETER_GRID",
    "ROUND2_PROBES",
    "rank_round2_snapshots",
    "run_round2_coordinate_search",
)
