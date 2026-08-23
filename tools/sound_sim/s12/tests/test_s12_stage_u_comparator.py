from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

from tools.sound_sim.s12.real_reference.stage_u_comparator import (
    StageUComparatorError,
    compare_reference_parent_candidate,
    compare_triad,
)


def _write(path: Path, signal: np.ndarray, fs: int = 48_000) -> None:
    wavfile.write(path, fs, signal.astype(np.float32))


def test_parent_and_candidate_with_same_on_disk_sha_are_rejected(tmp_path: Path) -> None:
    time_s = np.arange(48_000, dtype=np.float64) / 48_000
    audio = np.sin(2.0 * np.pi * 440.0 * time_s)
    reference, parent, candidate = (tmp_path / name for name in ("reference.wav", "parent.wav", "candidate.wav"))
    for path in (reference, parent, candidate):
        _write(path, audio)
    with pytest.raises(StageUComparatorError, match="SHA must differ"):
        compare_triad(reference, parent, candidate, "idle", "rx7_fd")


def test_candidate_closer_to_reference_has_positive_improvement(tmp_path: Path) -> None:
    time_s = np.arange(48_000, dtype=np.float64) / 48_000
    reference_audio = np.sin(2.0 * np.pi * 440.0 * time_s)
    parent_audio = reference_audio + 0.7 * np.sin(2.0 * np.pi * 4500.0 * time_s)
    candidate_audio = reference_audio + 0.1 * np.sin(2.0 * np.pi * 4500.0 * time_s)
    reference, parent, candidate = (tmp_path / name for name in ("reference.wav", "parent.wav", "candidate.wav"))
    _write(reference, reference_audio); _write(parent, parent_audio); _write(candidate, candidate_audio)
    result = compare_triad(reference, parent, candidate, "full_pull", "ferrari_458")
    assert result["candidate_distance"] < result["parent_distance"]
    assert result["absolute_improvement"] > 0.0
    assert result["relative_improvement"] > 0.0


def test_record_wrapper_hashes_all_inputs_from_disk_and_emits_legacy_binding(tmp_path: Path) -> None:
    time_s = np.arange(48_000, dtype=np.float64) / 48_000
    paths = {role: tmp_path / f"{role}.wav" for role in ("reference", "parent", "candidate")}
    _write(paths["reference"], np.sin(2.0 * np.pi * 440.0 * time_s))
    _write(paths["parent"], np.sin(2.0 * np.pi * 460.0 * time_s))
    _write(paths["candidate"], np.sin(2.0 * np.pi * 445.0 * time_s))
    record = {
        "reference_id": "reference-01",
        "candidate_id": "candidate-01",
        "vehicle_id": "ferrari_458",
        "scenario": "full_pull",
        "reference_path": str(paths["reference"]),
        "parent_path": str(paths["parent"]),
        "candidate_path": str(paths["candidate"]),
        "reference_sha256": "declared-value-must-not-be-copied",
        "parent_sha256": "declared-value-must-not-be-copied",
        "candidate_sha256": "declared-value-must-not-be-copied",
        "hard_gates_pass": True,
    }

    result = compare_reference_parent_candidate(record)

    assert result["reference_id"] == "reference-01"
    assert result["candidate_id"] == "candidate-01"
    for role, path in paths.items():
        assert result[f"{role}_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result["parent_sha256"] != result["candidate_sha256"]
