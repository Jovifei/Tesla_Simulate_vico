"""RED tests for the local Stage-W architecture review package."""

from __future__ import annotations

import json

from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import run_hellcat_bakeoff
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.review_package import (
    build_stage_w_review_package,
    validate_stage_w_review_package,
)


def test_review_package_keeps_reference_and_unavailable_paths_fail_closed(tmp_path) -> None:
    bakeoff = tmp_path / "bakeoff"
    package = tmp_path / "package"
    run_hellcat_bakeoff(bakeoff, duration_s=0.25)

    result = build_stage_w_review_package(bakeoff, package)

    assert result["status"] == "WAITING_FOR_JOVI_ARCHITECTURE_REVIEW"
    assert result["selected_architecture"] is None
    assert result["reference_status"] == "REFERENCE_POINTER_ONLY"
    assert result["long_window"] is False
    assert result["scene_duration_s"]["complete_cycle_60s"] == 0.25
    assert validate_stage_w_review_package(package) == []
    assert (package / "vehicles" / "hellcat" / "P3" / "complete_cycle_60s" / "raw_source.wav").is_file()
    assert (package / "vehicles" / "hellcat" / "P3" / "complete_cycle_60s" / "post_ptr_raw.wav").is_file()
    assert (package / "vehicles" / "hellcat" / "P3" / "complete_cycle_60s" / "monitor.wav").is_file()
    assert (package / "vehicles" / "hellcat" / "P5" / "complete_cycle_60s" / "post_ptr_raw.wav").is_file()
    reference = json.loads((package / "reference_pointer.json").read_text(encoding="utf-8"))
    assert reference["status"] == "REFERENCE_TARGET_MISSING"
    assert reference["selection_allowed"] is False
    unavailable = json.loads((package / "unavailable_paths.json").read_text(encoding="utf-8"))
    assert unavailable["P4"]["status"] == "REFERENCE_RECORDING_RIGHTS_PENDING"
    assert unavailable["P6"]["status"] == "TEACHER_NOT_RUNTIME_CANDIDATE"
