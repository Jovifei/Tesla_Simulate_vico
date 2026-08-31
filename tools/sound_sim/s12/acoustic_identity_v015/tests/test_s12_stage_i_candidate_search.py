from __future__ import annotations

import copy

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_i.candidate_search import (
    evaluate_stage_i_hard_gates,
    select_stage_i_candidates,
)


def _baseline() -> dict[str, float | int | bool]:
    return {
        "blower_to_exhaust_ratio_idle_db": -24.0,
        "blower_to_exhaust_ratio_acceleration_db": -10.0,
        "blower_to_exhaust_ratio_full_pull_db": -8.0,
        "single_ridge_concentration": 0.50,
        "upper_band_share_4_12khz": 0.006,
        "upper_band_short_time_peak": 0.008,
        "low_frequency_share_40_200hz": 0.40,
        "rumble_energy": 10.0,
        "whole_cycle_lufs": -16.0,
    }


def _metrics(*, accel_delta: float, upper_peak: float, sideband: float, ridge: float = 0.38) -> dict[str, float | int | bool]:
    baseline = _baseline()
    return {
        "shaft_order_error": 0.004,
        "lobe_order_error": 0.006,
        "blower_load_correlation": 0.91,
        "blower_to_exhaust_ratio_idle_db": -23.8,
        "blower_to_exhaust_ratio_acceleration_db": float(baseline["blower_to_exhaust_ratio_acceleration_db"]) + accel_delta,
        "blower_to_exhaust_ratio_full_pull_db": -5.5,
        "sideband_to_main_ratio": sideband,
        "order_cluster_width_ratio": 0.014,
        "single_ridge_concentration": ridge,
        "upper_band_share_4_12khz": 0.008,
        "upper_band_short_time_peak": upper_peak,
        "boost_attack_10_90_s": 0.080,
        "boost_release_90_10_s": 0.240,
        "bypass_decay_90_10_s": 0.160,
        "bypass_event_count": 1,
        "low_frequency_share_40_200hz": 0.405,
        "rumble_energy": 9.8,
        "whole_cycle_lufs": -15.8,
        "peak_dbfs": -1.7,
        "clipping_count": 0,
        "sample_rate_hz": 48000,
        "channels": 2,
        "pcm_bits": 24,
        "finite": True,
        "track_p_guard_pass": True,
        "regression_isolation_pass": True,
    }


def _candidate(candidate_id: str, accel_delta: float, upper_peak: float, sideband: float) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "parameters": {"gain": accel_delta, "sideband": sideband, "upper": upper_peak},
        "metrics": _metrics(accel_delta=accel_delta, upper_peak=upper_peak, sideband=sideband),
    }


def test_hard_gates_fail_closed_and_report_the_failed_gate() -> None:
    metrics = _metrics(accel_delta=3.0, upper_peak=0.007, sideband=0.14)
    passed = evaluate_stage_i_hard_gates(metrics, _baseline())
    assert passed["all_pass"] is True

    bad = copy.deepcopy(metrics)
    bad["blower_load_correlation"] = 0.70
    failed = evaluate_stage_i_hard_gates(bad, _baseline())
    assert failed["all_pass"] is False
    assert failed["blower_load_correlation"] is False

    missing = copy.deepcopy(metrics)
    del missing["shaft_order_error"]
    with pytest.raises(ValueError, match="shaft_order_error"):
        evaluate_stage_i_hard_gates(missing, _baseline())


@pytest.mark.parametrize("field", ["finite", "track_p_guard_pass", "regression_isolation_pass"])
@pytest.mark.parametrize("invalid", [-1, 0, 1, 0.5])
def test_boolean_evidence_requires_exact_true_bool(field: str, invalid: object) -> None:
    metrics = _metrics(accel_delta=3.0, upper_peak=0.007, sideband=0.14)
    metrics[field] = invalid
    with pytest.raises(ValueError, match=field):
        evaluate_stage_i_hard_gates(metrics, _baseline())

    metrics[field] = False
    gates = evaluate_stage_i_hard_gates(metrics, _baseline())
    assert gates["all_pass"] is False


def test_search_selects_three_distinct_stable_orientations() -> None:
    candidates = [
        _candidate("balanced", 3.0, 0.0074, 0.13),
        _candidate("forward", 3.9, 0.0078, 0.12),
        _candidate("soft", 2.2, 0.0055, 0.18),
        _candidate("alternate", 2.8, 0.0068, 0.15),
    ]

    first = select_stage_i_candidates(candidates, _baseline())
    second = select_stage_i_candidates(list(reversed(candidates)), _baseline())

    assert first == second
    assert set(first) == {"I6-A Balanced", "I6-B Whine Forward", "I6-C Softer Mechanical"}
    assert first["I6-A Balanced"]["candidate_id"] == "balanced"
    assert first["I6-B Whine Forward"]["candidate_id"] == "forward"
    assert first["I6-C Softer Mechanical"]["candidate_id"] == "soft"
    assert len({entry["candidate_id"] for entry in first.values()}) == 3


def test_search_rejects_more_than_36_candidates_or_too_few_passing() -> None:
    with pytest.raises(ValueError, match="36"):
        select_stage_i_candidates([_candidate(f"c{index}", 3.0, 0.007, 0.13) for index in range(37)], _baseline())
    with pytest.raises(ValueError, match="three"):
        select_stage_i_candidates([_candidate("only", 3.0, 0.007, 0.13)], _baseline())
