import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

from tools.sound_sim.s12.acoustic_identity_v015.stage_ai8.reference_readiness import (
    _catalog_receipt,
    assess_readiness,
    main,
)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path):
    catalog = tmp_path / "catalog.json"
    vehicles = {}
    cases = []
    for vehicle in ("ferrari_458", "gtr_r35"):
        sources = []
        for index, split in enumerate(("train", "train", "validation")):
            wav = tmp_path / f"{vehicle}-{index}.wav"
            tone = 0.1 * np.sin(2 * np.pi * (120 + index * 20) * np.arange(4800) / 48000)
            wavfile.write(wav, 48000, tone.astype(np.float32))
            digest = _sha(wav)
            source_id = f"{vehicle}_{index}"
            sources.append({"id": source_id, "external_wav_path": str(wav),
                            "wav_sha256": digest, "source_url": f"local:{source_id}",
                            "rights_status": "UNVERIFIED_TEST"})
            cases.append({"vehicle": vehicle, "case_id": f"{vehicle}/{source_id}",
                          "source_id": source_id, "wav_path": str(wav),
                          "source_window_s": [0, .1], "scene": "02_full_pull",
                          "candidate_window_s": [0, .1], "split": split,
                          "comparable": True, "comparability_note": "reviewed fixture",
                          "viewpoint": "exterior", "state_family": "acceleration"})
        vehicles[vehicle] = {"sources": sources}
    catalog.write_text(json.dumps({"vehicles": vehicles}), encoding="utf-8")
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"schema": "s12.stage_ai.fourcar_reference_plan.v1",
        "catalog_path": str(catalog), "catalog_sha256": _sha(catalog),
        "evidence_level": "R3_UNSYNCHRONIZED", "cases": cases,
        "excluded_sources": [
            {"vehicle": "hellcat", "source_id": "h1", "reason": "HELLCAT_EXACT"},
            {"vehicle": "lfa", "source_id": "l1", "reason": "LFA_EXACT"}],
        "rules": []}), encoding="utf-8")
    return plan, catalog


def test_reports_only_reviewed_fourcar_as_search_ready(tmp_path):
    plan, _ = _fixture(tmp_path)
    report = assess_readiness(plan)
    assert report["vehicles"]["ferrari_458"]["search_ready"] is True, report["vehicles"]["ferrari_458"]["validation_error"]
    assert report["vehicles"]["gtr_r35"]["splits"] == {"train": 2, "validation": 1}
    assert report["vehicles"]["hellcat"]["excluded_reasons"] == ["HELLCAT_EXACT"]
    assert report["vehicles"]["lfa"]["excluded_reasons"] == ["LFA_EXACT"]
    for vehicle in ("c63_w204", "supra_jza80"):
        row = report["vehicles"][vehicle]
        assert row["search_ready"] is False
        assert "EXPLICIT_REVIEWED_PLAN_MISSING" in row["missing_items"]
    assert report["rights_policy"] == "UNVERIFIED_RIGHTS_DIAGNOSTIC_ONLY"


def test_stale_catalog_hash_fails_closed(tmp_path):
    plan, catalog = _fixture(tmp_path)
    catalog.write_text("{}", encoding="utf-8")
    report = assess_readiness(plan)
    for vehicle in ("ferrari_458", "gtr_r35"):
        assert report["vehicles"][vehicle]["search_ready"] is False
        assert "reference catalog drift" in report["vehicles"][vehicle]["validation_error"]


def test_split_leakage_fails_closed(tmp_path):
    plan, catalog = _fixture(tmp_path)
    payload = json.loads(plan.read_text(encoding="utf-8"))
    payload["cases"][2]["source_id"] = payload["cases"][0]["source_id"]
    payload["cases"][2]["wav_path"] = payload["cases"][0]["wav_path"]
    plan.write_text(json.dumps(payload), encoding="utf-8")
    report = assess_readiness(plan)
    assert report["vehicles"]["ferrari_458"]["search_ready"] is False
    assert "leakage" in report["vehicles"]["ferrari_458"]["validation_error"]


def test_cli_creates_output_exclusively(tmp_path):
    plan, _ = _fixture(tmp_path)
    out = tmp_path / "readiness.json"
    assert main(["--fourcar-plan", str(plan), "--out", str(out)]) == 0
    assert out.exists()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["fourcar_plan_sha256"] == _sha(plan)
    with pytest.raises(FileExistsError):
        main(["--fourcar-plan", str(plan), "--out", str(out)])


@pytest.mark.parametrize("variant", ["c63_url_only", "embedded_binding"])
def test_catalog_variants_separate_binding_from_governed_byte_receipt(tmp_path, variant):
    audio = tmp_path / "source.wav"
    audio.write_bytes(b"governed-source")
    digest = _sha(audio)
    source = {"id": "source", "url": "local:root/source.wav"}
    if variant == "embedded_binding":
        source.update(external_audio_path=str(audio), audio_sha256=digest,
                      rights_status="UNVERIFIED_PUBLIC")
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"sources": [source]}), encoding="utf-8")
    receipt = _catalog_receipt(catalog, tmp_path,
                               {"source": {"filename": "source.wav", "sha256": digest}})
    assert receipt["catalog_has_byte_bindings"] is (variant == "embedded_binding")
    assert receipt["governed_receipt_all_verified"] is True
    assert receipt["sources"][0]["governed_sha256_match"] is True
