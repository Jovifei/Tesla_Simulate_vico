"""Stage-K C63 source contracts.

The tests keep the M156 cross-plane event train from Stage J while making the
bark controls describe amplitude/decay rather than moving a notional
resonance.  The source is synthetic and is intentionally tested before it is
connected to the Stage-K renderer.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from acoustic_identity_v015.contracts import VehicleStateTrace
from acoustic_identity_v015.sources.mercedes_na_v8_source_v2 import render_c63_w204_v2
from acoustic_identity_v015.sources.mercedes_na_v8_source_v3 import render_c63_w204_v3


_SR = 48_000


def _trace(kind: str, duration_s: float = 1.25) -> VehicleStateTrace:
    count = int(round(duration_s * _SR)) + 1
    time_s = np.arange(count, dtype=np.float64) / _SR
    if kind == "idle":
        rpm = np.full(count, 850.0)
        load = np.full(count, 0.12)
        throttle = np.full(count, 0.06)
    elif kind == "accel":
        rpm = np.linspace(1800.0, 6800.0, count)
        load = np.full(count, 0.82)
        throttle = np.full(count, 0.88)
    elif kind == "lift":
        rpm = np.linspace(6200.0, 4000.0, count)
        load = np.where(time_s < 0.35, 0.82, 0.08)
        throttle = np.where(time_s < 0.35, 0.90, 0.02)
    else:
        raise ValueError(kind)
    acceleration = np.gradient(rpm / 60.0, time_s)
    return VehicleStateTrace(time_s, rpm, load, throttle, acceleration).validate()


def _l2(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(left) - np.asarray(right)))


def _band_rms(signal: np.ndarray, low_hz: float, high_hz: float, sample_rate_hz: int = _SR) -> float:
    mono = np.mean(np.asarray(signal, dtype=np.float64), axis=1)
    window = np.hanning(mono.size)
    spectrum = np.abs(np.fft.rfft(mono * window))
    frequencies = np.fft.rfftfreq(mono.size, 1.0 / sample_rate_hz)
    selected = (frequencies >= low_hz) & (frequencies < high_hz)
    return float(np.sqrt(np.mean(np.square(spectrum[selected]))))


def _roughness(signal: np.ndarray, sample_rate_hz: int = _SR) -> float:
    """Frame-to-frame high-band envelope movement, not broadband noise power."""
    mono = np.mean(np.asarray(signal, dtype=np.float64), axis=1)
    frame = max(256, int(round(0.020 * sample_rate_hz)))
    count = mono.size // frame
    if count < 3:
        return 0.0
    values = []
    for index in range(count):
        block = mono[index * frame : (index + 1) * frame] * np.hanning(frame)
        spectrum = np.abs(np.fft.rfft(block))
        frequencies = np.fft.rfftfreq(frame, 1.0 / sample_rate_hz)
        high = spectrum[(frequencies >= 4_000.0) & (frequencies < 12_000.0)]
        values.append(float(np.mean(high)))
    envelope = np.asarray(values)
    return float(np.mean(np.abs(np.diff(envelope, n=2))))


def test_c63_v3_is_finite_event_driven_and_rejects_old_resonance_knob() -> None:
    render = render_c63_w204_v3(_trace("accel"), _SR)

    assert render.pressure.shape == (int(1.25 * _SR) + 1, 2)
    assert {
        "exhaust",
        "exhaust_left_bank",
        "exhaust_right_bank",
        "bark",
        "mechanical",
        "closed_throttle_tail",
    } <= set(render.stems)
    assert np.all(np.isfinite(render.pressure))
    assert render.diagnostics["scope"] == "synthetic; uncalibrated; not OEM reproduction"
    assert render.diagnostics["bank_timing"] == "cross_plane_v8_event_pulses"
    assert render.diagnostics["moving_order_model"] is True
    assert "bark_resonance_scale" not in render.diagnostics["candidate_source_overrides"]
    with pytest.raises(ValueError, match="unsupported"):
        render_c63_w204_v3(_trace("accel"), _SR, {"bark_resonance_scale": 1.1})


@pytest.mark.parametrize(
    ("override", "stem"),
    (
        ({"bank_phase_offset_deg": 10.0}, "exhaust_right_bank"),
        ({"pulse_width_scale": 1.08}, "exhaust"),
        ({"bark_primary_order": 7.72}, "bark"),
        ({"bark_upper_partial_mix": 0.18}, "bark"),
        ({"bark_decay_ms": 10.0}, "bark"),
        ({"mechanical_upper_tilt_db": -3.2}, "mechanical"),
        ({"high_rpm_compression": 0.62}, "bark"),
        ({"mechanical_texture_scale": 1.25}, "mechanical"),
        ({"high_rpm_growth_scale": 1.25}, "bark"),
    ),
)
def test_c63_v3_each_public_override_changes_its_target_deterministically(override, stem: str) -> None:
    trace = _trace("accel")
    base = render_c63_w204_v3(trace, _SR)
    changed_once = render_c63_w204_v3(trace, _SR, overrides=override)
    changed_twice = render_c63_w204_v3(trace, _SR, overrides=override)

    assert _l2(base.stems[stem], changed_once.stems[stem]) > 1e-8
    assert np.array_equal(changed_once.stems[stem], changed_twice.stems[stem])
    parameter_name = next(iter(override))
    assert changed_once.diagnostics["parameter_usage"][parameter_name] == "active"


def test_c63_v3_preserves_cross_plane_timing_and_closed_throttle_tail() -> None:
    for kind in ("accel", "lift"):
        trace = _trace(kind)
        stage_j = render_c63_w204_v2(trace, _SR)
        stage_k = render_c63_w204_v3(trace, _SR)
        # v3 adds a fixed source-domain rise time, so sample amplitudes may
        # differ; the cross-plane event count and onset timeline stay fixed.
        assert stage_k.diagnostics["event_count"] == stage_j.diagnostics["event_count"]
        for name in ("exhaust_left_bank", "exhaust_right_bank"):
            old = np.asarray(stage_j.stems[name][:, 1])
            new = np.asarray(stage_k.stems[name][:, 1])
            old_onsets = np.flatnonzero((np.abs(old) > 1e-12) & (np.r_[True, np.abs(old[:-1]) <= 1e-12]))
            new_onsets = np.flatnonzero((np.abs(new) > 1e-12) & (np.r_[True, np.abs(new[:-1]) <= 1e-12]))
            assert old_onsets.size == new_onsets.size
            assert np.all(np.abs(old_onsets - new_onsets) <= 1)
        assert np.array_equal(stage_j.stems["closed_throttle_tail"], stage_k.stems["closed_throttle_tail"])
    assert render_c63_w204_v3(_trace("lift"), _SR).diagnostics["closed_throttle_event_count"] > 0


def test_c63_v3_reduces_high_frequency_peak_without_erasing_body() -> None:
    trace = _trace("accel")
    stage_j = render_c63_w204_v2(trace, _SR)
    stage_k = render_c63_w204_v3(trace, _SR)

    old_high = _band_rms(stage_j.pressure, 4_000.0, 12_000.0)
    new_high = _band_rms(stage_k.pressure, 4_000.0, 12_000.0)
    old_mid = _band_rms(stage_j.pressure, 1_000.0, 4_000.0)
    new_mid = _band_rms(stage_k.pressure, 1_000.0, 4_000.0)
    old_low = _band_rms(stage_j.pressure, 40.0, 200.0)
    new_low = _band_rms(stage_k.pressure, 40.0, 200.0)

    # The C63 complaint is a harsh upper transient, not a missing exhaust body.
    assert new_high <= old_high * (10.0 ** (-3.0 / 20.0))
    assert new_high >= old_high * (10.0 ** (-6.0 / 20.0))
    assert new_mid >= old_mid * 0.90
    assert new_low <= old_low * 1.05
    assert new_low >= old_low * 0.95
    assert _roughness(stage_k.pressure) <= _roughness(stage_j.pressure) * 0.80


def test_c63_v3_does_not_add_random_or_fixed_tone_noise() -> None:
    trace = _trace("accel")
    first = render_c63_w204_v3(trace, _SR)
    second = render_c63_w204_v3(trace, _SR)
    assert np.array_equal(first.pressure, second.pressure)
    assert first.diagnostics["noise_model"] == "none_deterministic_event_driven"
    assert first.diagnostics["bark_model"] == "event_driven_primary_plus_damped_partials"
