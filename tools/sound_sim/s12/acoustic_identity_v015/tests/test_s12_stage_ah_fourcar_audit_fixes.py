"""Regression contracts for the Stage AH four-car audit repairs."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile


@pytest.fixture(autouse=True)
def controlled_ir(tmp_path, monkeypatch):
    root = tmp_path / "controlled-ir"
    root.mkdir()
    t = np.arange(512) / 48_000.0
    impulse = 0.9 * np.exp(-t / 0.006) * np.cos(2.0 * np.pi * 120.0 * t)
    for name in (
        "mild_exhaust_reverb",
        "test_engine_16_eq_adjusted_16",
        "test_engine_14_eq_adjusted_16",
    ):
        wavfile.write(root / f"{name}.wav", 48_000, (impulse * 32767.0).astype(np.int16))
    monkeypatch.setenv("S12_ENGINE_SIM_IR_ROOT", str(root))
    return root


def test_render_observer_captures_one_report_per_scene(tmp_path, monkeypatch):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import fourcar_package

    dashboards = fourcar_package._import_dashboards()
    cfg = copy.deepcopy(dashboards.VEHICLE_CONFIGS["hellcat"])
    cfg["dir"] = tmp_path
    observed = []

    class FakeEngine:
        sr = 48_000

        def __init__(self, vehicle_type="hellcat", sr=48_000):
            self.last_report = {}
            self.calls = 0

        def render_track(self, rpm, throttle, duration, **events):
            self.calls += 1
            self.last_report = {
                "scene_marker": self.calls,
                "parent_peak": 0.1 + self.calls * 0.01,
            }
            return np.zeros((len(rpm), 2), dtype=np.int16)

    monkeypatch.setattr(dashboards, "EngineAcoustics", FakeEngine)
    cfg["_render_observer"] = lambda **payload: observed.append(payload)
    dashboards.render_vehicle_audio("hellcat", cfg)

    assert len(observed) == 10
    assert [item["scene_id"] for item in observed] == [
        scene["id"] for scene in cfg["scenes"]
    ]
    assert [item["report"]["scene_marker"] for item in observed] == list(range(1, 11))
    assert len({tuple(item["rpm"][:3]) for item in observed}) == 10


def test_parent_peak_lookup_requires_scene_and_trace_key():
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_pipeline import (
        FourCarRealReferenceEngine,
        load_real_reference_profile,
        scene_trace_key,
    )

    profile, _ = load_real_reference_profile("lfa")
    engine = FourCarRealReferenceEngine(
        "lfa",
        profile,
        parent_peaks={},
        source_adjustment_ratio=1.0,
        seed=20260908,
    )
    n = 480
    rpm = np.linspace(1_200.0, 2_000.0, n)
    throttle = np.full(n, 0.3)
    with pytest.raises(ValueError, match="parent denominator"):
        engine.render_track(rpm, throttle, n / 48_000.0)
    assert scene_trace_key("01_afterfire", "trace") == "01_afterfire|trace"


def test_control_and_candidate_use_the_same_seed():
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_package import _contract

    common = dict(
        package_id="test",
        vehicle="lfa",
        cfg={"port": 1, "_nav_ports": {}},
        source_receipt={},
        reference_sources={},
        candidate_hashes={},
        records=[],
    )
    c0 = _contract(group="C0", profile_metadata=None, **common)
    candidate = _contract(
        group="REALREF",
        profile_metadata={
            "changed_source_parameter": "high_rpm_growth_scale",
            "base_value": 1.15,
            "candidate_value": 1.35,
        },
        **common,
    )
    assert c0["seed"] == candidate["seed"] == 20260908


def test_ratio_one_candidate_is_pcm_identical_to_c0():
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.engine import (
        RemediationEngine,
        input_sha,
    )
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_pipeline import (
        FourCarRealReferenceEngine,
        load_real_reference_profile,
        scene_trace_key,
    )

    n = 2_400
    duration = n / 48_000.0
    rpm = np.linspace(1_200.0, 7_500.0, n)
    throttle = np.linspace(0.2, 1.0, n)
    control = RemediationEngine(
        "lfa", seed=20260908, variant="r1_baseline",
        output_policy="linked_soft_ceiling_v1", collect=True,
    )
    control_pcm = control.render_track(rpm, throttle, duration)
    trace = input_sha(rpm, throttle, duration, [None, None, None])
    profile, _ = load_real_reference_profile("lfa")
    candidate = FourCarRealReferenceEngine(
        "lfa", profile, seed=20260908, source_adjustment_ratio=1.0,
        parent_peaks={scene_trace_key("01_afterfire", trace): control.last_report["parent_peak"]},
    )
    candidate.set_scene_context("01_afterfire", trace)
    assert np.array_equal(control_pcm, candidate.render_track(rpm, throttle, duration))


def test_c0_r1_baseline_does_not_skip_linked_output_policy():
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.engine import RemediationEngine

    engine = RemediationEngine(
        "hellcat", seed=20260908, variant="r1_baseline",
        output_policy="linked_soft_ceiling_v1", collect=True,
    )
    n = 1_200
    engine.render_track(np.full(n, 2_000.0), np.full(n, 0.35), n / 48_000.0)
    assert engine.last_report["output_policy"] == "linked_soft_ceiling_v1"
    assert engine.last_report["normalization"]["guard_applied"] is True


@pytest.mark.parametrize("vehicle", ("hellcat", "ferrari_458", "lfa", "gtr_r35"))
@pytest.mark.parametrize("scenario", ("steady", "shift", "afterfire", "bov"))
def test_ratio_one_control_invariant_covers_four_vehicle_scenarios(vehicle, scenario):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.engine import RemediationEngine, input_sha
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_pipeline import (
        FourCarRealReferenceEngine,
        load_real_reference_profile,
        scene_trace_key,
    )

    n = 1_200
    duration = n / 48_000.0
    rpm = np.linspace(1_200.0, 5_500.0, n)
    throttle = np.full(n, 0.55)
    events = {
        "steady": (None, None, None),
        "shift": ([(0.015, 0.01)], None, None),
        "afterfire": (None, [(0.02, 0.2)], None),
        "bov": (None, None, [(0.02, 0.01)]),
    }[scenario]
    control = RemediationEngine(
        vehicle, seed=20260908, variant="r1_baseline",
        output_policy="linked_soft_ceiling_v1", collect=True,
    )
    control_pcm = control.render_track(rpm, throttle, duration, *events)
    trace = input_sha(rpm, throttle, duration, list(events))
    profile, _ = load_real_reference_profile(vehicle)
    candidate = FourCarRealReferenceEngine(
        vehicle, profile, seed=20260908, source_adjustment_ratio=1.0,
        parent_peaks={scene_trace_key("scenario", trace): control.last_report["parent_peak"]},
    )
    candidate.set_scene_context("scenario", trace)
    assert np.array_equal(
        control_pcm,
        candidate.render_track(rpm, throttle, duration, *events),
    )


@pytest.mark.parametrize("vehicle,stem", [("hellcat", "supercharger"), ("gtr_r35", "turbo")])
def test_source_adjustment_changes_only_named_stem(vehicle, stem, monkeypatch):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_pipeline import (
        RealReferenceSourcePolicy,
        source_adjustment_recipe,
    )
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ad import engine_sim_acoustics

    monkeypatch.setattr(
        engine_sim_acoustics,
        "load_impulse_response",
        lambda *args, **kwargs: np.array([1.0], dtype=np.float64),
    )
    n = 2_400
    rpm = np.linspace(1_200.0, 5_500.0, n)
    throttle = np.linspace(0.2, 1.0, n)
    duration = n / 48_000.0
    recipe = source_adjustment_recipe(vehicle)
    base_policy = RealReferenceSourcePolicy(
        vehicle, seed=20260908, ratio=1.0, collect=True,
        sample_rate=48_000, recipe=recipe,
    )
    adjusted_policy = RealReferenceSourcePolicy(
        vehicle, seed=20260908, ratio=1.25, collect=True,
        sample_rate=48_000, recipe=recipe,
    )
    base_engine = engine_sim_acoustics.EngineAcoustics(vehicle, sr=48_000)
    adjusted_engine = engine_sim_acoustics.EngineAcoustics(vehicle, sr=48_000)
    base_engine._source_policy = base_policy
    adjusted_engine._source_policy = adjusted_policy
    np.random.seed(20260908)
    base_engine.render_track(rpm, throttle, duration)
    np.random.seed(20260908)
    adjusted_engine.render_track(rpm, throttle, duration)
    assert np.array_equal(base_policy.stems["combustion_input"], adjusted_policy.stems["combustion_input"])
    assert np.array_equal(base_policy.stems[f"{stem}_before"], adjusted_policy.stems[f"{stem}_before"])
    assert not np.array_equal(base_policy.stems[f"{stem}_before"], adjusted_policy.stems[f"{stem}_after"])


def test_high_rpm_combustion_hook_observes_before_shift_pop(monkeypatch):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_pipeline import (
        RealReferenceSourcePolicy,
        source_adjustment_recipe,
    )
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ad import engine_sim_acoustics

    monkeypatch.setattr(
        engine_sim_acoustics,
        "load_impulse_response",
        lambda *args, **kwargs: np.array([1.0], dtype=np.float64),
    )
    n = 2_400
    rpm = np.linspace(2_000.0, 7_000.0, n)
    throttle = np.full(n, 0.8)
    duration = n / 48_000.0
    recipe = source_adjustment_recipe("ferrari_458")
    first = RealReferenceSourcePolicy(
        "ferrari_458", seed=20260908, ratio=1.0, collect=True,
        sample_rate=48_000, recipe=recipe,
    )
    second = RealReferenceSourcePolicy(
        "ferrari_458", seed=20260908, ratio=1.25, collect=True,
        sample_rate=48_000, recipe=recipe,
    )
    a = engine_sim_acoustics.EngineAcoustics("ferrari_458", sr=48_000)
    b = engine_sim_acoustics.EngineAcoustics("ferrari_458", sr=48_000)
    a._source_policy = first
    b._source_policy = second
    np.random.seed(20260908)
    a.render_track(rpm, throttle, duration, shift_events=[(0.03, 0.02)])
    np.random.seed(20260908)
    b.render_track(rpm, throttle, duration, shift_events=[(0.03, 0.02)])
    assert np.array_equal(first.stems["combustion_high_rpm_before"], second.stems["combustion_high_rpm_before"])


def test_source_recipe_declares_named_stem_scope():
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_pipeline import (
        source_adjustment_recipe,
    )

    assert source_adjustment_recipe("hellcat")["stem"] == "supercharger"
    assert source_adjustment_recipe("gtr_r35")["stem"] == "turbo"
    assert source_adjustment_recipe("ferrari_458")["stem"] == "combustion_high_rpm"
    assert source_adjustment_recipe("lfa")["stem"] == "combustion_high_rpm"


def test_reference_files_reject_parent_manifest_sha_drift(tmp_path):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_package import (
        _reference_files,
    )

    source = tmp_path / "s12-stage-ad-hellcat-closed-loop-v1" / "web_audio"
    source.mkdir(parents=True)
    reference = source / "ref_hot_idle.wav"
    reference.write_bytes(b"original")
    expected = {reference.name: "00" * 32}
    with pytest.raises(ValueError, match="parent reference SHA"):
        _reference_files(tmp_path, "hellcat", expected_reference_sha256=expected)


def test_reference_gate_is_truthful_for_unsynchronised_cues():
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_package import (
        _reference_gate,
    )

    gate = _reference_gate([], evidence_level="R3_PUBLIC_RECORDINGS_UNSYNCED")
    assert gate["status"] == "NOT_EVALUATED_UNSYNCHRONIZED_R3"
    assert gate["evaluated_rows"] == 0
    assert gate["regressions"] is None


def test_peak_estimate_4x_is_explicitly_diagnostic():
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_pipeline import peak_estimate_4x

    result = peak_estimate_4x(np.zeros((64, 2), dtype=np.float64))
    assert result["method"] == "scipy.signal.resample_poly_up4_down1"
    assert result["filter"] == "kaiser_beta_5.0"
    assert result["boundary"] == "line"
    assert result["standard"] == "DIAGNOSTIC_NOT_ITU_CERTIFIED"


def _valid_numeric_record(vehicle="hellcat", scene_id="01_afterfire", trace="a" * 64):
    counts = {
        "frame_count": 100,
        "legacy_ceiling_input_exceedance_samples": 2,
        "soft_guard_active_frames": 1,
        "post_guard_ceiling_exceedance_samples": 0,
        "emergency_clip_count": 0,
    }
    normalization = {
        "receipt_schema": "s12.stage_ah.output_guard_receipt.v2",
        "output_policy": "linked_soft_ceiling_v1",
        "knee_linear": 0.90,
        "ceiling_linear": 0.94,
        "stereo_link": "instantaneous_frame_peak_common_gain",
        "parent_denominator_policy": "caller_supplied_fixed_parent_peak",
        "soft_guard_active_frame_ratio": 0.01,
        "soft_guard_min_gain": 0.99,
        "soft_guard_max_attenuation_db": 0.1,
        "soft_guard_delta_peak": 0.01,
        "soft_guard_delta_rms": 0.001,
        "post_guard_peak": 0.93,
        "emergency_clip_error": 0.0,
        "emergency_clip_error_rms": 0.0,
        "normalization_denominator": 0.6,
        "pre_identity_pcm_sha256": "b" * 64,
        "pre_guard_peak": 0.95,
        "legacy_transfer_pre_guard_peak": 0.95,
        "pre_guard_exceedance_longest_run": {"samples": 2},
        **counts,
    }
    digest = hashlib.sha256(scene_id.encode()).hexdigest()
    return {
        "vehicle": vehicle,
        "scene_id": scene_id,
        "trace_sha256": trace,
        "sample_rate_hz": 48_000,
        "sample_count": 100,
        "seed": 20260908,
        "flags": [],
        "source_variant": "r1_baseline",
        "output_policy": "linked_soft_ceiling_v1",
        "parent_peak": 0.6,
        "candidate_raw_peak": 0.7,
        "final_peak": 0.93,
        "final_rms": 0.2,
        "candidate_pcm_sha256": digest,
        "wav_file_sha256": "c" * 64,
        "peak_estimate_4x": {"peak": 0.93, "method": "fixed"},
        "normalization": normalization,
        "identity_layer_clip_count": 0,
        "identity_layer_clip_error": 0.0,
        "identity_layer_clip_error_rms": 0.0,
        "post_identity_clip_count": 0,
        "post_identity_clip_error": 0.0,
        "post_identity_clip_error_rms": 0.0,
        "ir_effective_sha256": "d" * 64,
        "fixed_branch_spectral_diagnostics": {},
    }


def _forty_valid_records():
    vehicles = ("hellcat", "ferrari_458", "lfa", "gtr_r35")
    return [
        _valid_numeric_record(vehicle, f"{index:02d}_scene", hashlib.sha256(f"{vehicle}:{index}".encode()).hexdigest())
        for vehicle in vehicles for index in range(1, 11)
    ]


def test_numeric_gate_is_fail_closed_for_coverage_and_required_fields():
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_package import _numeric_gate

    assert _numeric_gate([])["status"] == "FAIL"
    missing = _forty_valid_records()
    missing[0].pop("normalization")
    assert _numeric_gate(missing)["status"] == "FAIL"
    duplicate = _forty_valid_records()
    duplicate[-1]["scene_id"] = duplicate[0]["scene_id"]
    assert _numeric_gate(duplicate)["status"] == "FAIL"


@pytest.mark.parametrize(
    "field,value",
    [
        ("identity_layer_clip_count", 2),
        ("post_identity_clip_error", 0.02),
        ("peak_estimate_4x", {"peak": 1.07}),
    ],
)
def test_numeric_gate_rejects_clip_error_and_reconstructed_peak(field, value):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_package import _numeric_gate

    records = _forty_valid_records()
    if field == "post_identity_clip_error":
        records[0][field] = value
    else:
        records[0][field] = value
    assert _numeric_gate(records)["status"] == "FAIL"


def test_numeric_gate_rejects_bool_or_negative_counts():
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_package import _numeric_gate

    for value in (True, -1):
        records = _forty_valid_records()
        records[0]["normalization"]["emergency_clip_count"] = value
        assert _numeric_gate(records)["status"] == "FAIL"


def test_source_receipt_uses_the_declared_fourcar_dependency_closure(monkeypatch):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import fourcar_package

    captured = {}

    def fake_receipt(**kwargs):
        captured.update(kwargs)
        return {
            "git_head": "test",
            "base_main": "test",
            "dependency_dirty": False,
            "source_status": "SOURCE_CLEAN",
            "promotable": True,
            "promotion_status": "PROMOTABLE",
        }

    monkeypatch.setattr(fourcar_package, "git_source_receipt", fake_receipt)
    fourcar_package._source_receipt()
    paths = {Path(path).name for path in captured["additional_paths"]}
    assert {"fourcar_pipeline.py", "source_policy.py", "output_guard.py"} <= paths
    assert "engine_sim_acoustics.py" in paths
    assert "vehicle_identity_r1.py" in paths
    assert "candidate_profiles.py" in paths


def test_server_collision_closes_unstarted_servers_without_shutdown(tmp_path, monkeypatch):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import fourcar_package

    manifest = {
        "vehicles": [
            {"vehicle": "hellcat", "directory": "a", "port": 1, "scenes": []},
            {"vehicle": "ferrari_458", "directory": "b", "port": 1, "scenes": []},
        ],
        "numeric_gate": {"status": "PASS"},
    }
    entry = {"group": "REALREF", "package": str(tmp_path), "package_manifest_sha256": "x"}
    monkeypatch.setattr(
        fourcar_package,
        "_read_sealed",
        lambda path: {"groups": [entry]} if path.name == "experiment.json" else manifest,
    )
    monkeypatch.setattr(fourcar_package, "_verify_group", lambda item, **kwargs: manifest)
    closed = []

    class FakeServer:
        calls = 0

        def __init__(self, address, handler):
            type(self).calls += 1
            if type(self).calls == 2:
                raise OSError("occupied")

        def server_close(self):
            closed.append("close")

        def shutdown(self):
            raise AssertionError("shutdown called before serve_forever")

    monkeypatch.setattr(fourcar_package, "ThreadingHTTPServer", FakeServer)
    with pytest.raises(OSError):
        fourcar_package.serve_run(tmp_path / "experiment.json")
    assert closed == ["close"]


def test_failed_build_leaves_failure_receipt_in_staging(tmp_path, monkeypatch):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import fourcar_package

    monkeypatch.setattr(
        fourcar_package,
        "_source_receipt",
        lambda: {"git_head": "test", "base_main": "test", "dependency_dirty": False},
    )
    monkeypatch.setattr(fourcar_package, "_validate_parent_package", lambda root: {})
    monkeypatch.setattr(
        fourcar_package,
        "load_real_reference_profile",
        lambda vehicle: (None, {}),
    )

    def fail_group(**kwargs):
        raise RuntimeError("injected before publish")

    monkeypatch.setattr(fourcar_package, "_build_group", fail_group)
    with pytest.raises(RuntimeError, match="injected before publish"):
        fourcar_package.build_run(
            output_root=tmp_path,
            run_id="failure-test",
            reference_root=fourcar_package.DEFAULT_REFERENCE_ROOT,
        )
    assert not (tmp_path / "failure-test").exists()
    failures = list((tmp_path / ".staging").glob("*/FAIL.json"))
    assert len(failures) == 1


def test_fourcar_short_end_to_end_reaches_strict_preflight(tmp_path, monkeypatch):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import fourcar_package

    monkeypatch.setattr(
        fourcar_package,
        "_source_receipt",
        lambda: {
            "git_head": "test",
            "base_main": "test",
            "dependency_dirty": False,
            "source_status": "SOURCE_CLEAN",
            "promotable": True,
        },
    )
    monkeypatch.setattr(fourcar_package, "_validate_parent_package", lambda root: {})
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import run_experiment
    monkeypatch.setattr(
        run_experiment,
        "reference_rows",
        lambda parent, candidate, manifest: [
            {"vehicle": vehicle, "scene": scene, "regression_gt_3pct": False}
            for vehicle in ("hellcat", "ferrari_458", "lfa", "gtr_r35")
            for scene in ("01_afterfire", "02_full_pull", "03_hot_idle", "09_steady_mid")
        ],
    )
    dashboards = fourcar_package._import_dashboards()

    def short_schedule(vehicle, cfg):
        engine = dashboards.EngineAcoustics(vehicle_type=vehicle, sr=48_000)
        web = cfg["dir"] / "web_audio"
        for index, scene in enumerate(cfg["scenes"], start=1):
            n = 4_800
            duration = n / 48_000.0
            rpm = np.full(n, 1_000.0 + index * 250.0)
            throttle = np.full(n, min(0.95, 0.1 + index * 0.07))
            afterfire = [(0.04, 0.2)] if scene["id"] in {"01_afterfire", "05_lift"} else None
            shift = [(0.05, 0.01)] if scene["id"] == "06_shift" else None
            before = cfg.get("_render_context_observer")
            after = cfg.get("_render_observer")
            payload = {
                "scene_id": scene["id"], "engine": engine, "rpm": rpm,
                "throttle": throttle, "duration": duration,
                "shift_events": shift, "afterfire_events": afterfire,
                "bov_events": None,
            }
            if callable(before):
                before(**payload)
            pcm = engine.render_track(
                rpm, throttle, duration,
                shift_events=shift, afterfire_events=afterfire,
            )
            wavfile.write(web / scene["candidate_file"], 48_000, pcm)
            wavfile.write(cfg["dir"] / scene["candidate_file"], 48_000, pcm)
            if callable(after):
                after(**payload, audio=pcm, report=copy.deepcopy(getattr(engine, "last_report", {})))

    monkeypatch.setattr(dashboards, "render_vehicle_audio", short_schedule)
    experiment = fourcar_package.build_run(
        output_root=tmp_path,
        run_id="short-e2e",
        reference_root=fourcar_package.DEFAULT_REFERENCE_ROOT,
        port_c0=29080,
        port_realref=29180,
    )
    sealed = fourcar_package._read_sealed(experiment)
    assert {group["status"] for group in sealed["groups"]} == {
        "READY_FOR_HUMAN_REVIEW_REFERENCE_DIAGNOSTIC"
    }
    for group in sealed["groups"]:
        fourcar_package._verify_group(group, run_root=experiment.parent)
