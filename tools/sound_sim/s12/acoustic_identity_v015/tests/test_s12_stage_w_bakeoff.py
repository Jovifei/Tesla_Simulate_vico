"""RED tests for the comparator-driven Hellcat architecture bake-off."""

from __future__ import annotations

import json

from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import (
    run_hellcat_bakeoff,
    validate_bakeoff_manifest,
)


def test_bakeoff_renders_real_p1_p2h_p3_and_rejects_unavailable_paths(tmp_path) -> None:
    result = run_hellcat_bakeoff(tmp_path / "bakeoff", duration_s=0.25)
    root = tmp_path / "bakeoff"
    assert result["status"] == "REFERENCE_TARGET_MISSING"
    assert result["selected_architecture"] is None
    assert set(result["architectures"]) >= {"P1", "P2", "P2H", "P3", "P4", "P5", "P6"}
    for architecture in ("P1", "P2", "P2H", "P3"):
        assert (root / architecture / "complete_cycle_60s" / "raw_source.wav").is_file()
        assert (root / architecture / "complete_cycle_60s" / "metrics.json").is_file()
    assert result["architectures"]["P4"]["status"] == "REFERENCE_RECORDING_RIGHTS_PENDING"
    assert result["architectures"]["P6"]["status"] == "BLOCKED_TOOLCHAIN_NO_CLANG_MAKE"
    assert validate_bakeoff_manifest(root) == []
    manifest = json.loads((root / "bakeoff_manifest.json").read_text(encoding="utf-8"))
    assert manifest["reference_status"] == "REFERENCE_POINTER_ONLY"
