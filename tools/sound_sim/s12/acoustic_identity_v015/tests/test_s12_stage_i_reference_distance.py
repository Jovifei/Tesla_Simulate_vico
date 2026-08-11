from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import sys

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_i import reference_distance


_CANDIDATES = (
    "I6-A Balanced",
    "I6-B Whine Forward",
    "I6-C Softer Mechanical",
)
_TARGET = [0.4, 0.3, 0.2, 0.1]


def _write_target(path: Path, *, include_afterfire: bool = True) -> Path:
    states = ("idle", "acceleration", "afterfire") if include_afterfire else ("idle", "acceleration")
    stock = {}
    for state in states:
        stock[f"{state}_band_shares"] = _TARGET
        stock[f"{state}_spectral_centroid_hz"] = 500.0
    path.write_text(
        json.dumps(
            {
                "schema": "test",
                "vehicle": "hellcat",
                "provenance": "B/R2 relative features",
                "boundary": "uncalibrated; not OEM reproduction",
                "stock_median": stock,
            }
        ),
        encoding="utf-8",
    )
    return path


def _features(error: float) -> dict[str, object]:
    shares = [_TARGET[0] + error, _TARGET[1] - error, _TARGET[2], _TARGET[3]]
    return {
        "segments": {
            state: {"band_shares": shares, "spectral_centroid_hz": 500.0 + error}
            for state in reference_distance.WINDOWS
        }
    }


def test_stage_i_reference_distance_uses_fixed_final_pcm_formula_and_per_candidate_gates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = _write_target(tmp_path / "hellcat_reference_targets.json")
    paths = {
        "stage_h.wav": _features(0.10),
        "a.wav": _features(0.05),
        "b.wav": _features(0.11),
        "c.wav": _features(0.12),
    }
    calls: list[tuple[str, dict[str, tuple[float, float]]]] = []

    def fake_extract(path: Path, *, segments):
        calls.append((path.name, dict(segments)))
        return paths[path.name]

    monkeypatch.setattr(reference_distance, "extract_reference_features", fake_extract)
    result = reference_distance.compute_stage_i_reference_distance(
        tmp_path / "stage_h.wav",
        {
            _CANDIDATES[0]: tmp_path / "a.wav",
            _CANDIDATES[1]: tmp_path / "b.wav",
            _CANDIDATES[2]: tmp_path / "c.wav",
        },
        target,
    )

    assert result["domain"] == "final_pcm"
    assert result["windows_s"] == {
        "idle": [0.0, 8.0],
        "acceleration": [8.0, 26.0],
        "afterfire": [36.0, 46.0],
    }
    assert result["bands_hz"] == [[20.0, 250.0], [250.0, 1000.0], [1000.0, 4000.0], [4000.0, 12000.0]]
    assert all(windows == reference_distance.WINDOWS for _, windows in calls)

    balanced = result["candidates"][_CANDIDATES[0]]
    idle = balanced["states"]["idle"]
    expected_h = math.sqrt(0.25 * (0.10**2 + (-0.10) ** 2))
    expected_i = math.sqrt(0.25 * (0.05**2 + (-0.05) ** 2))
    assert idle["stage_h_distance"] == pytest.approx(expected_h)
    assert idle["stage_i_distance"] == pytest.approx(expected_i)
    assert idle["improvement_ratio"] == pytest.approx(0.5)
    assert idle["signed_error"] == pytest.approx([0.05, -0.05, 0.0, 0.0])
    assert idle["absolute_error"] == pytest.approx([0.05, 0.05, 0.0, 0.0])
    assert set(idle) >= {"target", "actual_stage_h", "actual_stage_i", "reference_provenance"}
    assert balanced["automatic_status"] == "PASS"
    assert result["candidates"][_CANDIDATES[1]]["gates"]["no_state_worse_than_10_percent"] is True
    assert result["candidates"][_CANDIDATES[1]]["automatic_status"] == "PARTIAL / AUTOMATED_GATE_FAIL"
    assert result["candidates"][_CANDIDATES[2]]["gates"]["no_state_worse_than_10_percent"] is False
    assert result["automatic_status"] == "PARTIAL / AUTOMATED_GATE_FAIL"
    serialized = json.dumps(result).lower()
    assert "lufs" not in serialized
    assert "rms" not in serialized


def test_stage_i_reference_distance_marks_missing_target_as_not_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = _write_target(tmp_path / "hellcat_reference_targets.json", include_afterfire=False)
    monkeypatch.setattr(reference_distance, "extract_reference_features", lambda path, *, segments: _features(0.05))
    result = reference_distance.compute_stage_i_reference_distance(
        tmp_path / "stage_h.wav",
        {candidate: tmp_path / f"{index}.wav" for index, candidate in enumerate(_CANDIDATES)},
        target,
    )

    for candidate in _CANDIDATES:
        row = result["candidates"][candidate]["states"]["afterfire"]
        assert row["availability"] == "not_available"
        assert row["target"] is None
        assert row["actual_stage_h"] is None
        assert row["actual_stage_i"] is None
        assert row["stage_h_distance"] is None
        assert row["stage_i_distance"] is None
        assert row["improvement_ratio"] is None
        assert result["candidates"][candidate]["gates"]["all_required_states_available"] is False
        assert result["candidates"][candidate]["automatic_status"] == "PARTIAL / AUTOMATED_GATE_FAIL"


def test_stage_i_reference_distance_requires_exact_three_candidate_ids(tmp_path: Path) -> None:
    target = _write_target(tmp_path / "hellcat_reference_targets.json")
    with pytest.raises(ValueError, match="candidate IDs"):
        reference_distance.compute_stage_i_reference_distance(
            tmp_path / "stage_h.wav",
            {_CANDIDATES[0]: tmp_path / "a.wav"},
            target,
        )


def test_stage_i_reference_distance_candidate_mapping_order_does_not_change_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = _write_target(tmp_path / "hellcat_reference_targets.json")
    monkeypatch.setattr(reference_distance, "extract_reference_features", lambda path, *, segments: _features(0.05))
    reversed_paths = {
        _CANDIDATES[2]: tmp_path / "c.wav",
        _CANDIDATES[1]: tmp_path / "b.wav",
        _CANDIDATES[0]: tmp_path / "a.wav",
    }
    result = reference_distance.compute_stage_i_reference_distance(
        tmp_path / "stage_h.wav", reversed_paths, target
    )
    assert tuple(result["candidates"]) == _CANDIDATES


def test_stage_i_reference_distance_script_supports_direct_help_invocation() -> None:
    repo_root = Path(__file__).resolve().parents[5]
    script = (
        repo_root
        / "tools"
        / "sound_sim"
        / "s12"
        / "acoustic_identity_v015"
        / "scripts"
        / "compute_stage_i_reference_distance.py"
    )
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--stage-h-wav" in completed.stdout
