"""Actual R1 -> AH -> original rich dashboard integration with synthetic assets."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

from tools.sound_sim.s12.acoustic_identity_v015.stage_ag.vehicle_identity_r1 import VehicleIdentityR1Engine
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.engine import RemediationEngine, spectrum_report
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import package, run_experiment
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.source_policy import VARIANTS
from tools.sound_sim.s12.acoustic_identity_v015.stage_af.package_integrity import sha256_file
from tools.sound_sim.s12.acoustic_identity_v015.stage_ag.build_identity_dashboards_r1 import build_identity_package_r1

VEHICLES = ("hellcat", "ferrari_458", "lfa", "gtr_r35")


@pytest.fixture
def ir_root(tmp_path, monkeypatch):
    root = tmp_path / "controlled-ir"
    root.mkdir()
    t = np.arange(1000) / 48000.
    ir = .02 * np.exp(-t/.006) * np.cos(2*np.pi*120*t)
    ir[0] = .9
    for name in ("mild_exhaust_reverb", "test_engine_16_eq_adjusted_16", "test_engine_14_eq_adjusted_16"):
        wavfile.write(root / f"{name}.wav", 48000, (ir * 32767).astype(np.int16))
    monkeypatch.setenv("S12_ENGINE_SIM_IR_ROOT", str(root))
    return root


@pytest.mark.parametrize("vehicle", VEHICLES)
def test_r1_baseline_and_no_event_afterfire_are_bit_exact(vehicle, ir_root):
    rpm = np.linspace(2600., 3300., 12000)
    throttle = np.full(12000, .4)
    original = VehicleIdentityR1Engine(vehicle, seed=91)
    expected = original.render_track(rpm, throttle, .25)
    for variant in ("r1_baseline", "afterfire_pressure"):
        engine = RemediationEngine(vehicle, seed=91, variant=variant)
        assert np.array_equal(engine.render_track(rpm, throttle, .25), expected)
        assert engine.last_report["normalization"]["ceiling_samples"] == 0


def test_stereo_spectral_power_does_not_cancel():
    t = np.arange(48000) / 48000.
    x = np.sin(2*np.pi*95*t)
    report = spectrum_report(np.column_stack([x, -x]))
    assert abs(report["lf_peak_hz"] - 95.) < 3.
    assert report["rms_digital"] > .7


def test_all_variants_build_real_rich_html_and_embedded_wav(tmp_path, monkeypatch, ir_root):
    # Synthetic short schedules reduce CI runtime but do NOT stub the renderer,
    # dashboard builder, contracts, WAV encoder, Base64 store or strict validator.
    stage_ad = Path(package.__file__).parents[1] / "stage_ad"
    sys.path.insert(0, str(stage_ad))
    try:
        from tools.sound_sim.s12.acoustic_identity_v015.stage_ad import build_unified_dashboards as dashboards
    finally:
        sys.path.pop(0)

    def small_schedule(vehicle, cfg):
        engine = dashboards.EngineAcoustics(vehicle_type=vehicle, sr=48000)
        root = cfg["dir"]
        web = root / "web_audio"
        web.mkdir(exist_ok=True)
        for scene in cfg["scenes"]:
            n = 12000
            rpm = np.full(n, 3100.)
            throttle = np.full(n, .35)
            events = [(.11, .25)] if scene["id"] in ("01_afterfire", "05_lift") else None
            pcm = engine.render_track(rpm, throttle, .25, afterfire_events=events)
            wavfile.write(web / scene["candidate_file"], 48000, pcm)
            wavfile.write(root / scene["candidate_file"], 48000, pcm)

    monkeypatch.setattr(dashboards, "render_vehicle_audio", small_schedule)
    references = tmp_path / "references"
    for directory in run_experiment.EXPECTED_DIRS.values():
        root = references / directory / "web_audio"
        root.mkdir(parents=True)
        t = np.arange(12000)/48000.
        tone = (12000*np.sin(2*np.pi*200*t)).astype(np.int16)
        for name in ("afterfire", "full_pull", "hot_idle", "steady_low", "steady_mid", "steady_high"):
            wavfile.write(root / f"ref_{name}.wav", 48000, tone)
    parent_args = argparse.Namespace(output_root=tmp_path / "parent", reference_root=references,
        vehicle="all", seed=20260908, numerical_fixes=[], package_id="controlled-parent",
        candidate_id="controlled-parent", port_base=25100, allow_dirty_dev=False,
        identity_mode="vehicle_identity_v1r1", fit_root=None)
    parent = build_identity_package_r1(parent_args)
    parent_sha = sha256_file(parent / "audition_manifest.json")
    output = run_experiment.build(argparse.Namespace(parent_package=parent,
        parent_manifest_sha256=parent_sha, output_root=tmp_path / "experiments", run_id="ci-smoke",
        port_base=25300))
    result = run_experiment.read_sealed(output)
    assert {row["variant"] for row in result["variants"]} == set(VARIANTS)
    assert sha256_file(parent / "audition_manifest.json") == parent_sha
    baseline = result["variants"][0]
    assert baseline["status"] == "READY_FOR_HUMAN_REVIEW"
    for row in result["variants"]:
        verified = run_experiment.verify_package(Path(row["package"]), row["package_manifest_sha256"], row["variant"])
        assert len(verified["vehicles"]) == 4
        data = run_experiment.read_sealed(row["report"])
        assert len(data["records"]) == 40
        assert len(data["reference_rows"]) == 16
        assert all(r["normalization"]["normalization_denominator"] > 0 for r in data["records"])
    # Mode names and package metadata are covered end-to-end, not an allow-list assertion.
    original_configs = dashboards.VEHICLE_CONFIGS
    assert all("AH" not in cfg["title"] for cfg in original_configs.values())
    run_experiment.serve(argparse.Namespace(experiment=output, variant="r1_baseline", preflight_only=True))
    # Detect changed HTML/embedded audio, not just correct WAVs on disk.
    page = Path(baseline["package"]) / run_experiment.EXPECTED_DIRS['hellcat'] / 'index.html'
    page.write_text(page.read_text(encoding='utf-8') + '\n<!--tamper-->\n', encoding='utf-8')
    with pytest.raises(ValueError):
        run_experiment.verify_package(Path(baseline["package"]), baseline["package_manifest_sha256"])


def test_silence_and_lfa_body_range_are_not_misreported():
    report = spectrum_report(np.zeros((48000, 2)))
    assert report["silence"] is True
    assert report["lf_peak_hz"] is None
    assert report["body_20_600_peak_hz"] is None
    t = np.arange(48000) / 48000.
    tone = np.sin(2*np.pi*380*t)
    report = spectrum_report(tone)
    assert abs(report["body_20_600_peak_hz"] - 380.) < 3.
