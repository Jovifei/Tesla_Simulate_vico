from __future__ import annotations

import json
from pathlib import Path

from tools.sound_sim.s12.real_reference.feedback import CHINESE_DIMENSIONS, write_stage_s_waiting_outputs
from tools.sound_sim.s12.real_reference.inventory import build_inventory
from tools.sound_sim.s12.real_reference.baseline import build_stage_r_waiting_result


def test_chinese_contract_has_required_dimensions_and_no_audio_placeholder(tmp_path: Path) -> None:
    q_inventory = build_inventory(Path("E:/does-not-exist/s12-stage-q"))
    r_result = build_stage_r_waiting_result(q_inventory)
    outputs = write_stage_s_waiting_outputs(q_inventory, r_result, tmp_path)
    contract = json.loads(outputs["contract"].read_text(encoding="utf-8"))
    gate = json.loads(outputs["gate"].read_text(encoding="utf-8"))
    labels = {row["id"]: row["label_zh"] for row in contract["dimensions"]}
    assert set(labels) == set(CHINESE_DIMENSIONS)
    assert labels["realism"] == "真实感"
    assert contract["audio_materialization"]["status"] == "NOT_MATERIALIZED"
    assert gate["status"] == "WAITING_FOR_JOVI_HUMAN_FEEDBACK"
    assert gate["profile_candidate_ready"] is False
    assert not list(tmp_path.rglob("*.wav"))
