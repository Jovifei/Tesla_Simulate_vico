"""RED tests for the W6 RPM/load/boost timbre-map branch."""

from __future__ import annotations

import copy
import hashlib

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.timbre_map import render_timbre_map


def test_timbre_map_exposes_harmonics_sidebands_noise_and_resonances() -> None:
    phase = np.linspace(0.0, 20.0 * np.pi, 960, dtype=np.float64)
    base = render_timbre_map(phase, np.full(960, 2400.0), np.full(960, 0.4), np.full(960, 0.2), np.full(960, 0.6), load_config("hellcat_v1"), 0)
    altered = render_timbre_map(phase, np.full(960, 5200.0), np.full(960, 0.9), np.full(960, 0.8), np.full(960, 0.9), load_config("hellcat_v1"), 0)
    assert set(base) >= {"blower", "turbo", "sidebands", "broadband", "casing", "intake", "boost_state"}
    assert not np.array_equal(base["blower"], altered["blower"])
    assert np.max(np.abs(base["broadband"])) > 0.0


def test_persistent_engine_timbre_map_changes_candidate_without_changing_baseline() -> None:
    state = {"rpm": np.array([4200.0]), "load": np.array([0.7]), "throttle": np.array([0.8]), "acceleration_mps2": np.array([3.0])}
    baseline = PersistentEventDomainEngine(load_config("hellcat_v1"), 48000, 960, forced_induction_model="harmonic_v1")
    mapped = PersistentEventDomainEngine(load_config("hellcat_v1"), 48000, 960, forced_induction_model="timbre_map_v1")
    a = baseline.process(state).raw_pcm
    b = mapped.process(state).raw_pcm
    assert not np.array_equal(a, b)
    assert hashlib.sha256(a.tobytes()).hexdigest() != hashlib.sha256(b.tobytes()).hexdigest()
    assert mapped.diagnostics()["forced_induction_model"] == "timbre_map_v1"


def test_forced_induction_boost_and_bov_state_persist_across_blocks() -> None:
    config = load_config("hellcat_v1")
    engine = PersistentEventDomainEngine(config, 48000, 960, forced_induction_model="timbre_map_v1")
    high = {"rpm": np.array([5200.0]), "load": np.array([0.92]), "throttle": np.array([0.95]), "acceleration_mps2": np.array([4.0])}
    closure = {"rpm": np.array([4700.0]), "load": np.array([0.55]), "throttle": np.array([0.02]), "acceleration_mps2": np.array([-8.0])}
    engine.process(high)
    snapshot = engine.snapshot_state()
    expected = engine.process(closure).raw_pcm
    diagnostics = engine.diagnostics()
    assert diagnostics["boost_state"] > 0.0
    assert diagnostics["bov_event_count"] > 0
    engine.restore_state(snapshot)
    replay = engine.process(closure).raw_pcm
    assert np.array_equal(expected, replay)


def test_naturally_aspirated_vehicle_does_not_emit_bov() -> None:
    config = load_config("ferrari_458_v1")
    engine = PersistentEventDomainEngine(config, 48000, 960, forced_induction_model="timbre_map_v1")
    engine.process({"rpm": np.array([5200.0]), "load": np.array([0.92]), "throttle": np.array([0.95]), "acceleration_mps2": np.array([4.0])})
    engine.process({"rpm": np.array([4700.0]), "load": np.array([0.55]), "throttle": np.array([0.02]), "acceleration_mps2": np.array([-8.0])})
    assert engine.diagnostics()["bov_event_count"] == 0
    assert engine.diagnostics()["boost_state"] == 0.0


def test_forced_induction_consumes_configured_spool_time_constants() -> None:
    fast_config = load_config("hellcat_v1")
    slow_config = copy.deepcopy(fast_config)
    fast_config["primary_spool_tau"] = {"value": 0.01, "unit": "s", "range": [0.001, 2.0], "source_level": "C", "source": "synthetic test", "verification_state": "synthetic_assumption"}
    slow_config["primary_spool_tau"] = {"value": 0.50, "unit": "s", "range": [0.001, 2.0], "source_level": "C", "source": "synthetic test", "verification_state": "synthetic_assumption"}
    state = {"rpm": np.array([5200.0]), "load": np.array([0.92]), "throttle": np.array([0.95]), "acceleration_mps2": np.array([4.0])}
    fast = PersistentEventDomainEngine(fast_config, 48000, 960, forced_induction_model="timbre_map_v1")
    slow = PersistentEventDomainEngine(slow_config, 48000, 960, forced_induction_model="timbre_map_v1")
    fast.process(state)
    slow.process(state)
    assert fast.diagnostics()["boost_state"] > slow.diagnostics()["boost_state"]


def test_bov_gain_and_decay_parameters_change_the_closure_signal() -> None:
    low_config = load_config("hellcat_v1")
    high_config = copy.deepcopy(low_config)
    low_config["blow_off_gain"] = {"value": 0.02, "unit": "normalized_gain", "range": [0.0, 1.0], "source_level": "C", "source": "synthetic test", "verification_state": "synthetic_assumption"}
    high_config["blow_off_gain"] = {"value": 0.30, "unit": "normalized_gain", "range": [0.0, 1.0], "source_level": "C", "source": "synthetic test", "verification_state": "synthetic_assumption"}
    low = PersistentEventDomainEngine(low_config, 48000, 960, forced_induction_model="timbre_map_v1")
    high = PersistentEventDomainEngine(high_config, 48000, 960, forced_induction_model="timbre_map_v1")
    high_state = {"rpm": np.array([5200.0]), "load": np.array([0.92]), "throttle": np.array([0.95]), "acceleration_mps2": np.array([4.0])}
    closure = {"rpm": np.array([4700.0]), "load": np.array([0.55]), "throttle": np.array([0.02]), "acceleration_mps2": np.array([-8.0])}
    low.process(high_state)
    high.process(high_state)
    assert not np.array_equal(low.process(closure).raw_pcm, high.process(closure).raw_pcm)
