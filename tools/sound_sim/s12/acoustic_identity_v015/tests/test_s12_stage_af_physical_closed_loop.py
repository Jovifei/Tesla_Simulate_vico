from __future__ import annotations

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.stage_ad import engine_sim_acoustics
from tools.sound_sim.s12.acoustic_identity_v015.stage_af.physical_closed_loop import (
    FAMILY_PARAMETERS,
    TunableEngineAcoustics,
    fixed_reference_distance,
)


def _identity_ir(*args, **kwargs):
    return np.asarray([1.0], dtype=np.float64)


def test_fixed_reference_distance_is_zero_for_same_audio():
    rng = np.random.default_rng(7)
    audio = rng.normal(0.0, 0.1, (48_000, 2))
    assert fixed_reference_distance(audio, audio) == 0.0


def test_tunable_adapter_preserves_engineacoustics_and_changes_physical_path(monkeypatch):
    monkeypatch.setattr(engine_sim_acoustics, "load_impulse_response", _identity_ir)
    baseline = TunableEngineAcoustics("hellcat", seed=7)
    tuned = TunableEngineAcoustics(
        "hellcat",
        overrides={"primary_length_scale": 1.10, "exhaust_gain_scale": 1.08},
        seed=7,
    )
    assert tuned.engine.__class__ is engine_sim_acoustics.EngineAcoustics
    assert not np.array_equal(tuned.engine.delays_sec, baseline.engine.delays_sec)
    assert tuned.engine.exhaust_gain > baseline.engine.exhaust_gain


def test_stage_af_parameter_families_do_not_expose_master_gain():
    names = {p.name for group in FAMILY_PARAMETERS.values() for p in group}
    forbidden = {"master_gain", "global_gain", "monitor_gain", "whole_mix_gain", "pre_ptr_gain"}
    assert names.isdisjoint(forbidden)


def test_tunable_adapter_makes_baseline_noise_deterministic(monkeypatch):
    monkeypatch.setattr(engine_sim_acoustics, "load_impulse_response", _identity_ir)
    sr = 48_000
    duration = 0.15
    n = int(sr * duration)
    rpm = np.full(n, 3000.0)
    throttle = np.full(n, 0.5)
    a = TunableEngineAcoustics("gtr_r35", seed=123).render_track(rpm, throttle, duration)
    b = TunableEngineAcoustics("gtr_r35", seed=123).render_track(rpm, throttle, duration)
    assert np.array_equal(a, b)
