from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.sound_sim.s12.acoustic_identity_v015.stage_ag import analyze_vehicle_identity as analyzer
from tools.sound_sim.s12.acoustic_identity_v015.stage_ag import build_identity_dashboards as ag_builder
from tools.sound_sim.s12.acoustic_identity_v015.stage_ag.build_blind_identity_package import (
    build_blind_package,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ag.render_identity_probe import (
    DEFAULT_SCENES,
    VEHICLES,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ag.vehicle_identity import (
    IDENTITY_MODE_LEGACY,
    IDENTITY_MODE_V1,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tone(freq: float, n: int = 8192, sr: int = 48_000) -> np.ndarray:
    t = np.arange(n, dtype=np.float64) / sr
    values = np.sin(2.0 * np.pi * freq * t) * 0.25
    return np.column_stack([values, values])


def _write_probe(root: Path) -> None:
    records = []
    vehicle_freq = {
        "hellcat": 160.0,
        "ferrari_458": 260.0,
        "lfa": 340.0,
        "gtr_r35": 220.0,
    }
    for vehicle in VEHICLES:
        vehicle_root = root / vehicle
        vehicle_root.mkdir(parents=True, exist_ok=True)
        for scene_index, scene in enumerate(DEFAULT_SCENES):
            for mode in (IDENTITY_MODE_LEGACY, IDENTITY_MODE_V1):
                # Hellcat stays identical; other identity candidates shift slightly.
                freq = vehicle_freq[vehicle] + 20.0 * scene_index
                if mode == IDENTITY_MODE_V1 and vehicle != "hellcat":
                    freq += {"ferrari_458": 25.0, "lfa": 45.0, "gtr_r35": 15.0}[vehicle]
                pcm = np.round(_tone(freq) * 32767).astype(np.int16)
                path = vehicle_root / f"{scene}__{mode}.wav"
                wavfile.write(path, 48_000, pcm)
                records.append(
                    {
                        "vehicle": vehicle,
                        "scene": scene,
                        "identity_mode": mode,
                        "path": path.relative_to(root).as_posix(),
                        "sha256": _sha(path),
                        "sample_rate": 48_000,
                    }
                )
    manifest = {
        "schema": "s12.stage_ag.vehicle_identity_probe.v1",
        "artifacts": records,
    }
    (root / "identity_probe_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


def test_identity_analyzer_emits_pairwise_scorecard_without_claiming_realism(
    tmp_path, monkeypatch
):
    probe = tmp_path / "probe"
    probe.mkdir()
    _write_probe(probe)

    # Keep this unit test hermetic: matched-state renderer behavior is tested by
    # the Stage AG engine tests; here we test scorecard logic only.
    fake_rendered = {
        vehicle: {
            "quarter_redline": _tone(120 + 30 * i),
            "mid_redline": _tone(180 + 40 * i),
            "high_redline": _tone(240 + 50 * i),
            "normalized_full_pull": _tone(300 + 60 * i),
        }
        for i, vehicle in enumerate(VEHICLES)
    }

    def fake_render(vehicle, mode, **kwargs):
        offset = 0.0 if mode == IDENTITY_MODE_LEGACY or vehicle == "hellcat" else 17.0
        return {
            state: _tone(
                140.0
                + 45.0 * VEHICLES.index(vehicle)
                + 25.0 * list(fake_rendered[vehicle]).index(state)
                + offset
            )
            for state in fake_rendered[vehicle]
        }

    monkeypatch.setattr(analyzer, "_render_matched", fake_render)
    output = tmp_path / "scorecard.json"
    analyzer.analyze_identity(probe, output, seed=11)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == "s12.stage_ag.identity_separation_scorecard.v1"
    assert payload["status"] == "DIAGNOSTIC_ONLY_NOT_HUMAN_PASS"
    assert len(payload["matched_state_pairwise"]) == 6 * 4
    assert payload["summary"]["reference_rows"] == 0
    hellcat = [
        row
        for row in payload["legacy_to_identity"]
        if row["vehicle"] == "hellcat"
    ]
    assert hellcat and all(row["pcm_changed"] is False for row in hellcat)


def _fake_dashboard_cfg(root: Path) -> dict:
    return {
        "dir": root,
        "port": 19088,
        "name": "Fixture Hellcat",
        "title": "Fixture Hellcat",
        "subtitle": "Fixture",
        "badge": "Fixture",
        "icon": "F",
        "idle_rpm": 720.0,
        "redline_rpm": 6500.0,
        "pull_start": 1500.0,
        "pull_end": 6200.0,
        "shift_cut": 0.12,
        "scenes": [
            {
                "id": "03_hot_idle",
                "index": 3,
                "category": "idle",
                "candidate_file": "03_hot_idle.wav",
                "ref_file": "",
                "title": "Fixture",
                "desc": "Fixture",
                "focus": "Fixture",
            }
        ],
    }


def test_identity_package_reuses_af_r_integrity_and_stays_not_fitted(
    tmp_path, monkeypatch
):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ad import (
        build_unified_dashboards as dashboards,
    )

    monkeypatch.setattr(
        dashboards, "VEHICLE_CONFIGS", {"hellcat": _fake_dashboard_cfg(tmp_path / "unused")}
    )
    monkeypatch.setattr(
        ag_builder,
        "stage_ag_source_receipt",
        lambda **kwargs: {
            "repository": "Jovifei/Tesla_Simulate_vico",
            "git_head": "a" * 40,
            "base_main": "b" * 40,
            "dependency_dirty": False,
            "source_policy": "TRACKED_SOURCE_CLEAN_REQUIRED",
            "source_status": "SOURCE_CLEAN",
            "promotable": True,
            "promotion_status": "PROMOTABLE",
        },
    )
    monkeypatch.setattr(
        ag_builder,
        "renderer_identity",
        lambda vehicle, flags: {
            "vehicle": vehicle,
            "ir_source_sha256": "c" * 64,
            "ir_effective_sha256": "d" * 64,
        },
    )
    monkeypatch.setattr(
        ag_builder,
        "identity_runtime_fingerprint",
        lambda: [{"path": "stage_ag/vehicle_identity.py", "sha256": "e" * 64}],
    )
    monkeypatch.setattr(
        ag_builder,
        "dependency_fingerprint",
        lambda: {
            "audio_runtime_fingerprint": [],
            "fit_algorithm_fingerprint": [],
            "package_ui_fingerprint": [],
        },
    )

    def fake_render(vehicle, cfg):
        web = Path(cfg["dir"]) / "web_audio"
        web.mkdir(parents=True, exist_ok=True)
        data = b"candidate-fixture"
        (web / "03_hot_idle.wav").write_bytes(data)
        (Path(cfg["dir"]) / "03_hot_idle.wav").write_bytes(data)

    def fake_dashboard(vehicle, cfg):
        (Path(cfg["dir"]) / "index.html").write_text("<html>id</html>", encoding="utf-8")
        (Path(cfg["dir"]) / "index_standalone.html").write_text(
            "<html>id</html>", encoding="utf-8"
        )

    monkeypatch.setattr(dashboards, "render_vehicle_audio", fake_render)
    monkeypatch.setattr(dashboards, "build_dashboard", fake_dashboard)

    args = argparse.Namespace(
        output_root=tmp_path / "packages",
        reference_root=None,
        vehicle="hellcat",
        identity_mode=IDENTITY_MODE_V1,
        seed=20260908,
        numerical_fixes=[],
        package_id="stage-ag-fixture",
        candidate_id="identity-v1",
        port_base=19088,
        allow_dirty_dev=False,
        fit_root=None,
    )
    published = ag_builder.build_identity_package(args)
    manifest = json.loads((published / "audition_manifest.json").read_text(encoding="utf-8"))
    contract = json.loads(
        (
            published
            / ag_builder.af_builder.DIR_NAMES["hellcat"]
            / "dashboard_contract.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["identity_mode"] == IDENTITY_MODE_V1
    assert manifest["fit_status"] == "NOT_FITTED"
    assert contract["identity_mode"] == IDENTITY_MODE_V1
    assert contract["fit_status"] == "NOT_FITTED"
    assert contract["human_status"] == "WAITING_FOR_JOVI_FEEDBACK"
    assert contract["package_gain_db"] == 0.0


def _fake_source_identity_package(root: Path) -> Path:
    vehicles = []
    for vehicle_index, vehicle in enumerate(VEHICLES):
        directory = f"pkg-{vehicle}"
        web = root / directory / "web_audio"
        web.mkdir(parents=True, exist_ok=True)
        hashes = {}
        for scene_index, filename in enumerate(("03_hot_idle.wav", "09_steady_mid.wav", "02_full_pull.wav")):
            payload = f"{vehicle}-{scene_index}".encode("utf-8")
            path = web / filename
            path.write_bytes(payload)
            hashes[filename] = _sha(path)
        vehicles.append(
            {
                "vehicle": vehicle,
                "directory": directory,
                "candidate_pcm_sha256": hashes,
            }
        )
    manifest = {
        "schema": "s12.stage_ag.package_manifest.v1",
        "identity_mode": IDENTITY_MODE_V1,
        "vehicles": vehicles,
    }
    encoded = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    manifest["manifest_sha256"] = hashlib.sha256(encoded).hexdigest()
    (root / "audition_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return root


def test_blind_package_keeps_mapping_outside_public_package_and_copies_bytes(
    tmp_path,
):
    source = _fake_source_identity_package(tmp_path / "source")
    output = tmp_path / "blind-public"
    mapping = tmp_path / "sealed" / "mapping.json"
    manifest_path = build_blind_package(source, output, mapping, seed=29)
    public_text = manifest_path.read_text(encoding="utf-8")
    html_text = (output / "index.html").read_text(encoding="utf-8")
    assert mapping.is_file()
    assert mapping.parent != output
    assert all(vehicle not in public_text for vehicle in VEHICLES)
    assert all(vehicle not in html_text for vehicle in VEHICLES)
    public = json.loads(public_text)
    assert public["mapping_status"] == "SEALED_UNTIL_JOVI_FEEDBACK"
    assert public["randomization_mode"] == "DETERMINISTIC_DIAGNOSTIC"
    assert public["status"] == "WAITING_FOR_JOVI_BLIND_IDENTITY_FEEDBACK"
    assert len(public["artifacts"]) == 12
    for record in public["artifacts"]:
        assert _sha(output / record["path"]) == record["sha256"]
