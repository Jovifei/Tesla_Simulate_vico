from __future__ import annotations

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_comparator.core import ComparisonCase, compare_signals

SR = 8_000

def _signal(seconds: float = 1.0, hz: float = 200.0) -> np.ndarray:
    t = np.arange(int(seconds * SR)) / SR
    return np.sin(2 * np.pi * hz * t)

def _case(*, scenario: str = "acceleration", rpm: tuple[float, float] = (3000.0, 3000.0), reference_present: bool = True) -> ComparisonCase:
    return ComparisonCase("c63_w204", scenario, "r2-reference" if reference_present else None, "candidate", SR, (rpm[0], rpm[0]), (rpm[1], rpm[1]), (0.2, 0.9), (0.2, 0.9), "unaltered_analysis_signal")

def test_same_signal_has_near_zero_spectral_distance() -> None:
    result = compare_signals(_signal(), _signal(), _case())
    assert result["spectral"]["log_distance"] < 1e-9

def test_gain_changes_level_not_identity_distance() -> None:
    result = compare_signals(_signal(), _signal() * 0.5, _case())
    assert result["spectral"]["log_distance"] < 1e-9
    assert result["loudness"]["delta_db"] < -5.9

def test_lowpass_changes_high_band_and_sharpness() -> None:
    x = _signal(hz=2_000) + _signal(hz=100)
    result = compare_signals(x, _signal(hz=100), _case())
    assert result["bands"]["5500_12000"]["candidate_share"] <= result["bands"]["5500_12000"]["reference_share"]
    assert result["psychoacoustics"]["sharpness_proxy_delta"] < 0

def test_small_time_shift_is_aligned_without_identity_failure() -> None:
    x = np.random.default_rng(7).normal(0.0, 0.1, SR)
    x[1_000:1_020] += np.hanning(20) * 2.0
    result = compare_signals(x, np.roll(x, 80), _case())
    assert result["alignment"]["applied_shift_samples"] == -80
    assert result["spectral"]["log_distance"] < 1e-9

def test_rpm_mismatch_is_identified() -> None:
    result = compare_signals(_signal(), _signal(), _case(rpm=(2000.0, 8000.0)))
    assert result["order"]["rpm_compatible"] is False

def test_injected_afterfire_is_detected() -> None:
    x = _signal()
    x[4_000:4_080] += 5
    result = compare_signals(_signal(), x, _case())
    assert result["events"]["candidate_event_count"] >= 1

def test_wrong_condition_event_is_rejected() -> None:
    x = _signal(); x[4_000:4_080] += 5
    result = compare_signals(_signal(), x, _case(), eligible_event_mask=np.zeros(x.size, dtype=bool))
    assert result["events"]["wrong_condition_event_count"] >= 1

def test_scenario_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="scenario"):
        compare_signals(_signal(), _signal(), _case(scenario="idle"), candidate_scenario="acceleration")

def test_review_copy_cannot_be_raw_analysis_input() -> None:
    with pytest.raises(ValueError, match="review"):
        compare_signals(_signal(), _signal(), _case(), candidate_domain="review_gain_copy")

def test_missing_reference_returns_uncertainty_not_score() -> None:
    result = compare_signals(None, _signal(), _case(reference_present=False))
    assert result["uncertainty"]["reference_missing"] is True
    assert result["spectral"]["log_distance"] is None
