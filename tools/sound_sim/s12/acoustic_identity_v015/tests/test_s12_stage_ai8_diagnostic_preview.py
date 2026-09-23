import copy
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

from tools.sound_sim.s12.acoustic_identity_v015.stage_ai8 import diagnostic_preview


@pytest.fixture(autouse=True)
def _fast_reconstruction(monkeypatch):
    def receipt(values, *, sample_rate=48_000):
        peak = float(np.max(np.abs(values)))
        rows = {str(factor): {"factor": factor, "peak": peak, "channel": 0,
                              "upsampled_index": 0, "time_s": 0.0,
                              "exceedance_count": 0} for factor in (4, 8, 16)}
        return {"schema": "s12.stage_ai.reconstruction_peak_receipt.v1",
                "sample_rate_hz": sample_rate, "frame_count": len(values), "channels": 2,
                "sample_peak": peak, "threshold": 1.0, "factors": rows,
                "factor_order": [4, 8, 16], "worst_factor": 4, "worst_peak": peak,
                "status": "PASS", "method": "synthetic-test-stub", "domain": "FINAL_DECODED_PCM_FLOAT",
                "standard": "ENGINEERING_DIAGNOSTIC_NOT_ITU_EBU_CERTIFIED", "audio_modified": False}
    monkeypatch.setattr(diagnostic_preview, "reconstructed_peak_receipt", receipt)


def _good_report(vehicle, pcm):
    peak = float(np.max(np.abs(pcm.astype(np.float64) / 32767.0)))
    variants = {"c63_w204": diagnostic_preview.C63_SOURCE_VARIANT,
                "supra_jza80": diagnostic_preview.SUPRA_SOURCE_VARIANT}
    return {
        "vehicle": vehicle,
        "scene_id": "continuous_drive",
        "source_variant": variants.get(vehicle, "r1_baseline"),
        "output_policy": "linked_soft_ceiling_v1",
        "parent_peak": 1.0,
        "candidate_raw_peak": 0.5,
        "normalization_denominator": 1.0,
        "final_peak": peak,
        "final_rms": 0.1,
        "sample_rate_hz": 48_000,
        "sample_count": len(pcm),
        "seed": 1,
        "flags": [],
        "peak_estimate_4x": {"peak": peak},
        "normalization": {
            "output_policy": "linked_soft_ceiling_v1",
            "normalization_denominator": 1.0,
            "post_guard_ceiling_exceedance_samples": 0,
            "emergency_clip_count": 0,
            "legacy_ceiling_input_exceedance_samples": 0,
            "pre_guard_exceedance_longest_run": 0,
            "emergency_clip_error": 0.0,
            "emergency_clip_error_rms": 0.0,
            "legacy_transfer_pre_guard_peak": 0.5,
            "pre_guard_peak": 0.5,
            "soft_guard_delta_peak": 0.0,
            "soft_guard_delta_rms": 0.0,
            "post_guard_peak": peak,
        },
        "identity_layer_clip_count": 0,
        "post_identity_clip_count": 0,
        "identity_layer_clip_error": 0.0,
        "post_identity_clip_error": 0.0,
    }


def _synthetic_renderer(vehicle):
    # Deterministic orchestration stub; it is not acoustic evidence.
    pcm = np.tile(np.array([[1000, -1000], [2000, -2000]], dtype=np.int16), (720_000, 1))
    return pcm, _good_report(vehicle, pcm)


def _identity():
    return {"commit": "a" * 40, "scope": "synthetic-test", "source_status": "SOURCE_CLEAN"}


def test_render_requires_fresh_output_directory(tmp_path):
    output = tmp_path / "preview"
    diagnostic_preview.render_preview(output, vehicles=("hellcat",), renderer=_synthetic_renderer,
                                      runtime_identity_fn=_identity)
    with pytest.raises(FileExistsError):
        diagnostic_preview.render_preview(output, vehicles=("hellcat",), renderer=_synthetic_renderer,
                                          runtime_identity_fn=_identity)


