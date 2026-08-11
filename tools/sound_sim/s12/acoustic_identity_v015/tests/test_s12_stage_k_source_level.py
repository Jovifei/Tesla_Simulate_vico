"""TDD contract for Stage-K source operating level balance."""

from __future__ import annotations

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import SourceRender, VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_k.source_level import (
    OperatingLevelTrim,
    apply_source_operating_trim,
)


def _trace(rpm_start: float = 1000.0, rpm_end: float = 7000.0) -> VehicleStateTrace:
    time_s = np.linspace(0.0, 1.0, 5)
    load = np.asarray([0.10, 0.20, 0.50, 0.80, 0.90], dtype=np.float64)
    throttle = np.asarray([0.10, 0.25, 0.50, 0.75, 0.95], dtype=np.float64)
    rpm = np.linspace(rpm_start, rpm_end, time_s.size)
    return VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)).validate()


def _render(count: int = 48001) -> SourceRender:
    t = np.arange(count, dtype=np.float64) / 48000.0
    body = np.column_stack((np.sin(2.0 * np.pi * 80.0 * t), np.sin(2.0 * np.pi * 80.0 * t + 0.2)))
    identity = 0.5 * body
    event = 0.25 * np.column_stack((np.sin(2.0 * np.pi * 1200.0 * t), np.sin(2.0 * np.pi * 1200.0 * t)))
    return SourceRender(body + identity + event, {"exhaust": body, "identity": identity, "shift_impact": event}, {}).validate()


def test_trim_uses_load_throttle_not_rpm() -> None:
    trim = OperatingLevelTrim(1.5, -1.5, (0.25, 0.75), 0.15)
    first = apply_source_operating_trim(_render(), _trace(1000.0, 7000.0), stem_names=("exhaust", "identity"), trim=trim)
    second = apply_source_operating_trim(_render(), _trace(3000.0, 9000.0), stem_names=("exhaust", "identity"), trim=trim)
    assert np.array_equal(first.diagnostics["operating_trim_gain_db"], second.diagnostics["operating_trim_gain_db"])


def test_low_and_high_load_have_bounded_opposite_trim() -> None:
    trim = OperatingLevelTrim(1.5, -1.5, (0.25, 0.75), 0.15)
    result = apply_source_operating_trim(_render(), _trace(), stem_names=("exhaust", "identity"), trim=trim)
    gains = np.asarray(result.diagnostics["operating_trim_gain_db"], dtype=np.float64)
    assert 1.0 <= gains[0] <= 2.0
    assert -2.0 <= gains[-1] <= -1.0
    assert np.all(np.diff(gains) <= 1e-8)


def test_event_stems_are_unchanged_and_pressure_delta_is_exact() -> None:
    trim = OperatingLevelTrim(1.5, -1.5, (0.25, 0.75), 0.15)
    source = _render()
    result = apply_source_operating_trim(source, _trace(), stem_names=("exhaust", "identity"), trim=trim)
    assert np.array_equal(result.stems["shift_impact"], source.stems["shift_impact"])
    expected_delta = (result.stems["exhaust"] - source.stems["exhaust"]) + (result.stems["identity"] - source.stems["identity"])
    assert np.allclose(result.pressure - source.pressure, expected_delta, rtol=0.0, atol=1e-14)


def test_zero_input_stays_zero_and_trim_is_finite() -> None:
    zero = SourceRender(np.zeros((48001, 2)), {"exhaust": np.zeros((48001, 2))}, {}).validate()
    trim = OperatingLevelTrim(1.5, -1.5, (0.25, 0.75), 0.15)
    result = apply_source_operating_trim(zero, _trace(), stem_names=("exhaust",), trim=trim)
    assert np.array_equal(result.pressure, zero.pressure)
    assert np.all(np.isfinite(result.pressure))


def test_event_stems_are_rejected_even_when_passed_directly() -> None:
    trim = OperatingLevelTrim(1.5, -1.5, (0.25, 0.75), 0.15)
    with pytest.raises(ValueError, match="event stem"):
        apply_source_operating_trim(_render(), _trace(), stem_names=("shift_impact",), trim=trim)
