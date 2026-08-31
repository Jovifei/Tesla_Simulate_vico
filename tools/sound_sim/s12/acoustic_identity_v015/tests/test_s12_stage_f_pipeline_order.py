import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_f.candidate_profiles import load_stage_f_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_f.render_candidate import render_stage_f_candidate


def test_stage_f_candidate_overlay_is_before_frozen_boundary():
    from pathlib import Path
    t = np.arange(0.0, 0.05, 1.0 / 48000.0)
    trace = VehicleStateTrace(t, np.full(t.size, 3000.0), np.full(t.size, 0.7), np.full(t.size, 0.7), np.zeros(t.size)).validate()
    profile = load_stage_f_candidate(Path(__file__).resolve().parents[1] / "targets/stage_f_candidates/Ferrari_candidate_v3.json")
    render = render_stage_f_candidate("ferrari_458", trace, profile)
    order = render.diagnostics["pipeline_order"]
    assert order.index("transient_peak_shaping") < order.index("pre_ptr_equalization") < order.index("frozen_ptr")
    assert render.diagnostics["stage_f_overlay_position"] == "before_pre_ptr_equalization_and_frozen_ptr"
