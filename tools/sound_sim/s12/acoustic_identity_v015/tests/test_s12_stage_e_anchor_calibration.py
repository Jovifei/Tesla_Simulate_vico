import numpy as np
from pathlib import Path

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_e.candidate_profiles import load_stage_e_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_e.render_candidate import render_stage_e_candidate


def test_non_anchor_is_rejected():
    trace = VehicleStateTrace(np.array([0.0, 0.01]), np.array([3000.0, 3000.0]), np.array([.5, .5]), np.array([.5, .5]), np.zeros(2))
    try:
        render_stage_e_candidate("lfa", trace)
    except ValueError:
        return
    raise AssertionError("unknown Stage-E vehicle must fail closed")


def test_rx7_candidate_changes_turbo_time_structure():
    root = Path(__file__).resolve().parents[1]
    profile = load_stage_e_candidate(root / "targets/stage_e_candidates/RX7_candidate_v2.json")
    t = np.linspace(0.0, .2, 21)
    trace = VehicleStateTrace(t, np.linspace(3500.0, 7000.0, t.size), np.full(t.size, .8), np.full(t.size, .9), np.zeros(t.size))
    a = render_stage_e_candidate("rx7_fd", trace, profile)
    b = render_stage_e_candidate("rx7_fd", trace, profile.with_parameter("source", "primary_spool_tau_s", .21))
    assert not np.array_equal(a.stems["turbo"], b.stems["turbo"])