def test_invalid_waveform_and_numeric_failure_retain_unplayable_evidence(tmp_path):
    def renderer(vehicle):
        if vehicle == "hellcat":
            return np.array([np.nan, 0.0]), {"vehicle": vehicle}
        pcm, report = _synthetic_renderer(vehicle)
        report = copy.deepcopy(report)
        report["normalization"]["emergency_clip_count"] = 1
        return pcm, report

    output = tmp_path / "preview"
    summary = diagnostic_preview.render_preview(
        output, vehicles=("hellcat", "ferrari_458"), renderer=renderer,
        runtime_identity_fn=_identity,
    )
    assert summary["vehicles"]["hellcat"]["status"] == "RENDER_FAILED"
    failed = summary["vehicles"]["ferrari_458"]
    assert failed["status"] == "FAILED_NUMERIC_GATE"
    assert (output / failed["wav"]).exists()
    assert (output / failed["report"]).exists()
    index = (output / "index.html").read_text(encoding="utf-8")
    assert "unavailable: numeric gate failed" in index
    assert "<audio" not in index


def test_manifest_verify_detects_content_drift(tmp_path):
    output = tmp_path / "preview"
    diagnostic_preview.render_preview(output, vehicles=("gtr_r35",), renderer=_synthetic_renderer,
                                      runtime_identity_fn=_identity)
    assert diagnostic_preview.verify_preview(output)["status"] == "VERIFIED"
    wav = next(output.glob("*.wav"))
    wav.write_bytes(wav.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="content drift"):
        diagnostic_preview.verify_preview(output)


def test_verify_accepts_pinned_manifest_sha(tmp_path):
    output = tmp_path / "preview"
    diagnostic_preview.render_preview(output, vehicles=("gtr_r35",), renderer=_synthetic_renderer,
                                      runtime_identity_fn=_identity)
    digest = _file_sha(output / "manifest.json")
    assert diagnostic_preview.verify_preview(output, expected_manifest_sha256=digest)["status"] == "VERIFIED"
    with pytest.raises(ValueError, match="manifest SHA"):
        diagnostic_preview.verify_preview(output, expected_manifest_sha256="0" * 64)


def test_verify_recomputes_numeric_gate_even_when_hashes_are_refreshed(tmp_path):
    output = tmp_path / "preview"
    diagnostic_preview.render_preview(output, vehicles=("lfa",), renderer=_synthetic_renderer,
                                      runtime_identity_fn=_identity)
    report_path = output / "lfa.report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["normalization"]["emergency_clip_count"] = 1
    report_path.write_text(json.dumps(report), encoding="utf-8")
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][report_path.name] = _file_sha(report_path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="numeric gate drift"):
        diagnostic_preview.verify_preview(output)


def _file_sha(path):
    return __import__("hashlib").sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("vehicle", ["../hellcat", "rx7_fd", "hellcat/../../x"])
def test_rejects_unsupported_vehicle_and_path_traversal(tmp_path, vehicle):
    with pytest.raises(ValueError, match="unsupported vehicle"):
        diagnostic_preview.render_preview(tmp_path / "preview", vehicles=(vehicle,),
                                          renderer=_synthetic_renderer,
                                          runtime_identity_fn=_identity)


