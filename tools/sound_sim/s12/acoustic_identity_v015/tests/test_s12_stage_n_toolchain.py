from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_n.toolchain import (
    build_cross_tool_validation,
    default_capability_matrix,
    verify_artifact_manifest,
    write_artifact_manifest,
    write_toolchain_matrix,
)


def _validated_matlab_receipt() -> dict[str, object]:
    return {
        "status": "VALIDATED",
        "matlab_release": "2026a",
        "fixture_validated": True,
        "vehicle_data_executed": True,
        "vehicle_count": 8,
        "vehicles": {f"v{index}": {} for index in range(8)},
        "fixture": {
            "provenance": {
                "fixture_id": "s12-shared-fixture-v1",
                "fixture_manifest_sha256": "a" * 64,
                "fixture_mat_sha256": "b" * 64,
            },
            "validation": {
                "gain_increases_loudness": True,
                "high_frequency_increases_sharpness": True,
                "fast_am_increases_roughness": True,
                "prominent_tone_increases_tonality": True,
            },
            "metrics": {
                "base": {"loudness_sone": 1.0, "sharpness_acum": 1.0, "roughness_asper": 1.0},
                "prominent_tone": {"tone_to_noise_ratio_db": 2.0},
            },
        },
    }


def test_toolchain_matrix_preserves_partial_status_and_mosqito_fixture_receipt(tmp_path: Path) -> None:
    receipt = {
        "status": "VALIDATED",
        "fixtures": {"base": {"mosqito_version": "1.2.1"}},
    }
    matrix = write_toolchain_matrix(tmp_path, default_capability_matrix(receipt, webmushra_output="webmushra_package_manifest.json"))
    saved = json.loads((tmp_path / "toolchain_capability_matrix.json").read_text(encoding="utf-8"))
    assert saved["overall_status"] == "PROFESSIONAL_COMPARATOR_TOOLCHAIN_PARTIAL"
    mosqito = next(record for record in saved["records"] if record["tool"] == "MoSQITo")
    assert mosqito["status"] == "VALIDATED"
    assert mosqito["actually_invoked"] is True
    project_receipt = {"status": "EXECUTED_ON_PROJECT_DATA", "vehicle_count": 8, "vehicles": {f"v{index}": {} for index in range(8)}}
    project_matrix = default_capability_matrix(receipt, mosqito_project_receipt=project_receipt)
    project_mosqito = next(record for record in project_matrix if record["tool"] == "MoSQITo")
    assert project_mosqito["vehicle_data_executed"] is True
    assert any(item["status"] == "INDUSTRY_REFERENCE_NOT_INSTALLED" for item in matrix["industry_references"])


def test_artifact_manifest_detects_post_write_mutation(tmp_path: Path) -> None:
    (tmp_path / "evidence.json").write_text('{"status":"BLOCKED"}\n', encoding="utf-8")
    write_artifact_manifest(tmp_path)
    assert verify_artifact_manifest(tmp_path) == []
    (tmp_path / "evidence.json").write_text('{"status":"MUTATED"}\n', encoding="utf-8")
    assert verify_artifact_manifest(tmp_path) == ["sha256: evidence.json"]


def test_real_matlab_receipts_require_fixture_and_project_execution_and_cross_tool_trends() -> None:
    matlab = _validated_matlab_receipt()
    mosqito = {
        "status": "VALIDATED",
        "fixtures": {
            "base": {"mosqito_version": "1.2.1", "results": {"loudness_sone": 0.9, "sharpness_acum": 0.9, "roughness_asper": 0.9}},
            "prominent_tone": {"results": {"tone_to_noise_ratio_db": 1.5}},
        },
        "validation": {
            "gain_increases_loudness": True,
            "high_frequency_increases_sharpness": True,
            "fast_am_increases_roughness": True,
            "prominent_tone_reports_tonality": True,
        },
        "shared_fixture_provenance": {
            "fixture_id": "s12-shared-fixture-v1",
            "fixture_manifest_sha256": "a" * 64,
            "fixture_mat_sha256": "b" * 64,
        },
    }
    cross = build_cross_tool_validation(matlab, mosqito)
    assert cross["status"] == "VALIDATED"
    assert cross["passed"] is True
    matrix = default_capability_matrix(
        mosqito,
        matlab_order_receipt=matlab,
        matlab_psychoacoustic_receipt=matlab,
    )
    order = next(record for record in matrix if record["tool"] == "MATLAB Signal Processing Toolbox: rpmordermap")
    psycho = next(record for record in matrix if record["tool"] == "MATLAB Audio Toolbox: acousticLoudness")
    assert order["status"] == "VALIDATED" and order["vehicle_data_executed"] is True
    assert psycho["status"] == "VALIDATED" and psycho["fixture_validated"] is True


def test_cross_tool_validation_rejects_nonidentical_shared_fixture_provenance() -> None:
    matlab = _validated_matlab_receipt()
    matlab["fixture"]["provenance"] = {
        "fixture_id": "s12-shared-fixture-v1",
        "fixture_manifest_sha256": "a" * 64,
        "fixture_mat_sha256": "b" * 64,
    }
    mosqito = {
        "status": "VALIDATED",
        "fixtures": {
            "base": {"mosqito_version": "1.2.1", "results": {}},
            "prominent_tone": {"results": {}},
        },
        "validation": {
            "gain_increases_loudness": True,
            "high_frequency_increases_sharpness": True,
            "fast_am_increases_roughness": True,
            "prominent_tone_reports_tonality": True,
        },
        "shared_fixture_provenance": {
            "fixture_id": "s12-shared-fixture-v1",
            "fixture_manifest_sha256": "c" * 64,
            "fixture_mat_sha256": "b" * 64,
        },
    }
    result = build_cross_tool_validation(matlab, mosqito)
    assert result["status"] == "CROSS_TOOL_COMPARISON_BLOCKED"
    assert "shared fixture" in result["reason"]


def test_shared_fixture_builder_module_is_available() -> None:
    assert importlib.util.find_spec("tools.sound_sim.s12.acoustic_identity_v015.stage_n.shared_psychoacoustic_fixture") is not None


def test_shared_fixture_builder_writes_hash_bound_non_overwriting_mat_payload(tmp_path: Path) -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_n import shared_psychoacoustic_fixture

    builder = getattr(shared_psychoacoustic_fixture, "write_shared_fixture", None)
    assert callable(builder)
    receipt = builder(tmp_path / "shared")
    fixture_root = tmp_path / "shared"
    manifest = json.loads((fixture_root / "fixture_manifest.json").read_text(encoding="utf-8"))
    assert receipt["fixture_id"] == manifest["fixture_id"]
    assert manifest["sample_rate_hz"] == 48_000
    assert set(manifest["signals"]) == {"base", "gain", "high_frequency_boost", "fast_am", "slow_am", "prominent_tone"}
    assert (fixture_root / "shared_psychoacoustic_fixture.mat").is_file()
    assert len(manifest["fixture_mat_sha256"]) == 64
    with pytest.raises(FileExistsError):
        builder(fixture_root)
