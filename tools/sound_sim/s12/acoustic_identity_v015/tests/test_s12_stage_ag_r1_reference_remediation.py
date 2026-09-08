from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_af.package_integrity import (
    canonical_json_bytes,
    sha256_file,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ag import (
    build_identity_dashboards as base_identity_builder,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ag.build_blind_identity_package import (
    build_blind_package,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ag.build_identity_dashboards_r1 import (
    build_identity_package_r1,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ag.render_identity_probe_r1 import (
    render_probe_r1,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ag.run_local_identity_validation_r1 import (
    resume_after_package_r1,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ag.vehicle_identity import (
    VEHICLE_IDENTITY_PROFILES,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ag.vehicle_identity_r1 import (
    IDENTITY_MODE_LEGACY,
    IDENTITY_MODE_V1R1,
    R1_CONTROLS,
    VehicleIdentityR1Engine,
    _state_envelope,
    synthesize_vehicle_identity_layer_r1,
    vehicle_identity_r1_signature,
)


def _identity_ir(*args, **kwargs):
    return np.asarray([1.0], dtype=np.float64)


def _trace(rpm: float, throttle: float, duration: float = 0.18, sr: int = 48_000):
    n = int(duration * sr)
    return (
        np.full(n, rpm, dtype=np.float64),
        np.full(n, throttle, dtype=np.float64),
        duration,
    )


def _write_fake_stage_ag_package(root: Path, identity_mode: str) -> Path:
    scene_files = ("03_hot_idle.wav", "09_steady_mid.wav", "02_full_pull.wav")
    vehicles = []
    for vehicle in ("hellcat", "ferrari_458", "lfa", "gtr_r35"):
        directory = f"pkg-{vehicle}"
        web_audio = root / directory / "web_audio"
        web_audio.mkdir(parents=True, exist_ok=True)
        hashes = {}
        for filename in scene_files:
            # Hellcat remains the byte-identical anchor; non-Hellcat R1 differs.
            mode_token = "anchor" if vehicle == "hellcat" else identity_mode
            data = f"{vehicle}:{filename}:{mode_token}".encode("utf-8")
            path = web_audio / filename
            path.write_bytes(data)
            hashes[filename] = sha256_file(path)
        vehicles.append(
            {
                "vehicle": vehicle,
                "directory": directory,
                "candidate_pcm_sha256": hashes,
                "reference_sha256": {"same-reference": "a" * 64},
            }
        )
    payload = {
        "schema": "s12.stage_ag.package_manifest.v1",
        "identity_mode": identity_mode,
        "vehicles": vehicles,
    }
    payload["manifest_sha256"] = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    (root / "audition_manifest.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    return root


def test_r1_signature_records_absolute_state_policy():
    signature = vehicle_identity_r1_signature("ferrari_458")
    assert signature["identity_mode"] == IDENTITY_MODE_V1R1
    assert signature["state_control"]["redline_rpm"] == 9000.0
    assert "NO_PER_TRACK_IDENTITY_PEAK_NORMALIZATION" in signature["amplitude_policy"]


def test_r1_idle_layer_is_not_peak_recovered():
    for vehicle, idle in (("ferrari_458", 1050.0), ("lfa", 850.0)):
        rpm_idle, thr_idle, _ = _trace(idle, 0.0)
        rpm_pull, thr_pull, _ = _trace(R1_CONTROLS[vehicle].redline_rpm * 0.75, 1.0)
        idle_layer = synthesize_vehicle_identity_layer_r1(vehicle, rpm_idle, thr_idle, seed=7)
        pull_layer = synthesize_vehicle_identity_layer_r1(vehicle, rpm_pull, thr_pull, seed=7)
        idle_peak = float(np.max(np.abs(idle_layer)))
        pull_peak = float(np.max(np.abs(pull_layer)))
        assert idle_peak < 0.20
        assert pull_peak > idle_peak * 3.0
        assert pull_peak <= 0.94 + 1e-12


def test_gtr_r1_full_load_mix_is_selectively_attenuated():
    rpm, throttle, _ = _trace(6900.0, 1.0)
    _, scale = _state_envelope("gtr_r35", rpm, throttle)
    assert float(np.min(scale)) == pytest.approx(0.68)
    effective_mix = VEHICLE_IDENTITY_PROFILES["gtr_r35"].identity_mix * scale
    assert float(np.max(effective_mix)) == pytest.approx(0.1088)

    rpm_mid, throttle_mid, _ = _trace(3600.0, 0.45)
    _, mid_scale = _state_envelope("gtr_r35", rpm_mid, throttle_mid)
    assert np.allclose(mid_scale, 1.0)


def test_r1_hellcat_is_byte_preserving(monkeypatch):
    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_ad.engine_sim_acoustics.load_impulse_response",
        _identity_ir,
    )
    rpm, throttle, duration = _trace(3200.0, 0.55)
    legacy = VehicleIdentityR1Engine(
        "hellcat", identity_mode=IDENTITY_MODE_LEGACY, seed=11
    ).render_track(rpm, throttle, duration)
    r1 = VehicleIdentityR1Engine(
        "hellcat", identity_mode=IDENTITY_MODE_V1R1, seed=11
    ).render_track(rpm, throttle, duration)
    assert np.array_equal(legacy, r1)


@pytest.mark.parametrize("vehicle", ["ferrari_458", "lfa", "gtr_r35"])
def test_r1_changes_non_hellcat_pcm_without_clipping(monkeypatch, vehicle):
    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_ad.engine_sim_acoustics.load_impulse_response",
        _identity_ir,
    )
    rpm, throttle, duration = _trace(R1_CONTROLS[vehicle].redline_rpm * 0.55, 0.55)
    legacy = VehicleIdentityR1Engine(
        vehicle, identity_mode=IDENTITY_MODE_LEGACY, seed=13
    ).render_track(rpm, throttle, duration)
    r1 = VehicleIdentityR1Engine(
        vehicle, identity_mode=IDENTITY_MODE_V1R1, seed=13
    ).render_track(rpm, throttle, duration)
    assert legacy.shape == r1.shape
    assert not np.array_equal(legacy, r1)
    assert np.max(np.abs(r1.astype(np.int32))) <= int(0.94 * 32767) + 1


def test_r1_probe_binds_new_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_ad.engine_sim_acoustics.load_impulse_response",
        _identity_ir,
    )
    manifest = render_probe_r1(
        tmp_path / "probe",
        vehicles=("hellcat",),
        scenes=("hot_idle",),
        seed=17,
    )
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["candidate_identity_mode"] == IDENTITY_MODE_V1R1
    modes = {row["identity_mode"] for row in payload["artifacts"]}
    assert modes == {IDENTITY_MODE_LEGACY, IDENTITY_MODE_V1R1}
    rows = {row["identity_mode"]: row for row in payload["artifacts"]}
    assert rows[IDENTITY_MODE_LEGACY]["sha256"] == rows[IDENTITY_MODE_V1R1]["sha256"]


def test_r1_package_adapter_binds_and_restores_globals(monkeypatch, tmp_path):
    original_mode = base_identity_builder.IDENTITY_MODE_V1
    original_modes = base_identity_builder.IDENTITY_MODES
    original_engine = base_identity_builder.VehicleIdentityEngine
    original_signature = base_identity_builder.vehicle_identity_signature
    original_fingerprint = base_identity_builder.identity_runtime_fingerprint

    captured = {}

    def fake_build(args):
        captured["mode"] = base_identity_builder.IDENTITY_MODE_V1
        captured["modes"] = base_identity_builder.IDENTITY_MODES
        captured["engine"] = base_identity_builder.VehicleIdentityEngine
        captured["signature"] = base_identity_builder.vehicle_identity_signature("lfa")
        captured["fingerprint"] = base_identity_builder.identity_runtime_fingerprint()
        return tmp_path / "published"

    monkeypatch.setattr(base_identity_builder, "build_identity_package", fake_build)
    result = build_identity_package_r1(argparse.Namespace(identity_mode=IDENTITY_MODE_V1R1))

    assert result == tmp_path / "published"
    assert captured["mode"] == IDENTITY_MODE_V1R1
    assert IDENTITY_MODE_V1R1 in captured["modes"]
    assert captured["engine"] is VehicleIdentityR1Engine
    assert captured["signature"]["identity_mode"] == IDENTITY_MODE_V1R1
    assert captured["fingerprint"][0]["path"].endswith("vehicle_identity_r1.py")

    assert base_identity_builder.IDENTITY_MODE_V1 == original_mode
    assert base_identity_builder.IDENTITY_MODES == original_modes
    assert base_identity_builder.VehicleIdentityEngine is original_engine
    assert base_identity_builder.vehicle_identity_signature is original_signature
    assert base_identity_builder.identity_runtime_fingerprint is original_fingerprint


def test_blind_builder_accepts_r1_identity_package(tmp_path):
    source = _write_fake_stage_ag_package(tmp_path / "source-r1", IDENTITY_MODE_V1R1)
    public_root = tmp_path / "blind"
    mapping = tmp_path / "private" / "mapping.json"
    manifest = build_blind_package(source, public_root, mapping, seed=123)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["source_identity_mode"] == IDENTITY_MODE_V1R1
    assert payload["status"] == "WAITING_FOR_JOVI_BLIND_IDENTITY_FEEDBACK"
    assert mapping.is_file()
    private = json.loads(mapping.read_text(encoding="utf-8"))
    assert private["source_identity_mode"] == IDENTITY_MODE_V1R1


def test_r1_resume_after_package_builds_blind_and_summary(tmp_path):
    output_root = tmp_path / "review"
    mapping_root = tmp_path / "private"
    run_id = "r1-resume-test"
    run_root = output_root / run_id
    (run_root / "probe").mkdir(parents=True)
    probe = run_root / "probe" / "identity_probe_manifest.json"
    probe.write_text("{}\n", encoding="utf-8")

    scorecard = {
        "seed": 20260908,
        "numerical_fixes": [],
        "summary": {
            "reference_regressions_gt_3pct": 0,
            "separation_nonnegative": True,
        },
    }
    scorecard_path = run_root / "identity_separation_scorecard_r1.json"
    scorecard_path.write_text(json.dumps(scorecard) + "\n", encoding="utf-8")
    gate = {
        "schema": "s12.stage_ag.r1_gate_receipt.v1",
        "scorecard_sha256": sha256_file(scorecard_path),
        "reference_regressions_gt_3pct": 0,
        "separation_nonnegative": True,
    }
    (run_root / "stage_ag_r1_gate_receipt.json").write_text(
        json.dumps(gate) + "\n", encoding="utf-8"
    )

    package_root = run_root / "packages"
    _write_fake_stage_ag_package(
        package_root / f"{run_id}-legacy", IDENTITY_MODE_LEGACY
    )
    _write_fake_stage_ag_package(
        package_root / f"{run_id}-identity-v1r1", IDENTITY_MODE_V1R1
    )

    summary_path = resume_after_package_r1(
        output_root=output_root,
        mapping_root=mapping_root,
        run_id=run_id,
        reference_root=None,
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "STAGE_AG_R1_IDENTITY_CANDIDATES_READY"
    assert summary["candidate_identity_mode"] == IDENTITY_MODE_V1R1
    assert summary["hellcat_anchor_byte_identical"] is True
    assert Path(summary["blind_manifest"]).is_file()
    assert Path(summary["sealed_mapping_path"]).is_file()