def test_qualified_output_is_int16_and_playable_diagnostic_only(tmp_path):
    output = tmp_path / "preview"
    summary = diagnostic_preview.render_preview(
        output, vehicles=("supra_jza80",), renderer=_synthetic_renderer,
        runtime_identity_fn=_identity,
    )
    row = summary["vehicles"]["supra_jza80"]
    assert row["status"] == "DIAGNOSTIC_BASELINE"
    rate, pcm = wavfile.read(output / row["wav"])
    assert rate == 48_000 and pcm.dtype == np.int16
    index = (output / "index.html").read_text(encoding="utf-8")
    assert "DIAGNOSTIC_BASELINE" in index
    assert "validated B" not in index and "human pass" not in index


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("promotable", True),
        ("oem_match", "OEM_MATCH"),
        ("human_status", "HUMAN_PASS"),
        ("validated_b", True),
        ("nested_oem_match", True),
    ],
)
def test_renderer_claims_are_rejected_and_never_published(tmp_path, field, value):
    def renderer(vehicle):
        pcm, report = _synthetic_renderer(vehicle)
        if field == "nested_oem_match":
            report["normalization"]["oem_match"] = value
        else:
            report[field] = value
        return pcm, report

    output = tmp_path / "preview"
    summary = diagnostic_preview.render_preview(
        output, vehicles=("hellcat",), renderer=renderer,
        runtime_identity_fn=_identity,
    )
    row = summary["vehicles"]["hellcat"]
    assert row["status"] == "RENDER_FAILED"
    assert "claim" in (output / row["report"]).read_text(encoding="utf-8").lower()
    assert "hellcat.wav" not in {path.name for path in output.glob("*.wav")}


def test_verifier_rejects_resealed_report_with_oem_claim(tmp_path):
    output = tmp_path / "preview"
    diagnostic_preview.render_preview(
        output, vehicles=("hellcat",), renderer=_synthetic_renderer,
        runtime_identity_fn=_identity,
    )
    report_path = output / "hellcat.report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["oem_match"] = True
    report_path.write_text(json.dumps(report), encoding="utf-8")
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][report_path.name] = _file_sha(report_path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="claim|report schema"):
        diagnostic_preview.verify_preview(output)


def test_verifier_rejects_resealed_nested_claim_field(tmp_path):
    output = tmp_path / "preview"
    diagnostic_preview.render_preview(
        output, vehicles=("hellcat",), renderer=_synthetic_renderer,
        runtime_identity_fn=_identity,
    )
    report_path = output / "hellcat.report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["normalization"]["oem_match"] = True
    report_path.write_text(json.dumps(report), encoding="utf-8")
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][report_path.name] = _file_sha(report_path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="report schema"):
        diagnostic_preview.verify_preview(output)


def test_short_stereo_waveform_cannot_pass_production_gate(tmp_path):
    def short(vehicle):
        pcm = np.zeros((20, 2), dtype=np.int16)
        return pcm, _good_report(vehicle, pcm)
    summary = diagnostic_preview.render_preview(tmp_path / "preview", vehicles=("hellcat",),
                                                renderer=short, runtime_identity_fn=_identity)
    assert summary["vehicles"]["hellcat"]["status"] == "RENDER_FAILED"


def test_runtime_identity_drift_aborts_without_manifest(tmp_path):
    calls = iter((_identity(), {**_identity(), "commit": "b" * 40}))
    output = tmp_path / "preview"
    with pytest.raises(ValueError, match="changed during render"):
        diagnostic_preview.render_preview(output, vehicles=("hellcat",), renderer=_synthetic_renderer,
                                          runtime_identity_fn=lambda: next(calls))
    assert not (output / "manifest.json").exists()


def test_manifest_rejects_traversal_entry(tmp_path):
    output = tmp_path / "preview"
    diagnostic_preview.render_preview(output, vehicles=("hellcat",), renderer=_synthetic_renderer,
                                      runtime_identity_fn=_identity)
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["../escape"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="unsafe manifest path"):
        diagnostic_preview.verify_preview(output)


def test_resealed_summary_cannot_redirect_report_or_unblock_index(tmp_path):
    output = tmp_path / "preview"
    diagnostic_preview.render_preview(output, vehicles=("hellcat",), renderer=_synthetic_renderer,
                                      runtime_identity_fn=_identity)
    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["vehicles"]["hellcat"]["report"] = "../outside.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][summary_path.name] = _file_sha(summary_path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="index semantic drift|unsafe report binding"):
        diagnostic_preview.verify_preview(output)
