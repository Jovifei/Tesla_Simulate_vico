from __future__ import annotations

import pytest

from tools.sound_sim.s12.real_reference.stage_u_grid import (
    StageUGridError,
    candidate_grid_specs,
    validate_rendered_candidate_record,
)


def test_stage_u_grid_has_real_bounded_candidates_for_each_vehicle() -> None:
    for vehicle_id in ("ferrari_458", "hellcat", "rx7_fd"):
        candidates = candidate_grid_specs(vehicle_id)
        assert 1 < len(candidates) <= 64
        assert len({item["candidate_id"] for item in candidates}) == len(candidates)
        assert all(item["parameter_values"] for item in candidates)


def _record() -> dict:
    return {
        "parent_sha256": "a" * 64,
        "candidate_sha256": "b" * 64,
        "pcm_sha256": "c" * 64,
        "trace_sha256": "d" * 64,
        "finite_pcm": True,
        "clipping_count": 0,
        "wrong_condition_event_count": 0,
        "requested_parameters": ["source.metallic_gain_scale"],
        "consumed_parameters": ["source.metallic_gain_scale"],
        "package_integrity": True,
        "non_target_vehicle_sha_unchanged": True,
    }


def test_grid_record_rejects_parent_candidate_identity() -> None:
    record = _record(); record["candidate_sha256"] = record["parent_sha256"]
    with pytest.raises(StageUGridError, match="Parent/Candidate"):
        validate_rendered_candidate_record(record)


def test_grid_record_rejects_unused_parameter_and_wrong_condition_event() -> None:
    record = _record(); record["consumed_parameters"] = []
    with pytest.raises(StageUGridError, match="consumed"):
        validate_rendered_candidate_record(record)
    record = _record(); record["wrong_condition_event_count"] = 1
    with pytest.raises(StageUGridError, match="wrong-condition"):
        validate_rendered_candidate_record(record)
