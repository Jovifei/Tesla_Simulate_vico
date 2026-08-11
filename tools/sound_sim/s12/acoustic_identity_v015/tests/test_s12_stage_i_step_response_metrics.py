from __future__ import annotations

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.stage_i.perceptual_metrics import (
    measure_bypass_decay,
    measure_step_response,
)


def _linear_transition(
    sample_rate_hz: int,
    duration_s: float,
    start_s: float,
    transition_s: float,
    start_value: float,
    end_value: float,
) -> np.ndarray:
    count = int(round(duration_s * sample_rate_hz))
    values = np.full(count, start_value, dtype=np.float64)
    start = int(round(start_s * sample_rate_hz))
    stop = start + int(round(transition_s * sample_rate_hz))
    values[start:stop] = np.linspace(start_value, end_value, max(stop - start, 1), endpoint=False)
    values[stop:] = end_value
    return values


def test_step_response_measures_actual_ten_to_ninety_times() -> None:
    sample_rate_hz = 1000
    command = np.zeros(1400, dtype=np.float64)
    command[200:700] = 1.0
    response = _linear_transition(sample_rate_hz, 1.4, 0.20, 0.10, 0.0, 1.0)
    falling = _linear_transition(sample_rate_hz, 1.4, 0.70, 0.30, 1.0, 0.0)
    response[700:] = falling[700:]

    metrics = measure_step_response(response, command, sample_rate_hz)

    assert abs(metrics["boost_attack_10_90_s"] - 0.080) <= 0.003
    assert abs(metrics["boost_release_90_10_s"] - 0.240) <= 0.003


def test_bypass_decay_requires_a_real_event_and_measures_ninety_to_ten() -> None:
    sample_rate_hz = 1000
    gate = np.zeros(900, dtype=np.float64)
    gate[200:] = 1.0
    bypass = np.zeros_like(gate)
    bypass[200:400] = np.linspace(1.0, 0.0, 200, endpoint=False)

    metrics = measure_bypass_decay(bypass, gate, sample_rate_hz)
    absent = measure_bypass_decay(np.zeros_like(bypass), gate, sample_rate_hz)

    assert metrics["bypass_event_count"] == 1
    assert abs(metrics["bypass_decay_90_10_s"] - 0.160) <= 0.003
    assert absent == {"bypass_event_count": 0, "bypass_decay_90_10_s": 0.0}


def test_step_response_rejects_mismatched_or_nonfinite_inputs() -> None:
    with np.testing.assert_raises(ValueError):
        measure_step_response(np.ones(5), np.ones(4), 1000)
    with np.testing.assert_raises(ValueError):
        measure_step_response(np.asarray([0.0, np.nan]), np.ones(2), 1000)


def test_step_response_without_command_events_returns_zero_durations() -> None:
    assert measure_step_response(np.zeros(32), np.zeros(32), 1000) == {
        "boost_attack_10_90_s": 0.0,
        "boost_release_90_10_s": 0.0,
    }
