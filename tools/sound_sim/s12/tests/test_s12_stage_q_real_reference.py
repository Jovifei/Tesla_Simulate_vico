from __future__ import annotations

import json
import wave
from pathlib import Path

from tools.sound_sim.s12.real_reference.inventory import (
    ALL_VEHICLES,
    ANCHOR_VEHICLES,
    CATALOG,
    build_inventory,
    write_stage_q_outputs,
)


def _write_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(48_000)
        wav.writeframes(b"\x00\x00" * 48_000)


def test_catalog_contains_eight_vehicles_and_three_anchors() -> None:
    assert set(item["vehicle_id"] for item in CATALOG) == set(ALL_VEHICLES)
    assert ANCHOR_VEHICLES == ("ferrari_458", "hellcat", "rx7_fd")


def test_unverified_reference_is_fail_closed(tmp_path: Path) -> None:
    _write_wav(tmp_path / "ferrari_458_accel.wav")
    inventory = build_inventory(tmp_path)
    ferrari = next(row for row in inventory["recordings"] if row["recording_id"] == "ferrari_458_accel")
    assert ferrari["file_present"] is True
    assert ferrari["sha256"]
    assert ferrari["evidence"]["level"] == "R3"
    assert ferrari["evidence"]["r1_eligible"] is False
    assert ferrari["evidence"]["automatic_tuning_eligible"] is False
    assert "synchronized_rpm_trace" in ferrari["required_missing"]
    assert inventory["status"] == "REAL_REFERENCE_DATASET_LIMITED"
    assert inventory["stop_state"] == "WAITING_FOR_REAL_REFERENCE_DATA"


def test_outputs_do_not_copy_raw_audio(tmp_path: Path) -> None:
    _write_wav(tmp_path / "ferrari_458_accel.wav")
    out_dir = tmp_path / "out"
    inventory = build_inventory(tmp_path)
    outputs = write_stage_q_outputs(inventory, out_dir)
    assert outputs["report"].exists()
    assert outputs["manifest"].exists()
    assert not list(out_dir.rglob("*.wav"))
    manifest = json.loads(outputs["manifest"].read_text(encoding="utf-8"))
    assert manifest["raw_audio_policy"] == "external_only_not_in_git"
    assert "unmapped_external_media" in manifest
    ferrari = next(row for row in manifest["recordings"] if row["recording_id"] == "ferrari_458_accel")
    assert ferrari["external_path"].endswith("ferrari_458_accel.wav")


def test_manifest_schema_matches_stage_q_contract() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "real_reference" / "schemas" / "stage_q_reference_manifest.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["$id"] == "s12-stage-q-reference-database-v2"
    assert schema["properties"]["status"]["enum"] == ["REAL_REFERENCE_DATASET_READY", "REAL_REFERENCE_DATASET_LIMITED"]
