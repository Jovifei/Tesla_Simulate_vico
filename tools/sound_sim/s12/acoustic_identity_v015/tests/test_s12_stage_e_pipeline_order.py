import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_e.render_candidate import render_stage_e_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_e.candidate_profiles import load_stage_e_candidate
from pathlib import Path


def test_candidate_pipeline_order_is_before_frozen_ptr():
    t = np.linspace(0.0, 0.15, 16)
    trace = VehicleStateTrace(t, np.full(t.size, 3000.0), np.full(t.size, 0.6), np.full(t.size, 0.6), np.zeros(t.size))
    candidate = load_stage_e_candidate(Path(__file__).resolve().parents[1] / "targets" / "stage_e_candidates" / "Hellcat_candidate_v2.json")
    render = render_stage_e_candidate("hellcat", trace, candidate)
    order = render.diagnostics["pipeline_order"]
    assert order.index("transient_peak_shaping") < order.index("pre_ptr_equalization") < order.index("frozen_ptr")
