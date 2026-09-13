"""Regression contracts for the Stage AH four-car audit repairs."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest


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
    monkeypatch.setattr(fourcar_package, "_verify_group", lambda item: manifest)
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
