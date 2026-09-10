"""C1 linked output-policy contract tests."""
from __future__ import annotations

import math

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.output_guard import (
    GuardConfig,
    LINKED_SOFT_CEILING_V1,
    linked_soft_ceiling,
)


def test_reported_worst_case_is_bounded_without_hard_clip():
    parent_peak, raw_peak = 0.535647104226, 0.695661216502
    legacy = 0.94 * math.tanh(1.5 * raw_peak / parent_peak) / math.tanh(1.5)
    assert abs(legacy - 0.997141325557) < 1e-12
    output, receipt = linked_soft_ceiling(np.array([[0.2, legacy]]))
    assert abs(output[0, 1] - 0.9393829361909013) < 1e-12
    assert receipt["legacy_ceiling_input_exceedance_samples"] == 1
    assert receipt["post_guard_ceiling_exceedance_samples"] == 0
    assert receipt["emergency_clip_count"] == 0
    assert receipt["soft_guard_delta_peak"] > 0.05


def test_knee_below_and_silence_are_exactly_unchanged():
    x = np.array([[0.0, 0.0], [0.9, -0.9], [0.4, -0.7]])
    y, receipt = linked_soft_ceiling(x)
    assert np.array_equal(y, x)
    assert receipt["soft_guard_active_frames"] == 0
    assert receipt["soft_guard_min_gain"] == 1.0


def test_output_is_monotone_odd_bounded_and_never_amplified():
    x = np.linspace(-5.0, 5.0, 200001)[:, None]
    y, _ = linked_soft_ceiling(x)
    assert np.max(np.abs(y)) <= 0.94
    assert np.all(np.diff(y[:, 0]) >= -1e-15)
    assert np.all(np.abs(y) <= np.abs(x) + 1e-15)
    yn, _ = linked_soft_ceiling(-x)
    assert np.array_equal(yn, -y)


def test_stereo_link_preserves_ratio_and_channel_swap():
    x = np.array([[0.5, 1.02], [-1.03, 0.12], [0.0, 0.998]])
    y, _ = linked_soft_ceiling(x)
    assert np.allclose(y[:, 0] * x[:, 1], y[:, 1] * x[:, 0], rtol=0, atol=1e-15)
    swapped, _ = linked_soft_ceiling(x[:, ::-1])
    assert np.array_equal(swapped, y[:, ::-1])


def test_knee_is_continuous_through_second_derivative():
    eps = 1e-5
    x = np.array([[0.90 - 2 * eps], [0.90 - eps], [0.90], [0.90 + eps], [0.90 + 2 * eps]])
    y, _ = linked_soft_ceiling(x)
    first_left = (y[2, 0] - y[1, 0]) / eps
    first_right = (y[3, 0] - y[2, 0]) / eps
    second_left = (y[2, 0] - 2 * y[1, 0] + y[0, 0]) / eps**2
    second_right = (y[4, 0] - 2 * y[3, 0] + y[2, 0]) / eps**2
    assert abs(first_left - 1.0) < 1e-6
    assert abs(first_right - 1.0) < 1e-6
    assert abs(second_left) < 1e-4
    assert abs(second_right) < 2e-2


def test_blocking_is_independent_of_chunk_size_and_extremes_stay_finite():
    x = np.random.default_rng(9).uniform(-1.04, 1.04, (1357, 2))
    full, _ = linked_soft_ceiling(x)
    chunks = [linked_soft_ceiling(part)[0] for part in np.array_split(x, 31)]
    assert np.array_equal(full, np.concatenate(chunks))
    extreme, _ = linked_soft_ceiling(np.array([[1e6, -1e6], [1e100, -1e100]]))
    assert np.all(np.isfinite(extreme))
    assert np.max(np.abs(extreme)) <= 0.94


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_input_is_rejected(bad):
    with pytest.raises(ValueError):
        linked_soft_ceiling(np.array([[bad, 0.0]]))


@pytest.mark.parametrize(
    "config",
    [GuardConfig(knee=0.94), GuardConfig(knee=-0.1), GuardConfig(ceiling=1.1), GuardConfig(knee=float("nan"))],
)
def test_invalid_config_is_rejected(config):
    with pytest.raises(ValueError):
        linked_soft_ceiling(np.zeros((2, 2)), config)


def test_c0_is_not_consumed_by_baseline_early_return(monkeypatch):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ad import engine_sim_acoustics as base
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.engine import RemediationEngine

    t = np.arange(12000, dtype=np.float64) / 48000.0
    ir = np.zeros(1200, dtype=np.float64)
    ir[0] = 0.9
    ir[1] = 0.02
    monkeypatch.setattr(base, "load_impulse_response", lambda *args, **kwargs: ir.copy())
    rpm = np.full(t.shape, 4200.0)
    throttle = np.full(t.shape, 0.8)

    engine = RemediationEngine(
        "hellcat",
        seed=17,
        variant="r1_baseline",
        output_policy=LINKED_SOFT_CEILING_V1,
    )
    engine.render_track(rpm, throttle, 0.25)
    report = engine.last_report
    receipt = report["normalization"]
    assert report["source_variant"] == "r1_baseline"
    assert report["output_policy"] == LINKED_SOFT_CEILING_V1
    assert receipt["receipt_schema"] == "s12.stage_ah.output_guard_receipt.v2"
    assert receipt["normalization_denominator"] == report["parent_pre_saturation_peak"]
    assert receipt["soft_guard_active_frames"] > 0
    assert receipt["post_guard_ceiling_exceedance_samples"] == 0
    assert receipt["emergency_clip_count"] == 0
    assert report["post_identity_clip_count"] == 0


def test_linked_policy_preserves_source_variant_no_event_controls(monkeypatch):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ad import engine_sim_acoustics as base
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.engine import RemediationEngine

    ir = np.zeros(1200, dtype=np.float64)
    ir[0] = 0.9
    monkeypatch.setattr(base, "load_impulse_response", lambda *args, **kwargs: ir.copy())
    rpm = np.linspace(2600.0, 3300.0, 12000)
    throttle = np.full(12000, 0.4)
    kwargs = dict(seed=91, output_policy=LINKED_SOFT_CEILING_V1)
    c0 = RemediationEngine("ferrari_458", variant="r1_baseline", **kwargs)
    c1 = RemediationEngine("ferrari_458", variant="body_damping", **kwargs)
    c2 = RemediationEngine("ferrari_458", variant="afterfire_pressure", **kwargs)
    c3 = RemediationEngine("ferrari_458", variant="combined", **kwargs)
    p0 = c0.render_track(rpm, throttle, 0.25)
    p1 = c1.render_track(rpm, throttle, 0.25)
    p2 = c2.render_track(rpm, throttle, 0.25)
    p3 = c3.render_track(rpm, throttle, 0.25)
    assert np.array_equal(p0, p2)
    assert np.array_equal(p1, p3)
