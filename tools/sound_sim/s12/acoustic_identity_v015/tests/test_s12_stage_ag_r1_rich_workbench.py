from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_af.package_integrity import (
    seal_payload,
    sha256_file,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ag.build_r1_rich_audition_view import (
    FORBIDDEN_SIMPLE_MARKERS,
    RICH_REQUIRED_MARKERS,
    build_rich_view,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ag.serve_r1_rich_audition import (
    validate_view_root,
)

DIR_NAMES = {
    "hellcat": "s12-stage-ad-hellcat-closed-loop-v1",
    "ferrari_458": "s12-stage-ad-ferrari-458-closed-loop-v1",
    "lfa": "s12-stage-ad-lfa-closed-loop-v1",
    "gtr_r35": "s12-stage-ad-gtr-r35-closed-loop-v1",
}
VEHICLES = tuple(DIR_NAMES)
CANDIDATES = (
    "01_afterfire.wav",
    "02_full_pull.wav",
    "03_hot_idle.wav",
    "04_idle_return.wav",
    "05_lift.wav",
    "06_shift.wav",
    "07_steady_high.wav",
    "08_steady_low.wav",
    "09_steady_mid.wav",
    "10_tip_in.wav",
)


def _make_source_package(tmp_path: Path, identity_mode: str = "vehicle_identity_v1r1"):
    root = tmp_path / "source-package"
    root.mkdir()
    vehicles = []
    for vehicle_index, vehicle in enumerate(VEHICLES):
        directory = DIR_NAMES[vehicle]
        vehicle_root = root / directory
        web = vehicle_root / "web_audio"
        web.mkdir(parents=True)
        hashes = {}
        for file_index, filename in enumerate(CANDIDATES):
            # build_dashboard embeds bytes only; synthetic deterministic bytes are enough
            # for the view-layer contract test and prove there is no re-render path.
            path = web / filename
            path.write_bytes(
                b"RIFF-S12-RICH-VIEW-TEST-"
                + vehicle.encode("ascii")
                + b"-"
                + str(vehicle_index).encode()
                + b"-"
                + str(file_index).encode()
            )
            hashes[filename] = sha256_file(path)
        contract = {
            "schema": "s12.stage_af.dashboard_contract.v1",
            "package_id": "synthetic-r1-package",
            "candidate_id": "synthetic-r1",
            "vehicle": vehicle,
            "identity_mode": identity_mode,
            "flags": [],
            "seed": 20260908,
            "fit_status": "NOT_FITTED",
            "fit_metric_status": "NOT_MEASURED",
            "measurement_status": "NOT_MEASURED",
            "human_status": "WAITING_FOR_JOVI_FEEDBACK",
            "sample_rate_hz": 48000,
            "references": {},
            "parameters": [],
            "candidate_pcm_sha256": hashes,
            "reference_sha256": {},
            "package_gain_db": 0.0,
            "gain_policy": "no_additional_package_gain",
        }
        (vehicle_root / "dashboard_contract.json").write_text(
            json.dumps(contract), encoding="utf-8"
        )
        vehicles.append(
            {
                "vehicle": vehicle,
                "directory": directory,
                "identity_mode": identity_mode,
                "candidate_pcm_sha256": hashes,
                "reference_sha256": {},
            }
        )
    payload = seal_payload(
        {
            "schema": "s12.stage_ag.package_manifest.v1",
            "package_id": "synthetic-r1-package",
            "candidate_id": "synthetic-r1",
            "identity_mode": identity_mode,
            "human_status": "WAITING_FOR_JOVI_FEEDBACK",
            "fit_status": "NOT_FITTED",
            "source_receipt": {"git_head": "deadbeef" * 5},
            "vehicles": vehicles,
            "artifacts": [],
        },
        "s12.stage_ag.package_manifest.v1",
    )
    manifest = root / "audition_manifest.json"
    manifest.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return root, sha256_file(manifest), vehicles


def test_rich_view_rebuild_uses_exact_pcm_and_expected_ui(tmp_path):
    source, manifest_sha, vehicles = _make_source_package(tmp_path)
    view = tmp_path / "rich-view"
    receipt = build_rich_view(
        source,
        view,
        expected_manifest_sha256=manifest_sha,
        expected_identity_mode="vehicle_identity_v1r1",
        port_base=24480,
    )
    assert receipt.is_file()
    result = validate_view_root(
        view,
        expected_source_manifest_sha256=manifest_sha,
        expected_identity_mode="vehicle_identity_v1r1",
    )
    assert result["audio_policy"] == "EXACT_BYTE_COPY_NO_RENDER_NO_NORMALIZATION"
    assert result["status"] == "VIEW_ONLY / NOT_EVIDENCE_PACKAGE"

    manifest_by_vehicle = {row["vehicle"]: row for row in vehicles}
    for vehicle in VEHICLES:
        directory = DIR_NAMES[vehicle]
        html = (view / directory / "index.html").read_text(encoding="utf-8")
        for marker in RICH_REQUIRED_MARKERS:
            assert marker in html
        for marker in FORBIDDEN_SIMPLE_MARKERS:
            assert marker not in html
        assert "Stage AG-R1 · Vehicle Identity v1r1" in html
        assert "Reference (R3 / AUDITION_ONLY)" in html
        for filename, expected in manifest_by_vehicle[vehicle]["candidate_pcm_sha256"].items():
            assert sha256_file(view / directory / "web_audio" / filename) == expected


def test_rich_view_rejects_wrong_source_manifest_sha(tmp_path):
    source, _, _ = _make_source_package(tmp_path)
    with pytest.raises(ValueError, match="manifest file SHA mismatch"):
        build_rich_view(
            source,
            tmp_path / "view",
            expected_manifest_sha256="0" * 64,
            expected_identity_mode="vehicle_identity_v1r1",
            port_base=24480,
        )


def test_rich_server_rejects_old_simple_dashboard_marker(tmp_path):
    source, manifest_sha, _ = _make_source_package(tmp_path)
    view = tmp_path / "view"
    build_rich_view(
        source,
        view,
        expected_manifest_sha256=manifest_sha,
        expected_identity_mode="vehicle_identity_v1r1",
        port_base=24480,
    )
    ferrari = view / DIR_NAMES["ferrari_458"] / "index.html"
    ferrari.write_text(
        ferrari.read_text(encoding="utf-8") + "\npackage-wide gain\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="old/simple dashboard markers"):
        validate_view_root(
            view,
            expected_source_manifest_sha256=manifest_sha,
            expected_identity_mode="vehicle_identity_v1r1",
        )


def test_rich_view_legacy_label_is_explicit(tmp_path):
    source, manifest_sha, _ = _make_source_package(tmp_path, identity_mode="legacy")
    view = tmp_path / "legacy-view"
    build_rich_view(
        source,
        view,
        expected_manifest_sha256=manifest_sha,
        expected_identity_mode="legacy",
        port_base=24380,
    )
    html = (view / DIR_NAMES["hellcat"] / "index.html").read_text(encoding="utf-8")
    assert "Stage AG-R1 · Legacy Anchor" in html
    assert "Stage AG-R1 · Vehicle Identity v1r1" not in html
