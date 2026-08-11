"""RED-first contracts for the Stage J C63 W204 synthetic source."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from acoustic_identity_v015.contracts import VehicleStateTrace
from acoustic_identity_v015.sources.mercedes_na_v8_source_v2 import render_c63_w204_v2


_SR = 8000


def _trace(kind: str) -> VehicleStateTrace:
    time_s = np.arange(int(1.25 * _SR), dtype=np.float64) / _SR
    if kind == "idle":
        rpm = np.full(time_s.size, 850.0)
        load = np.full(time_s.size, 0.12)
        throttle = np.full(time_s.size, 0.06)
    elif kind == "accel":
        rpm = np.linspace(1800.0, 6800.0, time_s.size)
        load = np.full(time_s.size, 0.82)
        throttle = np.full(time_s.size, 0.88)
    elif kind == "lift":
        rpm = np.linspace(6200.0, 4000.0, time_s.size)
        load = np.where(time_s < 0.35, 0.82, 0.08)
        throttle = np.where(time_s < 0.35, 0.90, 0.02)
    else:
        raise ValueError(kind)
    return VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)).validate()


def _l2_delta(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.linalg.norm(left - right))


def test_c63_v2_returns_event_driven_synthetic_pre_ptr_stems() -> None:
    render = render_c63_w204_v2(_trace("accel"), _SR)

    assert render.pressure.shape == (int(1.25 * _SR), 2)
    assert {"exhaust", "exhaust_left_bank", "exhaust_right_bank", "bark", "mechanical"} <= set(render.stems)
    assert np.all(np.isfinite(render.pressure))
    assert render.diagnostics["scope"] == "synthetic; uncalibrated; not OEM reproduction"
    assert render.diagnostics["bank_timing"] == "cross_plane_v8_event_pulses"
    assert render.diagnostics["event_count"] > 20
    assert render.diagnostics["moving_order_model"] is True


def test_c63_v2_separates_idle_acceleration_and_closed_throttle_time_structure() -> None:
    idle = render_c63_w204_v2(_trace("idle"), _SR)
    accel = render_c63_w204_v2(_trace("accel"), _SR)
    lift = render_c63_w204_v2(_trace("lift"), _SR)

    def rms(render, stem: str) -> float:
        return float(np.sqrt(np.mean(np.square(render.stems[stem]))))

    assert rms(accel, "bark") > rms(idle, "bark") * 2.0
    assert rms(lift, "bark") < rms(accel, "bark")
    assert lift.diagnostics["closed_throttle_event_count"] > 0
    assert idle.diagnostics["state"] == "idle"
    assert accel.diagnostics["state"] == "acceleration"
    assert lift.diagnostics["state"] == "closed_throttle"


@pytest.mark.parametrize(
    ("override", "stem"),
    (
        ({"bank_phase_offset_deg": 14.0}, "exhaust_right_bank"),
        ({"pulse_width_scale": 1.35}, "exhaust"),
        ({"bark_resonance_scale": 1.25}, "bark"),
        ({"mechanical_texture_scale": 1.40}, "mechanical"),
        ({"high_rpm_growth_scale": 1.35}, "bark"),
    ),
)
def test_c63_v2_each_public_override_deterministically_changes_its_target_stem(override, stem: str) -> None:
    trace = _trace("accel")
    base = render_c63_w204_v2(trace, _SR)
    changed_once = render_c63_w204_v2(trace, _SR, overrides=override)
    changed_twice = render_c63_w204_v2(trace, _SR, overrides=override)

    assert _l2_delta(base.stems[stem], changed_once.stems[stem]) > 1e-8
    assert np.array_equal(changed_once.stems[stem], changed_twice.stems[stem])
    assert changed_once.diagnostics["parameter_usage"][next(iter(override))] == "active"


def test_c63_v2_rejects_unknown_or_nonfinite_overrides() -> None:
    trace = _trace("accel")
    with pytest.raises(ValueError, match="unsupported"):
        render_c63_w204_v2(trace, _SR, overrides={"global_gain": 2.0})
    with pytest.raises(ValueError, match="finite"):
        render_c63_w204_v2(trace, _SR, overrides={"pulse_width_scale": np.nan})
