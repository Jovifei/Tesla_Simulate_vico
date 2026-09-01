from __future__ import annotations

import hashlib
import json

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.stage_z.method_ablation import (
    METHOD_CATALOG,
    build_method_adoption_matrix,
    build_teacher_vs_reduced_response,
    render_ablation_case,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_z.package_v2 import (
    build_stage_z_package,
    validate_stage_z_package,
)


def test_method_catalog_has_explicit_runtime_and_ablation_contracts() -> None:
    required = {
        "source_id",
        "method_id",
        "method_name",
        "adoption_status",
        "implementation_files",
        "runtime_call_path",
        "tests",
        "ablation_scenario",
        "target_metric",
        "evidence_receipt",
        "copied_source_code",
        "copied_audio_asset",
        "copied_model_weight",
    }
    ids = [item["method_id"] for item in METHOD_CATALOG]
    assert len(ids) == len(set(ids))
    assert {"engine_sim_path_waveguide", "vehicle_noise_state_crossfade", "stage_y_fitted_timbre_map"} <= set(ids)
    for item in METHOD_CATALOG:
        assert required <= set(item)
        assert item["implementation_files"]
        assert item["runtime_call_path"]
        assert item["tests"]
        assert item["copied_source_code"] is False
        assert item["copied_audio_asset"] is False
        assert item["copied_model_weight"] is False


def test_engine_sim_path_ablation_changes_pcm_and_target_metric() -> None:
    result = render_ablation_case("engine_sim_path_waveguide", "complete_cycle", duration_s=0.25)
    assert result.off_pcm.shape == result.on_pcm.shape
    assert np.all(np.isfinite(result.off_pcm)) and np.all(np.isfinite(result.on_pcm))
    assert hashlib.sha256(result.off_pcm.tobytes()).hexdigest() != hashlib.sha256(result.on_pcm.tobytes()).hexdigest()
    assert abs(result.target_metric_after - result.target_metric_before) > 1.0e-8
    assert result.off_guard_metric["passed"] is True
    assert result.on_guard_metric["passed"] is True
    assert result.global_gain_changed is False


def test_adoption_matrix_covers_registry_ids_and_required_rights_split() -> None:
    matrix = build_method_adoption_matrix()
    registry = json.loads(
        ("docs/research/engine-audio-ecosystem/source_registry.json")
        and open("docs/research/engine-audio-ecosystem/source_registry.json", encoding="utf-8").read()
    )
    assert {item["source_id"] for item in matrix} == {item["id"] for item in registry["sources"]}
    markeasting = [item for item in matrix if item["source_id"] == "markeasting-engine-audio"]
    assert markeasting
    assert any(item["source_license"] == "MIT" and item["asset_rights_status"] == "UNVERIFIED" for item in markeasting)


def test_teacher_reduction_contract_is_machine_readable() -> None:
    evidence = build_teacher_vs_reduced_response()
    assert evidence["status"] == "REFERENCE_TEACHER_ONLY"
    assert evidence["teacher_vs_reduced"]["arrival_timing"]["finite"] is True
    assert evidence["teacher_vs_reduced"]["spectral_envelope"]["finite"] is True
    assert evidence["runtime_approximation"]["runtime_candidate"] is False


def test_stage_z_package_has_current_main_overall_and_blinded_ablation_views(tmp_path) -> None:
    root = tmp_path / "s12-stage-y-hellcat-layers-v2"
    manifest = build_stage_z_package(root, duration_s=0.25, hot_idle_duration_s=0.25)
    assert validate_stage_z_package(root) == []
    assert manifest["schema"] == "s12.stage_z.audition_package.v2"
    assert manifest["main_head"] == manifest["tested_head"]
    assert manifest["overall_views"]
    assert manifest["method_ablation_views"]
    assert manifest["review_pages"] == ["overall_review.html", "method_ablation_review.html", "answers_manifest.html"]
    assert manifest["parent_sha256"] != manifest["final_raw_sha256"]
    assert (root / "overall_review.html").is_file()
    assert (root / "method_ablation_review.html").is_file()
    assert (root / "answers_manifest.html").is_file()
