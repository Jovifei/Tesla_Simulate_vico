"""TDD gates for Ferrari flat-plane and RX-7 rotary event-domain paths."""

from __future__ import annotations

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_v.pipeline import render_stage_v_case
from tools.sound_sim.s12.acoustic_identity_v015.stage_v.publish import publish_three_vehicle_slices
from tools.sound_sim.s12.acoustic_identity_v015.stage_v.review_package import (
    build_three_vehicle_review_package,
    validate_three_vehicle_review_package,
)


def test_ferrari_event_domain_slice_is_finite_and_distinct() -> None:
    result = render_stage_v_case("ferrari_458_v1", "full_load_acceleration", duration_s=0.35)
    assert result.candidate.pressure.shape[1] == 2
    assert np.all(np.isfinite(result.candidate.pressure))
    assert not np.array_equal(result.parent.pressure, result.candidate.pressure)
    assert result.diagnostics["source_model"] == "event_domain_v1"


def test_rx7_rotary_event_width_and_housing_parameters_are_reachable() -> None:
    config = load_config("rx7_fd_v1")
    for name in ("rotary_event_width_scale", "rotary_event_gain_scale", "housing_gain_scale", "housing_decay_scale", "housing_order_mix", "primary_spool_tau", "secondary_spool_tau", "blow_off_gain", "blow_off_decay"):
        assert name in config
    baseline = render_stage_v_case("rx7_fd_v1", "steady_1500_2500rpm", duration_s=0.35)
    changed = render_stage_v_case("rx7_fd_v1", "steady_1500_2500rpm", duration_s=0.35, candidate_overrides={"rotary_event_width_scale": 1.5, "housing_gain_scale": 0.35, "housing_decay_scale": 0.45, "blow_off_decay": 0.40})
    assert not np.array_equal(baseline.candidate.pressure, changed.candidate.pressure)
    assert "housing" in changed.candidate.stems
    assert "blowoff" in changed.candidate.stems


def test_three_vehicle_publication_reopens_all_slices(tmp_path) -> None:
    result = publish_three_vehicle_slices(tmp_path / "three_vehicle", duration_s=0.25)
    assert result["status"] == "EVENT_DOMAIN_THREE_VEHICLE_CANDIDATES_READY"
    for vehicle_id in ("hellcat_v1", "ferrari_458_v1", "rx7_fd_v1"):
        root = tmp_path / "three_vehicle" / vehicle_id
        assert (root / "manifest.json").is_file()
        assert (root / "hot_idle_20s" / "event_candidate_raw.wav").is_file()


def test_three_vehicle_review_package_keeps_raw_monitor_and_blind_keys_separate(tmp_path) -> None:
    source = tmp_path / "three_vehicle"
    publish_three_vehicle_slices(source, duration_s=0.25)
    package = build_three_vehicle_review_package(source, tmp_path / "review")
    assert package["status"] == "WAITING_FOR_JOVI_THREE_VEHICLE_REVIEW"
    assert validate_three_vehicle_review_package(tmp_path / "review") == []
