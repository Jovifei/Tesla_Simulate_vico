"""Deterministic bounded-search contract for the Stage-L Round-2 probes."""

from __future__ import annotations

from copy import deepcopy
import importlib
import math
from typing import Any


def _search_module() -> Any:
    return importlib.import_module(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_l.round2_search"
    )


def _seed_profile(module: Any) -> dict[str, object]:
    profile: dict[str, object] = {}
    for path, (_, seed, _) in module.ROUND2_PARAMETER_GRID:
        section, name = path.split(".", 1)
        profile.setdefault(section, {})[name] = seed
    profile["candidate_id"] = "hellcat_stage_l_v9"
    profile["locked"] = {"shared": "unchanged"}
    return profile


def _passing_gates(module: Any) -> dict[str, bool]:
    return {name: True for name in module.REQUIRED_FULL_GATES}


def test_round2_search_declares_three_ordered_ten_second_probes_and_exact_13_axis_grid() -> None:
    search = _search_module()

    assert search.ROUND2_PROBES == (
        {"probe_id": "shift_whine_balance", "duration_s": 10.0},
        {"probe_id": "sustained_high_load", "duration_s": 10.0},
        {"probe_id": "lift_afterfire", "duration_s": 10.0},
    )
    assert search.ROUND2_PARAMETER_GRID == (
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


def test_round2_coordinate_search_promotes_winner_pools_every_short_pass_and_keeps_seed_immutable() -> None:
    search = _search_module()
    seed = _seed_profile(search)
    original = deepcopy(seed)
    calls: list[tuple[str, str]] = []

    def evaluate(profile: dict[str, object], probe: dict[str, object]) -> dict[str, object]:
        calls.append((str(profile["candidate_id"]), str(probe["probe_id"])))
        normalized_error = 0.0
        for path, (low, _, high) in search.ROUND2_PARAMETER_GRID:
            section, name = path.split(".", 1)
            value = float(profile[section][name])
            normalized_error += (high - value) / (high - low)
        return {
            "full_gates": _passing_gates(search),
            "feedback_error": normalized_error,
            "frozen_reference_distance": normalized_error + 0.25,
            "source_render_residency_max": 1,
        }

    result = search.run_round2_coordinate_search(seed, evaluate)

    assert seed == original
    assert result["seed_profile_mutated"] is False
    assert result["candidate_file_update_performed"] is False
    assert result["parameter_count"] == 13
    assert result["evaluated_candidate_count"] == 39
    assert len(calls) == 39 * 3
    assert [probe_id for _, probe_id in calls[:3]] == [
        "shift_whine_balance", "sustained_high_load", "lift_afterfire"
    ]
    assert len(result["short_pass_pool"]) == 39
    assert 1 <= len(result["full_render_shortlist"]) <= 9
    assert result["full_render_residency_evidence"] == {
        "contract": "one SourceRender resident at a time",
        "observed_max": 1,
        "passes": True,
    }
    winner = result["current_winner_profile"]
    for path, (_, _, high) in search.ROUND2_PARAMETER_GRID:
        section, name = path.split(".", 1)
        assert winner[section][name] == high
    assert result["status"] == search.DIAGNOSTIC_STATUS
    assert result["qualification_upgrade_performed"] is False


def test_round2_ranking_is_hard_gates_then_feedback_reference_delta_and_candidate_id() -> None:
    search = _search_module()
    seed = _seed_profile(search)
    gates = _passing_gates(search)

    def row(candidate_id: str, *, passes: bool = True, feedback: float = 1.0,
            reference: float = 1.0, delta: float = 1.0) -> dict[str, object]:
        row_gates = dict(gates)
        if not passes:
            row_gates[search.REQUIRED_FULL_GATES[0]] = False
        return {
            "candidate_id": candidate_id,
            "profile_snapshot": deepcopy(seed),
            "hard_gates": row_gates,
            "hard_gates_pass": passes,
            "feedback_error": feedback,
            "frozen_reference_distance": reference,
            "shared_v9_parameter_delta": delta,
        }

    rows = [
        row("z-failing", passes=False, feedback=0.0, reference=0.0, delta=0.0),
        row("z-feedback", feedback=2.0, reference=0.0, delta=0.0),
        row("z-reference", feedback=1.0, reference=2.0, delta=0.0),
        row("z-delta", feedback=1.0, reference=1.0, delta=2.0),
        row("b-lexical", feedback=1.0, reference=1.0, delta=1.0),
        row("a-lexical", feedback=1.0, reference=1.0, delta=1.0),
    ]

    ranked = search.rank_round2_snapshots(reversed(rows))

    assert [item["candidate_id"] for item in ranked] == [
        "a-lexical", "b-lexical", "z-delta", "z-reference", "z-feedback", "z-failing"
    ]


def test_round2_ranking_fail_closes_a_self_asserted_pass_with_missing_gate() -> None:
    search = _search_module()
    complete = _passing_gates(search)
    incomplete = dict(complete)
    incomplete.pop("afterfire")
    rows = [
        {
            "candidate_id": "self-asserted",
            "hard_gates": incomplete,
            "hard_gates_pass": True,
            "feedback_error": 0.0,
            "frozen_reference_distance": 0.0,
            "shared_v9_parameter_delta": 0.0,
        },
        {
            "candidate_id": "measured-complete",
            "hard_gates": complete,
            "hard_gates_pass": True,
            "feedback_error": 1.0,
            "frozen_reference_distance": 1.0,
            "shared_v9_parameter_delta": 1.0,
        },
    ]

    ranked = search.rank_round2_snapshots(rows)

    assert [item["candidate_id"] for item in ranked] == [
        "measured-complete", "self-asserted"
    ]


def test_round2_search_fail_closes_all_full_gates_and_emits_only_best_diagnostic_v9() -> None:
    search = _search_module()
    seed = _seed_profile(search)
    required = set(search.REQUIRED_FULL_GATES)
    call_index = 0

    def evaluate(profile: dict[str, object], probe: dict[str, object]) -> dict[str, object]:
        nonlocal call_index
        call_index += 1
        gates = _passing_gates(search)
        missing_gate = search.REQUIRED_FULL_GATES[(call_index - 1) % len(search.REQUIRED_FULL_GATES)]
        gates.pop(missing_gate)
        return {
            "full_gates": gates,
            "feedback_error": math.nan if call_index == 1 else float(call_index),
            "frozen_reference_distance": float(call_index),
            "source_render_residency_max": 2 if call_index == 2 else 1,
        }

    result = search.run_round2_coordinate_search(seed, evaluate)

    assert result["short_pass_pool"] == []
    assert result["full_render_shortlist"] == []
    assert result["best_diagnostic_v9"] is not None
    assert result["selected_candidate_id"] is None
    assert result["status"] == search.DIAGNOSTIC_STATUS
    assert "PASS" not in result["status"]
    assert result["qualification_upgrade_performed"] is False
    assert result["candidate_file_update_performed"] is False
    assert result["full_render_residency_evidence"]["passes"] is False
    evaluated = result["evaluated"]
    assert evaluated
    assert all(set(item["hard_gates"]) == required | {"one_render_residency"} for item in evaluated)
    assert all(item["hard_gates_pass"] is False for item in evaluated)
