"""RED tests for Stage-W Ferrari/RX-7 preselection migration."""

from __future__ import annotations

import json

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_w.migration import (
    MIGRATION_SCENES,
    run_preselection_vehicle_migration,
    validate_vehicle_migration_manifest,
)


def test_migration_uses_the_required_five_vehicle_scenes() -> None:
    assert MIGRATION_SCENES == ("hot_idle", "steady_mid", "full_pull", "lift", "complete_cycle")


@pytest.mark.parametrize("vehicle_id", ("ferrari_458", "rx7_fd"))
def test_preselection_migration_renders_ptr_bound_candidates(vehicle_id: str, tmp_path) -> None:
    root = tmp_path / vehicle_id
    result = run_preselection_vehicle_migration(root, vehicle_id, duration_s=0.25)

    assert result["status"] == "UNSELECTED_CANDIDATE_MIGRATION"
    assert result["vehicle_id"] == vehicle_id
    assert result["selected_architecture"] is None
    assert validate_vehicle_migration_manifest(root) == []
    frame_counts: dict[str, list[int]] = {scene: [] for scene in MIGRATION_SCENES}
    for architecture in ("P1", "P2H", "P3"):
        for scene in MIGRATION_SCENES:
            case = root / architecture / scene
            assert (case / "raw_source.wav").is_file()
            assert (case / "post_ptr_raw.wav").is_file()
            assert (case / "monitor.wav").is_file()
            assert (case / "phase_trace.json").is_file()
            assert (case / "event_trace.json").is_file()
            assert (case / "path_trace.json").is_file()
            assert (case / "gain_trace.json").is_file()
            metrics = json.loads((case / "metrics.json").read_text(encoding="utf-8"))
            assert metrics["ptr_status"] == "FROZEN_RUNTIME_PTR_ADAPTER"
            assert 0.0 < metrics["publication_output_scale"] <= 0.05
            assert metrics["raw_metrics"]["clipping"] == 0
            assert metrics["post_ptr_metrics"]["frames"] > 0
            assert metrics["post_ptr_metrics"]["clipping"] == 0
            frame_counts[scene].append(metrics["post_ptr_metrics"]["frames"])
            if architecture in {"P2H", "P3"} and scene == "lift":
                assert metrics["engine_diagnostics"]["afterfire_event_count"] > 0
                phase_trace = json.loads((case / "phase_trace.json").read_text(encoding="utf-8"))
                assert phase_trace["status"] == "PERSISTENT_ENGINE_TRACE"
                assert len(phase_trace["phase_rad"]) == len(phase_trace["sample_counter"])
    assert all(len(set(counts)) == 1 for counts in frame_counts.values())


def test_migration_manifest_keeps_w10_selection_gate_closed(tmp_path) -> None:
    root = tmp_path / "ferrari"
    run_preselection_vehicle_migration(root, "ferrari_458", duration_s=0.25)

    manifest = json.loads((root / "migration_manifest.json").read_text(encoding="utf-8"))
    assert manifest["reference_status"] == "REFERENCE_TARGET_MISSING"
    assert manifest["selected_architecture"] is None
    assert manifest["status"] == "UNSELECTED_CANDIDATE_MIGRATION"


def test_migration_validator_requires_complete_case_artifact_inventory(tmp_path) -> None:
    root = tmp_path / "incomplete"
    run_preselection_vehicle_migration(root, "rx7_fd", duration_s=0.25)

    relative = "P2H/lift/phase_trace.json"
    (root / relative).unlink()
    manifest = json.loads((root / "migration_manifest.json").read_text(encoding="utf-8"))
    manifest["files"].pop(relative)
    (root / "migration_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    errors = validate_vehicle_migration_manifest(root)
    assert f"missing_required:{relative}" in errors


def test_migration_is_deterministic_for_identical_rx7_input(tmp_path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    run_preselection_vehicle_migration(first, "rx7_fd", duration_s=0.25)
    run_preselection_vehicle_migration(second, "rx7_fd", duration_s=0.25)

    first_manifest = json.loads((first / "migration_manifest.json").read_text(encoding="utf-8"))
    second_manifest = json.loads((second / "migration_manifest.json").read_text(encoding="utf-8"))
    for relative, sha256 in first_manifest["files"].items():
        if relative.endswith(("raw_source.wav", "post_ptr_raw.wav", "monitor.wav")):
            assert second_manifest["files"][relative] == sha256
