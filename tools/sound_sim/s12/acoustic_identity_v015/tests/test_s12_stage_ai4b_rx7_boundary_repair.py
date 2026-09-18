"""AI-4B RED tests for the measured RX-7 startup-boundary overshoot."""
from __future__ import annotations

import numpy as np
import pytest
from scipy import signal

from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_pipeline import peak_estimate_4x
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.rx7_boundary_repair import (
    RX7_BOUNDARY_POLICY_V1,
    RX7_BOUNDARY_FADE_FRAMES,
    apply_rx7_boundary_repair,
)


def _peak(audio: np.ndarray, factor: int) -> float:
    return float(np.max(np.abs(signal.resample_poly(
        audio, factor, 1, axis=0, window=("kaiser", 5.0), padtype="line"
    ))))


def _measured_shape() -> np.ndarray:
    audio = np.zeros((48_000, 2), dtype=np.float64)
    audio[20:, 0] = -0.93
    audio[20:, 1] = 0.72
    return audio


def test_boundary_repair_removes_measured_startup_intersample_overshoot():
    audio = _measured_shape()
    assert peak_estimate_4x(audio)["peak"] > 1.0
    repaired, receipt = apply_rx7_boundary_repair(audio)
    assert receipt["policy_id"] == RX7_BOUNDARY_POLICY_V1
    assert receipt["fade_frames"] == RX7_BOUNDARY_FADE_FRAMES
    assert receipt["modified_frames"] == RX7_BOUNDARY_FADE_FRAMES
    assert receipt["delta_peak"] > 0.0
    assert receipt["delta_rms"] > 0.0
    np.testing.assert_array_equal(repaired[RX7_BOUNDARY_FADE_FRAMES:], audio[RX7_BOUNDARY_FADE_FRAMES:])
    assert all(_peak(repaired, factor) <= 1.0 for factor in (4, 8, 16))


def test_boundary_repair_uses_one_common_stereo_ramp_and_preserves_input():
    audio = _measured_shape()
    saved = audio.copy()
    repaired, receipt = apply_rx7_boundary_repair(audio)
    np.testing.assert_array_equal(audio, saved)
    ratio = np.divide(repaired[:RX7_BOUNDARY_FADE_FRAMES], audio[:RX7_BOUNDARY_FADE_FRAMES],
                      out=np.ones_like(repaired[:RX7_BOUNDARY_FADE_FRAMES]), where=audio[:RX7_BOUNDARY_FADE_FRAMES] != 0)
    np.testing.assert_allclose(ratio[:, 0], ratio[:, 1], atol=1e-15, rtol=1e-15)
    assert receipt["scope"] == "rx7_start_boundary_only"


def test_boundary_repair_rejects_nonfinite_or_wrong_shape():
    with pytest.raises(ValueError):
        apply_rx7_boundary_repair(np.ones((100, 2), dtype=np.float64) * np.nan)
    with pytest.raises(ValueError):
        apply_rx7_boundary_repair(np.ones((100, 3), dtype=np.float64))


def test_boundary_repair_disabled_is_explicit():
    audio = _measured_shape()
    repaired, receipt = apply_rx7_boundary_repair(audio, policy=None)
    np.testing.assert_array_equal(repaired, audio)
    assert receipt["policy_id"] is None
    assert receipt["modified_frames"] == 0



def test_remaining_engine_boundary_policy_is_opt_in_and_receipted():
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.remaining_vehicle_pipeline import RemainingVehicleEngine

    rpm = np.full(24_000, 3_400.0, dtype=np.float64)
    throttle = np.full(24_000, 0.35, dtype=np.float64)
    engine = RemainingVehicleEngine(
        "rx7_fd",
        output_policy="linked_soft_ceiling_v1",
        boundary_policy=RX7_BOUNDARY_POLICY_V1,
        ir=np.array([0.9, 0.02], dtype=np.float64),
        scene_ids=("09_steady_mid",),
    )
    engine.render_track(rpm, throttle, 0.5)
    record = engine.reports[-1]
    assert record["boundary_policy"] == RX7_BOUNDARY_POLICY_V1
    assert record["boundary_repair"]["modified_frames"] == RX7_BOUNDARY_FADE_FRAMES
    assert record["peak_estimate_4x"]["peak"] <= 1.0


def test_remaining_engine_default_boundary_policy_is_legacy_compatible():
    from inspect import signature
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.remaining_vehicle_pipeline import RemainingVehicleEngine

    assert signature(RemainingVehicleEngine).parameters["boundary_policy"].default is None
