import hashlib
import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.stage_w.click_contract import block_boundary_click_metrics
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.fixture_cycles import synthesize_hellcat_cycle_bank
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.cycle_sync_resynth import CycleSyncResampler
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import PLACEHOLDER_RECORDS, RENDERABLE_ARCHITECTURES, _render_architecture
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import build_hellcat_bakeoff_trace


def test_p4_is_not_a_placeholder() -> None:
    assert "P4" not in PLACEHOLDER_RECORDS
    assert "P4" in RENDERABLE_ARCHITECTURES


def test_cycle_sync_shares_phase_and_has_no_block_click() -> None:
    bank = synthesize_hellcat_cycle_bank(sample_rate_hz=48000)
    resampler = CycleSyncResampler(bank, sample_rate_hz=48000)
    phase = np.linspace(0.0, 40.0 * np.pi, 9600)
    rpm = np.full(9600, 2000.0)
    audio = resampler.render(phase, rpm)
    assert audio.shape == (9600, 2)
    assert np.all(np.isfinite(audio))
    metrics = block_boundary_click_metrics(audio, 960)
    assert metrics.get("max_abs_jump", metrics.get("max_boundary_jump")) < 0.35
    resampler2 = CycleSyncResampler(bank, sample_rate_hz=48000)
    assert hashlib.sha256(resampler2.render(phase, rpm).tobytes()).hexdigest() == hashlib.sha256(audio.tobytes()).hexdigest()


def test_cycle_sync_uses_full_four_stroke_720_degree_fixture_cycle() -> None:
    """A 360-degree crank turn must not reset a non-symmetric fixture cycle."""
    bank = synthesize_hellcat_cycle_bank(sample_rate_hz=48000)
    resampler = CycleSyncResampler(bank, sample_rate_hz=48000)
    phase = np.array([0.0, 2.0 * np.pi, 4.0 * np.pi])
    rpm = np.full(phase.size, 2000.0)

    audio = resampler.render(phase, rpm)

    assert not np.array_equal(audio[0], audio[1])
    np.testing.assert_array_equal(audio[0], audio[2])


def test_p4_bakeoff_render_differs_from_p2h() -> None:
    trace = build_hellcat_bakeoff_trace("steady_2000rpm", 1.5)
    _p2h_raw, p2h_post, _p2h_mon, _p2h_diag = _render_architecture("P2H", trace)
    p4_raw, p4_post, _p4_mon, _p4_diag = _render_architecture("P4", trace)
    assert np.max(np.abs(p4_raw)) < 1.0
    assert hashlib.sha256(p4_post.tobytes()).hexdigest() != hashlib.sha256(p2h_post.tobytes()).hexdigest()
