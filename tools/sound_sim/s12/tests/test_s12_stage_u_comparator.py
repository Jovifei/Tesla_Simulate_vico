from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.sound_sim.s12.real_reference.stage_u_comparator import compare_triad


def _write(path: Path, signal: np.ndarray, fs: int = 48_000) -> None:
    wavfile.write(path, fs, signal.astype(np.float32))


def test_identical_wavs_have_near_zero_triad_distance(tmp_path: Path) -> None:
    time_s = np.arange(48_000, dtype=np.float64) / 48_000
    audio = np.sin(2.0 * np.pi * 440.0 * time_s)
    reference, parent, candidate = (tmp_path / name for name in ("reference.wav", "parent.wav", "candidate.wav"))
    for path in (reference, parent, candidate):
        _write(path, audio)
    result = compare_triad(reference, parent, candidate, "idle", "rx7_fd")
    assert result["parent_distance"] == 0.0
    assert result["candidate_distance"] == 0.0
    assert result["absolute_improvement"] == 0.0


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
