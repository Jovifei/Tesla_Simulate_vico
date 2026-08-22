from __future__ import annotations

import json
from pathlib import Path

from tools.sound_sim.s12.real_reference.baseline import build_stage_r_waiting_result
from tools.sound_sim.s12.real_reference.feedback import write_stage_s_waiting_outputs
from tools.sound_sim.s12.real_reference.handoff import write_stage_t_waiting_outputs
from tools.sound_sim.s12.real_reference.inventory import build_inventory


def test_stage_t_does_not_create_profile_candidate(tmp_path: Path) -> None:
    q_inventory = build_inventory(Path("E:/does-not-exist/s12-stage-q"))
    r_result = build_stage_r_waiting_result(q_inventory)
    s_paths = write_stage_s_waiting_outputs(q_inventory, r_result, tmp_path / "s")
    s_gate = json.loads(s_paths["gate"].read_text(encoding="utf-8"))
    outputs = write_stage_t_waiting_outputs(q_inventory, r_result, s_gate, tmp_path / "t")
    gate = json.loads(outputs["gate"].read_text(encoding="utf-8"))
    assert gate["status"] == "BLOCKED_PROFILE_CANDIDATE_NOT_READY"
    assert gate["profile_candidate_ready"] is False
    assert gate["profile_freeze_authorized"] is False
    assert not (tmp_path / "t" / "approved_profile_candidate").exists()
