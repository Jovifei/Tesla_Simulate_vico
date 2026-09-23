"""AI-8 four-car run qualification contracts using synthetic gate probes only."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import fourcar_reference_loop as loop
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.feedback_evidence import Journal, SCENES
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.qualification import QUALIFICATION_FILENAME
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.reconstruction_peak import reconstructed_peak_receipt
from tools.sound_sim.s12.acoustic_identity_v015.stage_af.package_integrity import seal_payload
from tools.sound_sim.s12.acoustic_identity_v015.tests import test_s12_stage_ai_fourcar as existing_fourcar


def _pcm_sha(pcm: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(pcm, dtype="<i2").tobytes()).hexdigest()


def _record(vehicle: str, scene: str, pcm: np.ndarray) -> dict:
    audio = pcm.astype(np.float64) / 32767.0
    peak = float(np.max(np.abs(audio)))
    return {
        "vehicle": vehicle, "scene_id": scene,
        "trace_sha256": hashlib.sha256(scene.encode()).hexdigest(),
        "sample_rate_hz": 48_000, "sample_count": len(pcm), "seed": 20260908,
        "flags": [], "parent_peak_key": "parent/" + scene,
        "parent_peak": 0.8, "candidate_raw_peak": 0.7,
        "normalization_denominator": 0.8, "output_policy": loop.LINKED_SOFT_CEILING_V1,
        "normalization": {
            "output_policy": loop.LINKED_SOFT_CEILING_V1, "normalization_denominator": 0.8,
            "legacy_ceiling_input_exceedance_samples": 0, "legacy_transfer_pre_guard_peak": 0.2,
            "pre_guard_exceedance_longest_run": 0, "pre_guard_peak": 0.2,
            "frame_count": len(pcm), "soft_guard_active_frames": 0,
            "soft_guard_delta_peak": 0.0, "soft_guard_delta_rms": 0.0,
            "post_guard_peak": peak, "post_guard_ceiling_exceedance_samples": 0,
            "emergency_clip_count": 0, "emergency_clip_error": 0.0,
            "emergency_clip_error_rms": 0.0,
        },
        "identity_layer_clip_count": 0, "identity_layer_clip_error": 0.0,
        "identity_layer_clip_error_rms": 0.0, "post_identity_clip_count": 0,
        "post_identity_clip_error": 0.0, "post_identity_clip_error_rms": 0.0,
        "final_peak": peak, "final_rms": float(np.sqrt(np.mean(audio * audio))),
        "final_pcm_sha256": _pcm_sha(pcm), "peak_estimate_4x": {"peak": peak},
        "reconstruction_peak": reconstructed_peak_receipt(audio),
    }


def _evidence(root: Path, *, numeric_blocked: bool = False) -> dict:
    vehicle = "hellcat"
    result = {
        "schema": "s12.stage_ah.reference_feedback.v1",
        "status": "ALL_SCENE_NUMERIC_REJECTED_ROLLED_BACK" if numeric_blocked else "NO_IMPROVEMENT",
        "baseline_records": {}, "selected_records": {}, "logs": {},
        "eligibility": {"available": False, "reasons": ["NO_VALIDATED_IMPROVEMENT"]},
    }
    for role, field, hashes in (("baseline", "baseline_records", "baseline_wav_sha256"),
                                ("tuned", "selected_records", "selected_wav_sha256")):
        web = root / role / vehicle / "web_audio"
        web.mkdir(parents=True)
        result[hashes] = {}
        for index, scene in enumerate(SCENES):
            t = np.arange(64, dtype=np.float64)
            pcm = np.column_stack((1200*np.sin(2*np.pi*(index+1)*t/64),
                                   900*np.cos(2*np.pi*(index+2)*t/64))).astype(np.int16)
            path = web / f"{scene}.wav"
            wavfile.write(path, 48_000, pcm)
            result[field][scene] = _record(vehicle, scene, pcm)
            result[hashes][scene] = loop.sha_file(path)
    diagnostics = root / "diagnostics" / vehicle
    diagnostics.mkdir(parents=True)
    for name in ("trials.jsonl", "render_journal.jsonl"):
        with Journal(diagnostics / name) as journal:
            journal.append("SYNTHETIC_TEST", {"vehicle": vehicle})
    result["logs"] = {"trials": f"diagnostics/{vehicle}/trials.jsonl",
                      "renders": f"diagnostics/{vehicle}/render_journal.jsonl"}
    if numeric_blocked:
        failure = diagnostics / "failure.json"
        loop.write_json(failure, seal_payload({"vehicle": vehicle, "status": result["status"],
                                               "reason": "synthetic numeric rejection"},
                                              "s12.stage_ai.fourcar_vehicle_failure.v1"))
        result["failure_receipt"] = f"diagnostics/{vehicle}/failure.json"
    return {"schema": loop.RUN_SCHEMA, "vehicles": {vehicle: result}, "blocked_vehicles": {},
            "output_policy": loop.LINKED_SOFT_CEILING_V1, "promotable": False,
            "human_status": "NOT_EVALUATED"}


def _seal_run(root: Path) -> None:
    files = {p.relative_to(root).as_posix(): loop.sha_file(p)
             for p in root.rglob("*") if p.is_file() and p.name != "ARTIFACTS.json"}
    loop.write_json(root / "ARTIFACTS.json",
                    seal_payload({"files": files}, "s12.stage_ai.feedback_artifacts.v1"))


def test_fourcar_run_writes_and_verifies_independent_qualification(tmp_path, monkeypatch):
    summary = _evidence(tmp_path)
    loop.write_json(tmp_path / "summary.json", summary)
    receipt = loop._write_qualification(tmp_path, summary)
    assert receipt["status"] == "PASS"
    assert receipt["vehicles"]["hellcat"]["status"] == "PASS"
    assert (tmp_path / QUALIFICATION_FILENAME).is_file()
    _seal_run(tmp_path)
    monkeypatch.setattr(loop, "fit_eligibility", lambda result: result["eligibility"])
    assert loop.verify_run(tmp_path)["output_policy"] == loop.LINKED_SOFT_CEILING_V1


def test_verify_run_recomputes_qualification_and_rejects_tamper(tmp_path, monkeypatch):
    summary = _evidence(tmp_path)
    loop.write_json(tmp_path / "summary.json", summary)
    loop._write_qualification(tmp_path, summary)
    receipt_path = tmp_path / QUALIFICATION_FILENAME
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["qualified_vehicle_count"] = 99
    receipt_path.unlink()
    loop.write_json(receipt_path, receipt)
    _seal_run(tmp_path)
    monkeypatch.setattr(loop, "fit_eligibility", lambda result: result["eligibility"])
    with pytest.raises(ValueError, match="does not match recomputed evidence"):
        loop.verify_run(tmp_path)


def test_numeric_rejection_is_persisted_as_blocked_not_ready(tmp_path, monkeypatch):
    summary = _evidence(tmp_path, numeric_blocked=True)
    loop.write_json(tmp_path / "summary.json", summary)
    receipt = loop._write_qualification(tmp_path, summary)
    assert receipt["status"] == "BLOCKED"
    assert receipt["vehicles"]["hellcat"] == {
        "status": "BLOCKED", "reason": "UPSTREAM_BASELINE_BLOCKED",
    }
    _seal_run(tmp_path)
    monkeypatch.setattr(loop, "fit_eligibility", lambda result: result["eligibility"])
    verified = loop.verify_run(tmp_path)
    assert verified["vehicles"]["hellcat"]["status"] == "ALL_SCENE_NUMERIC_REJECTED_ROLLED_BACK"


def test_actual_engine_records_include_independent_qualification_fields(tmp_path, monkeypatch):
    parent, entries, _ = existing_fourcar.fixture.__wrapped__(tmp_path, monkeypatch)
    vehicle = "hellcat"
    entry = next(row for row in entries if row["vehicle"] == vehicle)
    _, contexts, baseline_records, peaks = loop.capture_baseline(
        vehicle, tmp_path / "baseline-replay", entry, parent,
    )
    renderer = loop.FourCarFeedbackRenderer(vehicle, contexts, peaks)
    selected = renderer(renderer.baseline, "01_afterfire").diagnostics
    for record in (*baseline_records.values(), selected):
        assert record["parent_peak_key"]
        assert record["flags"] == []
        assert record["sample_rate_hz"] == 48_000
        assert record["sample_count"] > 0
        assert record["reconstruction_peak"]["status"] == "PASS"
