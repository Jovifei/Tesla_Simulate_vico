"""Stage AI-6 independent report/WAV qualification.

The audio fixtures are synthetic gate probes, not vehicle-fidelity evidence.
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.feedback_evidence import SCENES
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.reconstruction_peak import (
    reconstructed_peak_receipt,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_af.package_integrity import seal_payload


BLIND_SPOT = np.array([
    [0.575237664059, -0.589608332237],
    [0.731863379758, 0.326017770083],
    [0.852349233806, -0.545495167886],
    [-0.502438076346, -0.081669497849],
    [-0.660339073466, -0.865313964125],
    [-0.278412751054, 0.472018061502],
    [0.731291863699, -0.501337777496],
    [0.835290939563, -0.791032098956],
], dtype=np.float64)


def _qualification():
    return importlib.import_module(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_ah.qualification"
    )


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _record(scene: str, pcm: np.ndarray) -> dict:
    audio = pcm.astype(np.float64) / 32767.0
    peak = float(np.max(np.abs(audio)))
    return {
        "vehicle": "rx7_fd",
        "scene_id": scene,
        "trace_sha256": hashlib.sha256(scene.encode()).hexdigest(),
        "sample_rate_hz": 48_000,
        "sample_count": len(pcm),
        "seed": 20260908,
        "flags": [],
        "parent_peak_key": "parent/" + scene,
        "parent_peak": 0.8,
        "candidate_raw_peak": 0.7,
        "normalization_denominator": 0.8,
        "output_policy": "linked_soft_ceiling_v1",
        "normalization": {
            "output_policy": "linked_soft_ceiling_v1",
            "normalization_denominator": 0.8,
            "legacy_ceiling_input_exceedance_samples": 3,
            "legacy_transfer_pre_guard_peak": 0.96,
            "pre_guard_exceedance_longest_run": 2,
            "pre_guard_peak": 0.96,
            "frame_count": len(pcm),
            "soft_guard_active_frames": 1,
            "soft_guard_delta_peak": 0.03,
            "soft_guard_delta_rms": 0.01,
            "post_guard_peak": peak,
            "post_guard_ceiling_exceedance_samples": 0,
            "emergency_clip_count": 0,
            "emergency_clip_error": 0.0,
            "emergency_clip_error_rms": 0.0,
        },
        "identity_layer_clip_count": 0,
        "identity_layer_clip_error": 0.0,
        "post_identity_clip_count": 0,
        "post_identity_clip_error": 0.0,
        "final_peak": peak,
        "final_rms": float(np.sqrt(np.mean(audio * audio))),
        "final_pcm_sha256": _sha_bytes(np.ascontiguousarray(pcm, dtype="<i2").tobytes()),
        "peak_estimate_4x": {"peak": peak},
        "reconstruction_peak": reconstructed_peak_receipt(audio),
    }


@pytest.fixture
def evidence(tmp_path: Path) -> tuple[Path, dict]:
    vehicle = "rx7_fd"
    result = {"status": "NO_IMPROVEMENT", "baseline_records": {}, "selected_records": {}}
    for role, field in (("baseline", "baseline_records"), ("tuned", "selected_records")):
        root = tmp_path / role / vehicle / "web_audio"
        root.mkdir(parents=True)
        for index, scene in enumerate(SCENES):
            t = np.arange(64, dtype=np.float64)
            pcm = np.column_stack([
                3000 * np.sin(2 * np.pi * (index + 1) * t / 64),
                2400 * np.cos(2 * np.pi * (index + 2) * t / 64),
            ]).astype(np.int16)
            wavfile.write(root / f"{scene}.wav", 48_000, pcm)
            result[field][scene] = _record(scene, pcm)
    return tmp_path, {
        "schema": "s12.stage_ah.reference_feedback_run.v1",
        "output_policy": "linked_soft_ceiling_v1",
        "vehicles": {vehicle: result},
    }


def _assert_blocked(root: Path, summary: dict) -> dict:
    receipt = _qualification().build_qualification_receipt(root, summary)
    assert receipt["status"] == "BLOCKED"
    with pytest.raises(ValueError):
        _qualification().verify_qualification_receipt(root, summary, receipt)
    return receipt


def test_valid_evidence_produces_independent_pass_receipt(evidence):
    root, summary = evidence
    module = _qualification()
    receipt = module.build_qualification_receipt(root, summary)
    assert receipt["schema"] == "s12.stage_ah.independent_qualification.v1"
    assert receipt["status"] == "PASS"
    scene = receipt["vehicles"]["rx7_fd"]["roles"]["baseline"]["scenes"]["01_afterfire"]
    assert scene["wav_file_sha256"] != scene["decoded_pcm_sha256"]
    assert scene["reconstruction"]["factor_order"] == [4, 8, 16]
    assert scene["reconstruction"]["domain"] == "FINAL_DECODED_PCM_FLOAT"
    assert scene["report_identity"]["scene_id"] == "01_afterfire"
    assert module.verify_qualification_receipt(root, summary, receipt) == receipt


def test_missing_receipt_or_report_evidence_fails_closed(evidence):
    root, summary = evidence
    with pytest.raises(ValueError, match="qualification receipt"):
        _qualification().verify_qualification_receipt(root, summary, None)
    broken = copy.deepcopy(summary)
    broken["vehicles"]["rx7_fd"].pop("selected_records")
    _assert_blocked(root, broken)


def test_fabricated_pass_cannot_override_recomputed_failure(evidence):
    root, summary = evidence
    broken = copy.deepcopy(summary)
    broken["vehicles"]["rx7_fd"]["selected_records"]["01_afterfire"]["post_identity_clip_count"] = 1
    receipt = _qualification().build_qualification_receipt(root, broken)
    receipt["status"] = "PASS"
    receipt["vehicles"]["rx7_fd"]["status"] = "PASS"
    with pytest.raises(ValueError):
        _qualification().verify_qualification_receipt(root, broken, receipt)


@pytest.mark.parametrize("mutation", [
    lambda records: records.pop("10_tip_in"),
    lambda records: (
        records.__setitem__("duplicate_alias", copy.deepcopy(records["01_afterfire"])),
        records.pop("10_tip_in"),
    ),
])
def test_missing_or_duplicate_scenes_fail_closed(evidence, mutation):
    root, summary = evidence
    records = summary["vehicles"]["rx7_fd"]["selected_records"]
    mutation(records)
    _assert_blocked(root, summary)


@pytest.mark.parametrize("field,value", [
    ("trace_sha256", "f" * 64),
    ("seed", 7),
    ("flags", ["changed"]),
    ("parent_peak_key", "other-parent"),
    ("normalization_denominator", 0.7),
    ("output_policy", "legacy_clip_v1"),
    ("sample_rate_hz", 44_100),
])
def test_role_identity_mismatch_fails_closed(evidence, field, value):
    root, summary = evidence
    summary["vehicles"]["rx7_fd"]["selected_records"]["01_afterfire"][field] = value
    _assert_blocked(root, summary)


def test_pcm_sha_or_wav_format_mismatch_fails_closed(evidence):
    root, summary = evidence
    valid_summary = copy.deepcopy(summary)
    record = summary["vehicles"]["rx7_fd"]["selected_records"]["01_afterfire"]
    record["final_pcm_sha256"] = "0" * 64
    _assert_blocked(root, summary)

    summary = valid_summary
    path = root / "tuned" / "rx7_fd" / "web_audio" / "01_afterfire.wav"
    _, pcm = wavfile.read(path)
    wavfile.write(path, 44_100, pcm)
    _assert_blocked(root, summary)


@pytest.mark.parametrize("path,value", [
    (("final_peak",), float("nan")),
    (("normalization_denominator",), float("inf")),
    (("sample_count",), True),
    (("seed",), -1),
    (("normalization", "emergency_clip_error"), 0.01),
    (("identity_layer_clip_count",), 1),
])
def test_nonfinite_negative_bool_and_nonzero_clip_fields_fail_closed(evidence, path, value):
    root, summary = evidence
    target = summary["vehicles"]["rx7_fd"]["selected_records"]["01_afterfire"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    _assert_blocked(root, summary)


def test_legacy_pre_guard_exceedance_remains_diagnostic(evidence):
    root, summary = evidence
    record = summary["vehicles"]["rx7_fd"]["selected_records"]["01_afterfire"]
    record["normalization"]["legacy_ceiling_input_exceedance_samples"] = 99
    receipt = _qualification().build_qualification_receipt(root, summary)
    assert receipt["status"] == "PASS"


def test_recomputed_8x_16x_only_overshoot_blocks_even_stored_pass(evidence):
    root, summary = evidence
    pcm = np.rint(BLIND_SPOT * 32767.0).astype(np.int16)
    path = root / "tuned" / "rx7_fd" / "web_audio" / "01_afterfire.wav"
    wavfile.write(path, 48_000, pcm)
    record = _record("01_afterfire", pcm)
    assert record["reconstruction_peak"]["factors"]["4"]["peak"] < 1.0
    assert record["reconstruction_peak"]["factors"]["8"]["peak"] > 1.0
    record["reconstruction_peak"]["status"] = "PASS"
    summary["vehicles"]["rx7_fd"]["selected_records"]["01_afterfire"] = record
    receipt = _assert_blocked(root, summary)
    assert "reconstructed" in receipt["vehicles"]["rx7_fd"]["reason"].lower()


def test_reference_feedback_verify_run_requires_new_receipt(tmp_path, monkeypatch):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import reference_feedback_cli as cli

    summary = {"schema": cli.RUN_SCHEMA, "promotable": False, "vehicles": {
        "rx7_fd": {"status": "NO_IMPROVEMENT", "baseline_records": {}, "selected_records": {}},
    }}
    cli._write(tmp_path / "summary.json", summary)
    for role in ("baseline", "tuned"):
        folder = tmp_path / role / "rx7_fd"
        folder.mkdir(parents=True)
        cli._write(folder / "dashboard_contract.json", seal_payload({}, "test.contract.v1"))
        (folder / "index.html").write_text("test", encoding="utf-8")
        (folder / "index_standalone.html").write_text("test", encoding="utf-8")
    files = {
        path.relative_to(tmp_path).as_posix(): cli._sha(path)
        for path in tmp_path.rglob("*") if path.is_file()
    }
    cli._write(tmp_path / "ARTIFACTS.json", seal_payload(
        {"files": files}, "s12.stage_ah.reference_feedback.artifacts.v1"
    ))
    monkeypatch.setattr(cli, "_verify_html", lambda *args: None)
    monkeypatch.setattr(cli, "_embedded", lambda *args: [])
    with pytest.raises(ValueError, match="qualification receipt"):
        cli.verify_run(tmp_path)
