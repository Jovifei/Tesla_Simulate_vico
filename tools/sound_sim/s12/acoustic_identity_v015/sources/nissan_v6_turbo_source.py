"""Synthetic, uncalibrated Nissan GT-R R35 (VR38DETT 3.8L V6 twin-turbo) source.

Crisp, high-pitched racy note (per reviews: "more racy than a hollow NA V6
groan") plus prominent twin-turbo whistle and spool. Mid-dominant
acceleration (reference: accel 250-1k = 0.501, 1-4k = 0.120) with a moderate
low end. No supercharger — turbo whistle is the forced-induction signature.

Band-safety design: exhaust low fundamental (1st/2nd engine order, <= ~680 Hz
at 6800 rpm) with a stronger low gain to supply the moderate low end the
reference wants. The racy layer is a *fixed-center* mid tone (300/420 Hz, no
engine-order modulation) hard-gated at idle. Turbo whistle drops the 10th
order (would spill into 1-4 kHz) and the 5th order is reduced.

Boundary: synthetic; uncalibrated; not OEM reproduction.
"""

from __future__ import annotations

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace
from ..synth_primitives import combustion_impulse_train, decaying_tone, mechanical_texture, to_stereo, turbo_layer


def render_gtr_r35(trace: VehicleStateTrace, sample_rate_hz: int = 48000) -> SourceRender:
    """Render finite stereo pre-PTR pressure; this is not OEM reproduction."""
    trace.validate()
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    ev = combustion_impulse_train(
        trace, sample_rate_hz, events_per_rev=3.0, pressure_exp=1.3, max_comp=2.0
    )
    count = ev["count"]
    rpm = ev["rpm"]
    load = ev["load"]
    throttle = ev["throttle"]
    phase = ev["phase"]
    impulses = ev["impulses"]
    high_rpm = np.clip((rpm - 2500.0) / 4500.0, 0.0, 1.0)

    # V6 exhaust: crisp, low fundamental, slight uneven cadence. 1st/2nd engine
    # order only (2nd stays ~680 Hz at redline, mid). Gain trimmed from 0.060 so
    # the source low end (plus the low-frequency-body radiation it drives) eases
    # toward the 0.373 accel-low reference instead of dominating.
    exhaust_env = decaying_tone(impulses, 85.0, 0.034, sample_rate_hz)
    exhaust_mono = 0.033 * exhaust_env * (
        np.sin(2.0 * np.pi * phase * 1.0) + 0.4 * np.sin(2.0 * np.pi * phase * 2.0)
    )

    # Racy high-harmonic edge (V6 rasp, not a V10 scream). Fixed-center tones at
    # 300/420 Hz (mid band) PLUS an 1150 Hz component that feeds the 1-4 kHz high
    # band the reference wants. Strong idle floor so the idle clip carries real
    # mid content (idle centroid target ~400 Hz) instead of sitting at ~90 Hz.
    racy_env = (
        0.45 * decaying_tone(impulses, 300.0, 0.026, sample_rate_hz)
        + 0.55 * decaying_tone(impulses, 420.0, 0.024, sample_rate_hz)
        + 0.18 * decaying_tone(impulses, 1150.0, 0.020, sample_rate_hz)
    )
    racy_mono = 0.068 * (0.96 + 0.04 * throttle) * racy_env

    # Idle-only mid lift (turbo/idle whirr) to raise the idle spectral centroid toward
    # the 400 Hz reference target. Gated to idle (idle_gate) so acceleration bands are
    # untouched (their margins are large). Upstream perceptual compensation only.
    idle_gate = np.clip((1850.0 - rpm) / 850.0, 0.0, 1.0)
    idle_mid_env = (
        0.45 * decaying_tone(impulses, 540.0, 0.030, sample_rate_hz)
        + 0.35 * decaying_tone(impulses, 700.0, 0.028, sample_rate_hz)
        + 0.20 * decaying_tone(impulses, 900.0, 0.025, sample_rate_hz)
    )
    # Boosted to pull the idle spectral centroid from ~291 Hz toward the ~400 Hz
    # reference target (gate keeps acceleration bands untouched). Upstream
    # perceptual compensation only — not a radiation/physics change.
    idle_mid_mono = 0.100 * idle_gate * idle_mid_env

    # Twin-turbo whistle + spool (IHI turbos, quick spool). A mid + an 8th shaft
    # order (lands ~1.0-2.0 kHz at redline) carries the 1-4 kHz high band, but the
    # 10th order is dropped again so the high band does not overshoot the reference.
    turbo = turbo_layer(
        rpm, load, throttle, sample_rate_hz,
        shaft_ratio_base=2.0, orders=(1.0, 5.0, 8.0), order_weights=(0.45, 0.35, 0.20),
        boost_tau_attack=0.07, boost_tau_release=0.18,
    )
    whistle_mono = 0.110 * turbo["whine_mono"]

    # Mechanical: valvetrain + accessory, lighter (no blower, turbo instead).
    texture = mechanical_texture(count, sample_rate_hz, 0.07, seed=8.8)
    valvetrain_mono = 0.009 * (rpm > 0.0) * (0.4 + 0.6 * load) * np.sin(2.0 * np.pi * phase * 1.0)
    mechanical_mono = 0.5 * valvetrain_mono + 0.003 * texture

    exhaust = to_stereo(exhaust_mono, 0.5)
    racy = to_stereo(racy_mono, 0.4)
    whistle = to_stereo(whistle_mono, 0.5)
    mechanical = to_stereo(mechanical_mono, 0.5)
    idle_mid = to_stereo(idle_mid_mono, 0.45)

    render = SourceRender(
        pressure=exhaust + racy + whistle + mechanical + idle_mid,
        stems={
            "exhaust": exhaust,
            "racy": racy,
            "whistle": whistle,
            "mechanical": mechanical,
            "idle_mid": idle_mid,
        },
        diagnostics={
            "vehicle_id": "gtr_r35",
            "scope": "synthetic; uncalibrated; not OEM reproduction",
            "engine": "VR38DETT 3.8L V6 twin-turbo",
            "firing": "v6_60deg",
            "events_per_rev": 3.0,
            "identity": "crisp racy V6 + twin-turbo whistle, mid-dominant",
            "exhaust_fundamental_hz": 85.0,
            "turbo_boost_state_peak": float(np.max(turbo["boost_state"])),
        },
    )
    return render.validate()
