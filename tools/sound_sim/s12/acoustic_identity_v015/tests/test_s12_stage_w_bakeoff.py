"""RED tests for the comparator-driven Hellcat architecture bake-off."""

from __future__ import annotations

import hashlib
import json
import shutil

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_v.io import read_pcm24_wav
from tools.sound_sim.s12.acoustic_identity_v015.stage_w import bakeoff as bakeoff_module
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import (
    render_hellcat_architecture_stage,
    run_hellcat_bakeoff,
    validate_hellcat_architecture_stage,
    validate_bakeoff_manifest,
)


def test_architecture_stage_renders_all_scenes_and_validates(tmp_path) -> None:
    stage_root = tmp_path / "p1-stage"

    result = render_hellcat_architecture_stage(stage_root, "P1", duration_s=0.20)

    assert result["status"] == "STAGE_COMPLETE"
    assert result["reference_status"] == "REFERENCE_POINTER_ONLY"
    assert result["selected_architecture"] is None
    manifest = json.loads((stage_root / "stage_manifest.json").read_text(encoding="utf-8"))
    assert manifest["architecture"] == "P1"
    assert manifest["status"] == "STAGE_COMPLETE"
    assert manifest["reference_status"] == "REFERENCE_POINTER_ONLY"
    assert manifest["selected_architecture"] is None
    assert manifest["scene_duration_s"] == {scene: 0.20 for scene in bakeoff_module.SCENES}
    assert set(manifest["files"]) == {
        f"P1/{scene}/{filename}"
        for scene in bakeoff_module.SCENES
        for filename in bakeoff_module.STAGE_CASE_FILES
    }
    assert validate_hellcat_architecture_stage(stage_root, "P1", 0.20) == []


