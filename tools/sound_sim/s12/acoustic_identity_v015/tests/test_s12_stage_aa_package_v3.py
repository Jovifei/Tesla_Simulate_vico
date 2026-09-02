from __future__ import annotations

from tools.sound_sim.s12.acoustic_identity_v015.stage_aa.package_v3 import build_stage_aa_package, validate_stage_aa_package


def test_stage_aa_package_v3_has_required_views_and_blind_dynamic_page(tmp_path) -> None:
    root = tmp_path / "s12-stage-aa-hellcat-quality-v3"
    manifest = build_stage_aa_package(root, duration_s=0.25, hot_idle_duration_s=0.25, main_head="main", tested_head="tested")
    assert manifest["schema"] == "s12.stage_aa.audition_package.v3"
    assert manifest["selected_candidate"] == "AA-C3"
    assert len(manifest["scenes"]) == 11
    assert validate_stage_aa_package(root) == []
    dynamic = (root / "dynamic_review.html").read_text(encoding="utf-8")
    assert "Stage-Z" not in dynamic and "AA-C3" not in dynamic
    answers = (root / "answers_manifest.html").read_text(encoding="utf-8")
    assert "Stage-Z" in answers and "AA-C3" in answers
    assert (root / "reference_diagnostic.json").is_file()
    assert (root / "timbre_review.html").is_file()
    assert (root / "dynamic_review.html").is_file()
