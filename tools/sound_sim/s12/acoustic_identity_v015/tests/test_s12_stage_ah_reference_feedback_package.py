"""End-to-end CLI/transaction/UI tests: real engines, synthetic assets/schedules."""
from pathlib import Path
import json

import numpy as np
import pytest
from scipy.io import wavfile

from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import reference_feedback_cli as cli
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.reference_feedback import SearchConfig, SR
from tools.sound_sim.s12.acoustic_identity_v015.stage_af.package_integrity import seal_payload


@pytest.fixture
def governed_fixture(tmp_path, monkeypatch):
    ir = tmp_path / "ir"
    ir.mkdir()
    wavfile.write(ir / "mild_exhaust_reverb.wav", SR, np.array([28000, 2000, -800, 100], dtype=np.int16))
    monkeypatch.setenv("S12_ENGINE_SIM_IR_ROOT", str(ir))
    bundle = tmp_path / "old-run" / "reference_bundle"
    clips = {}
    for vi, vehicle in enumerate(("rx7_fd", "aventador_lp700")):
        root = bundle / vehicle
        root.mkdir(parents=True)
        for index, scene in enumerate(("03_hot_idle", "07_steady_high")):
            t = np.arange(12000) / SR
            pcm = (5500*np.sin(2*np.pi*(250+90*index+vi*30)*t + index*.13)
                   + 2500*np.sin(2*np.pi*2400*t)).astype(np.int16)
            path = root / f"ref_{scene}.wav"
            wavfile.write(path, SR, pcm)
            clips[f"{vehicle}/{path.name}"] = {
                "vehicle": vehicle, "scene_id": scene, "filename": path.name,
                "source_video_id": f"synthetic-{vehicle}-{index}",
                "source_sha256": str(vi*2+index+1)*64, "sha256": cli._sha(path), "duration_s": .25,
            }
    cli._write(bundle / "reference_clip_receipt.json", seal_payload({"clips": clips},
              "s12.stage_ah.remaining_vehicles.reference_clip_receipt.v1"))
    plan = tmp_path / "plan.json"
    cli.prepare_plan(bundle.parent, plan)
    payload = cli._read(plan)
    for row in payload["cases"]:
        row["comparable"] = True
        row["comparability_note"] = "controlled synthetic reference for integration only, not a field recording"
        row["candidate_window_s"] = [0.0, .25]
    cli._write(plan, payload)

    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.remaining_vehicle_package import _dashboards
    def short_scenes(vehicle, cfg):
        sim = _dashboards.EngineAcoustics(vehicle_type=vehicle, sr=SR)
        web = cfg["dir"] / "web_audio"
        web.mkdir(parents=True)
        for i, row in enumerate(cfg["scenes"]):
            n = 12000
            context = dict(rpm=np.full(n, 4200. + i*30.), throttle=np.full(n, .6), duration=.25,
                           shift_events=None, afterfire_events=None, bov_events=None)
            audio = sim.render_track(context["rpm"], context["throttle"], context["duration"])
            for path in (cfg["dir"] / row["candidate_file"], web / row["candidate_file"]):
                wavfile.write(path, SR, audio)
            cfg["_render_observer"](scene_id=row["id"], engine=sim, audio=audio, **context)
    monkeypatch.setattr(_dashboards, "render_vehicle_audio", short_scenes)
    return plan


