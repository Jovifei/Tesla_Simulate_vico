"""RED tests for the comparator-driven Hellcat architecture bake-off."""

from __future__ import annotations

import json

from tools.sound_sim.s12.acoustic_identity_v015.stage_v.io import read_pcm24_wav
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import (
    run_hellcat_bakeoff,
    validate_bakeoff_manifest,
)


def test_bakeoff_renders_real_p1_p2h_p3_and_rejects_unavailable_paths(tmp_path) -> None:
    result = run_hellcat_bakeoff(tmp_path / "bakeoff", duration_s=0.25)
    root = tmp_path / "bakeoff"
    assert result["status"] == "REFERENCE_TARGET_MISSING"
    assert result["selected_architecture"] is None
    assert result["requested_duration_s"] == 0.25
    assert result["block_aligned_duration_s"] == 0.24
    assert set(result["architectures"]) >= {"P1", "P2", "P2H", "P3", "P4", "P5", "P6"}
    for architecture in ("P1", "P2", "P2H", "P3"):
        assert (root / architecture / "complete_cycle_60s" / "raw_source.wav").is_file()
        assert (root / architecture / "complete_cycle_60s" / "metrics.json").is_file()
        assert (root / architecture / "complete_cycle_60s" / "phase_trace.json").is_file()
        assert (root / architecture / "complete_cycle_60s" / "event_trace.json").is_file()
        assert (root / architecture / "complete_cycle_60s" / "path_trace.json").is_file()
        assert (root / architecture / "complete_cycle_60s" / "gain_trace.json").is_file()
    phase_trace = json.loads((root / "P2H" / "complete_cycle_60s" / "phase_trace.json").read_text(encoding="utf-8"))
    assert phase_trace["status"] == "PERSISTENT_ENGINE_TRACE"
    for scene in ("hot_idle_20s", "full_load_acceleration", "complete_cycle_60s"):
        frames = [read_pcm24_wav(root / architecture / scene / "post_ptr_raw.wav")[1]["frames"] for architecture in ("P1", "P2", "P2H", "P3")]
        assert len(set(frames)) == 1
    eligible = json.loads((root / "P2H" / "afterfire_eligible" / "event_trace.json").read_text(encoding="utf-8"))
    ineligible = json.loads((root / "P2H" / "afterfire_ineligible" / "event_trace.json").read_text(encoding="utf-8"))
    assert eligible["afterfire_event_count"][-1] > 0
    assert ineligible["afterfire_event_count"][-1] == 0
    assert result["architectures"]["P4"]["status"] == "REFERENCE_RECORDING_RIGHTS_PENDING"
    assert result["architectures"]["P6"]["status"] == "BLOCKED_TOOLCHAIN_NO_CLANG_MAKE"
    assert validate_bakeoff_manifest(root) == []
    manifest = json.loads((root / "bakeoff_manifest.json").read_text(encoding="utf-8"))
    assert manifest["reference_status"] == "REFERENCE_POINTER_ONLY"
