"""TDD contract for the Stage-K synthetic GT-R parallel twin-turbo source.

The source is deliberately C-level synthetic engineering work.  These tests
protect the topology (two concurrent shaft states, shaft-phase BPF and
boost-history release) without claiming measured OEM calibration.
"""

from __future__ import annotations

import importlib

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace


def _module():
    return importlib.import_module(
        "tools.sound_sim.s12.acoustic_identity_v015.sources.nissan_parallel_twin_turbo_v6_source_v3"
    )


def _trace(duration_s: float = 1.8, state_rate_hz: int = 400) -> VehicleStateTrace:
    count = int(duration_s * state_rate_hz) + 1
    time_s = np.arange(count, dtype=np.float64) / state_rate_hz
    lift_start = int(1.15 * state_rate_hz)
    rpm = np.linspace(2400.0, 6800.0, count)
    load = np.full(count, 0.88)
    throttle = np.full(count, 0.92)
    rpm[lift_start:] = np.linspace(rpm[lift_start], 4100.0, count - lift_start)
    load[lift_start:] = 0.08
    throttle[lift_start:] = 0.035
    acceleration = np.gradient(rpm / 60.0, time_s)
    return VehicleStateTrace(time_s, rpm, load, throttle, acceleration)


def _steady_trace(duration_s: float = 1.0, rpm: float = 5200.0) -> VehicleStateTrace:
    count = int(duration_s * 400) + 1
    time_s = np.arange(count, dtype=np.float64) / 400.0
    return VehicleStateTrace(
        time_s,
        np.full(count, rpm),
        np.full(count, 0.86),
        np.full(count, 0.90),
        np.zeros(count),
    )


def _rms(value: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(value))))


def test_v3_exports_parallel_source_and_exact_pressure_stem_sum() -> None:
    render = _module().render_gtr_r35_v3(_trace())

    required = {
        "exhaust",
        "order_family",
        "turbo_primary",
        "turbo_secondary",
        "turbo_sidebands",
        "intake_duct",
        "wastegate",
        "mechanical",
    }
    assert required <= set(render.stems)
    np.testing.assert_allclose(
        render.pressure,
        sum(render.stems.values(), np.zeros_like(render.pressure)),
        rtol=0.0,
        atol=1e-12,
    )
    assert render.pressure.shape[1] == 2
    assert np.isfinite(render.pressure).all()
    assert render.diagnostics["combustion_event_model"] == "even_fire_v6_3_events_per_revolution"
    assert render.diagnostics["turbo_history_model"] == "parallel_two_shaft_state_with_boost_history"
    assert render.diagnostics["order_frequency_mode"] == "shaft_phase_bpf_not_engine_rpm_tone"


def test_both_turbo_shafts_are_active_at_the_same_load_without_secondary_gate() -> None:
    render = _module().render_gtr_r35_v3(_steady_trace())
    diagnostics = render.diagnostics

    assert diagnostics["shaft_a_state_peak"] > 0.0
    assert diagnostics["shaft_b_state_peak"] > 0.0
    assert diagnostics["shaft_a_active_fraction"] > 0.05
    assert diagnostics["shaft_b_active_fraction"] > 0.05
    assert diagnostics["secondary_rpm_gate"] is False
    assert diagnostics["shaft_detune_ratio"] > 0.0
    assert _rms(render.stems["turbo_primary"]) > 0.0
    assert _rms(render.stems["turbo_secondary"]) > 0.0


def test_bpf_is_derived_from_shaft_phase_and_tracks_two_detuned_ridges() -> None:
    render = _module().render_gtr_r35_v3(_steady_trace())
    diagnostics = render.diagnostics

    assert diagnostics["shaft_bpf_order"] > 0.0
    assert diagnostics["shaft_bpf_frequency_a_hz"] > 0.0
    assert diagnostics["shaft_bpf_frequency_b_hz"] > diagnostics["shaft_bpf_frequency_a_hz"]
    assert diagnostics["shaft_bpf_frequency_ratio"] > 1.0
    assert diagnostics["shaft_phase_integrated"] is True
    assert diagnostics["turbo_frequency_source"] == "integrated_shaft_state"


