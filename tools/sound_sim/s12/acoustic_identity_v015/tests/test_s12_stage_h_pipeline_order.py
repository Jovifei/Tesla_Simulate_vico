from __future__ import annotations

from pathlib import Path

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_h.candidate_profiles import load_stage_h_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_h.render_candidate import render_stage_h_candidate


def test_stage_h_diagnostics_prove_named_layers_are_before_frozen_ptr() -> None:
    count = 24001
    time_s = np.arange(count, dtype=np.float64) / 48000.0
    phase = time_s / time_s[-1]
    trace = VehicleStateTrace(time_s, 900.0 + 5200.0 * phase, 0.15 + 0.8 * phase, 0.15 + 0.83 * phase, np.zeros(count)).validate()
    path = Path(__file__).resolve().parents[1] / "targets" / "stage_h_candidates" / "Hellcat_candidate_v5.json"
    render = render_stage_h_candidate("hellcat", trace, load_stage_h_candidate(path))
    assert render.diagnostics["pipeline_order"] == (
        "independent_source", "idle_dynamics", "deterministic_afterfire", "low_frequency_body",
        "exhaust_rumble", "shift_dynamics", "transient_peak_shaping", "pre_ptr_equalization",
        "frozen_ptr", "fixed_whole_cycle_gain", "pcm24",
    )
    assert render.diagnostics["candidate_overlay_position"] == "before_pre_ptr_equalization"
    assert render.diagnostics["post_frozen_ptr_added_energy"] == 0.0
