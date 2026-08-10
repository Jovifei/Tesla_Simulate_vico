from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_g.response_contract import validate_stage_g_submission


def test_blank_prefilled_stage_g_forms_fail_closed(tmp_path: Path) -> None:
    manifest = {"package_id": "S12_Blind_Audition_Package_v4", "trials": [{"trial_id": f"R{1 + (i // 15)}_T{(i % 15) + 1:02d}", "round_id": 1 + (i // 15), "scene_id": "idle"} for i in range(30)]}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    blind_fields = ("package_id", "listener_id", "round_id", "trial_id", "guessed_vehicle_id", "confidence_1_5", "identity_strength_1_5", "realism_1_5", "artifact_freedom_1_5", "notes")
    with (tmp_path / "blind.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=blind_fields); writer.writeheader()
        for item in manifest["trials"]: writer.writerow({**{key: "" for key in blind_fields}, "package_id": manifest["package_id"], "listener_id": "jovi", "round_id": item["round_id"], "trial_id": item["trial_id"]})
    (tmp_path / "pairs.csv").write_text("", encoding="utf-8")
    (tmp_path / "context.json").write_text(json.dumps({"package_id": manifest["package_id"], "listener_id": "jovi"}), encoding="utf-8")
    with pytest.raises(ValueError, match="playback context"):
        validate_stage_g_submission(tmp_path / "manifest.json", tmp_path / "blind.csv", tmp_path / "pairs.csv", tmp_path / "context.json")

