"""TDD tests for the Stage-V Hellcat raw/monitor publication package."""

from __future__ import annotations

import json

from tools.sound_sim.s12.acoustic_identity_v015.stage_v.publish import (
    publish_hellcat_vertical_slice,
    validate_stage_v_manifest,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_v.scenarios import (
    STAGE_V_SCENARIOS,
)


def test_publish_reopens_every_hellcat_scenario_and_binds_all_sha(tmp_path) -> None:
    result = publish_hellcat_vertical_slice(tmp_path / "stage_v", duration_s=0.35)
    root = tmp_path / "stage_v"
    assert result["status"] == "EVENT_DOMAIN_HELLCAT_ACCEPTED"
    assert set(result["scenarios"]) == set(STAGE_V_SCENARIOS)
    for scenario in STAGE_V_SCENARIOS:
        case = root / scenario
        assert (case / "legacy_parent_raw.wav").is_file()
        assert (case / "event_candidate_raw.wav").is_file()
        assert (case / "event_candidate_monitor.wav").is_file()
        assert (case / "state_trace.json").is_file()
        assert (case / "event_trace.json").is_file()
        assert (case / "path_trace.json").is_file()
        assert (case / "gain_trace.json").is_file()
        assert (case / "metrics.json").is_file()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert validate_stage_v_manifest(root) == []
    assert manifest["scope"] == "synthetic; uncalibrated; not OEM reproduction"
    assert manifest["raw_monitor_separation"] is True
    for name in (
        "parameter_reachability_matrix.json",
        "event_timing_validation.json",
        "exhaust_path_validation.json",
        "raw_monitor_loudness_report.json",
        "afterfire_state_validation.json",
        "parent_candidate_professional_metrics.json",
        "candidate_grid_results.json",
        "selected_candidates.json",
        "rejected_candidates.json",
        "S12_Stage_V_Event_Domain_Final_Report.md",
        "S12_Stage_V_Audition_Guide_ZH.md",
    ):
        assert (root / name).is_file(), name


def test_manifest_rejects_parent_candidate_same_sha(tmp_path) -> None:
    publish_hellcat_vertical_slice(tmp_path / "stage_v", duration_s=0.35)
    manifest_path = tmp_path / "stage_v" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    first = manifest["scenarios"][STAGE_V_SCENARIOS[0]]
    first["event_candidate_raw_sha256"] = first["legacy_parent_raw_sha256"]
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    errors = validate_stage_v_manifest(tmp_path / "stage_v")
    assert any("Parent/Candidate" in error for error in errors)
