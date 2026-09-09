"""Hermetic AH regression. No local IR, audio fixture downloads or fake Human PASS."""
from __future__ import annotations
import importlib.util
import subprocess
from pathlib import Path

import numpy as np
import pytest
from tools.sound_sim.s12.acoustic_identity_v015.stage_ad import engine_sim_acoustics as base
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.source_policy import (
    SourcePolicy, VARIANTS, pressure_events, validate_events,
)

VEHICLES = ("hellcat", "ferrari_458", "lfa", "gtr_r35")
BASE_HEAD = "078643e9e90cb5b05f82225cc8404bef25a3db84"
BASE_FILE = "tools/sound_sim/s12/acoustic_identity_v015/stage_ad/engine_sim_acoustics.py"


@pytest.fixture
def fake_ir(monkeypatch):
    t = np.arange(1800) / 48000.
    ir = .02 * np.exp(-t / .012) * np.cos(2 * np.pi * 130 * t)
    ir[0] += 1.
    monkeypatch.setattr(base, "load_impulse_response", lambda *a, **k: ir.copy())
    return ir


def trace():
    n = 48_000
    return np.linspace(4200., 1100., n), np.r_[np.full(n // 3, .7), np.zeros(n - n // 3)]


@pytest.mark.parametrize("vehicle", VEHICLES)
def test_none_and_observer_match_fixed_git_oracle(vehicle, fake_ir, tmp_path):
    repo = Path(__file__).resolve().parents[5]
    try:
        source = subprocess.check_output(["git", "show", f"{BASE_HEAD}:{BASE_FILE}"], cwd=repo)
    except subprocess.CalledProcessError:
        # Local audit workspace has a separately SHA-verified copy. CI always
        # has full Git history and may never synthesize an oracle from new code.
        local = repo / "base_engine_verified.py"
        if not local.is_file():
            raise
        source = local.read_bytes()
        import hashlib
        assert hashlib.sha1(f"blob {len(source)}\0".encode() + source).hexdigest() == "3cec8c77108038f6b112594722b077890ab7c9e0"
    path = tmp_path / "frozen_engine.py"
    path.write_bytes(source)
    spec = importlib.util.spec_from_file_location("frozen_engine", path)
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    old.load_impulse_response = lambda *a, **k: fake_ir.copy()
    rpm, throttle = trace()
    kwargs = {"shift_events": [(.32, .055)], "afterfire_events": [(.58, .6)],
              "bov_events": [(.40, .16)]}
    np.random.seed(17)
    expected = old.EngineAcoustics(vehicle).render_track(rpm, throttle, 1., **kwargs)
    for observe in (False, True):
        engine = base.EngineAcoustics(vehicle)
        if observe:
            engine._source_policy = SourcePolicy(vehicle, "r1_baseline", seed=17, collect=True)
        np.random.seed(17)
        actual = engine.render_track(rpm, throttle, 1., **kwargs)
        assert np.array_equal(expected, actual)


@pytest.mark.parametrize("vehicle", VEHICLES)
def test_pressure_causal_tail_and_determinism(vehicle):
    events = [(.1, .5), (.299, .4)]
    a = pressure_events(vehicle, events, 14400, 48000, 7)
    b = pressure_events(vehicle, events, 14400, 48000, 7)
    assert np.array_equal(a, b)
    assert not a[:4800].any()
    edge = pressure_events(vehicle, [(.299, .4)], 14400, 48000, 7)
    assert np.any(edge[-48:])  # old code discarded the entire near-end event
    assert np.all(np.isfinite(a))
    assert not pressure_events(vehicle, [], 14400, 48000, 7).any()


@pytest.mark.parametrize("events", [[(-.1, 1)], [(.1, -1)], [(float('nan'), 1)], [(2., 1)]])
def test_event_validation(events):
    with pytest.raises(ValueError):
        validate_events(events, 1.)


def test_pressure_does_not_change_global_rng():
    np.random.seed(51)
    old = np.random.get_state()
    pressure_events("hellcat", [(.1, 1.)], 24000, 48000, 9)
    new = np.random.get_state()
    assert all(np.array_equal(a, b) for a, b in zip(old, new))


def test_body_damping_only_touches_added_body(fake_ir):
    rpm, thr = trace()
    engine = base.EngineAcoustics("hellcat")
    policies = []
    for variant in ("r1_baseline", "body_damping"):
        policy = SourcePolicy("hellcat", variant, seed=1, collect=True)
        engine._source_policy = policy
        np.random.seed(1)
        engine.render_track(rpm, thr, 1.)
        policies.append(policy)
    a, b = policies
    for name in ("ir_wet_left", "direct_left", "turbulence_modulator_left", "bass_body"):
        assert np.array_equal(a.stems[name], b.stems[name])
    assert np.linalg.norm(b.stems['body_ring_after_left']) < np.linalg.norm(a.stems['body_ring_after_left'])


def test_afterfire_branch_has_no_pre_response(fake_ir):
    engine = base.EngineAcoustics("ferrari_458")
    policy = SourcePolicy("ferrari_458", "afterfire_pressure", seed=3, collect=True)
    engine._source_policy = policy
    rpm, thr = trace()
    np.random.seed(4)
    engine.render_track(rpm, thr, 1., afterfire_events=[(.5, .5)])
    assert np.max(np.abs(policy.stems['afterfire_causal_left'][:24000])) < 1e-14
    assert np.any(policy.stems['afterfire_causal_left'][24000:])
