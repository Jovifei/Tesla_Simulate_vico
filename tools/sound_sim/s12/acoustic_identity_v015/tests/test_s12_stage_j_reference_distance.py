"""Stage-J final PCM reference-distance contract tests."""

from tools.sound_sim.s12.acoustic_identity_v015.stage_j.reference_distance import BANDS_HZ, WINDOWS_S


def test_stage_j_reference_contract_uses_fixed_final_pcm_bands_and_windows() -> None:
    assert BANDS_HZ == ((20.0, 250.0), (250.0, 1000.0), (1000.0, 4000.0), (4000.0, 12000.0))
    assert WINDOWS_S == {"idle": (0.0, 8.0), "acceleration": (8.0, 26.0), "afterfire": (36.0, 46.0)}
