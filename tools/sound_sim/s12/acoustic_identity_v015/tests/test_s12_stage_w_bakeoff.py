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
    resume_hellcat_bakeoff,
    run_hellcat_bakeoff,
    validate_bakeoff_manifest,
)


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
    assert p5_metrics["diagnostics"]["transient_residual_source"] == "synthetic_one_shot_v1"
    assert p5_metrics["diagnostics"]["transient_residual_event_count"] > 0
    assert not (root / "P5" / "gear_shift" / "post_ptr_raw.wav").read_bytes() == (root / "P3" / "gear_shift" / "post_ptr_raw.wav").read_bytes()
    assert result["architectures"]["P5"]["status"] == "RENDERED"
    assert result["architectures"]["P4"]["status"] == "REFERENCE_RECORDING_RIGHTS_PENDING"
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


def test_resume_bakeoff_defers_manifest_and_preserves_verified_cases(tmp_path) -> None:
    root = tmp_path / "bakeoff"
    first = resume_hellcat_bakeoff(root, "P1", duration_s=0.20)
    preserved = (root / "P1" / "hot_idle_20s" / "raw_source.wav").read_bytes()
    shutil.rmtree(root / "P1" / "complete_cycle_60s")
    (root / "P1" / "complete_cycle_60s").mkdir()
    again = resume_hellcat_bakeoff(root, "P1", duration_s=0.20)
    assert first["status"] == again["status"] == "IN_PROGRESS"
    assert (root / "P1" / "hot_idle_20s" / "raw_source.wav").read_bytes() == preserved
    assert (root / "P1" / "complete_cycle_60s" / "sha256_manifest.json").is_file()
    assert not (root / "bakeoff_manifest.json").exists()


def test_resume_bakeoff_finalizes_only_after_all_architectures(tmp_path) -> None:
    root = tmp_path / "bakeoff"
    for architecture in ("P1", "P2", "P2H", "P3"):
        result = resume_hellcat_bakeoff(root, architecture, duration_s=0.20)
        assert result["status"] == "IN_PROGRESS"
        assert not (root / "bakeoff_manifest.json").exists()
    final = resume_hellcat_bakeoff(root, "P5", duration_s=0.20)
    assert final["status"] == "REFERENCE_TARGET_MISSING"
    assert final["selected_architecture"] is None
    assert validate_bakeoff_manifest(root) == []


@pytest.mark.parametrize("mutator", ("incomplete_case", "duration", "long_window"))
def test_resume_bakeoff_rejects_bad_state_without_overwrite(tmp_path, mutator) -> None:
    root = tmp_path / "bakeoff"
    if mutator == "incomplete_case":
        case = root / "P1" / "hot_idle_20s"
        case.mkdir(parents=True)
        target = case / "raw_source.wav"
        target.write_bytes(b"partial")
        before = target.read_bytes()
        with pytest.raises(ValueError, match="incomplete"):
            resume_hellcat_bakeoff(root, "P1", duration_s=0.20)
        assert target.read_bytes() == before
        return
    resume_hellcat_bakeoff(root, "P1", duration_s=0.20, long_window=False)
    with pytest.raises(ValueError, match=mutator):
        resume_hellcat_bakeoff(
            root,
            "P2",
            duration_s=0.25 if mutator == "duration" else 0.20,
            long_window=mutator == "long_window",
        )


def test_resume_candidate_uses_verified_p1_parent_without_rerender(tmp_path, monkeypatch) -> None:
    root = tmp_path / "bakeoff"
    resume_hellcat_bakeoff(root, "P1", duration_s=0.20)
    original = bakeoff_module._render_architecture

    def no_parent_rerender(architecture, trace):
        if architecture == "P1":
            raise AssertionError("candidate resume must use verified P1 PCM")
        return original(architecture, trace)

    monkeypatch.setattr(bakeoff_module, "_render_architecture", no_parent_rerender)
    result = resume_hellcat_bakeoff(root, "P2", duration_s=0.20)
    assert result["status"] == "IN_PROGRESS"
