from __future__ import annotations

import hashlib
import numpy as np

from tools.sound_sim.s12.real_reference.stage_u_audio_feature_dtw import (
    _state_context,
    compare_audio_feature_batch,
    compare_audio_feature_triad,
)


def _receipt(values: np.ndarray, sha: str) -> dict:
    return {
        "input_sha256": sha,
        "sample_rate_hz": 48_000,
        "feature_info": {
            "barkSpectrum": [1, 2],
            "erbSpectrum": [3],
            "mfcc": [4, 5],
            "gtcc": [6],
            "spectralFlux": 7,
            "pitch": 8,
        },
        "features": values.tolist(),
    }


def test_audio_feature_triad_uses_only_fixed_dimension_terms_and_reports_improvement() -> None:
    reference = np.column_stack((np.ones(12), np.ones(12), np.ones(12), np.linspace(0, 1, 12), np.linspace(1, 2, 12), np.linspace(2, 3, 12), np.linspace(3, 4, 12), np.linspace(4, 5, 12)))
    parent = reference.copy(); parent[:, 3:] += 1.0
    candidate = reference.copy(); candidate[:, 3:] += 0.2
    context = {"scenario": "idle", "rpm_window": [900.0, 1200.0]}

    result = compare_audio_feature_triad(
        _receipt(reference, "ref"),
        _receipt(parent, "parent"),
        _receipt(candidate, "candidate"),
        context,
    )

    assert result["status"] == "AUDIO_FEATURE_TRIAD_COMPLETE"
    assert result["selected_feature_count"] == 5
    assert result["excluded_feature_families"] == ["barkSpectrum", "erbSpectrum"]
    assert result["candidate_distance"] < result["parent_distance"]
    assert result["absolute_improvement"] > 0.0


def test_audio_feature_triad_rejects_sha_or_feature_schema_mismatch() -> None:
    values = np.arange(48, dtype=float).reshape(6, 8)
    context = {"scenario": "idle", "rpm_window": [900.0, 1200.0]}
    candidate = _receipt(values, "candidate")
    candidate["feature_info"] = {"mfcc": [4, 5], "gtcc": [6], "spectralFlux": 7}

    try:
        compare_audio_feature_triad(_receipt(values, "ref"), _receipt(values, "parent"), candidate, context)
    except ValueError as error:
        assert "common fixed-dimension" in str(error)
    else:
        raise AssertionError("expected incompatible feature schemas to fail closed")


def test_audio_feature_batch_binds_every_triad_to_manifest_sha() -> None:
    reference = np.column_stack((np.ones(12), np.ones(12), np.ones(12), np.linspace(0, 1, 12), np.linspace(1, 2, 12), np.linspace(2, 3, 12), np.linspace(3, 4, 12), np.linspace(4, 5, 12)))
    parent = reference.copy(); parent[:, 3:] += 1.0
    candidate = reference.copy(); candidate[:, 3:] += 0.2
    clip_ids = {"reference": "reference::r", "parent": "parent::r", "candidate": "candidate::r::c"}
    manifest = {"clips": [
        {"clip_id": clip_ids["reference"], "sha256": "ref", "vehicle_id": "hellcat", "scenario": "idle_rev_acceleration"},
        {"clip_id": clip_ids["parent"], "sha256": "parent", "vehicle_id": "hellcat", "scenario": "idle_rev_acceleration"},
        {"clip_id": clip_ids["candidate"], "sha256": "candidate", "vehicle_id": "hellcat", "scenario": "idle_rev_acceleration"},
    ]}
    paths = {role: f"{role}.json" for role in clip_ids}
    batch = {"results": [{"clip_id": clip_ids[role], "input_sha256": role if role != "reference" else "ref", "feature_receipt_path": paths[role]} for role in clip_ids]}
    receipts = {paths["reference"]: _receipt(reference, "ref"), paths["parent"]: _receipt(parent, "parent"), paths["candidate"]: _receipt(candidate, "candidate")}
    legacy = [{"reference_id": "r", "candidate_id": "c", "vehicle_id": "hellcat", "hard_gates_pass": True}]

    result = compare_audio_feature_batch(legacy, manifest, batch, receipt_loader=receipts.__getitem__)

    row = result["results"][0]
    assert result["status"] == "AUDIO_FEATURE_BATCH_COMPLETE"
    assert row["professional_bound"] is True
    assert row["candidate_distance"] < row["parent_distance"]
    assert row["state_context"]["source"] == "INFERRED_MATCHING_RENDER_TRACE_NOT_R1"


def test_audio_feature_batch_freshly_hashes_matlab_receipt_input_when_embedded_sha_is_absent(tmp_path) -> None:
    reference = np.column_stack((np.ones(12), np.ones(12), np.ones(12), np.linspace(0, 1, 12), np.linspace(1, 2, 12), np.linspace(2, 3, 12), np.linspace(3, 4, 12), np.linspace(4, 5, 12)))
    parent = reference.copy(); parent[:, 3:] += 1.0
    candidate = reference.copy(); candidate[:, 3:] += 0.2
    roles = ("reference", "parent", "candidate")
    clip_ids = {"reference": "reference::r", "parent": "parent::r", "candidate": "candidate::r::c"}
    paths = {role: tmp_path / f"{role}.wav" for role in roles}
    for role, path in paths.items():
        path.write_bytes(role.encode("ascii"))
    hashes = {role: hashlib.sha256(path.read_bytes()).hexdigest() for role, path in paths.items()}
    values = {"reference": reference, "parent": parent, "candidate": candidate}
    receipts = {}
    for role in roles:
        receipt = _receipt(values[role], hashes[role])
        receipt.pop("input_sha256")
        receipt["input_path"] = str(paths[role])
        receipts[f"{role}.json"] = receipt
    manifest = {"clips": [
        {"clip_id": clip_ids[role], "sha256": hashes[role], "vehicle_id": "hellcat", "scenario": "idle_rev_acceleration"}
        for role in roles
    ]}
    batch = {"results": [
        {"clip_id": clip_ids[role], "input_sha256": hashes[role], "feature_receipt_path": f"{role}.json"}
        for role in roles
    ]}

    result = compare_audio_feature_batch(
        [{"reference_id": "r", "candidate_id": "c", "vehicle_id": "hellcat", "hard_gates_pass": True}],
        manifest,
        batch,
        receipt_loader=receipts.__getitem__,
    )

    assert result["results"][0]["sha_binding"] == hashes


def test_constant_rpm_matching_trace_uses_declared_tolerance_window_for_bounded_dtw() -> None:
    context = _state_context("rx7_fd", "idle")

    assert context["rpm_window"] == [895.0, 945.0]
    assert context["rpm_window_policy"] == "CONSTANT_RPM_PLUS_MINUS_25_OR_ONE_PERCENT"
