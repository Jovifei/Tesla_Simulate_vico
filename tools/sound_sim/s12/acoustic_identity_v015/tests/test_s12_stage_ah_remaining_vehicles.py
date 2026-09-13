"""Focused contracts for the RX-7/Aventador AH diagnostic adapter."""
from __future__ import annotations

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import SourceRender
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.remaining_vehicle_pipeline import (
    REMAINING_VEHICLES,
    RemainingVehicleEngine,
    apply_negative_feedback,
    apply_named_stem_scales,
    feedback_parameters,
    validate_source_pool,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.remaining_vehicle_package import (
    _artifact_paths,
    build_reference_bundle,
    _receipt_sha,
)


@pytest.fixture
def fake_ir() -> np.ndarray:
    ir = np.zeros(256, dtype=np.float64)
    ir[0] = 0.9
    ir[1] = 0.02
    return ir


def _curves(duration: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
    count = int(round(48_000 * duration))
    time = np.arange(count, dtype=np.float64) / 48_000.0
    rpm = np.linspace(900.0, 7_200.0, count)
    throttle = np.where(time < duration * 0.5, 0.8, 0.05)
    return rpm, throttle


def test_registry_contains_the_two_remaining_vehicles():
    assert REMAINING_VEHICLES == ("rx7_fd", "aventador_lp700")


def test_negative_feedback_is_deterministic_bounded_and_scoped():
    rows = [{"vehicle": "rx7_fd", "scene": "02_full_pull", "score": 1, "tags": ["rotary_weak"]}]
    first = apply_negative_feedback("rx7_fd", rows)
    second = apply_negative_feedback("rx7_fd", rows)
    assert first == second
    baseline = feedback_parameters("rx7_fd", [])
    assert first["parameters"]["rotary_pulse_width_scale"] > baseline["parameters"]["rotary_pulse_width_scale"]
    assert first["parameters"]["blow_off_gain_scale"] == baseline["parameters"]["blow_off_gain_scale"]
    assert first["parameters"]["rotary_pulse_width_scale"] <= 1.2


def test_negative_feedback_rejects_unknown_or_cross_vehicle_rows():
    with pytest.raises(ValueError, match="unknown feedback tag"):
        apply_negative_feedback(
            "rx7_fd",
            [{"vehicle": "rx7_fd", "scene": "idle", "score": 1, "tags": ["master_gain"]}],
        )
    with pytest.raises(ValueError, match="vehicle mismatch"):
        apply_negative_feedback(
            "rx7_fd",
            [{"vehicle": "aventador_lp700", "scene": "idle", "score": 1, "tags": []}],
        )


def test_aventador_feedback_scales_only_named_stem():
    base = np.ones((8, 2), dtype=np.float64)
    render = SourceRender(
        pressure=base * 3.0,
        stems={"wail": base.copy(), "scream": base.copy(), "mechanical": base.copy()},
        diagnostics={},
    )
    adjusted = apply_named_stem_scales(render, {"wail": 1.2})
    np.testing.assert_allclose(adjusted.stems["wail"], base * 1.2)
    np.testing.assert_allclose(adjusted.stems["scream"], base)
    np.testing.assert_allclose(adjusted.stems["mechanical"], base)
    np.testing.assert_allclose(adjusted.pressure, base * 3.2)


@pytest.mark.parametrize("vehicle", REMAINING_VEHICLES)
def test_b0_c0_share_pre_guard_and_bind_parent_to_scene_trace(vehicle, fake_ir):
    rpm, throttle = _curves()
    scene_ids = ("scene_a",)
    b0 = RemainingVehicleEngine(vehicle, output_policy="legacy_clip_v1", ir=fake_ir, scene_ids=scene_ids)
    b0_pcm = b0.render_track(rpm, throttle, 0.5)
    c0 = RemainingVehicleEngine(
        vehicle,
        output_policy="linked_soft_ceiling_v1",
        parent_peaks=b0.parent_peaks,
        ir=fake_ir,
        scene_ids=scene_ids,
    )
    c0_pcm = c0.render_track(rpm, throttle, 0.5)
    b0_record, c0_record = b0.reports[-1], c0.reports[-1]
    assert b0_record["parent_peak_key"] == f"scene_a|{b0_record['trace_sha256']}"
    assert b0_record["normalization"]["pre_guard_pcm_sha256"] == c0_record["normalization"]["pre_guard_pcm_sha256"]
    assert not np.array_equal(b0_pcm, c0_pcm)
    assert c0_record["normalization"]["post_guard_ceiling_exceedance_samples"] == 0


@pytest.mark.parametrize("vehicle", REMAINING_VEHICLES)
def test_parent_peak_for_different_scene_is_rejected(vehicle, fake_ir):
    rpm, throttle = _curves()
    anchor = RemainingVehicleEngine(vehicle, output_policy="legacy_clip_v1", ir=fake_ir, scene_ids=("scene_a",))
    anchor.render_track(rpm, throttle, 0.5)
    candidate = RemainingVehicleEngine(
        vehicle,
        output_policy="linked_soft_ceiling_v1",
        parent_peaks=anchor.parent_peaks,
        ir=fake_ir,
        scene_ids=("scene_b",),
    )
    with pytest.raises(ValueError, match="parent denominator missing"):
        candidate.render_track(rpm, throttle, 0.5)


def test_source_pool_requires_more_than_five_sources():
    payload = {
        "vehicles": {
            "rx7_fd": {"selected_sources": [{"video_id": str(i)} for i in range(6)]},
            "aventador_lp700": {"selected_sources": [{"video_id": str(i)} for i in range(6)]},
        }
    }
    assert validate_source_pool(payload) == {"rx7_fd": 6, "aventador_lp700": 6}
    payload["vehicles"]["rx7_fd"]["selected_sources"] = payload["vehicles"]["rx7_fd"]["selected_sources"][:5]
    with pytest.raises(ValueError, match="at least six"):
        validate_source_pool(payload)


def test_reference_bundle_uses_six_external_sources_without_copying_raw_media(tmp_path):
    sources = {}
    for vehicle in REMAINING_VEHICLES:
        rows = []
        for index in range(6):
            video_id = f"{vehicle}-{index}"
            path = tmp_path / f"{video_id}.wav"
            from scipy.io import wavfile

            wavfile.write(path, 48_000, np.zeros((4_800, 2), dtype=np.int16))
            import hashlib

            rows.append({"video_id": video_id, "audio_file": str(path), "audio_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        windows = {scene: [rows[index % 6]["video_id"], 0.0, 0.05] for index, scene in enumerate((
            "01_afterfire", "02_full_pull", "03_hot_idle", "04_idle_return", "05_lift",
            "06_shift", "07_steady_high", "08_steady_low", "09_steady_mid", "10_tip_in",
        ))}
        sources[vehicle] = {"selected_sources": rows, "reference_windows": windows}
    receipt = {"vehicles": sources}
    bundle = build_reference_bundle(tmp_path / "bundle", receipt, clip_duration_s=0.05)
    assert bundle["source_counts"] == {"rx7_fd": 6, "aventador_lp700": 6}
    assert bundle["clip_count_total"] == 20
    assert len(list((tmp_path / "bundle").glob("**/ref_*.wav"))) == 20
    assert not list((tmp_path / "bundle").glob("**/*.mp4"))


def test_reference_receipt_checksum_helper_accepts_contract_checksum():
    assert _receipt_sha({"contract_sha256": "a" * 64}) == "a" * 64
    with pytest.raises(ValueError, match="checksum"):
        _receipt_sha({})


def test_artifact_path_inventory_is_flat_paths(tmp_path):
    configs = {"rx7_fd": {"dir": tmp_path / "rx7", "scenes": [{"id": "01_afterfire"}]}}
    paths = _artifact_paths(tmp_path, configs, {})
    assert paths
    assert all(hasattr(path, "is_file") for path in paths)
