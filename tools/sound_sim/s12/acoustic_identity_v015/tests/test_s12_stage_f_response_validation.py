import csv
import json
from pathlib import Path

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_f.package_builder import build_stage_f_package
from tools.sound_sim.s12.acoustic_identity_v015.stage_f.response_contract import validate_stage_f_submission


def test_stage_f_rejects_incomplete_submission(tmp_path):
    result = build_stage_f_package(tmp_path / "package", seed=7, duration_s=1.0)
    root = Path(result["output_root"])
    with pytest.raises(ValueError, match="playback context"):
        validate_stage_f_submission(
            root / "listener" / "listener_manifest.json",
            root / "listener" / "blind_responses.csv",
            root / "listener" / "ab_responses.csv",
            root / "listener" / "playback_context.json",
        )


def test_stage_f_prefilled_submission_can_be_completed(tmp_path):
    result = build_stage_f_package(tmp_path / "package", seed=7, duration_s=1.0)
    root = Path(result["output_root"])
    blind = root / "listener" / "blind_responses.csv"
    rows = list(csv.DictReader(blind.open(newline="", encoding="utf-8")))
    for row in rows:
        row.update({"guessed_vehicle_id": "unsure", "confidence_1_5": "3", "identity_strength_1_5": "3", "realism_1_5": "3", "artifact_freedom_1_5": "3", "notes": "test"})
    with blind.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    ab = root / "listener" / "ab_responses.csv"
    ab_rows = list(csv.DictReader(ab.open(newline="", encoding="utf-8")))
    for row in ab_rows:
        row.update({"preferred_option": "equal", "low_frequency_naturalness_1_5": "3", "afterfire_naturalness_1_5": "3", "artifact_blocker": "false", "notes": "test"})
    with ab.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=ab_rows[0].keys()); writer.writeheader(); writer.writerows(ab_rows)
    context = root / "listener" / "playback_context.json"
    context.write_text(json.dumps({"package_id": result["package_id"], "listener_id": "jovi", "playback_device": "test", "headphones_or_speakers": "headphones", "windows_volume_percent": 40, "player": "test", "eq_enabled": False, "spatial_audio_enabled": False, "environment": "quiet", "start_time": "2026-08-10T10:00:00+08:00", "completion_time": "2026-08-10T10:10:00+08:00"}), encoding="utf-8")
    submission = validate_stage_f_submission(root / "listener" / "listener_manifest.json", blind, ab, context)
    assert len(submission.blind_rows) == 30
    assert len(submission.pair_rows) == 3
