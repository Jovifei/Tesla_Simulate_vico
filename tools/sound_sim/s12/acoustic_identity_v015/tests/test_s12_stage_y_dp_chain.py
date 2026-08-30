import hashlib
import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.stage_y.audio_chain_dp import PressureAudioChain
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.click_contract import block_boundary_click_metrics
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import build_hellcat_bakeoff_trace, _render_architecture


def test_warmup_then_stream_matches_oneshot_within_tolerance() -> None:
    chain = PressureAudioChain(sample_rate_hz=48000, delay_samples=64.0)
    noise = np.random.default_rng(0).standard_normal((48000, 2)) * 0.01
    chain.warmup(noise[: 4800])
    streamed = []
    for index in range(0, 9600, 960):
        streamed.append(chain.process(noise[index : index + 960]))
    streamed = np.concatenate(streamed, axis=0)
    oneshot = PressureAudioChain(sample_rate_hz=48000, delay_samples=64.0)
    oneshot.warmup(noise[: 4800])
    full = oneshot.process(noise[: 9600])
    assert np.max(np.abs(streamed - full)) < 1e-9
    metrics = block_boundary_click_metrics(streamed, 960)
    assert metrics.get("max_abs_jump", metrics.get("max_boundary_jump")) < 0.35


def test_dp_chain_ablation_changes_sha() -> None:
    trace = build_hellcat_bakeoff_trace("steady_2000rpm", 1.5)
    _off_raw, off_post, _off_mon, _off_d = _render_architecture("P3", trace)
    _on_raw, on_post, _on_mon, _on_d = _render_architecture("P3DP", trace)
    assert hashlib.sha256(on_post.tobytes()).hexdigest() != hashlib.sha256(off_post.tobytes()).hexdigest()
