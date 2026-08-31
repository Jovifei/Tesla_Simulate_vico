from __future__ import annotations

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_g.reference_gate import band_distance, compare_state_features


def test_stage_g_distance_uses_full_spectrum_target_shares() -> None:
    result = compare_state_features((0.4, 0.3, 0.2, 0.002), (0.4, 0.3, 0.2, 0.002), (0.5, 0.2, 0.2, 0.002))
    assert result["stage_c_distance"] == pytest.approx(0.0)
    assert result["stage_g_distance"] > 0.0
    assert result["improvement_ratio"] < 0.0


def test_stage_g_distance_rejects_wrong_shape() -> None:
    with pytest.raises(ValueError):
        band_distance((0.1, 0.2, 0.3), (0.1, 0.2, 0.3, 0.4))
