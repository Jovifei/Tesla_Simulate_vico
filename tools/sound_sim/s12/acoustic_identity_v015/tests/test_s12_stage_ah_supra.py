"""Focused contracts for the isolated SUPRA AH adapter."""
from __future__ import annotations

import numpy as np
import pytest
from pathlib import Path

import json

from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.supra_package import (
    REFERENCE_CLIPS,
    REFERENCE_SOURCES,
    _supra_config,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.supra_pipeline import SupraEngine
from tools.sound_sim.s12.acoustic_identity_v015.sources.toyota_i6_turbo_source_v2 import (
    SUPRA_V2_EDGE_SCALE,
    SUPRA_V2_HIBAND_SCALE,
    render_supra_jza80_v2,
)


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


def test_supra_b0_and_c0_share_pre_guard_pcm_but_c0_is_not_legacy(fake_ir):
    rpm, throttle = _curves()
    b0 = SupraEngine(output_policy="legacy_clip_v1", ir=fake_ir)
    b0_pcm = b0.render_track(rpm, throttle, 1.0)
    c0 = SupraEngine(
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


def test_supra_render_is_deterministic(fake_ir):
    rpm, throttle = _curves()
    first = SupraEngine(output_policy="linked_soft_ceiling_v1", ir=fake_ir)
    second = SupraEngine(output_policy="linked_soft_ceiling_v1", ir=fake_ir)
    assert np.array_equal(first.render_track(rpm, throttle, 1.0), second.render_track(rpm, throttle, 1.0))


def test_supra_uses_fixed_parent_denominator(fake_ir):
    rpm, throttle = _curves()
    anchor = SupraEngine(output_policy="legacy_clip_v1", ir=fake_ir)
    anchor.render_track(rpm, throttle, 1.0)
    candidate = SupraEngine(output_policy="linked_soft_ceiling_v1", parent_peaks=anchor.parent_peaks, ir=fake_ir)
    candidate.render_track(rpm, throttle, 1.0)
    assert candidate.reports[-1]["normalization_denominator"] == anchor.parent_peaks[0]
    assert candidate.reports[-1]["parent_denominator_policy"] == "fixed_parent_peak"


def test_supra_rejects_nonfinite_curves(fake_ir):
    rpm, throttle = _curves()
    rpm[100] = np.nan
    with pytest.raises(ValueError, match="finite"):
        SupraEngine(ir=fake_ir).render_track(rpm, throttle, 1.0)


def test_supra_config_keeps_ten_scene_layout():
    cfg = _supra_config(Path("supra"), 24680)
    assert len(cfg["scenes"]) == 10
    assert [scene["id"] for scene in cfg["scenes"]] == [
        "01_afterfire", "02_full_pull", "03_hot_idle", "04_idle_return", "05_lift",
        "06_shift", "07_steady_high", "08_steady_low", "09_steady_mid", "10_tip_in",
    ]
    assert cfg["scenes"][-1]["ref_file"] == ""


def test_supra_receipt_is_explicit_about_unverified_reference():
    cfg = _supra_config(Path("supra"), 24680)
    assert "未核验" in cfg["subtitle"]
    assert "unverified" in cfg["ref_source"].lower()


def test_supra_real_reference_contract_has_three_recordings():
    payload = json.loads(
        Path(
            "tools/sound_sim/s12/acoustic_identity_v015/reference_database/"
            "supra_jza80_multi_reference_targets_v3.json"
        ).read_text(encoding="utf-8")
    )
    assert len(payload["recordings"]) == 3
    assert payload["aggregate"]["source_adjustment"] == {
        "edge_scale": SUPRA_V2_EDGE_SCALE,
        "hiband_scale": SUPRA_V2_HIBAND_SCALE,
    }
    assert set(REFERENCE_SOURCES) >= {
        "supra_01_bone_stock_dyno",
        "supra_02_mostly_stock_road",
        "supra_03_stock_start_acceleration",
    }
    assert "ref_full_pull_dyno.wav" in REFERENCE_CLIPS


def test_supra_v2_source_reports_fixed_overlay():
    rpm, throttle = _curves()
    from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace

    time = np.arange(rpm.size, dtype=np.float64) / 48_000.0
    trace = VehicleStateTrace(
        time, rpm, throttle, throttle, np.gradient(rpm / 60.0, time)
    ).validate()
    render = render_supra_jza80_v2(trace)
    assert render.diagnostics["source_variant"] == "supra_i6_twin_turbo_realref_v3"
    assert render.diagnostics["source_overlay"]["edge_scale"] == SUPRA_V2_EDGE_SCALE
    assert render.diagnostics["source_overlay"]["hiband_scale"] == SUPRA_V2_HIBAND_SCALE
