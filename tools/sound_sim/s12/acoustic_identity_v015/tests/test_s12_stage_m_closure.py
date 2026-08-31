from pathlib import Path

from tools.sound_sim.s12.acoustic_identity_v015.stage_m.closure import write_automated_closure


def test_automated_closure_is_waiting_for_named_review(tmp_path: Path) -> None:
    vehicles = ["ferrari_458", "hellcat", "rx7_fd", "supra_jza80", "aventador_lp700", "c63_w204", "gtr_r35", "lfa"]
    comparison = {"vehicles": {vehicle: {"comparison_kind": "synthetic_parent_to_candidate_internal_regression_only", "spectral": {"log_distance": 0.1}, "uncertainty": {"external_reference_missing": True}} for vehicle in vehicles}}
    write_automated_closure(tmp_path, comparison, feedback_schema={"type": "object"}, review_package_root=Path("review-package"))
    assert (tmp_path / "S12_Stage_M_Qualification_Callgraph.md").is_file()
    assert "WAITING_FOR_JOVI_NAMED_REVIEW" in (tmp_path / "S12_Stage_M_Round2_Qualification_Report.md").read_text()
