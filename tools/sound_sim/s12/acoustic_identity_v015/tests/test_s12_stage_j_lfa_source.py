"""RED contracts for the independent Stage J Lexus LFA v2 source."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np
import pytest


S12_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(S12_ROOT))

from acoustic_identity_v015.contracts import SourceRender, VehicleStateTrace  # noqa: E402


_SAMPLE_RATE_HZ = 8000
_REQUIRED_STEMS = {"exhaust", "order_family", "intake", "mechanical", "metallic"}


def _renderer():
    try:
        module = importlib.import_module(
            "acoustic_identity_v015.sources.lexus_high_rev_v10_source_v2"
        )
    except ModuleNotFoundError as error:
        pytest.fail(f"Stage J LFA v2 source is missing: {error}")
    return module.render_lfa_v2


def _trace(
    *,
    duration_s: float = 1.1,
    rpm: tuple[float, ...] = (3600.0, 7600.0),
    load: tuple[float, ...] = (0.42, 0.94),
    throttle: tuple[float, ...] = (0.48, 0.98),
) -> VehicleStateTrace:
    count = int(round(duration_s * _SAMPLE_RATE_HZ)) + 1
    time_s = np.arange(count, dtype=np.float64) / _SAMPLE_RATE_HZ
    anchors = np.linspace(0.0, duration_s, len(rpm))
    rpm_values = np.interp(time_s, anchors, rpm)
    load_values = np.interp(time_s, anchors, load)
    throttle_values = np.interp(time_s, anchors, throttle)
    return VehicleStateTrace(
        time_s,
        rpm_values,
        load_values,
        throttle_values,
        np.gradient(rpm_values / 60.0, time_s),
    ).validate()


def _energy(stereo: np.ndarray) -> float:
    return float(np.sum(np.square(stereo)))


def test_v2_lfa_render_has_event_driven_v10_stems_and_reconciled_pressure() -> None:
    render = _renderer()(_trace(), sample_rate_hz=_SAMPLE_RATE_HZ)

    assert isinstance(render, SourceRender)
    render.validate()
    assert _REQUIRED_STEMS <= set(render.stems)
    np.testing.assert_allclose(
        render.pressure,
        sum(render.stems.values()),
        rtol=0.0,
        atol=1e-15,
    )
    assert render.diagnostics["vehicle_id"] == "lfa"
    assert render.diagnostics["scope"] == "synthetic; uncalibrated; not OEM reproduction"
    assert render.diagnostics["firing_event_train"] == "V10 even-fire 72-degree event train"
    assert tuple(render.diagnostics["order_families"]) == (5.0, 10.0, 15.0)
    assert render.diagnostics["fixed_center_tone"] is False
    assert render.diagnostics["random_white_noise"] is False


def test_v2_lfa_orders_follow_continuous_rpm_rise() -> None:
    trace = _trace(rpm=(3000.0, 9000.0))
    render = _renderer()(trace, sample_rate_hz=_SAMPLE_RATE_HZ)

    order_frequency_hz = render.diagnostics["order_frequency_hz"]
    expected_rpm = np.interp(
        np.arange(render.pressure.shape[0], dtype=np.float64) / _SAMPLE_RATE_HZ,
        trace.time_s,
        trace.rpm,
    )
    for order in (5.0, 10.0, 15.0):
        measured = np.asarray(order_frequency_hz[str(int(order))], dtype=np.float64)
        np.testing.assert_allclose(measured, expected_rpm * order / 60.0, rtol=0.0, atol=1e-12)
        assert measured[-1] > measured[0] * 2.9
    assert _energy(render.stems["order_family"][-1000:]) > _energy(render.stems["order_family"][:1000])


def test_v2_lfa_idle_cruise_accel_full_pull_and_lift_have_distinct_time_structures() -> None:
    traces = {
        "idle": _trace(rpm=(900.0, 900.0), load=(0.14, 0.14), throttle=(0.14, 0.14)),
        "cruise": _trace(rpm=(2600.0, 2700.0), load=(0.34, 0.36), throttle=(0.31, 0.34)),
        "accel": _trace(rpm=(3000.0, 7200.0), load=(0.42, 0.90), throttle=(0.48, 0.98)),
        "full_pull": _trace(rpm=(4600.0, 9000.0), load=(0.94, 1.0), throttle=(0.98, 1.0)),
        "lift": _trace(
            rpm=(7600.0, 8000.0, 7000.0),
            load=(0.94, 0.90, 0.14),
            throttle=(0.98, 0.94, 0.03),
        ),
    }
    renders = {name: _renderer()(trace, sample_rate_hz=_SAMPLE_RATE_HZ) for name, trace in traces.items()}

    signatures = {
        name: tuple(round(_energy(render.stems[stem]), 12) for stem in sorted(_REQUIRED_STEMS))
        for name, render in renders.items()
    }
    assert len(set(signatures.values())) == len(signatures)
    assert renders["full_pull"].diagnostics["high_rpm_growth_mean"] > renders["cruise"].diagnostics["high_rpm_growth_mean"]
    assert _energy(renders["lift"].stems["metallic"][-2000:]) < _energy(renders["lift"].stems["metallic"][:2000])


@pytest.mark.parametrize(
    ("parameter", "value", "target_stem"),
    (
        ("pulse_width_scale", 1.35, "exhaust"),
        ("phase_offset_deg", 27.0, "order_family"),
        ("order_family_mix", 0.42, "order_family"),
        ("intake_resonance_scale", 1.45, "intake"),
        ("metallic_texture_scale", 1.55, "metallic"),
        ("high_rpm_growth_scale", 1.60, "order_family"),
    ),
)
def test_v2_lfa_each_override_deterministically_changes_its_target_stem_and_metric(
    parameter: str,
    value: float,
    target_stem: str,
) -> None:
    trace = _trace(rpm=(4300.0, 8900.0), load=(0.62, 0.99), throttle=(0.70, 1.0))
    renderer = _renderer()
    baseline = renderer(trace, sample_rate_hz=_SAMPLE_RATE_HZ)
    changed = renderer(trace, sample_rate_hz=_SAMPLE_RATE_HZ, overrides={parameter: value})
    repeated = renderer(trace, sample_rate_hz=_SAMPLE_RATE_HZ, overrides={parameter: value})

    assert not np.array_equal(baseline.pressure, changed.pressure)
    assert not np.array_equal(baseline.stems[target_stem], changed.stems[target_stem])
    assert baseline.diagnostics["stem_energy"][target_stem] != changed.diagnostics["stem_energy"][target_stem]
    np.testing.assert_array_equal(changed.pressure, repeated.pressure)
    np.testing.assert_array_equal(changed.stems[target_stem], repeated.stems[target_stem])
