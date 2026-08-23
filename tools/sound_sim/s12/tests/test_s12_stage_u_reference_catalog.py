from __future__ import annotations

import json
from pathlib import Path

from tools.sound_sim.s12.real_reference.stage_u_reference_catalog import build_stage_u_reference_catalog


def _long_pair(vehicle_id: str, trial: str, window: str, scenario: str) -> dict[str, object]:
    return {
        "vehicle_id": vehicle_id,
        "pair_id": f"{trial}_{window}",
        "base_trial_id": trial,
        "scenario": scenario,
        "reference_class": "R3",
        "reference_path": f"E:/external/{trial}_{window}_reference.wav",
        "reference_sha256": (trial + window).ljust(64, "a")[:64],
        "microphone_uncertainty": "UNKNOWN_PUBLIC_VIDEO_CAPTURE",
    }


def _rx7_pair(index: int, scenario: str) -> dict[str, object]:
    return {
        "vehicle_id": "rx7_fd",
        "pair_id": f"rx7_{index}",
        "scenario": scenario,
        "reference_class": "R2",
        "reference_path": f"E:/external/rx7_{index}.wav",
        "reference_sha256": str(index).ljust(64, "b"),
        "microphone_uncertainty": "EXTERIOR_EXHAUST_AGC_UNKNOWN",
    }


def test_catalog_uses_one_15s_window_per_ferrari_hellcat_trial_and_all_rx7_r2(tmp_path: Path) -> None:
    long = {
        "pairs": [
            _long_pair("ferrari_458", "ferrari_01", "15s", "start_idle_rev_acceleration"),
            _long_pair("ferrari_458", "ferrari_01", "30s", "start_idle_rev_acceleration"),
            _long_pair("hellcat", "hellcat_01", "15s", "idle_rev_acceleration"),
            _long_pair("hellcat", "hellcat_01", "30s", "idle_rev_acceleration"),
        ]
    }
    rx7 = {"pairs": [_rx7_pair(1, "idle"), _rx7_pair(2, "steady_low"), _rx7_pair(3, "steady_mid"), _rx7_pair(4, "full_pull"), _rx7_pair(5, "full_pull_interior")]}
    long_path = tmp_path / "long.json"; rx7_path = tmp_path / "rx7.json"
    long_path.write_text(json.dumps(long), encoding="utf-8")
    rx7_path.write_text(json.dumps(rx7), encoding="utf-8")
    records = build_stage_u_reference_catalog(long_path, rx7_path)
    assert len(records) == 7
    assert sum(row["vehicle_id"] == "ferrari_458" for row in records) == 1
    assert sum(row["vehicle_id"] == "hellcat" for row in records) == 1
    assert sum(row["vehicle_id"] == "rx7_fd" for row in records) == 5
    assert all("stage_u_parent:" in row["candidate_audio_id"] for row in records)
    assert {row["reference_class"] for row in records if row["vehicle_id"] == "rx7_fd"} == {"R2"}
