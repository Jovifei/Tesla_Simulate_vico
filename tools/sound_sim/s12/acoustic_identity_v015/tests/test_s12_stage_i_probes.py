from __future__ import annotations

from pathlib import Path

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.stage_i.candidate_profiles import load_stage_i_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_i.probes import build_stage_i_response_probe


def _profile_path() -> Path:
    return Path(__file__).resolve().parents[1] / "targets" / "stage_i_candidates" / "Hellcat_candidate_v6_A_Balanced.json"


def test_probe_is_rendered_from_profile_and_content_addressed_deterministically() -> None:
    profile = load_stage_i_candidate(_profile_path())

    first = build_stage_i_response_probe("I6-A Balanced", profile)
    second = build_stage_i_response_probe("I6-A Balanced", profile)

    evidence = first["evidence"]
    assert evidence == second["evidence"]
    assert evidence["candidate_label"] == "I6-A Balanced"
    assert evidence["candidate_id"] == profile.candidate_id
    assert len(evidence["candidate_sha256"]) == 64
    assert len(evidence["profile_sha256"]) == 64
    assert set(evidence["probes"]) == {"boost", "lift"}
    for probe_name in ("boost", "lift"):
        assert len(evidence["probes"][probe_name]["trace_sha256"]) == 64
        assert len(evidence["probes"][probe_name]["render_sha256"]) == 64
        assert all(len(value) == 64 for value in evidence["probes"][probe_name]["stem_sha256"].values())
    for key in ("boost_response", "boost_command", "bypass_response", "bypass_gate"):
        assert np.array_equal(first[key], second[key])
        assert len(evidence["array_sha256"][key]) == 64


def test_probe_candidate_label_is_fail_closed() -> None:
    profile = load_stage_i_candidate(_profile_path())
    with np.testing.assert_raises(ValueError):
        build_stage_i_response_probe("", profile)
