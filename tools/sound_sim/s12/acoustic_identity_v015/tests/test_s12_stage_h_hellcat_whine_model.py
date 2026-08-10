from __future__ import annotations

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.sources.supercharger_whine_v2 import render_supercharger_whine_v2


def _signals(duration_s: float = 2.0, sample_rate_hz: int = 48000):
    count = int(duration_s * sample_rate_hz)
    time_s = np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = 900.0 + 5200.0 * time_s / duration_s
    load = 0.15 + 0.80 * time_s / duration_s
    throttle = 0.15 + 0.83 * time_s / duration_s
    engine_phase = np.cumsum(rpm) / (60.0 * sample_rate_hz)
    return rpm, load, throttle, engine_phase


def test_whine_has_order_families_and_named_stems() -> None:
    rpm, load, throttle, phase = _signals()
    render = render_supercharger_whine_v2(rpm, load, throttle, phase, 48000, {})
    assert set(("blower_shaft", "blower_lobe_family", "blower_upper_family", "blower_sidebands", "blower_bypass_release", "blower")) <= set(render.stems)
    assert tuple(render.diagnostics["order_families"]) == (2.36, 11.8, 23.6)
    assert render.diagnostics["pipeline_position"] == "before_pre_ptr_equalization"


def test_bypass_release_requires_closed_throttle_and_boost_history() -> None:
    rpm, load, throttle, phase = _signals()
    open_render = render_supercharger_whine_v2(rpm, load, np.ones_like(throttle), phase, 48000, {})
    assert np.allclose(open_render.stems["blower_bypass_release"], 0.0)
    closed_throttle = throttle.copy()
    closed_throttle[int(len(closed_throttle) * 0.55) :] = 0.0
    closed_render = render_supercharger_whine_v2(rpm, load, closed_throttle, phase, 48000, {})
    assert float(np.sum(np.square(closed_render.stems["blower_bypass_release"]))) > 0.0


def test_zero_load_and_throttle_without_boost_history_is_silent() -> None:
    rpm, load, throttle, phase = _signals()
    silent = render_supercharger_whine_v2(
        rpm,
        np.zeros_like(load),
        np.zeros_like(throttle),
        phase,
        48000,
        {},
    )
    assert np.allclose(silent.stems["blower"], 0.0)
    assert np.allclose(silent.stems["blower_bypass_release"], 0.0)


def test_attack_and_release_change_time_structure_not_only_total_gain() -> None:
    rpm, load, throttle, phase = _signals()
    fast = render_supercharger_whine_v2(rpm, load, throttle, phase, 48000, {"boost_attack_s": 0.06, "boost_release_s": 0.18})
    slow = render_supercharger_whine_v2(rpm, load, throttle, phase, 48000, {"boost_attack_s": 0.10, "boost_release_s": 0.30})
    assert not np.array_equal(fast.stems["blower"], slow.stems["blower"])
    assert fast.diagnostics["boost_attack_s"] != slow.diagnostics["boost_attack_s"]
    assert fast.diagnostics["boost_rise_time_s"] < slow.diagnostics["boost_rise_time_s"]
