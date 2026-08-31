from __future__ import annotations

import importlib

import numpy as np
import pytest


def _module():
    return importlib.import_module(
        "tools.sound_sim.s12.acoustic_identity_v015.sources.supercharger_whine_v4"
    )


def _signals(duration_s: float = 1.6, sample_rate_hz: int = 48_000):
    count = int(duration_s * sample_rate_hz)
    time_s = np.arange(count, dtype=np.float64) / sample_rate_hz
    split = int(0.62 * count)
    rpm = np.linspace(1_200.0, 6_400.0, count)
    load = np.full(count, 0.86)
    throttle = np.full(count, 0.92)
    throttle[split:] = 0.0
    engine_phase = np.cumsum(rpm) / (60.0 * sample_rate_hz)
    return rpm, load, throttle, engine_phase


_PARAMETERS = {
    "blower_gain_scale": 1.20,
    "blower_boost_mix": 1.20,
    "upper_family_tilt_db": -7.0,
    "cluster_spread_ratio": 0.018,
    "sideband_main_ratio": 0.16,
    "intake_voicing_mix": 0.26,
    "boost_attack_10_90_s": 0.10,
    "boost_release_90_10_s": 0.30,
    "bypass_release_gain": 0.16,
    "bypass_decay_90_10_s": 0.24,
}


def test_stage_k_v4_has_named_stems_and_exact_aggregate_sum() -> None:
    module = _module()
    render = module.render_supercharger_whine_v4(*_signals(), 48_000, {})
    audible = (
        "blower_shaft",
        "blower_rotor_family",
        "blower_gear_casing",
        "blower_sidebands",
        "blower_intake_voicing",
        "blower_bypass_release",
    )
    assert set(audible) <= set(render.stems)
    expected = sum((render.stems[name] for name in audible), np.zeros_like(render.stems["blower"]))
    np.testing.assert_allclose(render.stems["blower"], expected, rtol=0.0, atol=1.0e-12)
    np.testing.assert_array_equal(render.pressure, render.stems["blower"])
    assert tuple(render.diagnostics["order_families"]) == (2.36, 11.8, 23.6)
    assert render.diagnostics["pipeline_position"] == "before_pre_ptr_equalization"


def test_stage_k_v4_is_silent_without_load_or_throttle() -> None:
    module = _module()
    rpm, load, throttle, phase = _signals()
    render = module.render_supercharger_whine_v4(
        rpm, np.zeros_like(load), np.zeros_like(throttle), phase, 48_000, {}
    )
    assert np.count_nonzero(render.stems["blower"]) == 0
    assert np.count_nonzero(render.stems["blower_bypass_release"]) == 0


def test_bypass_requires_boost_history_and_closed_throttle() -> None:
    module = _module()
    rpm, load, throttle, phase = _signals()
    closed = module.render_supercharger_whine_v4(rpm, load, throttle, phase, 48_000, {})
    open_throttle = np.full_like(throttle, 0.92)
    opened = module.render_supercharger_whine_v4(rpm, load, open_throttle, phase, 48_000, {})
    assert np.sum(np.square(closed.stems["blower_bypass_release"])) > 0.0
    assert np.count_nonzero(opened.stems["blower_bypass_release"]) == 0


def test_attack_and_release_are_measured_time_controls() -> None:
    module = _module()
    rpm, load, throttle, phase = _signals()
    fast = module.render_supercharger_whine_v4(
        rpm, load, throttle, phase, 48_000,
        {"boost_attack_10_90_s": 0.06, "boost_release_90_10_s": 0.18},
    )
    slow = module.render_supercharger_whine_v4(
        rpm, load, throttle, phase, 48_000,
        {"boost_attack_10_90_s": 0.12, "boost_release_90_10_s": 0.35},
    )
    assert fast.diagnostics["boost_attack_10_90_s"] < slow.diagnostics["boost_attack_10_90_s"]
    assert fast.diagnostics["boost_rise_time_s"] < slow.diagnostics["boost_rise_time_s"]
    assert fast.diagnostics["boost_release_90_10_s"] < slow.diagnostics["boost_release_90_10_s"]
    assert fast.diagnostics["boost_fall_time_s"] < slow.diagnostics["boost_fall_time_s"]


def test_sideband_is_direct_output_ratio_and_order_follows_rpm() -> None:
    module = _module()
    rpm, load, throttle, phase = _signals()
    render = module.render_supercharger_whine_v4(
        rpm, load, throttle, phase, 48_000, {"sideband_main_ratio": 0.14}
    )
    assert 0.08 <= render.diagnostics["sideband_main_ratio_actual"] <= 0.20
    assert render.diagnostics["sideband_multiplier"] == 1.0
    assert render.diagnostics["frequency_model"] == "rpm_integrated_order_phase"


@pytest.mark.parametrize("name, changed", tuple(_PARAMETERS.items()))
def test_every_v4_parameter_changes_audible_render(name: str, changed: float) -> None:
    module = _module()
    inputs = _signals()
    baseline = module.render_supercharger_whine_v4(*inputs, 48_000, {})
    perturbed = module.render_supercharger_whine_v4(*inputs, 48_000, {name: changed})
    assert not np.array_equal(baseline.stems["blower"], perturbed.stems["blower"]), name
    usage = perturbed.diagnostics["candidate_parameter_usage"]
    assert usage["requested"] == [name]
    assert usage["read"] == [name]
    assert usage["consumed"] == [name]
    assert usage["unused"] == []


def test_v4_rejects_unknown_override() -> None:
    module = _module()
    with pytest.raises(ValueError, match="unknown supercharger override"):
        module.render_supercharger_whine_v4(*_signals(), 48_000, {"unknown": 1.0})
