"""TDD tests for the LFA-specific ASG shift and lift layer."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.contracts import SourceRender, VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_k.lfa_transient_dynamics import apply_lfa_transient_dynamics


def _candidate() -> SimpleNamespace:
    values = {
        "shift_interruption_s": 0.20,
        "shift_min_gain": 0.55,
        "reengagement_decay_s": 0.12,
        "intake_reopen_gain": 0.20,
        "lift_high_order_decay_s": 0.12,
        "overrun_gain": 0.10,
    }
    return SimpleNamespace(parameter=lambda section, name, default=0.0: values.get(name, default))


def _trace(with_shift: bool = True, lift: bool = True) -> VehicleStateTrace:
    time_s = np.arange(0.0, 2.001, 0.01)
    rpm = np.full(time_s.size, 6500.0)
    throttle = np.full(time_s.size, 0.85)
    if with_shift:
        rpm[(time_s >= 0.90) & (time_s < 1.02)] = np.linspace(6500.0, 5600.0, int(np.sum((time_s >= 0.90) & (time_s < 1.02))))
        rpm[time_s >= 1.02] = 6500.0
    if lift:
        throttle[time_s >= 1.30] = 0.0
    load = np.clip(throttle * 0.95, 0.0, 1.0)
    return VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)).validate()


def _render() -> SourceRender:
    t = np.arange(96001, dtype=np.float64) / 48000.0
    exhaust = np.column_stack((0.12 * np.sin(2 * np.pi * 540 * t), 0.10 * np.sin(2 * np.pi * 540 * t + 0.2)))
    order = np.column_stack((0.05 * np.sin(2 * np.pi * 1080 * t), 0.04 * np.sin(2 * np.pi * 1080 * t)))
    intake = np.column_stack((0.03 * np.sin(2 * np.pi * 1800 * t), 0.02 * np.sin(2 * np.pi * 1800 * t)))
    metallic = np.column_stack((0.02 * np.sin(2 * np.pi * 5200 * t), 0.015 * np.sin(2 * np.pi * 5200 * t)))
    stems = {"exhaust": exhaust, "order_family": order, "intake": intake, "metallic": metallic}
    return SourceRender(sum(stems.values(), np.zeros_like(exhaust)), stems, {}).validate()


def test_monotonic_deceleration_has_no_shift_event() -> None:
    trace = _trace(with_shift=False, lift=True)
    result = apply_lfa_transient_dynamics(_render(), trace, _candidate())
    assert result.diagnostics["lfa_shift_event_count"] == 0
    assert not np.any(result.stems["lfa_shift_torque_cut"])


def test_shift_has_bounded_dip_and_no_fixed_recovery_tone() -> None:
    result = apply_lfa_transient_dynamics(_render(), _trace(with_shift=True, lift=False), _candidate())
    assert result.diagnostics["lfa_shift_event_count"] == 1
    assert 2.0 <= result.diagnostics["lfa_shift_dip_db"] <= 4.0
    assert 0.12 <= result.diagnostics["lfa_shift_settling_s"] <= 0.25
    assert result.diagnostics["lfa_shift_recovery_overshoot_db"] <= 1.0
    assert "shift_recovery_boom" not in result.stems
    assert np.sum(np.square(result.stems["lfa_shift_exhaust_reengagement"])) > 0.0


def test_lift_has_continuous_high_order_decay_and_overrun() -> None:
    result = apply_lfa_transient_dynamics(_render(), _trace(with_shift=False, lift=True), _candidate())
    assert result.diagnostics["lfa_lift_event_count"] == 1
    assert np.sum(np.square(result.stems["lfa_intake_lift_decay"])) > 0.0
    assert np.sum(np.square(result.stems["lfa_overrun"])) > 0.0
    assert result.diagnostics["lfa_afterfire_conditions"] == "delegated_high_rpm_hot_history_closed_throttle"