def test_boost_history_controls_bov_release_and_zero_history_is_silent() -> None:
    module = _module()
    lifted = module.render_gtr_r35_v3(_trace())
    no_history = module.render_gtr_r35_v3(
        VehicleStateTrace(
            _trace().time_s,
            _trace().rpm,
            np.zeros_like(_trace().load),
            np.zeros_like(_trace().throttle),
            _trace().acceleration_mps2,
        )
    )
    assert _rms(lifted.stems["wastegate"]) > 0.0
    assert lifted.diagnostics["bov_event_count"] >= 1
    assert np.count_nonzero(no_history.stems["wastegate"]) == 0
    assert lifted.diagnostics["bypass_requires_boost_history"] is True


@pytest.mark.parametrize(
    ("name", "changed", "metric"),
    (
        ("pulse_width_scale", 1.10, "exhaust_event_energy"),
        ("bank_phase_offset_deg", 126.0, "bank_phase_correlation"),
        ("primary_spool_tau_s", 0.21, "shaft_a_attack_63_time_s"),
        ("secondary_spool_tau_s", 0.38, "shaft_b_attack_63_time_s"),
        ("boost_attack_s", 0.13, "boost_attack_63_time_s"),
        ("boost_release_s", 0.31, "boost_release_37_time_s"),
        ("turbo_whistle_mix", 0.22, "turbo_whistle_rms"),
        ("turbo_a_inertia_s", 0.20, "shaft_a_attack_63_time_s"),
        ("turbo_b_inertia_s", 0.36, "shaft_b_attack_63_time_s"),
        ("shaft_detune_ratio", 0.022, "shaft_bpf_frequency_ratio"),
        ("shaft_bpf_order", 7.20, "shaft_bpf_frequency_a_hz"),
        ("intake_duct_mix", 0.31, "intake_duct_rms"),
        ("bov_release_gain", 0.16, "wastegate_energy"),
        ("bov_release_s", 0.29, "bov_decay_37_time_s"),
        ("wastegate_gain_scale", 1.25, "wastegate_energy"),
    ),
)
def test_each_public_override_changes_output_and_named_metric(name: str, changed: float, metric: str) -> None:
    module = _module()
    baseline = module.render_gtr_r35_v3(_trace())
    perturbed = module.render_gtr_r35_v3(_trace(), overrides={name: changed})

    assert not np.array_equal(baseline.pressure, perturbed.pressure), name
    baseline_metric = baseline.diagnostics["response_metrics"][metric]
    perturbed_metric = perturbed.diagnostics["response_metrics"][metric]
    assert baseline_metric != perturbed_metric, (name, metric)
    usage = perturbed.diagnostics["candidate_parameter_usage"]
    assert usage["requested"] == [name]
    assert usage["read"] == [name]
    assert usage["consumed"] == [name]
    assert usage["unused"] == []


def test_turbo_mix_is_an_absolute_ratio_and_unknown_or_invalid_keys_fail_closed() -> None:
    module = _module()
    baseline = module.render_gtr_r35_v3(_trace())
    assert 0.0 < baseline.diagnostics["turbo_whistle_mix"] <= 0.24
    with pytest.raises(ValueError, match="unknown gtr v3 override"):
        module.render_gtr_r35_v3(_trace(), overrides={"secondary_gate": 1.0})
    with pytest.raises(ValueError, match="turbo_whistle_mix must be in \[0, 1\]"):
        module.render_gtr_r35_v3(_trace(), overrides={"turbo_whistle_mix": 1.5})


def test_v6_order_is_preserved_and_no_fixed_engine_rpm_turbo_tone_is_reported() -> None:
    render = _module().render_gtr_r35_v3(_trace())
    metrics = render.diagnostics["response_metrics"]
    assert metrics["v6_events_per_revolution"] == 3
    assert metrics["v6_order_energy"] > 0.0
    assert metrics["half_order_leakage"] <= 0.10
    assert "engine_rpm_direct_turbo_tone" not in render.diagnostics["forbidden_models"]
