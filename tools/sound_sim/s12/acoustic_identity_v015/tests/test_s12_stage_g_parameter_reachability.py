from __future__ import annotations

from pathlib import Path

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.render_drive_cycle_v10 import build_drive_cycle_trace
from tools.sound_sim.s12.acoustic_identity_v015.stage_g.candidate_profiles import load_stage_g_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_g.parameter_reachability import audit_candidate_parameter_reachability
from tools.sound_sim.s12.acoustic_identity_v015.stage_g.render_candidate import render_stage_g_candidate


ROOT = Path(__file__).resolve().parents[1]


def test_every_public_stage_g_parameter_has_a_deterministic_effect() -> None:
    for filename, vehicle_id in (
        ("Ferrari_candidate_v4.json", "ferrari_458"),
        ("Hellcat_candidate_v4.json", "hellcat"),
        ("RX7_candidate_v4.json", "rx7_fd"),
    ):
        profile = load_stage_g_candidate(ROOT / "targets" / "stage_g_candidates" / filename)
        trace = build_drive_cycle_trace(vehicle_id, duration_s=2.0)
        evidence = audit_candidate_parameter_reachability(profile, trace)
        assert evidence["requested"] == evidence["consumed"]
        assert evidence["unused"] == []
        assert evidence["parameters"]
        assert all(float(item["target_l2_delta"]) > 1e-8 for item in evidence["parameters"])


def test_parameter_audit_does_not_claim_a_dead_field() -> None:
    profile = load_stage_g_candidate(ROOT / "targets" / "stage_g_candidates" / "Ferrari_candidate_v4.json")
    trace = build_drive_cycle_trace("ferrari_458", duration_s=2.0)
    evidence = audit_candidate_parameter_reachability(profile, trace)
    assert not evidence["unused"]
