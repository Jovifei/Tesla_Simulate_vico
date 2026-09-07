from __future__ import annotations

import hashlib
import http.client
import importlib.util
import json
import argparse
import socket
import socketserver
import sys
import threading
import time
from pathlib import Path

import pytest
from scipy.io import wavfile
import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.stage_af.package_integrity import (
    audio_runtime_fingerprint,
    canonical_json_bytes,
    compare_h0_with_legacy,
    dependency_fingerprint,
    fit_identity_projection,
    git_source_receipt,
    h0_oracle_cases,
    package_ui_fingerprint,
    publish_staged_package,
    snapshot_fit_file,
    validate_fit_snapshot,
    validate_reference_sources,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_af.package_integrity import (
    fit_algorithm_fingerprint,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_af.build_existing_dashboards import (
    _bind_references,
)
STAGE_AD_DIR = Path(__file__).resolve().parents[1] / "stage_ad"
sys.path.insert(0, str(STAGE_AD_DIR))
try:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ad import (
        build_unified_dashboards as dashboards,
    )
finally:
    sys.path.pop(0)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ad.engine_sim_acoustics import (
    EngineAcoustics,
    load_impulse_response,
)
from review_packages.serve_dashboards import ReusableTCPServer


def _scene_config(tmp_path: Path) -> dict:
    web_audio = tmp_path / "web_audio"
    web_audio.mkdir(parents=True)
    for name in ("03_hot_idle.wav", "ref_hot_idle.wav"):
        wavfile.write(web_audio / name, 48_000, np.zeros(64, dtype=np.int16))
    return {
        "dir": tmp_path,
        "port": 19088,
        "name": "Fixture Hellcat",
        "title": "Fixture Hellcat",
        "subtitle": "Stage AF-R fixture",
        "badge": "Fixture",
        "icon": "F",
        "scenes": [
            {
                "id": "03_hot_idle",
                "index": 3,
                "category": "cruise",
                "candidate_file": "03_hot_idle.wav",
                "ref_file": "ref_hot_idle.wav",
                "title": "Fixture scene",
                "desc": "Fixture",
                "focus": "Fixture",
            }
        ],
    }


def _hermetic_hellcat_ir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "ir" / "new"
    root.mkdir(parents=True)
    wavfile.write(
        root / "test_engine_16_eq_adjusted_16.wav",
        48_000,
        np.asarray([1000, 2000, 1000, 500], dtype=np.int16),
    )
    monkeypatch.setenv("S12_ENGINE_SIM_IR_ROOT", str(tmp_path / "ir"))


def _contract() -> dict:
    return {
        "schema": "s12.stage_af.dashboard_contract.v1",
        "package_id": "pkg-integrity-fixture",
        "candidate_id": "candidate-h0",
        "vehicle": "hellcat",
        "flags": [],
        "seed": 20260906,
        "fit_status": "NOT_FITTED",
        "measurement_status": "NOT_MEASURED",
        "sample_rate_hz": 48_000,
        "package_port": 19_088,
        "nav_urls": {"hellcat": "http://localhost:19088/"},
        "references": {
            "ref_hot_idle.wav": {
                "available": True,
                "fit_required": False,
                "source_label": "fixture reference",
                "sha256": "a" * 64,
            }
        },
        "candidate_pcm_sha256": {"03_hot_idle.wav": "b" * 64},
        "reference_sha256": {"03_hot_idle.wav": "a" * 64},
        "parameters": [],
    }


def test_dashboard_contract_removes_fixed_metrics_and_uses_truthful_state(tmp_path, monkeypatch):
    cfg = _scene_config(tmp_path)
    monkeypatch.setattr(
        dashboards,
        "TEMPLATE_PATH",
        Path(dashboards.__file__).with_name("audition_dashboard_template.html"),
    )
    cfg["_dashboard_contract"] = _contract()
    cfg["_nav_ports"] = {"hellcat": 19088, "ferrari_458": 19089, "lfa": 19090, "gtr_r35": 19091}
    dashboards.build_dashboard("hellcat", cfg)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")

    assert "0.880" not in html
    assert "0.64835" not in html
    assert "Stage AD Hellcat V8 Closed-Loop Calibration v1" not in html
    assert "NOT_FITTED" in html
    assert "pkg-integrity-fixture" in html
    assert "filterCategory('cruise')" in html
    assert "filterCategory('cruising')" not in html
    assert "candidate_pcm_sha256" in html
    assert "reference_sha256" in html
    assert "http://localhost:19088/" in html
    assert "SCORECARD_STORAGE_KEY" in html
    assert "hasReference(scene)" in html
    assert "AUDIO_SELF_CONTAINED / STYLE_NETWORK_DEPENDENCY" in html


def test_dashboard_build_keeps_missing_reference_unavailable(tmp_path, monkeypatch):
    cfg = _scene_config(tmp_path)
    (tmp_path / "web_audio" / "ref_hot_idle.wav").unlink()
    contract = _contract()
    contract["references"]["ref_hot_idle.wav"]["available"] = False
    cfg["_dashboard_contract"] = contract
    monkeypatch.setattr(
        dashboards,
        "TEMPLATE_PATH",
        Path(dashboards.__file__).with_name("audition_dashboard_template.html"),
    )
    dashboards.build_dashboard("hellcat", cfg)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert '"03_hot_idle_ref":' not in html


def test_single_vehicle_dashboard_navigation_is_package_scoped(tmp_path, monkeypatch):
    cfg = _scene_config(tmp_path)
    cfg["_dashboard_contract"] = _contract()
    cfg["_nav_ports"] = {"hellcat": 21088}
    cfg["_nav_vehicles"] = ("hellcat",)
    monkeypatch.setattr(
        dashboards,
        "TEMPLATE_PATH",
        Path(dashboards.__file__).with_name("audition_dashboard_template.html"),
    )
    dashboards.build_dashboard("hellcat", cfg)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "localhost:21088/" in html
    assert "Ferrari 458 Italia" not in html
    assert "localhost:19089/" not in html


def test_reference_fit_drift_is_rejected(tmp_path):
    reference_root = tmp_path / "references"
    source_dir = reference_root / "hellcat"
    source_dir.mkdir(parents=True)
    source = source_dir / "ref_hot_idle.wav"
    source.write_bytes(b"reference-B")
    cfg = {"dir": tmp_path / "out", "scenes": [{"ref_file": "ref_hot_idle.wav"}]}
    expected = {
        "hot_idle": {
            "filename": "ref_hot_idle.wav",
            "sha256": hashlib.sha256(b"reference-A").hexdigest(),
        }
    }

    with pytest.raises(ValueError, match="fit reference SHA mismatch"):
        _bind_references("hellcat", cfg, reference_root, expected_sources=expected)


def test_omitted_reference_root_never_searches_destination_or_old_packages(tmp_path):
    cfg = _scene_config(tmp_path / "candidate")
    (Path(cfg["dir"]) / "web_audio" / "ref_hot_idle.wav").unlink()
    old_package = tmp_path / "packages" / "old" / "hellcat"
    old_package.mkdir(parents=True)
    (old_package / "ref_hot_idle.wav").write_bytes(b"stale-old-reference")

    assert _bind_references("hellcat", cfg, None) == {}
    assert not (Path(cfg["dir"]) / "web_audio" / "ref_hot_idle.wav").exists()


def test_stale_destination_reference_is_fail_closed(tmp_path):
    cfg = _scene_config(tmp_path / "candidate")
    source_destination = Path(cfg["dir"]) / "web_audio" / "ref_hot_idle.wav"
    source_destination.write_bytes(b"stale-destination")

    with pytest.raises(ValueError, match="stale destination bytes"):
        _bind_references("hellcat", cfg, tmp_path / "missing-source")


def test_fit_payload_requires_all_fit_reference_scenes():
    from tools.sound_sim.s12.acoustic_identity_v015.stage_af.physical_closed_loop import (
        validate_fit_payload,
    )

    payload = {
        "schema": "s12.stage_af.physical_fit.v5",
        "vehicle": "hellcat",
        "seed": 20260906,
        "numerical_fixes": [],
        "reference_level": "R3_PRIVATE_DIAGNOSTIC_ONLY",
        "reference_sources": {"hot_idle": {"filename": "ref_hot_idle.wav", "sha256": "a" * 64}},
    }
    with pytest.raises(ValueError, match="fit reference missing"):
        validate_fit_payload(payload, "hellcat", (), 20260906)


def test_fit_payload_rejects_unapproved_reference_level():
    from tools.sound_sim.s12.acoustic_identity_v015.stage_af.physical_closed_loop import (
        validate_fit_payload,
    )

    payload = {
        "schema": "s12.stage_af.physical_fit.v5",
        "vehicle": "hellcat",
        "seed": 20260906,
        "numerical_fixes": [],
        "reference_level": "R1_FORMAL_CALIBRATION",
        "reference_sources": {},
    }
    with pytest.raises(ValueError, match="unsupported reference evidence level"):
        validate_fit_payload(payload, "hellcat", (), 20260906)


def test_fit_v4_is_not_silently_reinterpreted():
    from tools.sound_sim.s12.acoustic_identity_v015.stage_af.physical_closed_loop import (
        validate_fit_payload,
    )

    payload = {
        "schema": "s12.stage_af.physical_fit.v4",
        "vehicle": "hellcat",
        "seed": 20260906,
        "numerical_fixes": [],
    }
    with pytest.raises(ValueError, match="old/unversioned fit"):
        validate_fit_payload(payload, "hellcat", (), 20260906)


def test_publish_refuses_existing_package_and_keeps_staging_recoverable(tmp_path):
    staging = tmp_path / "staging" / "run-1"
    staging.mkdir(parents=True)
    (staging / "READY.marker").write_text("validated", encoding="utf-8")
    published = tmp_path / "run-1"
    published.mkdir()

    with pytest.raises(FileExistsError):
        publish_staged_package(staging, published)
    assert staging.is_dir()
    assert published.is_dir()


def test_builder_publishes_fresh_package_with_manifest_and_contract(tmp_path, monkeypatch):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_af import build_existing_dashboards as builder

    monkeypatch.setattr(dashboards, "VEHICLE_CONFIGS", {"hellcat": _scene_config(tmp_path / "unused")})
    monkeypatch.setattr(
        builder,
        "git_source_receipt",
        lambda allow_dirty_dev=False: {
            "repository": "Jovifei/Tesla_Simulate_vico",
            "git_head": "fixture-head",
            "base_main": "fixture-main",
            "dependency_dirty": True,
            "source_policy": "DEV_DIRTY_SOURCE / NOT_PROMOTABLE",
            "source_status": "DEV_DIRTY_SOURCE",
            "promotable": False,
            "promotion_status": "NOT_PROMOTABLE",
        },
    )

    def fake_render(vehicle, cfg):
        web_dir = Path(cfg["dir"]) / "web_audio"
        web_dir.mkdir(parents=True, exist_ok=True)
        payload = b"candidate-pcm"
        (web_dir / "03_hot_idle.wav").write_bytes(payload)
        (Path(cfg["dir"]) / "03_hot_idle.wav").write_bytes(payload)

    def fake_dashboard(vehicle, cfg):
        (Path(cfg["dir"]) / "index.html").write_text("<html>index</html>", encoding="utf-8")
        (Path(cfg["dir"]) / "index_standalone.html").write_text("<html>standalone</html>", encoding="utf-8")

    monkeypatch.setattr(dashboards, "render_vehicle_audio", fake_render)
    monkeypatch.setattr(dashboards, "build_dashboard", fake_dashboard)
    monkeypatch.setattr(builder, "renderer_identity", lambda *args, **kwargs: {"vehicle": "hellcat", "numerical_fixes": []})
    monkeypatch.setattr(
        builder,
        "dependency_fingerprint",
        lambda: {
            "audio_runtime_fingerprint": [{"path": "audio.py", "sha256": "a" * 64}],
            "fit_algorithm_fingerprint": [{"path": "fit.py", "sha256": "a" * 64}],
            "package_ui_fingerprint": [{"path": "ui.py", "sha256": "a" * 64}],
        },
    )

    reference_root = tmp_path / "references"
    source = reference_root / "hellcat" / "ref_hot_idle.wav"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"reference")
    output_root = tmp_path / "packages"
    args = argparse.Namespace(
        package_id="pkg-fresh",
        candidate_id="candidate-r",
        output_root=output_root,
        reference_root=reference_root,
        vehicle="hellcat",
        baseline=True,
        fit_root=None,
        numerical_fixes=[],
        seed=20260906,
        port_base=19088,
        allow_dirty_dev=True,
    )

    published = builder._build_package(args)
    assert published == output_root / "pkg-fresh"
    manifest = json.loads((published / "audition_manifest.json").read_text(encoding="utf-8"))
    contract = json.loads((published / builder.DIR_NAMES["hellcat"] / "dashboard_contract.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "s12.stage_af.package_manifest.v1"
    assert manifest["manifest_sha256"]
    assert manifest["audio_runtime_fingerprint"]
    assert manifest["fit_algorithm_fingerprint"]
    assert manifest["package_ui_fingerprint"]
    assert manifest["source_status"] == "DEV_DIRTY_SOURCE"
    assert manifest["promotable"] is False
    assert manifest["promotion_status"] == "NOT_PROMOTABLE"
    assert manifest["source_receipt"]["source_policy"] == "DEV_DIRTY_SOURCE / NOT_PROMOTABLE"
    assert manifest["vehicles"][0]["fit_snapshot"] is None
    manifest_without_checksum = dict(manifest)
    manifest_sha = manifest_without_checksum.pop("manifest_sha256")
    assert hashlib.sha256(canonical_json_bytes(manifest_without_checksum)).hexdigest() == manifest_sha
    assert contract["package_id"] == "pkg-fresh"
    assert contract["fit_status"] == "NOT_FITTED"
    assert contract["fit_metric_status"] == "NOT_MEASURED"
    assert contract["human_status"] == "WAITING_FOR_JOVI_FEEDBACK"
    assert contract["candidate_pcm_sha256"]["03_hot_idle.wav"]
    assert contract["contract_sha256"]
    contract_without_checksum = dict(contract)
    contract_sha = contract_without_checksum.pop("contract_sha256")
    assert hashlib.sha256(canonical_json_bytes(contract_without_checksum)).hexdigest() == contract_sha
    binding = json.loads(
        (published / builder.DIR_NAMES["hellcat"] / "stage_af_binding.json").read_text(encoding="utf-8")
    )
    assert binding["scenes"][0]["candidate_pcm_sha256"] == contract["candidate_pcm_sha256"]["03_hot_idle.wav"]
    assert binding["scenes"][0]["reference_available"] is True
    assert binding["scenes"][0]["ir_source_sha256"] is None
    assert manifest["vehicles"][0]["html"]["index"].endswith("/index.html")
    assert not (output_root / ".stage_af_r_staging" / "pkg-fresh").exists()


def test_builder_cleans_failed_staging_and_refuses_existing_package(tmp_path, monkeypatch):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_af import build_existing_dashboards as builder

    monkeypatch.setattr(dashboards, "VEHICLE_CONFIGS", {"hellcat": _scene_config(tmp_path / "unused")})
    monkeypatch.setattr(builder, "renderer_identity", lambda *args, **kwargs: {"vehicle": "hellcat", "numerical_fixes": []})
    monkeypatch.setattr(
        builder,
        "dependency_fingerprint",
        lambda: {
            "audio_runtime_fingerprint": [{"path": "audio.py", "sha256": "a" * 64}],
            "fit_algorithm_fingerprint": [{"path": "fit.py", "sha256": "a" * 64}],
            "package_ui_fingerprint": [{"path": "ui.py", "sha256": "a" * 64}],
        },
    )
    monkeypatch.setattr(dashboards, "render_vehicle_audio", lambda vehicle, cfg: (_ for _ in ()).throw(RuntimeError("injected render failure")))
    monkeypatch.setattr(dashboards, "build_dashboard", lambda vehicle, cfg: None)
    args = argparse.Namespace(
        package_id="pkg-fail",
        candidate_id="candidate-r",
        output_root=tmp_path / "packages",
        reference_root=tmp_path / "references",
        vehicle="hellcat",
        baseline=True,
        fit_root=None,
        numerical_fixes=[],
        seed=20260906,
        port_base=19088,
        allow_dirty_dev=True,
    )
    with pytest.raises(RuntimeError, match="injected render failure"):
        builder._build_package(args)
    assert not (args.output_root / "pkg-fail").exists()
    assert not (args.output_root / ".stage_af_r_staging" / "pkg-fail").exists()

    existing = args.output_root / "pkg-existing"
    existing.mkdir(parents=True)
    args.package_id = "pkg-existing"
    with pytest.raises(FileExistsError):
        builder._build_package(args)


def test_builder_cleans_staging_when_fit_is_missing(tmp_path):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_af import build_existing_dashboards as builder

    args = argparse.Namespace(
        package_id="pkg-missing-fit",
        candidate_id="candidate-r",
        output_root=tmp_path / "packages",
        reference_root=tmp_path / "references",
        vehicle="hellcat",
        baseline=False,
        fit_root=tmp_path / "missing-fit-root",
        numerical_fixes=[],
        seed=20260906,
        port_base=19088,
        allow_dirty_dev=True,
    )
    with pytest.raises(ValueError, match="requested fit missing"):
        builder._build_package(args)
    assert not (args.output_root / ".stage_af_r_staging" / "pkg-missing-fit").exists()


def test_builder_rejects_dirty_tracked_source_without_dev_flag(tmp_path, monkeypatch):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_af import build_existing_dashboards as builder

    def fake_receipt(*, allow_dirty_dev=False):
        if not allow_dirty_dev:
            raise ValueError("tracked source is dirty; use --allow-dirty-dev for a non-promotable smoke")
        return {
            "repository": "fixture",
            "git_head": "fixture-head",
            "base_main": "fixture-main",
            "dependency_dirty": True,
            "source_policy": "DEV_DIRTY_SOURCE / NOT_PROMOTABLE",
            "source_status": "DEV_DIRTY_SOURCE",
            "promotable": False,
            "promotion_status": "NOT_PROMOTABLE",
        }
    monkeypatch.setattr(builder, "git_source_receipt", fake_receipt)

    args = argparse.Namespace(
        package_id="pkg-dirty-source",
        candidate_id="candidate-r",
        output_root=tmp_path / "packages",
        reference_root=None,
        vehicle="hellcat",
        baseline=True,
        fit_root=None,
        numerical_fixes=[],
        seed=20260906,
        port_base=19088,
        allow_dirty_dev=False,
    )
    with pytest.raises(ValueError, match="tracked source is dirty"):
        builder._build_package(args)
    assert not (args.output_root / ".stage_af_r_staging" / "pkg-dirty-source").exists()


def test_fitted_package_keeps_an_independent_fit_snapshot(tmp_path, monkeypatch):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_af import build_existing_dashboards as builder

    monkeypatch.setattr(dashboards, "VEHICLE_CONFIGS", {"hellcat": _scene_config(tmp_path / "unused")})
    monkeypatch.setattr(builder, "renderer_identity", lambda *args, **kwargs: {"vehicle": "hellcat", "numerical_fixes": []})
    monkeypatch.setattr(builder, "validate_fit_payload", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        builder,
        "dependency_fingerprint",
        lambda: {
            "audio_runtime_fingerprint": [{"path": "audio.py", "sha256": "a" * 64}],
            "fit_algorithm_fingerprint": [{"path": "fit.py", "sha256": "a" * 64}],
            "package_ui_fingerprint": [{"path": "ui.py", "sha256": "a" * 64}],
        },
    )

    def fake_render(vehicle, cfg):
        web_dir = Path(cfg["dir"]) / "web_audio"
        web_dir.mkdir(parents=True, exist_ok=True)
        payload = b"candidate-pcm"
        (web_dir / "03_hot_idle.wav").write_bytes(payload)
        (Path(cfg["dir"]) / "03_hot_idle.wav").write_bytes(payload)

    monkeypatch.setattr(dashboards, "render_vehicle_audio", fake_render)
    monkeypatch.setattr(
        dashboards,
        "build_dashboard",
        lambda vehicle, cfg: (
            (Path(cfg["dir"]) / "index.html").write_text("<html>index</html>", encoding="utf-8"),
            (Path(cfg["dir"]) / "index_standalone.html").write_text("<html>standalone</html>", encoding="utf-8"),
        ),
    )

    fit_payload = {
        "schema": "s12.stage_af.physical_fit.v5",
        "vehicle": "hellcat",
        "seed": 20260906,
        "numerical_fixes": [],
        "reference_level": "R3_PRIVATE_DIAGNOSTIC_ONLY",
        "reference_sources": {},
        "overrides": {},
        "fit_identity": {},
        "baseline_distance": 1.0,
        "final_distance": 0.5,
        "renderer_identity": {"vehicle": "hellcat", "numerical_fixes": []},
    }
    fit_payload["fit_sha256"] = hashlib.sha256(canonical_json_bytes(fit_payload)).hexdigest()
    fit_root = tmp_path / "fits" / "hellcat"
    fit_root.mkdir(parents=True)
    fit_source = fit_root / "final_r3_diagnostic_fit.json"
    fit_source.write_text(json.dumps(fit_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    args = argparse.Namespace(
        package_id="pkg-fit-snapshot",
        candidate_id="candidate-r",
        output_root=tmp_path / "packages",
        reference_root=None,
        vehicle="hellcat",
        baseline=False,
        fit_root=tmp_path / "fits",
        numerical_fixes=[],
        seed=20260906,
        port_base=19088,
        allow_dirty_dev=True,
    )
    published = builder._build_package(args)
    snapshot = published / builder.DIR_NAMES["hellcat"] / "evidence" / "fit" / "final_fit.json"
    source_sha = hashlib.sha256(fit_source.read_bytes()).hexdigest()
    fit_source.unlink()
    restored = validate_fit_snapshot(snapshot)
    manifest = json.loads((published / "audition_manifest.json").read_text(encoding="utf-8"))
    contract = json.loads(
        (published / builder.DIR_NAMES["hellcat"] / "dashboard_contract.json").read_text(encoding="utf-8")
    )
    assert contract["fit_status"] == "FITTED"
    assert contract["fit_metric_status"] == "FIT_DIAGNOSTIC_DISTANCE_AVAILABLE"
    assert contract["human_status"] == "WAITING_FOR_JOVI_FEEDBACK"
    assert restored["snapshot_sha256"] == hashlib.sha256(snapshot.read_bytes()).hexdigest()
    assert any(item["role"] == "fit:snapshot" for item in manifest["artifacts"])
    assert manifest["vehicles"][0]["fit_snapshot"]["snapshot_sha256"] == restored["snapshot_sha256"]
    assert json.loads(snapshot.read_text(encoding="utf-8"))["fit_sha256"] == fit_payload["fit_sha256"]
    assert source_sha == restored["snapshot_sha256"]


def test_dependency_fingerprint_covers_renderer_adapter_and_convolver():
    fingerprint = dependency_fingerprint()
    assert set(fingerprint) == {
        "audio_runtime_fingerprint",
        "fit_algorithm_fingerprint",
        "package_ui_fingerprint",
    }
    paths = {
        entry["path"]
        for entries in fingerprint.values()
        for entry in entries
    }
    assert any(path.endswith("engine_sim_acoustics.py") for path in paths)
    assert any(path.endswith("physical_closed_loop.py") for path in paths)
    assert any(path.endswith("partitioned_convolver.py") for path in paths)


def test_dependency_identity_has_explicit_scopes():
    audio = {entry["path"] for entry in audio_runtime_fingerprint()}
    fit = {entry["path"] for entry in fit_algorithm_fingerprint()}
    ui = {entry["path"] for entry in package_ui_fingerprint()}
    assert any(path.endswith("engine_sim_acoustics.py") for path in audio)
    assert any(path.endswith("partitioned_convolver.py") for path in audio)
    assert any(path.endswith("physical_closed_loop.py") for path in fit)
    assert any(path.endswith("spectral_guard.py") for path in fit)
    assert any(path.endswith("fit_cli.py") for path in fit)
    assert any(path.endswith("audition_dashboard_template.html") for path in ui)
    assert any(path.endswith("serve_dashboards.py") for path in ui)


def test_ui_fingerprint_does_not_invalidate_fit_identity(tmp_path, monkeypatch):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_af.physical_closed_loop import (
        renderer_identity,
    )

    _hermetic_hellcat_ir(tmp_path, monkeypatch)
    identity = renderer_identity("hellcat")
    changed = json.loads(json.dumps(identity))
    changed["package_ui_fingerprint"][0]["sha256"] = "0" * 64
    assert fit_identity_projection(identity) == fit_identity_projection(changed)


def test_audio_or_fit_fingerprint_invalidates_fit_identity(tmp_path, monkeypatch):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_af.physical_closed_loop import (
        renderer_identity,
    )

    _hermetic_hellcat_ir(tmp_path, monkeypatch)
    identity = renderer_identity("hellcat")
    for field in ("audio_runtime_fingerprint", "fit_algorithm_fingerprint"):
        changed = json.loads(json.dumps(identity))
        changed[field][0]["sha256"] = "0" * 64
        assert fit_identity_projection(identity) != fit_identity_projection(changed)


def test_fit_snapshot_is_exact_and_self_validating(tmp_path):
    payload = {
        "schema": "s12.stage_af.physical_fit.v5",
        "vehicle": "hellcat",
        "seed": 20260906,
        "numerical_fixes": [],
        "reference_level": "R3_PRIVATE_DIAGNOSTIC_ONLY",
        "reference_sources": {},
        "overrides": {},
        "fit_identity": {},
    }
    payload["fit_sha256"] = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    source = tmp_path / "source-fit.json"
    source.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    snapshot = tmp_path / "evidence" / "fit" / "final_fit.json"
    record = snapshot_fit_file(source, snapshot)
    source.unlink()
    restored = validate_fit_snapshot(snapshot)
    assert record["snapshot_sha256"] == restored["snapshot_sha256"]
    assert restored["fit_sha256"] == payload["fit_sha256"]


def test_git_source_receipt_has_required_fields():
    receipt = git_source_receipt(allow_dirty_dev=True)
    assert {
        "repository",
        "git_head",
        "base_main",
        "dependency_dirty",
        "source_policy",
    } <= set(receipt)
    assert receipt["source_policy"] in {
        "TRACKED_SOURCE_CLEAN_REQUIRED",
        "DEV_DIRTY_SOURCE / NOT_PROMOTABLE",
    }


def test_h0_oracle_cases_cover_steady_shift_afterfire_windows():
    cases = h0_oracle_cases(3.0)
    assert set(cases) == {"steady_body", "shift", "afterfire"}
    for name in ("shift", "afterfire"):
        events = cases[name][name + "_events"]
        assert events
        assert all(0.0 < event[0] < 3.0 for event in events)


def test_h0_uses_legacy_ir_search_priority(tmp_path, monkeypatch):
    root = tmp_path / "ir"
    (root / "new").mkdir(parents=True)
    wavfile.write(root / "example.wav", 48_000, np.asarray([1000], dtype=np.int16))
    wavfile.write(root / "new" / "example.wav", 48_000, np.asarray([3000], dtype=np.int16))
    monkeypatch.setenv("S12_ENGINE_SIM_IR_ROOT", str(root))

    loaded = load_impulse_response("example", target_sr=48_000)

    assert loaded[0] == pytest.approx(3000.0 / 32768.0)


def test_h0_compares_against_fixed_pre_fix_commit(monkeypatch):
    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_ad.engine_sim_acoustics.load_impulse_response",
        lambda *args, **kwargs: np.asarray([1.0], dtype=np.float64),
    )
    n = 2_400
    rpm = np.linspace(900.0, 3_800.0, n)
    throttle = np.linspace(0.15, 1.0, n)
    assert compare_h0_with_legacy(
        "28ee2bd73298959dc4831320e8b080b833c8c3d8",
        "hellcat",
        rpm,
        throttle,
        duration=n / 48_000.0,
        seed=20260906,
    )


class _SlowHandler(socketserver.BaseRequestHandler):
    body = b"X" * (2 * 1024 * 1024)

    def handle(self):
        self.request.recv(4096)
        self.request.sendall(
            b"HTTP/1.0 200 OK\r\nContent-Length: "
            + str(len(self.body)).encode("ascii")
            + b"\r\n\r\n"
        )
        for offset in range(0, len(self.body), 4096):
            self.request.sendall(self.body[offset : offset + 4096])
            time.sleep(0.001)


def _second_request(port: int, timeout: float) -> tuple[int, bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    connection.request("GET", "/fast")
    response = connection.getresponse()
    data = response.read(32)
    connection.close()
    return response.status, data


def test_threaded_review_server_handles_slow_client_and_second_request():
    server = ReusableTCPServer(("127.0.0.1", 0), _SlowHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    slow = socket.create_connection(server.server_address, timeout=2)
    slow.sendall(b"GET /slow HTTP/1.0\r\nHost: localhost\r\n\r\n")
    time.sleep(0.05)
    try:
        status, data = _second_request(server.server_address[1], timeout=2)
        assert status == 200
        assert data == b"X" * 32
    finally:
        slow.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_single_thread_control_is_blocked_by_same_slow_client():
    server = socketserver.TCPServer(("127.0.0.1", 0), _SlowHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    slow = socket.create_connection(server.server_address, timeout=2)
    slow.sendall(b"GET /slow HTTP/1.0\r\nHost: localhost\r\n\r\n")
    time.sleep(0.05)
    try:
        with pytest.raises((TimeoutError, socket.timeout, ConnectionError, OSError)):
            _second_request(server.server_address[1], timeout=0.2)
    finally:
        slow.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
