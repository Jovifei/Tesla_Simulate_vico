"""Short TDD contracts for the independent four-vehicle Round-2 package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import wave
import zipfile

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_k.round2_remaining_package import (
    PACKAGE_ID,
    PIPELINE_ORDER,
    STATUS,
    VEHICLES,
    build_stage_k_remaining_four_round2_review,
)


@pytest.fixture(scope="module")
def remaining_package(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, object]]:
    root = tmp_path_factory.mktemp("stage_k_remaining_round2") / "review"
    result = build_stage_k_remaining_four_round2_review(
        root,
        duration_s=12.0,
        diagnostic_duration_s=12.0,
    )
    return root, result


def test_remaining_package_is_independent_four_vehicle_short_artifact(
    remaining_package: tuple[Path, dict[str, object]],
) -> None:
    root, result = remaining_package
    assert result["package_id"] == PACKAGE_ID
    assert PACKAGE_ID != "S12_Stage_K_Three_Vehicle_Round2_v1"
    assert result["schema_version"] != "s12-stage-k-three-vehicle-round2-artifact-1"
    assert tuple(result["vehicle_ids"]) == VEHICLES
    assert set(result["vehicles"]) == set(VEHICLES)
    assert result["status"] == STATUS
    assert result["human_pass"] is False
    assert result["csv_content_read"] is False
    assert isinstance(result["source_dirty"], bool)
    assert isinstance(result["source_commit"], str) and len(result["source_commit"]) == 40

    for vehicle_id in VEHICLES:
        vehicle = result["vehicles"][vehicle_id]
        assert set(vehicle["formal"]) == {"baseline", "candidate", "comfort"}
        assert len(vehicle["diagnostics"]) == 4
        gains = {vehicle["formal"][role]["whole_cycle_gain_linear"] for role in ("baseline", "candidate")}
        assert len(gains) == 1
        assert vehicle["formal"]["baseline"]["pipeline_order"] == list(PIPELINE_ORDER)
        assert vehicle["formal"]["candidate"]["pipeline_order"] == list(PIPELINE_ORDER)
        comfort = vehicle["formal"]["comfort"]
        assert comfort["input_sha256"] == vehicle["formal"]["candidate"]["sha256"]
        assert comfort["comfort_static_gain_applied_once"] is True
        for record in vehicle["formal"].values():
            path = root / record["path"]
            assert path.is_file()
            with wave.open(str(path), "rb") as stream:
                assert (stream.getframerate(), stream.getnchannels(), stream.getsampwidth()) == (48000, 2, 3)
                assert stream.getnframes() == record["frames"]
        for record in vehicle["diagnostics"].values():
            assert record["source_domain"] is True
            assert record["vehicle_id"] == vehicle_id
            assert (root / record["path"]).is_file()
        for source_record in vehicle["formal"]["baseline"]["production_source_files"]:
            source_path = Path(__file__).resolve().parents[5] / source_record["path"]
            assert hashlib.sha256(source_path.read_bytes()).hexdigest() == source_record["sha256"]


def test_remaining_package_manifest_sums_and_zip_crc_are_content_bound(
    remaining_package: tuple[Path, dict[str, object]],
) -> None:
    root, result = remaining_package
    manifest_path = root / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["package_id"] == PACKAGE_ID
    assert manifest["manifest_source"] == "builder_derived"
    assert manifest["caller_manifest_used"] is False
    sums_path = root / "SHA256SUMS.txt"
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == digest
    zip_path = root / result["zip_name"]
    with zipfile.ZipFile(zip_path) as archive:
        assert archive.read("artifact_manifest.json") == manifest_path.read_bytes()
        assert zip_path.name not in archive.namelist()
        crc = json.loads((root / "ZIP_CRC32.json").read_text(encoding="utf-8"))
        assert set(crc) == set(archive.namelist())
        assert all(int(crc[name]) == archive.getinfo(name).CRC for name in archive.namelist())


def test_remaining_package_root_is_atomic_and_never_overwritten(tmp_path: Path) -> None:
    root = tmp_path / "review"
    root.mkdir()
    with pytest.raises(FileExistsError):
        build_stage_k_remaining_four_round2_review(root, duration_s=12.0, diagnostic_duration_s=12.0)


def test_remaining_round2_cli_help_works_direct_and_as_module() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_stage_k_remaining_four_round2.py"
    direct = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True, check=False)
    module = subprocess.run(
        [sys.executable, "-m", "tools.sound_sim.s12.acoustic_identity_v015.scripts.build_stage_k_remaining_four_round2", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert direct.returncode == 0, direct.stderr
    assert module.returncode == 0, module.stderr
    assert "--duration-s" in direct.stdout
    assert "--duration-s" in module.stdout
