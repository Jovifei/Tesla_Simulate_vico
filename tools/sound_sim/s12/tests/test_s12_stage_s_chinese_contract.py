from __future__ import annotations

import json
import hashlib
import wave
from pathlib import Path

import numpy as np

from tools.sound_sim.s12.real_reference.feedback import CHINESE_DIMENSIONS, write_stage_s_waiting_outputs
from tools.sound_sim.s12.real_reference.inventory import build_inventory
from tools.sound_sim.s12.real_reference.baseline import build_stage_r_waiting_result
import tools.sound_sim.s12.real_reference.build_r2_ab_package as r2_ab_package


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


def test_r2_ab_package_accepts_case_insensitive_source_shas(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(r2_ab_package, "ALLOWED_DOWNLOAD_ROOT", tmp_path)
    reference_path = tmp_path / "reference.wav"
    candidate_path = tmp_path / "candidate.wav"
    pcm = np.zeros(4_096, dtype="<i2").tobytes()
    for path in (reference_path, candidate_path):
        with wave.open(str(path), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(48_000)
            stream.writeframes(pcm)
    reference_sha = hashlib.sha256(reference_path.read_bytes()).hexdigest()
    candidate_sha = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "recordings": [
                    {
                        "recording_id": "rx7sim_fixture",
                        "reference_id": "q:rx7sim:fixture",
                        "vehicle_id": "rx7_fd",
                        "scenario": "full_pull",
                        "external_path": str(reference_path),
                        "sha256": reference_sha.upper(),
                        "provenance": {
                            "license": "CC0",
                            "source_url": "https://example.test/rx7sim",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    candidate_spec_path = tmp_path / "candidate_spec.json"
    candidate_spec_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "recording_id": "rx7sim_fixture",
                        "candidate_path": str(candidate_path),
                        "candidate_sha256": candidate_sha.upper(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = r2_ab_package.build_package(manifest_path, candidate_spec_path, tmp_path / "package")
    assert result["case_count"] == 1
    assert (tmp_path / "package" / "study_manifest.json").is_file()
