"""Regression isolation and cross-vehicle configuration gates."""

from __future__ import annotations

import hashlib

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import (
    load_config,
)
from tools.sound_sim.s12.acoustic_identity_v015.sources.supercharged_hemi_source import (
    render_hellcat,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_v.scenarios import (
    build_stage_v_scenario_trace,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_v.pipeline import (
    render_stage_v_case,
)


def test_legacy_parent_is_deterministic_and_candidate_is_distinct() -> None:
    trace = build_stage_v_scenario_trace("hellcat_v1", "hot_idle_20s", duration_s=0.35)
    first = render_hellcat(trace)
    second = render_hellcat(trace)
    first_sha = hashlib.sha256(first.pressure.tobytes()).hexdigest()
    second_sha = hashlib.sha256(second.pressure.tobytes()).hexdigest()
    assert first_sha == second_sha
    candidate = render_stage_v_case("hellcat_v1", "hot_idle_20s", duration_s=0.35).candidate
    assert not np.array_equal(first.pressure * 0.25, candidate.pressure)


def test_rotary_configuration_is_not_forced_through_piston_firing_order() -> None:
    config = load_config("rx7_fd_v1")
    assert config["architecture"] == "rotary_wankel"
    assert config["cycle_definition"]["value"] in {"rotary_360", "rotary_1080"}
    evidence = config.get("firing_order_evidence", {})
    assert evidence.get("range") == "not_used_for_rotary"
    assert "not piston" in evidence.get("source", "")
