from __future__ import annotations

import hashlib

from tools.sound_sim.s12.acoustic_identity_v015.stage_aa.candidates import (
    CANDIDATES,
    render_candidate,
    validate_candidate_gates,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_z.method_ablation import render_final_scene


def test_candidate_catalog_is_small_and_hypothesis_bound() -> None:
    assert tuple(item.candidate_id for item in CANDIDATES) == ("AA-C0", "AA-C1", "AA-C2", "AA-C3")
    assert all(item.global_gain_changed is False and item.fixed_tone_filler is False for item in CANDIDATES)


def test_c0_matches_current_stage_z_final_and_passes_hard_gates() -> None:
    candidate = render_candidate("AA-C0", "full_load", duration_s=0.25)
    _raw, final, _monitor, _diag, _elapsed, _memory = render_final_scene("full_load_acceleration", 0.25)
    assert hashlib.sha256(candidate.raw_pcm.tobytes()).hexdigest() == hashlib.sha256(final.tobytes()).hexdigest()
    gates = validate_candidate_gates(candidate)
    assert gates["finite"] and gates["clipping"] == 0 and gates["click"] is True
    assert gates["ptr_radiation_track_p_unchanged"] is True
    assert gates["raw_monitor_separated"] is True


def test_c2_changes_only_local_event_body_and_preserves_hard_gates() -> None:
    candidate = render_candidate("AA-C2", "full_load", duration_s=0.25)
    assert candidate.raw_pcm.shape[1] == 2
    assert candidate.parameter_consumed is True
    gates = validate_candidate_gates(candidate)
    assert gates["finite"] and gates["clipping"] == 0 and gates["click"] is True
    assert gates["wrong_condition_afterfire"] == 0
    assert gates["global_gain_changed"] is False
