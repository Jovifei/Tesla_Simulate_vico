from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_af.package_integrity import (
    seal_payload,
    sha256_file,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ag.serve_r1_review_strict import (
    EXPECTED_DIRS,
    RICH_HTML_REQUIRED_MARKERS,
    validate_package,
)


def _fake_package(root: Path, mode: str, *, rich: bool = True) -> Path:
    vehicles = []
    for vehicle, directory in EXPECTED_DIRS.items():
        vehicle_root = root / directory
        web = vehicle_root / "web_audio"
        web.mkdir(parents=True, exist_ok=True)
        candidate = web / "03_hot_idle.wav"
        reference = web / "ref_hot_idle.wav"
        candidate.write_bytes(f"{mode}:{vehicle}:candidate".encode())
        reference.write_bytes(f"{vehicle}:reference".encode())
        candidate_map = {candidate.name: sha256_file(candidate)}
        reference_map = {reference.name: sha256_file(reference)}
        html = "\n".join(RICH_HTML_REQUIRED_MARKERS) if rich else (
            "Stage AE canonical S12 renderer package-wide gain A/B diagnostic"
        )
        (vehicle_root / "index.html").write_text(html, encoding="utf-8")
        contract = {
            "identity_mode": mode,
            "human_status": "WAITING_FOR_JOVI_FEEDBACK",
            "candidate_pcm_sha256": candidate_map,
            "reference_sha256": reference_map,
        }
        (vehicle_root / "dashboard_contract.json").write_text(
            json.dumps(contract), encoding="utf-8"
        )
        vehicles.append(
            {
                "vehicle": vehicle,
                "directory": directory,
                "candidate_pcm_sha256": candidate_map,
                "reference_sha256": reference_map,
            }
        )
    manifest = seal_payload(
        {
            "identity_mode": mode,
            "vehicles": vehicles,
            "source_receipt": {"git_head": "deadbeef"},
        },
        "s12.stage_ag.package_manifest.v1",
    )
    (root / "audition_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return root


def test_strict_review_accepts_rich_r1_package(tmp_path):
    package = _fake_package(tmp_path / "r1", "vehicle_identity_v1r1")
    receipt = validate_package(
        package,
        expected_mode="vehicle_identity_v1r1",
        expected_manifest_sha256=sha256_file(package / "audition_manifest.json"),
    )
    assert receipt["identity_mode"] == "vehicle_identity_v1r1"
    assert set(receipt["vehicles"]) == set(EXPECTED_DIRS)


def test_strict_review_rejects_stale_simple_stage_ae_page(tmp_path):
    package = _fake_package(tmp_path / "stale", "vehicle_identity_v1r1", rich=False)
    with pytest.raises(ValueError, match="approved rich Ferrari-style"):
        validate_package(package, expected_mode="vehicle_identity_v1r1")


def test_strict_review_rejects_wrong_manifest_sha(tmp_path):
    package = _fake_package(tmp_path / "legacy", "legacy")
    with pytest.raises(ValueError, match="package manifest SHA mismatch"):
        validate_package(
            package,
            expected_mode="legacy",
            expected_manifest_sha256="0" * 64,
        )


def test_strict_review_rejects_candidate_byte_drift(tmp_path):
    package = _fake_package(tmp_path / "r1", "vehicle_identity_v1r1")
    vehicle_root = package / EXPECTED_DIRS["ferrari_458"] / "web_audio"
    (vehicle_root / "03_hot_idle.wav").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="candidate WAV SHA mismatch"):
        validate_package(package, expected_mode="vehicle_identity_v1r1")
