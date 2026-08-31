"""TDD tests for the local Stage-V Chinese listening package."""

from __future__ import annotations

from tools.sound_sim.s12.acoustic_identity_v015.stage_v.publish import (
    publish_hellcat_vertical_slice,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_v.review_package import (
    build_stage_v_review_package,
    validate_stage_v_review_package,
)


def test_review_package_binds_parent_candidate_monitor_and_blind_stimuli(tmp_path) -> None:
    source = tmp_path / "stage_v"
    publish_hellcat_vertical_slice(source, duration_s=0.25)
    package = build_stage_v_review_package(source, tmp_path / "review")
    assert package["status"] == "WAITING_FOR_JOVI_HELLCAT_REVIEW"
    assert package["reference_status"] == "REFERENCE_POINTER_ONLY"
    assert validate_stage_v_review_package(tmp_path / "review") == []
    assert (tmp_path / "review" / "README_ZH.md").is_file()
    assert (tmp_path / "review" / "blind_manifest.json").is_file()
    assert (tmp_path / "review" / "blind_key_external.json").is_file()