def test_complete_two_vehicle_render_package_verify_and_tamper(governed_fixture, tmp_path):
    out = tmp_path / "actual-loop-smoke"
    result = cli.run_plan(governed_fixture, out, config=SearchConfig(max_trials=1))
    assert result["comparison"] == "BASELINE_C0_VS_TUNED_C0_FIXED_BASELINE_DENOMINATORS"
    assert result["runtime"]["source_status"] == "SOURCE_CLEAN"
    manifest_sha = cli._sha(out / "ARTIFACTS.json")
    cli.verify_run(out, manifest_sha)
    for vehicle, row in result["vehicles"].items():
        assert row["status"] == "NO_IMPROVEMENT"
        assert row["off_switch_pcm_equal_count"] == 10
        assert len(row["baseline_records"]) == len(row["selected_records"]) == 10
        assert row["baseline_pcm_sha256"] == row["selected_pcm_sha256"]
        assert len({r["trace_sha256"] for r in row["baseline_records"].values()}) == 10
        for group in ("baseline", "tuned"):
            text = (out / group / vehicle / "index.html").read_text(encoding="utf-8")
            assert "实时动态声学分析仪" in text
            assert "http://localhost:0/" not in text
            assert "__AUDIOS_JSON__" not in text
    cli.serve_run(out, 29380, manifest_sha, preflight_only=True)
    with pytest.raises(FileExistsError):
        cli.run_plan(governed_fixture, out, config=SearchConfig(max_trials=1))
    assert cli._sha(out / "ARTIFACTS.json") == manifest_sha
    assert not (out.parent / ("."+out.name+".lock")).exists()
    wav = out / "tuned" / "rx7_fd" / "web_audio" / "03_hot_idle.wav"
    data = bytearray(wav.read_bytes())
    data[-1] ^= 1
    wav.write_bytes(data)
    with pytest.raises(ValueError, match="artifact drift"):
        cli.verify_run(out, manifest_sha)


def test_receipt_binding_cannot_be_relabelled(governed_fixture):
    payload = cli._read(governed_fixture)
    payload["cases"][0]["source_sha256"] = "f"*64
    cli._write(governed_fixture, payload)
    with pytest.raises(ValueError, match="original reference receipt"):
        cli.load_plan(governed_fixture)


def test_prepare_does_not_invent_comparability(governed_fixture, tmp_path):
    baseline = Path(cli._read(governed_fixture)["baseline_run"])
    fresh = tmp_path / "unreviewed.json"
    cli.prepare_plan(baseline, fresh)
    with pytest.raises(ValueError, match="review is incomplete"):
        cli.load_plan(fresh)


def test_missing_pcm_byte_fails_before_render(governed_fixture, tmp_path):
    p = Path(cli._read(governed_fixture)["cases"][0]["wav_path"])
    p.unlink()
    with pytest.raises(ValueError, match="reference missing"):
        cli.run_plan(governed_fixture, tmp_path / "not-published")
    assert not (tmp_path / "not-published").exists()


def test_failure_during_workbench_build_is_atomic(governed_fixture, tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("injected dashboard failure")
    monkeypatch.setattr(cli, "_dashboard", fail)
    out = tmp_path / "never-publish"
    with pytest.raises(RuntimeError, match="injected dashboard"):
        cli.run_plan(governed_fixture, out, config=SearchConfig(max_trials=1))
    assert not out.exists()
    assert not (tmp_path / ".never-publish.lock").exists()
    assert not list(tmp_path.glob(".never-publish-*"))


def test_baseline_numeric_block_isolated_and_other_vehicle_continues(governed_fixture, tmp_path, monkeypatch):
    original = cli._baseline

    def fail_rx7(vehicle, directory):
        if vehicle == "rx7_fd":
            raise cli.BaselineNumericGateError(
                vehicle, "09_steady_mid",
                {"peak_estimate_4x": {"peak": 1.0311131137519787}},
                ("03_hot_idle", "07_steady_high"),
            )
        return original(vehicle, directory)

    monkeypatch.setattr(cli, "_baseline", fail_rx7)
    monkeypatch.setattr(cli, "_runtime_identity", lambda: {"commit": "test", "scope": "test",
                                                             "inventory_sha256": "test", "source_files": {},
                                                             "source_status": "SOURCE_CLEAN"})
    out = tmp_path / "isolated-baseline-block"
    result = cli.run_plan(governed_fixture, out, config=SearchConfig(max_trials=1))

    blocked = result["vehicles"]["rx7_fd"]
    assert blocked["status"] == "ALL_SCENE_NUMERIC_REJECTED_ROLLED_BACK"
    assert blocked["failure_receipt"] == "diagnostics/rx7_fd-baseline-numeric-failure.json"
    assert result["vehicles"]["aventador_lp700"]["status"] == "NO_IMPROVEMENT"
    failure = cli._sealed(out / blocked["failure_receipt"])
    assert failure["vehicle"] == "rx7_fd"
    assert failure["scene"] == "09_steady_mid"
    assert failure["record"]["peak_estimate_4x"]["peak"] > 1.0
    manifest_sha = cli._sha(out / "ARTIFACTS.json")
    cli.verify_run(out, manifest_sha)
