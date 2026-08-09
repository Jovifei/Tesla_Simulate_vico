from pathlib import Path

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.stage_d.candidate_profiles import load_stage_d_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_d.render_candidate import render_stage_d_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_d.scenarios import build_stage_d_scenario_trace


_ROOT = Path(__file__).resolve().parents[1]
_CANDIDATES = {
    "ferrari_458": "Ferrari_candidate_v1.json",
    "hellcat": "Hellcat_candidate_v1.json",
    "rx7_fd": "RX7_candidate_v1.json",
}


def test_three_anchor_candidates_are_finite_and_pre_ptr() -> None:
    for vehicle_id, filename in _CANDIDATES.items():
        trace = build_stage_d_scenario_trace(vehicle_id, "acceleration", duration_s=2.0)
        candidate = load_stage_d_candidate(_ROOT / "targets" / "stage_d_candidates" / filename)
        render = render_stage_d_candidate(vehicle_id, trace, candidate)
        assert render.pressure.shape == (len(trace.time_s), 2)
        assert np.isfinite(render.pressure).all()
        assert render.diagnostics["stage_d_overlay_position"] == "before_frozen_ptr"


def test_stage_d_candidate_does_not_change_non_anchor_paths() -> None:
    trace = build_stage_d_scenario_trace("ferrari_458", "idle", duration_s=2.0)
    # Stage-D renderer is intentionally closed over the three anchors.
    try:
        render_stage_d_candidate("lfa", trace, None)
    except ValueError as error:
        assert "unsupported" in str(error)
    else:
        raise AssertionError("non-anchor vehicle must fail closed")
