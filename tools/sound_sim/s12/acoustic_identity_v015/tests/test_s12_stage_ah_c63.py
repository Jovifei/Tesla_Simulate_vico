"""Focused contracts for the isolated C63 AH adapter."""
from __future__ import annotations

import numpy as np
import pytest
from pathlib import Path

from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.c63_package import _c63_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.c63_pipeline import C63Engine


@pytest.fixture
def fake_ir() -> np.ndarray:
    ir = np.zeros(256, dtype=np.float64)
    ir[0] = 0.9
    ir[1] = 0.02
    return ir


def _curves(duration: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    count = int(round(48_000 * duration))
    time = np.arange(count, dtype=np.float64) / 48_000.0
    rpm = np.linspace(750.0, 6_800.0, count)
    throttle = np.where(time < duration * 0.45, 0.82, 0.03)
    return rpm, throttle


def test_c63_b0_and_c0_share_pre_guard_pcm_but_c0_is_not_legacy(fake_ir):
    rpm, throttle = _curves()
    b0 = C63Engine(output_policy="legacy_clip_v1", ir=fake_ir)
    b0_pcm = b0.render_track(rpm, throttle, 1.0)
    c0 = C63Engine(
        output_policy="linked_soft_ceiling_v1",
        parent_peaks=b0.parent_peaks,
        ir=fake_ir,
    )
    c0_pcm = c0.render_track(rpm, throttle, 1.0)
    b0_record, c0_record = b0.reports[-1], c0.reports[-1]
    assert b0_record["normalization"]["pre_guard_pcm_sha256"] == c0_record["normalization"]["pre_guard_pcm_sha256"]
    assert not np.array_equal(b0_pcm, c0_pcm)
    assert c0_record["normalization"]["soft_guard_active_frames"] > 0
    assert c0_record["normalization"]["post_guard_peak"] <= 0.94
    assert c0_record["normalization"]["post_guard_ceiling_exceedance_samples"] == 0


def test_c63_render_is_deterministic(fake_ir):
    rpm, throttle = _curves()
    first = C63Engine(output_policy="linked_soft_ceiling_v1", ir=fake_ir)
    second = C63Engine(output_policy="linked_soft_ceiling_v1", ir=fake_ir)
    assert np.array_equal(first.render_track(rpm, throttle, 1.0), second.render_track(rpm, throttle, 1.0))


def test_c63_uses_fixed_parent_denominator(fake_ir):
    rpm, throttle = _curves()
    anchor = C63Engine(output_policy="legacy_clip_v1", ir=fake_ir)
    anchor.render_track(rpm, throttle, 1.0)
    candidate = C63Engine(output_policy="linked_soft_ceiling_v1", parent_peaks=anchor.parent_peaks, ir=fake_ir)
    candidate.render_track(rpm, throttle, 1.0)
    assert candidate.reports[-1]["normalization_denominator"] == anchor.parent_peaks[0]
    assert candidate.reports[-1]["parent_denominator_policy"] == "fixed_parent_peak"


def test_c63_rejects_nonfinite_curves(fake_ir):
    rpm, throttle = _curves()
    rpm[100] = np.nan
    with pytest.raises(ValueError, match="finite"):
        C63Engine(ir=fake_ir).render_track(rpm, throttle, 1.0)


def test_c63_config_keeps_ten_scene_layout():
    cfg = _c63_config(Path("c63"), 24680)
    assert len(cfg["scenes"]) == 10
    assert [scene["id"] for scene in cfg["scenes"]] == [
        "01_afterfire", "02_full_pull", "03_hot_idle", "04_idle_return", "05_lift",
        "06_shift", "07_steady_high", "08_steady_low", "09_steady_mid", "10_tip_in",
    ]
    assert cfg["scenes"][-1]["ref_file"] == ""


def test_c63_receipt_is_explicit_about_unverified_reference():
    cfg = _c63_config(Path("c63"), 24680)
    assert "未核验" in cfg["subtitle"]
    assert "unverified" in cfg["ref_source"].lower()
