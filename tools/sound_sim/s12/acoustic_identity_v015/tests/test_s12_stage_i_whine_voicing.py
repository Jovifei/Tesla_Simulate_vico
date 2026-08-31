from __future__ import annotations

import importlib

import numpy as np
import pytest


_PARAMETERS = {
    "blower_gain_scale": 1.26,
    "blower_boost_mix": 1.28,
    "lobe_family_mix": 1.28,
    "upper_family_tilt_db": -7.0,
    "sideband_depth": 0.20,
    "phase_ripple_depth": 0.009,
    "order_cluster_spread_ratio": 0.022,
    "intake_voicing_mix": 0.28,
    "boost_attack_s": 0.11,
    "boost_release_s": 0.33,
    "bypass_release_gain": 0.19,
    "bypass_pitch_fall_ratio": 0.68,
    "bypass_decay_s": 0.28,
}


def _source_module():
    return importlib.import_module(
        "tools.sound_sim.s12.acoustic_identity_v015.sources.supercharger_whine_v3"
    )


def _signals(duration_s: float = 1.2, sample_rate_hz: int = 48000):
    count = int(duration_s * sample_rate_hz)
    time_s = np.arange(count, dtype=np.float64) / sample_rate_hz
    split = int(0.65 * count)
    rpm = np.linspace(1600.0, 5200.0, count)
    load = np.full(count, 0.88)
    throttle = np.full(count, 0.92)
    throttle[split:] = 0.0
    engine_phase = np.cumsum(rpm) / (60.0 * sample_rate_hz)
    return rpm, load, throttle, engine_phase


def test_stage_i_whine_v3_has_exact_audible_stem_sum_and_fixed_orders() -> None:
    module = _source_module()
    render = module.render_supercharger_whine_v3(*_signals(), 48000, {})
    audible = (
        "blower_shaft",
        "blower_lobe_family",
        "blower_upper_family",
        "blower_sidebands",
        "blower_bypass_release",
        "blower_intake_voicing",
    )
    assert set(audible) <= set(render.stems)
    expected = sum(
        (render.stems[name] for name in audible),
        np.zeros_like(render.stems["blower"]),
    )
    np.testing.assert_allclose(render.stems["blower"], expected, rtol=0.0, atol=1e-12)
    np.testing.assert_array_equal(render.pressure, render.stems["blower"])
    assert tuple(render.diagnostics["order_families"]) == (2.36, 11.8, 23.6)
    assert render.diagnostics["pipeline_position"] == "before_pre_ptr_equalization"
    assert render.diagnostics["transfer_modes"]["provenance"] == "C/synthetic"


def test_stage_i_whine_v3_zero_probe_is_strictly_silent() -> None:
    module = _source_module()
    rpm, load, throttle, phase = _signals()
    render = module.render_supercharger_whine_v3(
        rpm, np.zeros_like(load), np.zeros_like(throttle), phase, 48000, {}
    )
    assert np.count_nonzero(render.stems["blower"]) == 0
    assert np.count_nonzero(render.stems["blower_bypass_release"]) == 0


def test_stage_i_whine_v3_bypass_needs_boost_history_and_throttle_close() -> None:
    module = _source_module()
    rpm, load, throttle, phase = _signals()
    closed = module.render_supercharger_whine_v3(rpm, load, throttle, phase, 48000, {})
    open_throttle = np.full_like(throttle, 0.92)
    bypass_overrides = {
        "bypass_release_gain": _PARAMETERS["bypass_release_gain"],
        "bypass_pitch_fall_ratio": _PARAMETERS["bypass_pitch_fall_ratio"],
        "bypass_decay_s": _PARAMETERS["bypass_decay_s"],
    }
    opened = module.render_supercharger_whine_v3(
        rpm, load, open_throttle, phase, 48000, bypass_overrides
    )
    assert np.sum(np.square(closed.stems["blower_bypass_release"])) > 0.0
    assert np.count_nonzero(opened.stems["blower_bypass_release"]) == 0
    opened_usage = opened.diagnostics["candidate_parameter_usage"]
    assert set(opened_usage["inactive"]) >= {
        "bypass_release_gain",
        "bypass_pitch_fall_ratio",
        "bypass_decay_s",
    }
    assert set(opened_usage["active"]).isdisjoint(opened_usage["inactive"])


@pytest.mark.parametrize("name,changed", tuple(_PARAMETERS.items()))
def test_every_stage_i_source_parameter_changes_the_render(
    name: str, changed: float
) -> None:
    module = _source_module()
    inputs = _signals()
    baseline = module.render_supercharger_whine_v3(*inputs, 48000, {})
    perturbed = module.render_supercharger_whine_v3(
        *inputs, 48000, {name: changed}
    )
    assert not np.array_equal(baseline.stems["blower"], perturbed.stems["blower"]), name
    usage = perturbed.diagnostics["candidate_parameter_usage"]
    assert usage["requested"] == [name]
    assert usage["read"] == [name]
    assert usage["consumed"] == [name]
    assert usage["active"] == [name]
    assert usage["inactive"] == []
    assert usage["unused"] == []


def test_stage_i_whine_v3_rejects_unknown_override() -> None:
    module = _source_module()
    with pytest.raises(ValueError, match="unknown supercharger override"):
        module.render_supercharger_whine_v3(*_signals(), 48000, {"unknown": 1.0})
