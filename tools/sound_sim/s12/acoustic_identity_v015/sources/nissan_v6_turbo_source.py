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
    # order only (2nd stays ~680 Hz at redline, mid). Stronger low gain for the
    # moderate low end the reference wants.
    exhaust_env = decaying_tone(impulses, 85.0, 0.034, sample_rate_hz)
    exhaust_mono = 0.060 * exhaust_env * (
        np.sin(2.0 * np.pi * phase * 1.0) + 0.4 * np.sin(2.0 * np.pi * phase * 2.0)
    )

    # Racy high-harmonic edge (V6 rasp, not a V10 scream) — fixed-center mid
    # tones (300/420 Hz), NO engine-order modulation, hard-gated at idle.
    racy_env = (
        0.4 * decaying_tone(impulses, 300.0, 0.026, sample_rate_hz)
        + 0.6 * decaying_tone(impulses, 420.0, 0.024, sample_rate_hz)
    )
    racy_mono = 0.028 * (0.10 + 0.90 * throttle) * racy_env

    # Twin-turbo whistle + spool (IHI turbos, quick spool). Drop the 10th order
    # and reduce the 5th; keep the 1st shaft order clean and low-mid.
    turbo = turbo_layer(
        rpm, load, throttle, sample_rate_hz,
        shaft_ratio_base=2.0, orders=(1.0, 5.0), order_weights=(0.55, 0.45),
        boost_tau_attack=0.07, boost_tau_release=0.18,
    )
    whistle_mono = 0.070 * turbo["whine_mono"]

    # Mechanical: valvetrain + accessory, lighter (no blower, turbo instead).
    texture = mechanical_texture(count, sample_rate_hz, 0.07, seed=8.8)
    valvetrain_mono = 0.009 * (rpm > 0.0) * (0.4 + 0.6 * load) * np.sin(2.0 * np.pi * phase * 1.0)
    mechanical_mono = 0.5 * valvetrain_mono + 0.003 * texture

    exhaust = to_stereo(exhaust_mono, 0.5)
    racy = to_stereo(racy_mono, 0.4)
    whistle = to_stereo(whistle_mono, 0.5)
    mechanical = to_stereo(mechanical_mono, 0.5)

    render = SourceRender(
        pressure=exhaust + racy + whistle + mechanical,
        stems={
            "exhaust": exhaust,
            "racy": racy,
            "whistle": whistle,
            "mechanical": mechanical,
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
