import csv
import json
from pathlib import Path

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_e.blind_audition import validate_stage_e_responses


def test_blind_responses_require_complete_playback_context(tmp_path):
    response = tmp_path / "responses.csv"
    response.write_text("trial_id,guessed_vehicle_id,confidence_1_5,identity_strength_1_5,realism_1_5,artifact_freedom_1_5\n", encoding="utf-8")
    context = tmp_path / "context.json"
    context.write_text(json.dumps({"playback_device": ""}), encoding="utf-8")
    with pytest.raises(ValueError, match="playback context"):
        validate_stage_e_responses(response, context)


def test_blind_response_count_is_exact(tmp_path):
    response = tmp_path / "responses.csv"
    response.write_text("package_id,listener_id,round_id,trial_id,guessed_vehicle_id,confidence_1_5,identity_strength_1_5,realism_1_5,artifact_freedom_1_5,notes\n", encoding="utf-8")
    context = tmp_path / "context.json"
    context.write_text(json.dumps({k: (40 if k == "windows_volume_percent" else "x") for k in ("playback_device", "headphones_or_speakers", "windows_volume_percent", "player", "eq_enabled", "spatial_audio_enabled", "environment", "start_time", "completion_time")}), encoding="utf-8")
    with pytest.raises(ValueError, match="30"):
        validate_stage_e_responses(response, context)
