"""Stage-L L4 Hellcat-only load/shift transient contracts."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import SourceRender, VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.acoustic_layers.shift_dynamics import detect_shift_events
from tools.sound_sim.s12.acoustic_identity_v015.render_drive_cycle_v10 import build_drive_cycle_trace
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.candidate_profiles import load_stage_l_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.hellcat_transient_dynamics import (
    apply_hellcat_transient_dynamics,
)


_SR = 8_000
_ROOT = Path(__file__).resolve().parents[1]
_CANDIDATE = load_stage_l_candidate(
    _ROOT / "targets" / "stage_l_candidates" / "Hellcat_candidate_v8.json"
)
_HEMI = (
    "hemi_exhaust_left", "hemi_exhaust_right", "hemi_blowdown_body",
    "hemi_structure_shock", "hemi_mechanical_torque_ripple",
)
_SC = ("sc_intake_radiated", "sc_casing_radiated", "sc_bypass_release")


def _trace(*, shifts: bool = True, lift: bool = False) -> VehicleStateTrace:
    duration_s = 4.0
    time_s = np.arange(int(duration_s * 1000) + 1, dtype=np.float64) / 1000.0
    rpm = 2_000.0 + 700.0 * time_s
    if shifts:
        for center in (1.0, 2.0, 3.0):
            distance = np.abs(time_s - center)
            rpm -= np.where(distance < 0.060, 650.0 * (1.0 - distance / 0.060), 0.0)
    load = np.full(time_s.size, 0.88)
    throttle = np.full(time_s.size, 0.92)
    if lift:
        rpm = np.linspace(4_800.0, 1_600.0, time_s.size)
        load = np.linspace(0.70, 0.05, time_s.size)
        throttle = np.linspace(0.75, 0.03, time_s.size)
    return VehicleStateTrace(
        time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)
    ).validate()


def _render(trace: VehicleStateTrace) -> SourceRender:
    count = int(round((trace.time_s[-1] - trace.time_s[0]) * _SR)) + 1
    time_s = np.arange(count, dtype=np.float64) / _SR
    base = np.column_stack((
        0.12 * np.sin(2.0 * np.pi * 96.0 * time_s),
        0.11 * np.sin(2.0 * np.pi * 96.0 * time_s + 0.1),
    ))
    stems = {
        "hemi_exhaust_left": 0.42 * base,
        "hemi_exhaust_right": 0.38 * base,
        "hemi_blowdown_body": 0.20 * base,
        "hemi_structure_shock": 0.06 * base,
        "hemi_mechanical_torque_ripple": 0.04 * base,
        "sc_intake_radiated": 0.14 * base,
        "sc_casing_radiated": 0.05 * base,
        "sc_bypass_release": np.zeros_like(base),
        "afterfire": np.zeros_like(base),
    }
    contributors = list(_HEMI + _SC + ("afterfire",))
    pressure = sum((stems[name] for name in contributors), np.zeros_like(base))
    return SourceRender(
        pressure,
        stems,
        {"pressure_stem_contract": {"contributors": contributors, "diagnostic_aggregates": []}},
    ).validate()


def test_three_sustained_throttle_shifts_use_distinct_exhaust_and_sc_inertia() -> None:
    trace = _trace()
    before = _render(trace)
    result = apply_hellcat_transient_dynamics(before, trace, _CANDIDATE, _SR)
    assert result.diagnostics["hellcat_shift_event_count"] == 3
    assert result.diagnostics["generic_shift_dynamics_called"] is False
    assert result.diagnostics["fixed_70hz_recovery_used"] is False
    assert np.any(result.stems["hellcat_shift_torque_cut"])
    assert np.any(result.stems["hellcat_shift_reengagement"])
    assert np.any(result.stems["hellcat_sc_drive_transient"])
    assert not np.any(result.stems["sc_bypass_release"])
    assert result.diagnostics["shift_min_sc_gain_measured"] > result.diagnostics["shift_min_exhaust_gain_measured"]
    contributors = result.diagnostics["pressure_stem_contract"]["contributors"]
    expected = sum((result.stems[name] for name in contributors), np.zeros_like(result.pressure))
    np.testing.assert_allclose(result.pressure, expected, atol=1e-12, rtol=0.0)


def test_no_shift_and_monotonic_lift_do_not_create_shift_or_bypass_events() -> None:
    for trace in (_trace(shifts=False), _trace(shifts=False, lift=True)):
        before = _render(trace)
        result = apply_hellcat_transient_dynamics(before, trace, _CANDIDATE, _SR)
        assert result.diagnostics["hellcat_shift_event_count"] == 0
        for name in (
            "hellcat_shift_torque_cut", "hellcat_shift_reengagement",
            "hellcat_sc_drive_transient", "hellcat_tip_in_blowdown",
        ):
            assert not np.any(result.stems[name])


def test_transient_pressure_delta_is_not_double_counted() -> None:
    trace = _trace()
    before = _render(trace)
    result = apply_hellcat_transient_dynamics(before, trace, _CANDIDATE, _SR)
    primitive_delta = sum(
        (result.stems[name] - before.stems[name] for name in _HEMI + _SC),
        np.zeros_like(before.pressure),
    )
    additive = sum(
        (result.stems[name] for name in (
            "hellcat_shift_reengagement", "hellcat_sc_drive_transient", "hellcat_tip_in_blowdown",
        )),
        np.zeros_like(before.pressure),
    )
    np.testing.assert_allclose(result.pressure - before.pressure, primitive_delta + additive, atol=1e-12, rtol=0.0)
    assert "hellcat_shift_torque_cut" not in result.diagnostics["pressure_stem_contract"]["contributors"]


def test_transient_rebuilds_all_diagnostic_aggregates_from_current_primitives() -> None:
    trace = _trace()
    before = _render(trace)
    # Production aggregates intentionally contain stale pre-L4 values.
    before.stems.update({
        "exhaust": np.full_like(before.pressure, 99.0),
        "hemi_exhaust": np.full_like(before.pressure, 99.0),
        "hemi_combustion_and_blowdown": np.full_like(before.pressure, 99.0),
        "supercharger_intake": np.full_like(before.pressure, 99.0),
        "blower": np.full_like(before.pressure, 99.0),
    })
    result = apply_hellcat_transient_dynamics(before, trace, _CANDIDATE, _SR)
    np.testing.assert_allclose(result.stems["exhaust"], result.stems["hemi_exhaust_left"] + result.stems["hemi_exhaust_right"], atol=0, rtol=0)
    np.testing.assert_allclose(result.stems["hemi_exhaust"], result.stems["exhaust"], atol=0, rtol=0)
    np.testing.assert_allclose(result.stems["hemi_combustion_and_blowdown"], sum((result.stems[n] for n in _HEMI), np.zeros_like(result.pressure)), atol=1e-12, rtol=0)
    np.testing.assert_allclose(result.stems["supercharger_intake"], sum((result.stems[n] for n in _SC), np.zeros_like(result.pressure)), atol=1e-12, rtol=0)
    np.testing.assert_allclose(result.stems["blower"], result.stems["supercharger_intake"], atol=0, rtol=0)


def test_canonical_60_second_cycle_detects_exactly_three_shifts() -> None:
    trace = build_drive_cycle_trace("hellcat", duration_s=60.0)
    events = detect_shift_events(trace, 48_000)
    assert len(events) == 3
    assert all(trace.throttle[np.searchsorted(trace.time_s, event.time_s)] > 0.30 for event in events)


def test_shift_envelopes_meet_dip_settling_and_overshoot_gates() -> None:
    result = apply_hellcat_transient_dynamics(_render(_trace()), _trace(), _CANDIDATE, _SR)
    assert 2.0 <= result.diagnostics["shift_dip_db_measured"] <= 5.0
    assert 0.10 <= result.diagnostics["shift_settling_s_measured"] <= 0.30
    assert result.diagnostics["shift_overshoot_db_measured"] <= 1.5
    assert result.diagnostics["shift_min_sc_gain_measured"] > result.diagnostics["shift_min_exhaust_gain_measured"]
    rows = result.diagnostics["shift_event_measurements"]
    assert len(rows) == 3
    assert all(2.0 <= row["dip_db"] <= 5.0 for row in rows)
    assert all(0.10 <= row["settling_s"] <= 0.30 for row in rows)
    assert all(row["overshoot_db"] <= 1.5 for row in rows)
    assert all(row["before_window"][1] <= row["event_sample"] <= row["after_window"][0] for row in rows)
    assert all(len(row["measurement_sha256"]) == 64 for row in rows)


def test_no_fixed_70hz_recovery_component_is_synthesized() -> None:
    trace = _trace()
    result = apply_hellcat_transient_dynamics(_render(trace), trace, _CANDIDATE, _SR)
    reengagement = np.mean(result.stems["hellcat_shift_reengagement"], axis=1)
    spectrum = np.abs(np.fft.rfft(reengagement * np.hanning(reengagement.size)))
    frequencies = np.fft.rfftfreq(reengagement.size, 1.0 / _SR)
    bin70 = int(np.argmin(np.abs(frequencies - 70.0)))
    band = (frequencies >= 50.0) & (frequencies <= 140.0)
    # The re-engagement inherits the source; 70 Hz is not an injected dominant oscillator.
    assert spectrum[bin70] < np.max(spectrum[band])
    assert "shift_recovery_boom" not in result.stems


@pytest.mark.parametrize("parameter", (
    "shift_interruption_s", "shift_min_exhaust_gain", "shift_min_sc_gain",
    "reengagement_decay_s", "sc_drive_modulation_depth", "tip_in_blowdown_gain",
))
def test_each_l4_parameter_is_read_and_has_measured_or_trace_conditional_activity(parameter: str) -> None:
    trace = _trace()
    result = apply_hellcat_transient_dynamics(_render(trace), trace, _CANDIDATE, _SR)
    usage = result.diagnostics["candidate_parameter_usage"]
    full_name = f"shift_and_load_transient.{parameter}"
    assert full_name in usage["read"]
    assert full_name in usage["active"] or full_name in usage["inactive"]
    assert full_name not in usage["unused"]


@pytest.mark.parametrize("parameter,target", (
    ("shift_interruption_s", "hellcat_shift_torque_cut"),
    ("shift_min_exhaust_gain", "hellcat_shift_torque_cut"),
    ("shift_min_sc_gain", "sc_intake_radiated"),
    ("reengagement_decay_s", "hellcat_shift_reengagement"),
    ("sc_drive_modulation_depth", "hellcat_sc_drive_transient"),
))
def test_single_parameter_perturbation_changes_real_target(parameter: str, target: str) -> None:
    trace = _trace()
    baseline = apply_hellcat_transient_dynamics(_render(trace), trace, _CANDIDATE, _SR)
    record = _CANDIDATE.payload["shift_and_load_transient"][parameter]
    value = float(record["range"][1]) if float(record["value"]) != float(record["range"][1]) else float(record["range"][0])
    perturbed = _CANDIDATE.with_parameter("shift_and_load_transient", parameter, value)
    changed = apply_hellcat_transient_dynamics(_render(trace), trace, perturbed, _SR)
    assert not np.array_equal(baseline.stems[target], changed.stems[target])


def test_tip_in_parameter_is_active_only_on_a_real_tip_in_trace() -> None:
    trace = _trace(shifts=False)
    throttle = trace.throttle.copy()
    throttle[: throttle.size // 3] = 0.10
    throttle[throttle.size // 3 :] = 0.92
    tip = VehicleStateTrace(trace.time_s, trace.rpm, trace.load, throttle, trace.acceleration_mps2).validate()
    baseline = apply_hellcat_transient_dynamics(_render(tip), tip, _CANDIDATE, _SR)
    changed = apply_hellcat_transient_dynamics(
        _render(tip), tip, _CANDIDATE.with_parameter("shift_and_load_transient", "tip_in_blowdown_gain", 0.18), _SR,
    )
    assert np.any(baseline.stems["hellcat_tip_in_blowdown"])
    assert not np.array_equal(baseline.stems["hellcat_tip_in_blowdown"], changed.stems["hellcat_tip_in_blowdown"])
    assert "shift_and_load_transient.tip_in_blowdown_gain" in baseline.diagnostics["candidate_parameter_usage"]["active"]
    np.testing.assert_array_equal(baseline.stems["sc_bypass_release"], _render(tip).stems["sc_bypass_release"])
