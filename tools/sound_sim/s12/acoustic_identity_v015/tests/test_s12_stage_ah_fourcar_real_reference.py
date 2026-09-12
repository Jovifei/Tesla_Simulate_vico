"""Focused contracts for the four-car real-reference AH adapter."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "reference_database" / "fourcar_real_reference_targets_v1.json"


def test_real_reference_inventory_has_five_verified_wav_entries_per_vehicle() -> None:
    payload = json.loads(TARGETS.read_text(encoding="utf-8"))
    assert payload["schema"] == "s12.stage_ah.fourcar_real_reference_targets.v1"
    for vehicle, record in payload["vehicles"].items():
        assert record["source_count"] == 5
        assert len(record["sources"]) == 5
        for source in record["sources"]:
            path = Path(source["external_wav_path"])
            assert source["downloaded"] is True
            assert len(source["wav_sha256"]) == 64
            assert path.is_file(), (vehicle, path)
            assert hashlib.sha256(path.read_bytes()).hexdigest() == source["wav_sha256"]


def test_package_binds_the_accepted_r1_parent_manifest() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_package import (
        EXPECTED_PARENT_MANIFEST_SHA256,
    )

    assert EXPECTED_PARENT_MANIFEST_SHA256 == (
        "3fecb566416d498bcedcb6c1a5267f6c7b36e82e9e9a87af7c2740705f599519"
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
        parent_peaks={0: 0.75},
        seed=20260912,
    )
    first = FourCarRealReferenceEngine("lfa", profile, **kwargs)
    second = FourCarRealReferenceEngine("lfa", profile, **kwargs)
    audio_a = first.render_track(rpm, throttle, duration)
    audio_b = second.render_track(rpm, throttle, duration)
    assert np.array_equal(audio_a, audio_b)
    assert audio_a.dtype == np.int16
    report = first.reports[0]
    assert report["normalization_denominator"] == pytest.approx(0.75)
    assert report["output_policy"] == LINKED_SOFT_CEILING_V1
    assert report["source_adjustment_domain"] == "ah_r1_pre_saturation_before_output_guard"
    assert report["candidate_render_path"] == "current_ah_engine_pre_saturation_overlay"
    assert report["final_peak"] <= 0.94 + 1e-12
    assert report["normalization"]["post_guard_ceiling_exceedance_samples"] == 0
