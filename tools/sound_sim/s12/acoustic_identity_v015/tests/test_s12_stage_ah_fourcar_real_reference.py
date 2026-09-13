"""Focused contracts for the four-car real-reference AH adapter."""

from __future__ import annotations

import json
import hashlib
import os
import subprocess
from pathlib import Path
from pathlib import PureWindowsPath

import numpy as np
import pytest
from scipy.io import wavfile


ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "reference_database" / "fourcar_real_reference_targets_v1.json"


@pytest.fixture(autouse=True)
def controlled_ir(tmp_path, monkeypatch):
    root = tmp_path / "controlled-ir"
    root.mkdir()
    t = np.arange(512) / 48_000.0
    impulse = 0.9 * np.exp(-t / 0.006) * np.cos(2.0 * np.pi * 120.0 * t)
    for name in (
        "mild_exhaust_reverb",
        "test_engine_16_eq_adjusted_16",
        "test_engine_14_eq_adjusted_16",
    ):
        wavfile.write(root / f"{name}.wav", 48_000, (impulse * 32767.0).astype(np.int16))
    monkeypatch.setenv("S12_ENGINE_SIM_IR_ROOT", str(root))
    return root


def test_real_reference_inventory_has_five_verified_wav_entries_per_vehicle() -> None:
    payload = json.loads(TARGETS.read_text(encoding="utf-8"))
    assert payload["schema"] == "s12.stage_ah.fourcar_real_reference_targets.v1"
    for vehicle, record in payload["vehicles"].items():
        assert record["source_count"] == 5
        assert len(record["sources"]) == 5
        for source in record["sources"]:
            assert source["downloaded"] is True
            assert len(source["wav_sha256"]) == 64
            assert source["evidence_level"] == "R3"
            assert source["synchronization"] == "RPM/load/gear/microphone/AGC missing"
            assert PureWindowsPath(source["external_wav_path"]).is_absolute()


def test_local_reference_assets_are_checked_only_when_explicitly_requested() -> None:
    root = os.environ.get("S12_LOCAL_ASSET_ROOT")
    if not root:
        pytest.skip("set S12_LOCAL_ASSET_ROOT for the explicit local-asset task")
    base = Path(root)
    payload = json.loads(TARGETS.read_text(encoding="utf-8"))
    for vehicle, record in payload["vehicles"].items():
        for source in record["sources"]:
            path = base / PureWindowsPath(source["external_wav_path"]).name
            assert path.is_file(), (vehicle, path)
            import hashlib
            assert hashlib.sha256(path.read_bytes()).hexdigest() == source["wav_sha256"]


def test_package_binds_the_accepted_r1_parent_manifest() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_package import (
        EXPECTED_PARENT_MANIFEST_SHA256,
    )
    assert EXPECTED_PARENT_MANIFEST_SHA256 == (
        "3fecb566416d498bcedcb6c1a5267f6c7b36e82e9e9a87af7c2740705f599519"
    )


@pytest.mark.parametrize(
    "profile_path",
    (
        "targets/stage_k_candidates/hellcat_candidate_v7.json",
        "targets/stage_g_candidates/Ferrari_candidate_v4.json",
        "targets/stage_k_candidates/lfa_candidate_v2.json",
        "targets/stage_k_candidates/gtr_r35_candidate_v2.json",
    ),
)
def test_reference_target_sha_matches_profile_worktree_and_git_blob(profile_path: str) -> None:
    profile = ROOT / profile_path
    payload = json.loads(profile.read_text(encoding="utf-8"))
    relative = profile.parents[2] / payload["reference_target"]["path"]
    worktree = relative.read_bytes()
    blob = subprocess.check_output(
        ["git", "show", f"HEAD:{relative.relative_to(ROOT.parent.parent.parent.parent).as_posix()}"],
        cwd=ROOT.parent.parent.parent.parent,
    )
    digest = hashlib.sha256(worktree).hexdigest()
    blob_digest = hashlib.sha256(blob).hexdigest()
    assert payload["reference_target"]["sha256"] == digest == blob_digest
    assert worktree.count(b"\r\n") == 0
    assert worktree.count(b"\n") == blob.count(b"\n")

