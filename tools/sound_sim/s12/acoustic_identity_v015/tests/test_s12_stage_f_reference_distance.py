import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_f.reference_distance import band_distance, compare_final_pcm, final_pcm_band_shares


def test_band_distance_zero_and_improvement():
    target = (0.4, 0.3, 0.2, 0.1)
    assert band_distance(target, target) == 0.0
    result = compare_final_pcm({"band_shares": target}, (0.7, 0.1, 0.1, 0.1), target)
    assert result["availability"] == "eligible"
    assert result["improvement_ratio"] == 1.0


def test_missing_reference_is_not_zero_filled():
    result = compare_final_pcm({}, (0.25, 0.25, 0.25, 0.25), (0.25, 0.25, 0.25, 0.25))
    assert result["availability"] == "not_available"


def test_final_pcm_shares_are_finite():
    audio = np.column_stack((np.sin(np.linspace(0, 100, 4800)), np.sin(np.linspace(0, 100, 4800))))
    shares = final_pcm_band_shares(audio)
    assert len(shares) == 4
    assert np.isclose(sum(shares), 1.0)
