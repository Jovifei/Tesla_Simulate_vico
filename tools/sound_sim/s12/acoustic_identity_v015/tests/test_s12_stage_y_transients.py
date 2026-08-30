import hashlib
import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.stage_y.state_transients import StateTransientMixer
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import build_hellcat_bakeoff_trace, _render_architecture


def test_equal_power_crossfade_preserves_power() -> None:
    mixer = StateTransientMixer(sample_rate_hz=48000)
    a = np.ones((960, 2))
    b = np.ones((960, 2)) * 2.0
    out = mixer.equal_power_crossfade(a, b, mix=0.5)
    power = float(np.mean(np.square(out)))
    assert abs(power - 0.5 * (1.0 + 4.0)) < 0.15


def test_tip_in_and_shift_stems_change_sha() -> None:
    tip = build_hellcat_bakeoff_trace("throttle_tip_in", 2.0)
    shift = build_hellcat_bakeoff_trace("gear_shift", 2.0)
    _raw_off, post_off, _mon_off, _diag_off = _render_architecture("P3", tip)
    _raw_on, post_on, _mon_on, diag_on = _render_architecture("P5", tip)
    assert hashlib.sha256(post_on.tobytes()).hexdigest() != hashlib.sha256(post_off.tobytes()).hexdigest()
    assert diag_on.get("transient_model") == "state_v1"
    _sraw, spost, _smon, sdiag = _render_architecture("P5", shift)
    _p3s, p3spost, _p3sm, _ = _render_architecture("P3", shift)
    assert int(sdiag.get("transient_shift_count", 0)) >= 1 or hashlib.sha256(spost.tobytes()).hexdigest() != hashlib.sha256(p3spost.tobytes()).hexdigest()
