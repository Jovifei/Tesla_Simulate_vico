from __future__ import annotations

import json
from pathlib import Path

from tools.sound_sim.s12.real_reference.r1_pilot import write_r1_pilot_outputs


def test_empty_hellcat_pilot_writes_all_waiting_artifacts(tmp_path: Path) -> None:
    output = tmp_path / "r1-pilot-report"
    paths = write_r1_pilot_outputs(tmp_path / "s12-r1-pilot", "hellcat_full_pull_01", output)
    expected = {
        "S12_R1_Pilot_Acquisition_Report.md",
        "r1_pilot_preflight.json",
        "rights_scope_validation.json",
        "state_sync_validation.json",
        "comparison_results.json",
        "parameter_recommendations.json",
        "feedback_gate.json",
    }
    assert expected <= {path.name for path in output.iterdir()}
    preflight = json.loads(paths["preflight"].read_text(encoding="utf-8"))
    comparison = json.loads(paths["comparison"].read_text(encoding="utf-8"))
    recommendations = json.loads(paths["recommendations"].read_text(encoding="utf-8"))
    assert preflight["status"] == "WAITING_FOR_R1_PILOT_DELIVERY"
    assert comparison["status"] == "NOT_RUN_WAITING_FOR_R1_PILOT"
    assert comparison["cases"] == []
    assert comparison["matlab_order_status"] == "NOT_RUN_WAITING_FOR_R1_PILOT"
    assert recommendations["status"] == "WITHHELD_MISSING_R1_PILOT"
    assert recommendations["recommendations"] == []
    assert recommendations["automatic_tuning_eligible"] is False
    assert recommendations["profile_candidate_ready"] is False
    report = paths["report"].read_text(encoding="utf-8")
    assert "WAITING_FOR_R1_PILOT_DELIVERY" in report
    assert "不复制" in report


def test_empty_pilot_does_not_materialize_audio_or_state(tmp_path: Path) -> None:
    output = tmp_path / "out"
    write_r1_pilot_outputs(tmp_path / "pilot", "hellcat_full_pull_01", output)
    assert not list(output.rglob("*.wav"))
    assert not list(output.rglob("*.flac"))
    assert not list(output.rglob("*.csv"))
