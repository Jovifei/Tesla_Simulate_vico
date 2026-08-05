"""Synthetic, uncalibrated Toyota Supra JZA80 (2JZ-GTE 3.0L I6 twin-turbo) source.

Smooth inline-6 with a heavy low-end rumble (reference: accel 20-250 Hz =
0.730, idle low ~0.975) plus 2JZ twin-turbo whistle and spool. The low
frequency body layer is tuned heavy (Hellcat-class) to deliver the weight;
the source adds the smooth I6 character and turbo whistle. Target idle
centroid ~118 Hz (deep I6 rumble).

Band-safety design: heavy low exhaust fundamental (1st/2nd engine order, low
at idle ~40-150 Hz), boosted gain. The high-harmonic edge is a *fixed-center*
mid tone (360 Hz, no engine-order modulation) hard-gated at idle so the idle
stays deep. Turbo whistle drops the 10th and 5th orders (keep 1st only) to
stay out of 1-4 kHz. Energy is kept out of 1-4 kHz.

Boundary: synthetic; uncalibrated; not OEM reproduction.
"""

from __future__ import annotations

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace
from ..synth_primitives import combustion_impulse_train, decaying_tone, mechanical_texture, to_stereo, turbo_layer


def render_supra_jza80(trace: VehicleStateTrace, sample_rate_hz: int = 48000) -> SourceRender:
    """Render finite stereo pre-PTR pressure; this is not OEM reproduction."""
    trace.validate()
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    ev = combustion_impulse_train(
        trace, sample_rate_hz, events_per_rev=3.0, pressure_exp=1.25, max_comp=2.0
    )
    count = ev["count"]
    rpm = ev["rpm"]
    load = ev["load"]
    throttle = ev["throttle"]
    phase = ev["phase"]
    impulses = ev["impulses"]
    high_rpm = np.clip((rpm - 2500.0) / 4500.0, 0.0, 1.0)

    # Smooth inline-6 exhaust: heavy low fundamental, even cadence (no flat/cross
    # V8 lump). 1st/2nd engine order; at idle the fundamental is ~40-150 Hz (deep).
    # Boosted gain for the heavy low end the reference wants.
    exhaust_env = decaying_tone(impulses, 60.0, 0.040, sample_rate_hz)
    exhaust_mono = 0.060 * exhaust_env * (
        np.sin(2.0 * np.pi * phase * 1.0) + 0.4 * np.sin(2.0 * np.pi * phase * 2.0)
    )

    # 2JZ twin-turbo whistle + spool. Keep only the 1st shaft order (drop 5th/10th
    # so nothing spills into 1-4 kHz); lighter, higher than the GT-R's IHI set.
    turbo = turbo_layer(
        rpm, load, throttle, sample_rate_hz,
        shaft_ratio_base=1.8, orders=(1.0,), order_weights=(0.85,),
        boost_tau_attack=0.08, boost_tau_release=0.20,
    )
    whistle_mono = 0.055 * turbo["whine_mono"]

    # High-harmonic edge (I6 is smoother/calmer than a V8) — fixed-center mid tone
    # (360 Hz), NO engine-order modulation, hard-gated at idle (deep idle target).
    # Gate: fully open once throttle > ~0.16 (accel starts at 0.50), zero at idle
    # (throttle ~0.14) so the deep idle target (centroid ~118 Hz) is preserved.
    edge_env = decaying_tone(impulses, 360.0, 0.014, sample_rate_hz)
    edge_gate = np.clip((throttle - 0.16) / 0.30, 0.0, 1.0)
    edge_mono = 0.052 * edge_gate * (0.02 + 0.98 * throttle) * edge_env

    # Mechanical: smooth I6, light accessory texture. The broadband friction
    # texture (boxcar low-pass leaks wideband energy) and the sub-20 Hz
    # valvetrain tone are both hard-gated at idle (same gate as the edge) so the
    # idle stays a deep, in-band rumble (ref idle centroid 118 Hz, low 0.975).
    # At accel the exhaust/edge/whistle stems dominate and the mechanical whirr
    # returns for character; idle character at rest is supplied by idle_dynamics.
    mech_gate = np.clip((throttle - 0.16) / 0.30, 0.0, 1.0)
    texture = mechanical_texture(count, sample_rate_hz, 0.06, seed=4.4)
    valvetrain_mono = 0.009 * (rpm > 0.0) * (0.4 + 0.6 * load) * np.sin(2.0 * np.pi * phase * 1.0)
    mechanical_mono = mech_gate * (0.5 * valvetrain_mono + 0.0008 * texture)

    exhaust = to_stereo(exhaust_mono, 0.5)
    whistle = to_stereo(whistle_mono, 0.5)
    edge = to_stereo(edge_mono, 0.4)
    mechanical = to_stereo(mechanical_mono, 0.5)

    render = SourceRender(
        pressure=exhaust + whistle + edge + mechanical,
        stems={
            "exhaust": exhaust,
            "whistle": whistle,
            "edge": edge,
            "mechanical": mechanical,
        },
        diagnostics={
            "vehicle_id": "supra_jza80",
            "scope": "synthetic; uncalibrated; not OEM reproduction",
            "engine": "2JZ-GTE 3.0L I6 twin-turbo",
            "firing": "inline6_even",
            "events_per_rev": 3.0,
            "identity": "smooth heavy I6 rumble + 2JZ turbo whistle, low-dominant",
            "exhaust_fundamental_hz": 60.0,
            "turbo_boost_state_peak": float(np.max(turbo["boost_state"])),
        },
    )
    return render.validate()
