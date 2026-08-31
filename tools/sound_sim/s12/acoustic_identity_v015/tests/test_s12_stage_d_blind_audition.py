from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_d.blind_audition import build_blind_package, score_blind_responses


def test_blind_package_has_no_vehicle_labels_in_listener_tree(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    manifest = source / "manifest.json"
    manifest.write_text(json.dumps({"trials": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="trials"):
        build_blind_package(source, manifest, tmp_path / "package", seed=7)


def test_response_scorer_rejects_duplicate_trial(tmp_path: Path) -> None:
    key = tmp_path / "key.json"
    key.write_text(json.dumps({"trials": {"R1_T01": "ferrari_458"}}), encoding="utf-8")
    responses = tmp_path / "responses.csv"
    with responses.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["trial_id", "guessed_vehicle_id", "confidence_1_5", "identity_strength_1_5", "realism_1_5", "artifact_freedom_1_5"])
        writer.writeheader()
        row = {"trial_id": "R1_T01", "guessed_vehicle_id": "ferrari_458", "confidence_1_5": "4", "identity_strength_1_5": "4", "realism_1_5": "4", "artifact_freedom_1_5": "4"}
        writer.writerow(row)
        writer.writerow(row)
    with pytest.raises(ValueError, match="duplicate"):
        score_blind_responses(key, responses, tmp_path / "context.json", tmp_path / "result")
