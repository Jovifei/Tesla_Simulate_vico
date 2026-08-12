"""One shared deterministic Hellcat crank-clock contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.crank_clock import (
    HELLCAT_BANK_PATTERN,
    HELLCAT_FIRING_ORDER,
    build_hellcat_crank_clock,
)


def _constant_trace(rpm_value: float = 1200.0, duration_s: float = 0.2, sample_rate_hz: int = 8000) -> VehicleStateTrace:
    time_s = np.arange(int(round(duration_s * sample_rate_hz)) + 1, dtype=np.float64) / sample_rate_hz
    rpm = np.full(time_s.size, rpm_value, dtype=np.float64)
    return VehicleStateTrace(time_s, rpm, np.full_like(rpm, 0.7), np.full_like(rpm, 0.8), np.zeros_like(rpm)).validate()


def test_constant_rpm_clock_has_exact_four_event_per_revolution_schedule_and_bank_partition() -> None:
    sample_rate_hz = 8000
    clock = build_hellcat_crank_clock(_constant_trace(sample_rate_hz=sample_rate_hz), sample_rate_hz)
    expected_spacing = int(sample_rate_hz * 60.0 / (1200.0 * 4.0))
    indices = np.asarray(clock.event_sample_indices, dtype=np.int64)
    assert np.all(np.diff(indices) == expected_spacing)
    assert tuple(clock.bank_labels[: len(HELLCAT_BANK_PATTERN)]) == HELLCAT_BANK_PATTERN
    assert HELLCAT_FIRING_ORDER == (1, 8, 4, 3, 6, 5, 7, 2)
    assert np.array_equal(clock.left_bank_event_gate + clock.right_bank_event_gate, clock.firing_event_gate)
    assert not np.any((clock.left_bank_event_gate > 0.0) & (clock.right_bank_event_gate > 0.0))


def test_crank_and_cycle_phase_are_continuous_bounded_and_event_aligned() -> None:
    trace = _constant_trace()
    clock = build_hellcat_crank_clock(trace, 8000)
    assert clock.engine_phase_cycles[0] == 0.0
    assert np.all(np.diff(clock.engine_phase_cycles) > 0.0)
    assert np.all((clock.cycle_phase_cycles >= 0.0) & (clock.cycle_phase_cycles < 1.0))
    assert np.array_equal(np.flatnonzero(clock.firing_event_gate), np.asarray(clock.event_sample_indices))
    assert np.all(clock.torque_ripple_envelope >= 0.0)
    assert np.all(clock.torque_ripple_envelope <= 1.0)
    assert np.all(clock.torque_ripple_envelope[np.asarray(clock.event_sample_indices)] > 0.0)


def test_clock_is_frozen_and_its_arrays_are_read_only() -> None:
    clock = build_hellcat_crank_clock(_constant_trace(), 8000)
    with pytest.raises(FrozenInstanceError):
        clock.bank_labels = ()  # type: ignore[misc]
    with pytest.raises(ValueError):
        clock.engine_phase_cycles[0] = 1.0


def test_variable_rpm_clock_is_deterministic_and_event_density_increases_continuously() -> None:
    sample_rate_hz = 8000
    time_s = np.arange(3201, dtype=np.float64) / sample_rate_hz
    rpm = np.linspace(900.0, 3600.0, time_s.size)
    trace = VehicleStateTrace(
        time_s, rpm, np.linspace(0.2, 0.9, time_s.size), np.linspace(0.3, 0.95, time_s.size), np.gradient(rpm / 60.0, time_s)
    ).validate()
    first = build_hellcat_crank_clock(trace, sample_rate_hz)
    second = build_hellcat_crank_clock(trace, sample_rate_hz)
    assert np.array_equal(first.engine_phase_cycles, second.engine_phase_cycles)
    assert first.event_sample_indices == second.event_sample_indices
    intervals = np.diff(np.asarray(first.event_sample_indices))
    assert np.median(intervals[: max(2, intervals.size // 3)]) > np.median(intervals[-max(2, intervals.size // 3) :])


@pytest.mark.parametrize("sample_rate_hz", (7999, 8000.0, True))
def test_clock_rejects_invalid_sample_rates(sample_rate_hz: object) -> None:
    with pytest.raises(ValueError, match="sample_rate_hz"):
        build_hellcat_crank_clock(_constant_trace(), sample_rate_hz)  # type: ignore[arg-type]