def test_candidate_stage_requires_verified_p1_and_uses_parent_pcm(tmp_path, monkeypatch) -> None:
    parent_root = tmp_path / "p1-stage"
    candidate_root = tmp_path / "p2-stage"
    render_hellcat_architecture_stage(parent_root, "P1", duration_s=0.20)

    calls: list[str] = []
    original = bakeoff_module._render_architecture

    def spy(architecture, trace):
        calls.append(architecture)
        return original(architecture, trace)

    monkeypatch.setattr(bakeoff_module, "_render_architecture", spy)
    result = render_hellcat_architecture_stage(
        candidate_root,
        "P2",
        duration_s=0.20,
        parent_stage_root=parent_root,
    )

    assert result["status"] == "STAGE_COMPLETE"
    assert "P1" not in calls
    assert validate_hellcat_architecture_stage(candidate_root, "P2", 0.20) == []
    metrics = json.loads((candidate_root / "P2" / "steady_1200rpm" / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["comparison"]["parent_candidate_difference_rms"] > 0.0

    missing_parent_root = tmp_path / "missing-parent"
    with pytest.raises(ValueError, match="verified P1"):
        render_hellcat_architecture_stage(
            missing_parent_root,
            "P2",
            duration_s=0.20,
            parent_stage_root=tmp_path / "does-not-exist",
        )
    assert not missing_parent_root.exists()


def test_stage_rejects_nonempty_or_tampered_root_without_mutation(tmp_path) -> None:
    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    sentinel = nonempty / "sentinel.txt"
    sentinel.write_bytes(b"owner data")
    before = {path.relative_to(nonempty).as_posix(): path.read_bytes() for path in nonempty.rglob("*") if path.is_file()}
    with pytest.raises(FileExistsError):
        render_hellcat_architecture_stage(nonempty, "P1", duration_s=0.20)
    after = {path.relative_to(nonempty).as_posix(): path.read_bytes() for path in nonempty.rglob("*") if path.is_file()}
    assert after == before

    tampered = tmp_path / "tampered"
    render_hellcat_architecture_stage(tampered, "P1", duration_s=0.20)
    metrics_path = tampered / "P1" / "steady_1200rpm" / "metrics.json"
    original_metrics = metrics_path.read_bytes()
    metrics_path.write_text("{\"tampered\": true}\n", encoding="utf-8")
    assert validate_hellcat_architecture_stage(tampered, "P1", 0.20)
    tampered_before = {path.relative_to(tampered).as_posix(): path.read_bytes() for path in tampered.rglob("*") if path.is_file()}
    with pytest.raises(FileExistsError):
        render_hellcat_architecture_stage(tampered, "P1", duration_s=0.20)
    tampered_after = {path.relative_to(tampered).as_posix(): path.read_bytes() for path in tampered.rglob("*") if path.is_file()}
    assert tampered_after == tampered_before
    assert metrics_path.read_bytes() != original_metrics


def _rebind_stage_case_hashes(stage_root, architecture: str, scene: str) -> None:
    case = stage_root / architecture / scene
    inner_path = case / "sha256_manifest.json"
    inner = json.loads(inner_path.read_text(encoding="utf-8"))
    for filename in inner:
        inner[filename] = hashlib.sha256((case / filename).read_bytes()).hexdigest()
    inner_path.write_text(json.dumps(inner, sort_keys=True) + "\n", encoding="utf-8")
    outer_path = stage_root / "stage_manifest.json"
    outer = json.loads(outer_path.read_text(encoding="utf-8"))
    for filename in bakeoff_module.STAGE_CASE_FILES:
        outer["files"][f"{architecture}/{scene}/{filename}"] = hashlib.sha256((case / filename).read_bytes()).hexdigest()
    outer_path.write_text(json.dumps(outer, sort_keys=True) + "\n", encoding="utf-8")


def test_stage_rejects_click_gate_false_even_when_hashes_are_rebound(tmp_path) -> None:
    stage_root = tmp_path / "p1-stage"
    render_hellcat_architecture_stage(stage_root, "P1", duration_s=0.20)
    metrics_path = stage_root / "P1" / "steady_1200rpm" / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["click_metrics"]["raw"]["passed"] = False
    metrics_path.write_text(json.dumps(metrics, sort_keys=True) + "\n", encoding="utf-8")
    _rebind_stage_case_hashes(stage_root, "P1", "steady_1200rpm")

    errors = validate_hellcat_architecture_stage(stage_root, "P1", 0.20)

    assert any("click" in error for error in errors)


def test_stage_validator_rejects_deleted_or_tampered_parent_and_candidate_rms(tmp_path) -> None:
    parent_root = tmp_path / "p1-stage"
    candidate_root = tmp_path / "p2-stage"
    render_hellcat_architecture_stage(parent_root, "P1", duration_s=0.20)
    render_hellcat_architecture_stage(candidate_root, "P2", duration_s=0.20, parent_stage_root=parent_root)
    assert validate_hellcat_architecture_stage(candidate_root, "P2", 0.20, parent_stage_root=parent_root) == []

    deleted_parent = tmp_path / "deleted-parent"
    import shutil as _shutil
    _shutil.copytree(parent_root, deleted_parent)
    _shutil.rmtree(deleted_parent)
    assert validate_hellcat_architecture_stage(candidate_root, "P2", 0.20, parent_stage_root=deleted_parent)

    tampered_parent = tmp_path / "tampered-parent"
    _shutil.copytree(parent_root, tampered_parent)
    parent_pcm = tampered_parent / "P1" / "steady_1200rpm" / "post_ptr_raw.wav"
    payload = bytearray(parent_pcm.read_bytes())
    payload[-1] ^= 1
    parent_pcm.write_bytes(payload)
    assert validate_hellcat_architecture_stage(candidate_root, "P2", 0.20, parent_stage_root=tampered_parent)

    candidate_metrics = candidate_root / "P2" / "steady_1200rpm" / "metrics.json"
    metrics = json.loads(candidate_metrics.read_text(encoding="utf-8"))
    metrics["comparison"]["parent_candidate_difference_rms"] += 1.0
    candidate_metrics.write_text(json.dumps(metrics, sort_keys=True) + "\n", encoding="utf-8")
    _rebind_stage_case_hashes(candidate_root, "P2", "steady_1200rpm")
    errors = validate_hellcat_architecture_stage(candidate_root, "P2", 0.20, parent_stage_root=parent_root)
    assert any("parent_candidate_difference" in error for error in errors)


def test_stage_validator_rejects_huge_numeric_values_without_throwing(tmp_path) -> None:
    stage_root = tmp_path / "p1-stage"
    render_hellcat_architecture_stage(stage_root, "P1", duration_s=0.20)
    huge = 10**1000
    manifest_path = stage_root / "stage_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["requested_duration_s"] = huge
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")

    errors = validate_hellcat_architecture_stage(stage_root, "P1", 0.20)

    assert errors


def test_bakeoff_renders_executable_p5_and_rejects_unavailable_paths(tmp_path) -> None:
    result = run_hellcat_bakeoff(tmp_path / "bakeoff", duration_s=0.25)
    root = tmp_path / "bakeoff"
    assert result["status"] == "REFERENCE_TARGET_MISSING"
    assert result["selected_architecture"] is None
    assert result["requested_duration_s"] == 0.25
    assert result["block_aligned_duration_s"] == 0.24
    assert set(result["architectures"]) >= {"P1", "P2", "P2H", "P3", "P4", "P5", "P6"}
    for architecture in ("P1", "P2", "P2H", "P3", "P5"):
        assert (root / architecture / "complete_cycle_60s" / "raw_source.wav").is_file()
        assert (root / architecture / "complete_cycle_60s" / "metrics.json").is_file()
        assert (root / architecture / "complete_cycle_60s" / "phase_trace.json").is_file()
        assert (root / architecture / "complete_cycle_60s" / "event_trace.json").is_file()
        assert (root / architecture / "complete_cycle_60s" / "path_trace.json").is_file()
        assert (root / architecture / "complete_cycle_60s" / "gain_trace.json").is_file()
    phase_trace = json.loads((root / "P2H" / "complete_cycle_60s" / "phase_trace.json").read_text(encoding="utf-8"))
    assert phase_trace["status"] == "PERSISTENT_ENGINE_TRACE"
    for scene in ("hot_idle_20s", "full_load_acceleration", "complete_cycle_60s"):
        frames = [read_pcm24_wav(root / architecture / scene / "post_ptr_raw.wav")[1]["frames"] for architecture in ("P1", "P2", "P2H", "P3", "P5")]
        assert len(set(frames)) == 1
    eligible = json.loads((root / "P2H" / "afterfire_eligible" / "event_trace.json").read_text(encoding="utf-8"))
    ineligible = json.loads((root / "P2H" / "afterfire_ineligible" / "event_trace.json").read_text(encoding="utf-8"))
    assert eligible["afterfire_event_count"][-1] > 0
    assert ineligible["afterfire_event_count"][-1] == 0
    p5_metrics = json.loads((root / "P5" / "gear_shift" / "metrics.json").read_text(encoding="utf-8"))
    assert p5_metrics["diagnostics"]["transient_residual_source"] == "state_v1"
    assert p5_metrics["diagnostics"]["transient_residual_event_count"] > 0
    assert not (root / "P5" / "gear_shift" / "post_ptr_raw.wav").read_bytes() == (root / "P3" / "gear_shift" / "post_ptr_raw.wav").read_bytes()
    assert result["architectures"]["P5"]["status"] == "RENDERED"
    assert result["architectures"]["P4"]["status"] == "RENDERED"
    assert result["architectures"]["P6"]["status"] == "TEACHER_NOT_RUNTIME_CANDIDATE"
    assert validate_bakeoff_manifest(root) == []
    manifest = json.loads((root / "bakeoff_manifest.json").read_text(encoding="utf-8"))
    assert manifest["reference_status"] == "REFERENCE_POINTER_ONLY"
    parent_candidate = json.loads((root / "parent_candidate_metrics.json").read_text(encoding="utf-8"))
    assert parent_candidate["status"] == "REFERENCE_TARGET_MISSING"
    assert parent_candidate["selection_eligible"] is False
    assert parent_candidate["architectures"]["P2H"]["complete_cycle_60s"]["post_ptr_sha256"] != parent_candidate["parent"]["complete_cycle_60s"]["post_ptr_sha256"]
    ablations = json.loads((root / "ablation_results.json").read_text(encoding="utf-8"))
    assert ablations["status"] == "REFERENCE_TARGET_MISSING"
    assert ablations["selection_eligible"] is False
    assert set(ablations["ablations"]) == {"P2_to_P2H_waveguide", "P2H_to_P3_timbre_map", "P3_to_P5_transient"}
    assert ablations["ablations"]["P2_to_P2H_waveguide"]["complete_cycle_60s"]["post_ptr_sha256_different"] is True
    delivery = tmp_path / "delivery"
    receipt = bakeoff_module.publish_bakeoff_summaries(root, delivery)
    assert receipt["status"] == "REFERENCE_TARGET_MISSING"
    assert receipt["selection_eligible"] is False
    assert set(receipt["files"]) == {"bakeoff_results.json", "parent_candidate_metrics.json", "ablation_results.json", "selected_architecture.json", "rejected_architectures.json"}
    for name, expected_hash in receipt["files"].items():
        assert (delivery / name).is_file()
        assert hashlib.sha256((delivery / name).read_bytes()).hexdigest() == expected_hash
    refreshed = bakeoff_module.publish_bakeoff_summaries(root, delivery, overwrite=True)
    assert refreshed["files"] == receipt["files"]


def test_publisher_rejects_summary_without_manifest_binding(tmp_path) -> None:
    root = tmp_path / "bakeoff"
    run_hellcat_bakeoff(root, duration_s=0.25)
    manifest_path = root / "bakeoff_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"].pop("parent_candidate_metrics.json")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (root / "parent_candidate_metrics.json").write_text('{"tampered": true}', encoding="utf-8")
    with pytest.raises(ValueError, match="invalid bake-off source"):
        bakeoff_module.publish_bakeoff_summaries(root, tmp_path / "delivery")


def test_r2_summaries_preserve_reference_status(tmp_path) -> None:
    reference = np.zeros((11_520, 2), dtype=np.float64)
    root = tmp_path / "bakeoff"
    result = run_hellcat_bakeoff(root, duration_s=0.25, reference=reference)
    summaries = json.loads((root / "parent_candidate_metrics.json").read_text(encoding="utf-8"))
    ablations = json.loads((root / "ablation_results.json").read_text(encoding="utf-8"))
    assert result["reference_status"] == "EXTERNAL_R2_POINTER"
    assert summaries["reference_status"] == result["reference_status"]
    assert ablations["reference_status"] == result["reference_status"]


def test_long_window_duration_contract_uses_real_named_scene_lengths() -> None:
    assert bakeoff_module.scene_duration_s("hot_idle_20s", 1.0, long_window=True) == 20.0
    assert bakeoff_module.scene_duration_s("complete_cycle_60s", 1.0, long_window=True) == 60.0
    assert bakeoff_module.scene_duration_s("steady_1200rpm", 1.0, long_window=True) == 1.0


def test_bakeoff_trace_uses_exact_state_rate_timestamps() -> None:
    trace = bakeoff_module.build_hellcat_bakeoff_trace("hot_idle_20s", 0.25)
    assert np.array_equal(trace.time_s, np.arange(trace.time_s.size, dtype=np.float64) / bakeoff_module.STATE_RATE_HZ)


def test_bakeoff_validator_requires_case_files_and_nested_scene_inventory(tmp_path) -> None:
    baseline = tmp_path / "baseline"
    run_hellcat_bakeoff(baseline, duration_s=0.25)
    missing = tmp_path / "missing"
    shutil.copytree(baseline, missing)
    relative = "P2H/afterfire_eligible/phase_trace.json"
    (missing / relative).unlink()
    manifest = json.loads((missing / "bakeoff_manifest.json").read_text(encoding="utf-8"))
    manifest["files"].pop(relative)
    (missing / "bakeoff_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert f"missing_required:{relative}" in validate_bakeoff_manifest(missing)

    nested = tmp_path / "nested"
    shutil.copytree(baseline, nested)
    results_path = nested / "bakeoff_results.json"
    results = json.loads(results_path.read_text(encoding="utf-8"))
    results["architectures"]["P1"]["scenes"].pop("gear_shift")
    results_path.write_text(json.dumps(results), encoding="utf-8")
    manifest = json.loads((nested / "bakeoff_manifest.json").read_text(encoding="utf-8"))
    manifest["files"]["bakeoff_results.json"] = hashlib.sha256(results_path.read_bytes()).hexdigest()
    (nested / "bakeoff_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert any("nested" in error for error in validate_bakeoff_manifest(nested))
