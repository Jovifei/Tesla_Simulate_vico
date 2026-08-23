from __future__ import annotations

import pytest

from tools.sound_sim.s12.real_reference.long_window_analysis import (
    LongWindowError,
    choose_reference_window,
    choose_candidate_window,
)


def test_reference_window_keeps_requested_15_or_30_seconds_inside_source() -> None:
    assert choose_reference_window(120.0, 70.0, 15.0) == {"start_s": 62.5, "duration_s": 15.0, "end_s": 77.5}
    assert choose_reference_window(120.0, 70.0, 30.0) == {"start_s": 55.0, "duration_s": 30.0, "end_s": 85.0}


def test_reference_window_clamps_at_source_edges_without_padding() -> None:
    result = choose_reference_window(36.0, 17.0, 30.0)
    assert result == {"start_s": 2.0, "duration_s": 30.0, "end_s": 32.0}
    with pytest.raises(LongWindowError, match="shorter"):
        choose_reference_window(12.0, 5.0, 15.0)


@pytest.mark.parametrize(
    ("scenario", "duration", "expected_start"),
    [
        ("startup_idle_road_acceleration", 15.0, 0.0),
        ("onboard_acceleration_shift", 30.0, 8.0),
        ("launch_acceleration_shift", 15.0, 20.0),
        ("technical_sequential_turbo_demo", 30.0, 20.0),
        ("lift_afterfire_deceleration", 15.0, 34.0),
    ],
)
def test_candidate_window_maps_dynamic_scene_to_canonical_60s_cycle(scenario: str, duration: float, expected_start: float) -> None:
    assert choose_candidate_window(scenario, duration, 60.0)["start_s"] == expected_start


def test_candidate_window_rejects_duration_longer_than_cycle() -> None:
    with pytest.raises(LongWindowError, match="cycle"):
        choose_candidate_window("acceleration", 30.0, 20.0)
