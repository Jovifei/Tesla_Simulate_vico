from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_d.reference_distance import band_distance, summarize_reference_distance


def test_band_distance_is_weighted_l2() -> None:
    assert band_distance([0.5, 0.25, 0.15, 0.10], [0.25, 0.25, 0.25, 0.25]) == pytest.approx(np.sqrt(0.25 * (0.25**2 + 0.10**2 + 0.15**2)))


def test_reference_summary_rejects_single_state_regression() -> None:
    result = summarize_reference_distance({"idle": 0.10, "acceleration": 0.12}, {"idle": 0.05, "acceleration": 0.14})
    assert result["improvement_ratio"] < 0.30
    assert result["passes"] is False


def test_reference_distance_requires_four_finite_bands() -> None:
    with pytest.raises(ValueError):
        band_distance([0.5, 0.5], [0.5, 0.5])


def test_anchor_reference_manifest_matches_target_sha_and_states() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "reference_database" / "realism_reference_manifest.json").read_text(encoding="utf-8"))
    expected = {"ferrari_458", "hellcat", "rx7_fd"}
    for vehicle_id in expected:
        entry = manifest["vehicles"][vehicle_id]
        target = root / "reference_database" / entry["target_file"]
        assert hashlib.sha256(target.read_bytes()).hexdigest() == entry["target_sha256"]
        assert entry["eligible_states"] == ["idle", "acceleration", "afterfire"]
