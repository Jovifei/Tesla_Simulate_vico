from __future__ import annotations

import json
from pathlib import Path

from tools.sound_sim.s12.acoustic_identity_v015.stage_n.toolchain import (
    default_capability_matrix,
    verify_artifact_manifest,
    write_artifact_manifest,
    write_toolchain_matrix,
)


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
    assert any(item["status"] == "INDUSTRY_REFERENCE_NOT_INSTALLED" for item in matrix["industry_references"])


def test_artifact_manifest_detects_post_write_mutation(tmp_path: Path) -> None:
    (tmp_path / "evidence.json").write_text('{"status":"BLOCKED"}\n', encoding="utf-8")
    write_artifact_manifest(tmp_path)
    assert verify_artifact_manifest(tmp_path) == []
    (tmp_path / "evidence.json").write_text('{"status":"MUTATED"}\n', encoding="utf-8")
    assert verify_artifact_manifest(tmp_path) == ["sha256: evidence.json"]
