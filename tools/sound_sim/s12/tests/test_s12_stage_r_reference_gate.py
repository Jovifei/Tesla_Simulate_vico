from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.sound_sim.s12.real_reference.baseline import write_stage_r_waiting_outputs
from tools.sound_sim.s12.real_reference.inventory import build_inventory
from tools.sound_sim.s12.real_reference.qualification import ReferenceQualificationError, require_r1_reference


def test_unqualified_reference_cannot_enter_stage_r() -> None:
    inventory = build_inventory(Path("E:/does-not-exist/s12-stage-q"))
    record = next(row for row in inventory["recordings"] if row["recording_id"] == "ferrari_458_accel")
    with pytest.raises(ReferenceQualificationError, match="not R1-eligible"):
        require_r1_reference(record)


def test_stage_r_waiting_outputs_withhold_recommendations(tmp_path: Path) -> None:
    inventory = build_inventory(Path("E:/does-not-exist/s12-stage-q"))
    outputs = write_stage_r_waiting_outputs(inventory, tmp_path)
    result = json.loads(outputs["results"].read_text(encoding="utf-8"))
    recommendations = json.loads(outputs["recommendations"].read_text(encoding="utf-8"))
    assert result["status"] == "BLOCKED_REFERENCE_QUALIFICATION"
    assert result["stop_state"] == "WAITING_FOR_REAL_REFERENCE_DATA"
    assert result["qualified_cases"] == []
    assert recommendations["status"] == "WITHHELD_MISSING_R1_REFERENCE"
    assert recommendations["recommendations"] == []
