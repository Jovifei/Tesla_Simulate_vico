"""TDD contract for the Stage J synthetic GT-R R35 twin-turbo source."""

from __future__ import annotations

import importlib

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace


_OVERRIDES = {
    "pulse_width_scale": 1.38,
    "bank_phase_offset_deg": 23.0,
    "primary_spool_tau_s": 0.34,
    "secondary_spool_tau_s": 0.58,
    "boost_attack_s": 0.19,
    "boost_release_s": 0.52,
    "wastegate_gain_scale": 1.7,
    "turbo_whistle_mix": 0.28,
}

_RESPONSE_METRIC = {
    "pulse_width_scale": "exhaust_event_energy",
    "bank_phase_offset_deg": "bank_phase_correlation",
    "primary_spool_tau_s": "primary_spool_50_time_s",
    "secondary_spool_tau_s": "secondary_spool_50_time_s",
    "boost_attack_s": "boost_attack_63_time_s",
    "boost_release_s": "boost_release_37_time_s",
    "wastegate_gain_scale": "wastegate_energy",
    "turbo_whistle_mix": "turbo_primary_rms",
}


def _module():
    return importlib.import_module(
        "tools.sound_sim.s12.acoustic_identity_v015.sources.nissan_twin_turbo_v6_source_v2"
    )


def _trace(duration_s: float = 1.35, state_rate_hz: int = 500) -> VehicleStateTrace:
    count = int(duration_s * state_rate_hz) + 1
    time_s = np.arange(count, dtype=np.float64) / state_rate_hz
    lift_start = int(0.72 * count)
    rpm = np.linspace(2600.0, 6600.0, count)
    rpm[lift_start:] = np.linspace(rpm[lift_start], 4200.0, count - lift_start)
    load = np.full(count, 0.90)
    throttle = np.full(count, 0.94)
    load[lift_start:] = 0.08
    throttle[lift_start:] = 0.04
    acceleration = np.gradient(rpm / 60.0, time_s)
    return VehicleStateTrace(time_s, rpm, load, throttle, acceleration)


def _rms(signal: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(signal))))


def test_gtr_v2_is_a_synthetic_twin_turbo_v6_with_exact_pressure_stem_sum() -> None:
    render = _module().render_gtr_r35_v2(_trace())

    required = {
        "exhaust",
        "order_family",
        "turbo_primary",
        "turbo_secondary",
        "wastegate",
        "mechanical",
    }
    assert required <= set(render.stems)
    assert render.pressure.shape[1] == 2
    assert np.isfinite(render.pressure).all()
    np.testing.assert_allclose(
        render.pressure,
        sum(render.stems.values(), np.zeros_like(render.pressure)),
        rtol=0.0,
        atol=1e-12,
    )
    assert render.diagnostics["scope"] == "C/synthetic; uncalibrated; not OEM reproduction"
    assert render.diagnostics["combustion_event_model"] == "even_fire_v6_3_events_per_revolution"
    assert render.diagnostics["order_frequency_mode"] == "continuous_rpm_phase"


def test_gtr_v2_uses_twin_turbo_history_and_lift_transients() -> None:
    module = _module()
    lifted = module.render_gtr_r35_v2(_trace())
    held_trace = _trace()
    held = VehicleStateTrace(
        held_trace.time_s,
        held_trace.rpm,
        np.full_like(held_trace.load, 0.90),
        np.full_like(held_trace.throttle, 0.94),
        held_trace.acceleration_mps2,
    )
    open_throttle = module.render_gtr_r35_v2(held)

    assert lifted.diagnostics["turbo_history_model"] == "primary_secondary_spool_load_boost"
    assert lifted.diagnostics["primary_spool_peak"] > 0.0
    assert lifted.diagnostics["secondary_spool_peak"] > 0.0
    assert lifted.diagnostics["boost_peak"] > 0.0
    assert lifted.diagnostics["lift_event_count"] >= 1
    assert np.sum(np.square(lifted.stems["wastegate"])) > 0.0
    assert np.sum(np.square(open_throttle.stems["wastegate"])) == 0.0


@pytest.mark.parametrize("name,changed", tuple(_OVERRIDES.items()))
def test_every_gtr_v2_override_changes_output_and_its_deterministic_response_metric(
    name: str, changed: float
) -> None:
    module = _module()
    baseline = module.render_gtr_r35_v2(_trace())
    perturbed = module.render_gtr_r35_v2(_trace(), overrides={name: changed})

    assert not np.array_equal(baseline.pressure, perturbed.pressure), name
    metric = _RESPONSE_METRIC[name]
    assert baseline.diagnostics["response_metrics"][metric] != perturbed.diagnostics["response_metrics"][metric], name
    usage = perturbed.diagnostics["override_usage"]
    assert usage == {"requested": [name], "read": [name], "consumed": [name]}


def test_gtr_v2_rejects_unknown_or_nonpositive_time_constant_overrides() -> None:
    module = _module()
    with pytest.raises(ValueError, match="unknown gtr v2 override"):
        module.render_gtr_r35_v2(_trace(), overrides={"whistle": 1.0})
    with pytest.raises(ValueError, match="primary_spool_tau_s must be > 0"):
        module.render_gtr_r35_v2(_trace(), overrides={"primary_spool_tau_s": 0.0})
