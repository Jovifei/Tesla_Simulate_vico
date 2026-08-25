"""RED tests for the W6 RPM/load/boost timbre-map branch."""

from __future__ import annotations

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