def test_dashboard_parameter_rows_match_the_original_template_contract() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_package import _contract

    contract = _contract(
        package_id="fourcar-test",
        group="REALREF",
        vehicle="lfa",
        cfg={"port": 1, "_nav_ports": {}},
        source_receipt={},
        reference_sources={},
        candidate_hashes={},
        records=[],
        profile_metadata={
            "changed_source_parameter": "intake_resonance_scale",
            "base_value": 1.1,
            "candidate_value": 0.95,
        },
    )
    assert set(("group", "key", "name", "base", "final", "delta", "desc")) <= set(
        contract["parameters"][0]
    )


@pytest.mark.parametrize("vehicle", ("hellcat", "ferrari_458", "lfa", "gtr_r35"))
def test_real_reference_profile_is_a_single_source_parameter_delta(vehicle: str) -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_pipeline import load_real_reference_profile

    profile, metadata = load_real_reference_profile(vehicle)
    assert profile.vehicle_id == vehicle
    assert profile.candidate_id.endswith("real_reference_v1")
    assert metadata["tuning_basis"] == "primary_three_median"
    assert len(metadata["source_ids"]) == 5
    changed = metadata["changed_source_parameter"]
    assert changed in profile.payload["source"]
    assert metadata["base_value"] != metadata["candidate_value"]
    assert changed == metadata["active_source_parameter"]
    assert metadata["active_source_stem"]
    if vehicle == "lfa":
        assert set(metadata["full_field_diff"]) == {
            "high_rpm_growth_scale",
            "intake_resonance_scale",
        }
        assert metadata["unused_source_fields"] == ["intake_resonance_scale"]


def test_real_reference_engine_is_deterministic_bounded_and_reports_parent_denominator() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_pipeline import (
        FourCarRealReferenceEngine,
        load_real_reference_profile,
    )
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.output_guard import LINKED_SOFT_CEILING_V1

    profile, _ = load_real_reference_profile("lfa")
    sample_rate = 48_000
    duration = 0.5
    time = np.arange(int(sample_rate * duration), dtype=np.float64) / sample_rate
    rpm = np.linspace(1_200.0, 7_500.0, time.size)
    throttle = np.linspace(0.2, 1.0, time.size)
    kwargs = dict(
        output_policy=LINKED_SOFT_CEILING_V1,
        parent_peaks={},
        seed=20260908,
    )
    first = FourCarRealReferenceEngine("lfa", profile, **kwargs)
    second = FourCarRealReferenceEngine("lfa", profile, **kwargs)
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.engine import input_sha
    trace = input_sha(rpm, throttle, duration, [None, None, None])
    first.set_scene_context("01_afterfire", trace)
    second.set_scene_context("01_afterfire", trace)
    kwargs["parent_peaks"] = {"01_afterfire|" + trace: 0.75}
    first = FourCarRealReferenceEngine("lfa", profile, **kwargs)
    second = FourCarRealReferenceEngine("lfa", profile, **kwargs)
    first.set_scene_context("01_afterfire", trace)
    second.set_scene_context("01_afterfire", trace)
    audio_a = first.render_track(rpm, throttle, duration)
    audio_b = second.render_track(rpm, throttle, duration)
    assert np.array_equal(audio_a, audio_b)
    assert audio_a.dtype == np.int16
    report = first.reports[0]
    assert report["normalization_denominator"] == pytest.approx(0.75)
    assert report["output_policy"] == LINKED_SOFT_CEILING_V1
    assert report["source_adjustment_domain"] == "named_source_stem_before_output_guard"
    assert report["candidate_render_path"] == "current_ah_engine_named_source_recipe"
    assert report["source_adjustment"]["method"] == "named_engine_source_stem_gain"
    assert report["final_peak"] <= 0.94 + 1e-12
    assert report["normalization"]["post_guard_ceiling_exceedance_samples"] == 0
