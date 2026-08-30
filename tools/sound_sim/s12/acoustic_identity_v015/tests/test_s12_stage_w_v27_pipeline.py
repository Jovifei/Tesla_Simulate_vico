"""TDD coverage for the external v27 stage verifier and assembler."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import (
    RENDERABLE_ARCHITECTURES,
    render_hellcat_architecture_stage,
    validate_bakeoff_manifest,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.v27_pipeline import assemble_v27_bakeoff


ARCHITECTURES = RENDERABLE_ARCHITECTURES


def _render_stages(root: Path) -> dict[str, Path]:
    stages = {architecture: root / f"stage-{architecture.lower()}" for architecture in ARCHITECTURES}
    render_hellcat_architecture_stage(stages["P1"], "P1", duration_s=0.20)
    for architecture in ARCHITECTURES[1:]:
        render_hellcat_architecture_stage(
            stages[architecture],
            architecture,
            duration_s=0.20,
            parent_stage_root=stages["P1"],
        )
    return stages


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_assemble_v27_publishes_validator_clean_root_without_stage_extras(tmp_path: Path) -> None:
    stages = _render_stages(tmp_path / "stages")
    final_root = tmp_path / "bakeoff_final_v27"

    result = assemble_v27_bakeoff(final_root, stages, duration_s=0.20)

    assert result["status"] == "REFERENCE_TARGET_MISSING"
    assert result["reference_status"] == "REFERENCE_POINTER_ONLY"
    assert result["selected_architecture"] is None
    assert final_root.is_dir()
    assert validate_bakeoff_manifest(final_root) == []
    manifest = json.loads((final_root / "bakeoff_manifest.json").read_text(encoding="utf-8"))
    actual = {
        path.relative_to(final_root).as_posix()
        for path in final_root.rglob("*")
        if path.is_file() and path.name != "bakeoff_manifest.json"
    }
    assert actual == set(manifest["files"])
    assert not any(path.name in {"stage_manifest.json", "assembly_receipt.json"} for path in final_root.rglob("*"))
    assert all((final_root / architecture).is_dir() for architecture in ARCHITECTURES)


def test_assemble_rejects_missing_duplicate_or_tampered_stage_without_final_root(tmp_path: Path) -> None:
    stages = _render_stages(tmp_path / "stages")

    missing = dict(stages)
    missing.pop("P5")
    with pytest.raises(ValueError, match="exactly one stage root"):
        assemble_v27_bakeoff(tmp_path / "missing-final", missing, duration_s=0.20)
    assert not (tmp_path / "missing-final").exists()

    duplicate = dict(stages)
    duplicate["P2"] = stages["P1"]
    with pytest.raises(ValueError, match="duplicate|architecture"):
        assemble_v27_bakeoff(tmp_path / "duplicate-final", duplicate, duration_s=0.20)
    assert not (tmp_path / "duplicate-final").exists()

    tampered = stages["P3"] / "P3" / "steady_1200rpm" / "metrics.json"
    tampered.write_text('{"tampered": true}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="stage|verified"):
        assemble_v27_bakeoff(tmp_path / "tampered-final", stages, duration_s=0.20)
    assert not (tmp_path / "tampered-final").exists()
    assert not list(tmp_path.glob(".tampered-final.v27-build-*"))


def test_assemble_rechecks_candidate_parent_and_preserves_stage_roots(tmp_path: Path) -> None:
    stages = _render_stages(tmp_path / "stages")
    before = {architecture: _tree_hashes(path) for architecture, path in stages.items()}

    result = assemble_v27_bakeoff(tmp_path / "bakeoff_final_v27", stages, duration_s=0.20)

    assert result["selected_architecture"] is None
    assert {architecture: _tree_hashes(path) for architecture, path in stages.items()} == before
    for stage_root in stages.values():
        assert (stage_root / "stage_manifest.json").is_file()

    parent_binding = stages["P2"] / "stage_manifest.json"
    manifest = json.loads(parent_binding.read_text(encoding="utf-8"))
    manifest["parent_stage"]["post_ptr_sha256"]["steady_1200rpm"] = "0" * 64
    parent_binding.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="parent_stage|verified"):
        assemble_v27_bakeoff(tmp_path / "second-final", stages, duration_s=0.20)
    assert not (tmp_path / "second-final").exists()


def test_assemble_rejects_final_root_inside_stage_root_without_mutation(tmp_path: Path) -> None:
    stages = _render_stages(tmp_path / "stages")
    before = {architecture: _tree_hashes(path) for architecture, path in stages.items()}
    final_root = stages["P1"] / "nested-final"

    with pytest.raises(ValueError, match="inside|contained|stage root"):
        assemble_v27_bakeoff(final_root, stages, duration_s=0.20)

    assert not final_root.exists()
    assert {architecture: _tree_hashes(path) for architecture, path in stages.items()} == before
