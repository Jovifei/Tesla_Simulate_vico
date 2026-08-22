from __future__ import annotations

from pathlib import Path

from tools.sound_sim.s12.real_reference.baseline import build_stage_r_waiting_result
from tools.sound_sim.s12.real_reference.closed_loop_report import write_waiting_final_report
from tools.sound_sim.s12.real_reference.feedback import write_stage_s_waiting_outputs
from tools.sound_sim.s12.real_reference.handoff import build_stage_t_waiting_gate
from tools.sound_sim.s12.real_reference.inventory import build_inventory


def test_waiting_report_does_not_claim_completion(tmp_path: Path) -> None:
    q = build_inventory(Path("E:/does-not-exist/s12-stage-q"))
    r = build_stage_r_waiting_result(q)
    s_paths = write_stage_s_waiting_outputs(q, r, tmp_path / "s")
    import json

    s = json.loads(s_paths["gate"].read_text(encoding="utf-8"))
    t = build_stage_t_waiting_gate(q, r, s)
    report = write_waiting_final_report(q, r, s, t, tmp_path / "S12_Real_Sound_Closed_Loop_Final_Report.md", branch="test", commit="abc", working_tree_dirty=False)
    text = report.read_text(encoding="utf-8")
    assert "WAITING_FOR_REAL_REFERENCE_DATA" in text
    assert "approved_profile_candidate/`：未生成" in text
    assert "闭环已完成" in text
    assert "APPROVED_PROFILE" not in text
