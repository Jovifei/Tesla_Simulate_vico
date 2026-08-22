from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path

import jsonschema

from tools.sound_sim.s12.real_reference.inventory import (
    ALL_VEHICLES,
    ANCHOR_VEHICLES,
    CATALOG,
    build_inventory,
    write_stage_q_outputs,
)
from tools.sound_sim.s12.real_reference.qualification import qualify_r2_reference


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


def test_additional_external_roots_are_audited_but_not_mapped(tmp_path: Path) -> None:
    primary = tmp_path / "primary"
    extra = tmp_path / "extra"
    primary.mkdir()
    extra.mkdir()
    _write_wav(primary / "ferrari_458_accel.wav")
    _write_wav(extra / "old-public-candidate.wav")
    inventory = build_inventory(primary, additional_media_roots=(extra,))
    assert str(extra) in inventory["audited_external_roots"]
    assert not any(row["external_path"].endswith("old-public-candidate.wav") for row in inventory["recordings"])
    unmapped = next(row for row in inventory["unmapped_external_media"] if row["external_path"].endswith("old-public-candidate.wav"))
    assert unmapped["audit_root"] == str(extra)
    assert unmapped["use_policy"] == "DO_NOT_ANALYZE_OR_TUNE"


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


def test_web_authorized_manifest_is_explicitly_r2_only() -> None:
    manifest_path = (
        Path(__file__).resolve().parents[4]
        / "tasks"
        / "reports"
        / "runtime"
        / "s12-stage-q-real-reference"
        / "reference_database_v2"
        / "web_authorized_manifest_20260822.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "s12-stage-q-web-authorized-r2-v1"
    assert len(manifest["recordings"]) == 3
    for record in manifest["recordings"]:
        gate = qualify_r2_reference(record)
        assert gate["eligible"] is True
        assert gate["qualification"] == "R2"
        assert record["provenance"]["legal_permission"] == "CONFIRMED"
        assert record["evidence"]["r1_eligible"] is False
        assert record["evidence"]["automatic_tuning_eligible"] is False
        assert record["analysis_contract"]["rpm_state_status"] == "MISSING_RPM_STATE"
    assert manifest["qualitative_only"][0]["evidence_level"] == "R3"
    pontiac = next(row for row in manifest["qualitative_only"] if row["recording_id"] == "web_pontiac_g8_dyno_cc0_2019")
    assert pontiac["vehicle_id"] == "pontiac_g8_non_target"
    assert pontiac["license"] == "CC0 1.0"
    assert pontiac["video_metadata"]["audio_sample_rate_hz"] == 48_000
    assert pontiac["analysis_observation"]["tachometer_or_numeric_rpm_visible"] is False
    assert pontiac["analysis_observation"]["rpm_status"] == "MISSING_RPM_STATE"
    assert pontiac["use_policy"] == "dyno_process_qualitative_only"


def test_authorized_r2_manifest_merges_into_canonical_stage_q_without_copying_audio(tmp_path: Path) -> None:
    primary = tmp_path / "primary"
    primary.mkdir()
    _write_wav(primary / "ferrari_458_accel.wav")
    r2_audio = tmp_path / "r2" / "ferrari_458_goodwood.wav"
    r2_audio.parent.mkdir()
    _write_wav(r2_audio)
    r2_record = {
        "recording_id": "web_ferrari_458_goodwood_2010",
        "reference_id": "q:web:ferrari_458_goodwood_2010",
        "vehicle_id": "ferrari_458",
        "scenario": "acceleration",
        "external_path": str(r2_audio),
        "file_present": True,
        "sha256": hashlib.sha256(r2_audio.read_bytes()).hexdigest(),
        "audio": {"container": "WAV", "codec": "PCM", "channels": 1, "sample_rate_hz": 48_000, "sample_width_bits": 16, "frames": 48_000, "duration_s": 1.0},
        "provenance": {
            "source_url": "https://commons.wikimedia.org/wiki/File:Example.ogg",
            "source_kind": "wikimedia_commons_cc",
            "legal_permission": "CONFIRMED",
            "rights_evidence": "https://commons.wikimedia.org/wiki/File:Example.ogg",
        },
        "evidence": {"level": "R2", "r1_eligible": False, "r2_eligible": True, "automatic_tuning_eligible": False},
        "analysis_contract": {
            "analysis_signal": "unaltered_analysis_signal",
            "rpm_state_status": "MISSING_RPM_STATE",
            "load_throttle_status": "MISSING",
            "gear_shift_status": "MISSING",
        },
    }
    manifest = tmp_path / "authorized_r2.json"
    manifest.write_text(json.dumps({"raw_media_root": str(r2_audio.parent), "recordings": [r2_record]}), encoding="utf-8")

    inventory = build_inventory(primary, authorized_reference_manifests=(manifest,))
    merged = next(row for row in inventory["recordings"] if row["recording_id"] == r2_record["recording_id"])
    assert merged["evidence"]["level"] == "R2"
    assert merged["evidence"]["r2_eligible"] is True
    assert merged["evidence"]["r1_eligible"] is False
    ferrari = next(row for row in inventory["evidence_matrix"]["vehicles"] if row["vehicle_id"] == "ferrari_458")
    assert ferrari["r2_eligible_count"] == 1
    assert str(r2_audio.parent) in inventory["audited_external_roots"]

    outputs = write_stage_q_outputs(inventory, tmp_path / "out")
    assert not list((tmp_path / "out").rglob("*.wav"))
    canonical = json.loads(outputs["manifest"].read_text(encoding="utf-8"))
    canonical_row = next(row for row in canonical["recordings"] if row["recording_id"] == r2_record["recording_id"])
    assert canonical_row["evidence"]["level"] == "R2"
    assert canonical_row["integrity_check"]["status"] == "MATCH"


def test_authorized_r2_manifest_sha_mismatch_is_not_eligible(tmp_path: Path) -> None:
    primary = tmp_path / "primary"
    primary.mkdir()
    r2_audio = tmp_path / "r2" / "ferrari_458_bad_hash.wav"
    r2_audio.parent.mkdir()
    _write_wav(r2_audio)
    record = {
        "recording_id": "web_ferrari_458_bad_hash",
        "vehicle_id": "ferrari_458",
        "scenario": "acceleration",
        "external_path": str(r2_audio),
        "file_present": True,
        "sha256": "a" * 64,
        "provenance": {
            "legal_permission": "CONFIRMED",
            "rights_evidence": "receipt",
        },
    }
    manifest = tmp_path / "authorized_r2_bad_hash.json"
    manifest.write_text(json.dumps({"recordings": [record]}), encoding="utf-8")
    inventory = build_inventory(primary, authorized_reference_manifests=(manifest,))
    merged = next(row for row in inventory["recordings"] if row["recording_id"] == record["recording_id"])
    assert merged["integrity_check"]["status"] == "MISMATCH"
    assert merged["file_present"] is False
    assert merged["evidence"]["r2_eligible"] is False


def test_external_raw_r1_manifest_merges_into_stage_q_outputs(tmp_path: Path) -> None:
    primary = tmp_path / "primary"
    primary.mkdir()
    _write_wav(primary / "ferrari_458_accel.wav")
    raw_audio = tmp_path / "raw" / "ferrari_458_r1.wav"
    raw_audio.parent.mkdir()
    _write_wav(raw_audio)
    raw_record = {
        "recording_id": "ferrari_458_r1_external",
        "reference_id": "r1:ferrari_458_r1_external",
        "vehicle_id": "ferrari_458",
        "scenario": "full_pull",
        "scenario_hint": "full_pull",
        "external_path": str(raw_audio),
        "relative_path": raw_audio.name,
        "sha256": "a" * 64,
        "file_present": True,
        "audio": {"container": "WAV", "codec": "PCM", "channels": 1, "sample_rate_hz": 48_000, "sample_width_bits": 16, "frames": 48_000, "duration_s": 1.0},
        "provenance": {"source_url": "https://example.com/raw", "source_kind": "controlled_raw_audio", "legal_permission": "CONFIRMED", "rights_evidence": "receipt", "stock_identity": "VERIFIED_EXACT_TRIM", "stock_exhaust_confirmation": "CONFIRMED_STOCK", "microphone_perspective": "EXTERIOR_REAR", "recording_device_agc": "DOCUMENTED_NO_AGC", "raw_audio_confirmed": True, "raw_media_stored_outside_git": True},
        "evidence": {"level": "R1", "r1_eligible": True, "r2_eligible": True, "automatic_tuning_eligible": False, "order_hard_gate": True, "reason": "R1 contract passed"},
        "required_missing": [],
        "analysis_contract": {"analysis_signal": "unaltered_analysis_signal", "rpm_state_status": "SYNCED", "load_throttle_status": "SYNCED", "gear_shift_status": "SYNCED"},
        "state_bindings": {"time_window": {"start_s": 0.0, "end_s": 0.999}, "rpm_trace_path": str(tmp_path / "raw" / "rpm.csv"), "load_throttle_trace_path": str(tmp_path / "raw" / "load.csv"), "gear_shift_trace_path": str(tmp_path / "raw" / "gear.csv"), "raw_trace_sha256": {"rpm_trace_path": "b" * 64, "load_throttle_trace_path": "c" * 64, "gear_shift_trace_path": "d" * 64}, "synchronization": "timestamp_bound_state_traces"},
    }
    raw_manifest = tmp_path / "raw_manifest.json"
    raw_manifest.write_text(json.dumps({"records": [raw_record], "allowed_download_root": str(tmp_path / "raw")}, ensure_ascii=False), encoding="utf-8")

    inventory = build_inventory(primary, raw_reference_manifests=(raw_manifest,))
    merged = next(row for row in inventory["recordings"] if row["recording_id"] == raw_record["recording_id"])
    assert merged["evidence"]["r1_eligible"] is True
    assert merged["vehicle_name_zh"] == "法拉利 458"
    assert merged["scenario_hint"] == "full_pull"
    out_dir = tmp_path / "out"
    outputs = write_stage_q_outputs(inventory, out_dir)
    canonical_manifest = json.loads(outputs["manifest"].read_text(encoding="utf-8"))
    schema = json.loads((Path(__file__).resolve().parents[1] / "real_reference" / "schemas" / "stage_q_reference_manifest.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(canonical_manifest)
    bindings = json.loads(outputs["rpm_state_bindings"].read_text(encoding="utf-8"))
    binding = next(row for row in bindings if row["recording_id"] == raw_record["recording_id"])
    assert binding["status"] == "SYNCED"
    segments = json.loads(outputs["scenario_segments"].read_text(encoding="utf-8"))
    segment = next(row for row in segments if row["recording_id"] == raw_record["recording_id"])
    assert segment["start_s"] == 0.0
    assert segment["end_s"] == 0.999
    assert not list(out_dir.rglob("*.wav"))
