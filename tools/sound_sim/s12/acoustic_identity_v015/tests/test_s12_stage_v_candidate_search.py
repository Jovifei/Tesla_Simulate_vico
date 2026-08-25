"""TDD contracts for render/reopen/compare/rank candidate search."""

from __future__ import annotations

import json

from tools.sound_sim.s12.acoustic_identity_v015.stage_v.candidate_search import (
    run_hellcat_candidate_grid,
)


def test_candidate_grid_renders_reopens_and_withholds_selection_without_reference(tmp_path) -> None:
    result = run_hellcat_candidate_grid(tmp_path / "grid", duration_s=0.25)
    assert result["status"] == "REFERENCE_TARGET_MISSING"
    assert result["selected_candidates"] == []
    assert len(result["candidates"]) >= 3
    for candidate in result["candidates"]:
        assert candidate["rendered"] is True
        assert candidate["reopened"] is True
        assert candidate["raw_sha256"] != candidate["parent_sha256"]
    assert json.loads((tmp_path / "grid" / "candidate_grid_results.json").read_text(encoding="utf-8"))["status"] == "REFERENCE_TARGET_MISSING"
