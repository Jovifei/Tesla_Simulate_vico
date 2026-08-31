from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.sound_sim.s12.real_reference.baseline import write_stage_r_waiting_outputs
from tools.sound_sim.s12.real_reference.inventory import build_inventory
from tools.sound_sim.s12.real_reference.qualification import ReferenceQualificationError, qualify_r1_reference, qualify_r2_reference, require_r1_reference


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


def test_r2_gate_is_limited_and_never_tuning_authority() -> None:
    record = {
        "recording_id": "ferrari_r2",
        "vehicle_id": "ferrari_458",
        "scenario": "acceleration",
        "file_present": True,
        "sha256": "a" * 64,
        "provenance": {"legal_permission": "CONFIRMED"},
    }
    gate = qualify_r2_reference(record)
    assert gate["eligible"] is True
    assert gate["qualification"] == "R2"
    assert "spectrum" in gate["allowed_metric_groups"]
    assert gate["order_hard_gate"] is False
    assert gate["rpm_synchronised_automatic_tuning"] is False
    assert gate["automatic_tuning_eligible"] is False


def test_r1_gate_requires_auditable_raw_source_and_capture_contract() -> None:
    gate = qualify_r1_reference(
        {
            "recording_id": "r1-incomplete-source-contract",
            "vehicle_id": "ferrari_458",
            "scenario": "full_pull",
            "file_present": True,
            "sha256": "a" * 64,
            "audio": {"codec": "PCM", "sample_rate_hz": 48_000},
            "provenance": {
                "legal_permission": "CONFIRMED",
                "stock_identity": "VERIFIED_EXACT_TRIM",
                "microphone_perspective": "EXTERIOR_REAR",
                "recording_device_agc": "DOCUMENTED_NO_AGC",
                "source_kind": "user_provided_url_video_extracted",
                "raw_audio_confirmed": True,
            },
            "analysis_contract": {
                "rpm_state_status": "SYNCED",
                "load_throttle_status": "SYNCED",
                "gear_shift_status": "SYNCED",
            },
        }
    )
    assert gate["eligible"] is False
    assert "source_and_license" in gate["missing"]
    assert "raw_audio_source" in gate["missing"]
    assert "stock_exhaust_confirmation" in gate["missing"]
