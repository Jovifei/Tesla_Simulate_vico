from __future__ import annotations

from pathlib import Path

from tools.sound_sim.s12.acoustic_identity_v015.stage_d.scenarios import build_stage_d_scenario_trace
from tools.sound_sim.s12.acoustic_identity_v015.stage_g.candidate_profiles import load_stage_g_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_g.render_candidate import render_stage_g_candidate


ROOT = Path(__file__).resolve().parents[1]


def test_stage_g_diagnostics_prove_pre_frozen_boundary_order() -> None:
    profile = load_stage_g_candidate(ROOT / "targets" / "stage_g_candidates" / "Hellcat_candidate_v4.json")
    trace = build_stage_d_scenario_trace("hellcat", "shift", duration_s=2.0)
    render = render_stage_g_candidate("hellcat", trace, profile)
    assert render.diagnostics["pipeline_order"] == (
        "independent_source", "idle_dynamics", "deterministic_afterfire", "low_frequency_body",
        "exhaust_rumble", "shift_dynamics", "transient_peak_shaping", "pre_ptr_equalization",
        "frozen_ptr", "fixed_whole_cycle_gain", "pcm24",
    )
    assert render.diagnostics["candidate_overlay_position"] == "before_pre_ptr_equalization"
    assert render.diagnostics["post_frozen_ptr_added_energy"] == 0.0
