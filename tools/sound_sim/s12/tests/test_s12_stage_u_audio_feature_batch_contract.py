from __future__ import annotations

from pathlib import Path


def test_audio_feature_batch_treats_candidate_id_as_optional_for_reference_and_parent_rows() -> None:
    source = (Path(__file__).parents[1] / "real_reference" / "run_stage_u_audio_feature_batch.m").read_text(encoding="utf-8")

    assert "isfield(clip, 'candidate_id')" in source
