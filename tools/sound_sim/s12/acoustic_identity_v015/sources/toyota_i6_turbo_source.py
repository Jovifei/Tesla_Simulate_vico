"""Synthetic, uncalibrated Toyota Supra JZA80 (2JZ-GTE 3.0L I6 twin-turbo) source.

Smooth inline-6 with a deep low-end rumble (reference accel 20-250 Hz =
0.730, idle low ~0.975) plus 2JZ twin-turbo whistle and spool. The low
frequency body layer is tuned heavy (Hellcat-class) to deliver the weight;
the source adds the smooth I6 character, a mid-band racy/intake edge, and a
faint high-band turbo-compressor whistle. Target idle centroid ~118 Hz
(deep I6 rumble).

Coarse-realism tuning (handover §5/§6):
- The frozen low_frequency_body supplies the heavy 20-250 Hz weight, so the
  source is responsible for (a) lifting the idle spectral centroid from the
  baseline ~53 Hz toward 118 Hz, and (b) shifting acceleration energy from the
  low band into the mid band (target low/mid/high ~ 0.730/0.253/0.016).
- Idle centroid is lifted by raising the exhaust carrier to 120 Hz and using
  a 1st-6th engine-order mix (rather than just 1st/2nd). This keeps the idle
  deep (still <250 Hz) but centres the low-band energy near ~117 Hz. The
  shared idle_dynamics 28 Hz combustion ring is untouched (frozen layer).
- Acceleration mid band is carried by a 360 Hz "edge" tone (I6 racy/intake
  character), accel-gated so the idle stays deep.
- A faint 1800 Hz turbo-compressor whistle (accel-gated) provides the small
  1000-4000 Hz (high) band share the reference wants (~0.016). This is an
  upstream-excitation perceptual high-frequency compensation, declared as
  such; it stays inside the validated 55-5459 Hz band. The turbo whine itself
  keeps only the 1st shaft order so it does not spill into 1-4 kHz.

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

    # Smooth inline-6 exhaust: deep fundamental at 120 Hz (raised from the old
    # 60 Hz so the idle centroid lands near the 118 Hz target) with a 1st-6th
    # engine-order mix. The higher orders push low-band energy up toward
    # 100-250 Hz (lifting the idle centroid) while keeping the note a deep,
    # smooth I6 rather than a shrill tone.
    exhaust_env = decaying_tone(impulses, 120.0, 0.040, sample_rate_hz)
    exhaust_mono = 0.060 * exhaust_env * (
        0.6 * np.sin(2.0 * np.pi * phase * 1.0)
        + 0.8 * np.sin(2.0 * np.pi * phase * 2.0)
        + 0.9 * np.sin(2.0 * np.pi * phase * 3.0)
        + 0.7 * np.sin(2.0 * np.pi * phase * 4.0)
        + 0.4 * np.sin(2.0 * np.pi * phase * 5.0)
        + 0.2 * np.sin(2.0 * np.pi * phase * 6.0)
    )

    # 2JZ twin-turbo whistle + spool. Only the 1st shaft order is kept so the
    # whine stays out of 1-4 kHz (the high band is covered separately below).
    turbo = turbo_layer(
        rpm, load, throttle, sample_rate_hz,
        shaft_ratio_base=1.8, orders=(1.0,), order_weights=(0.7,),
        boost_tau_attack=0.08, boost_tau_release=0.20,
    )
    whistle_mono = 0.060 * turbo["whine_mono"]

    # Mid-band "racy/intake" edge (I6 is smoother/calmer than a V8) — 360 Hz
    # fixed-center tone, NO engine-order modulation, hard-gated at idle (deep
    # idle target preserved). Open once throttle > ~0.16 so it carries the
    # acceleration mid band (target 250-1000 Hz ~ 0.253).
    edge_env = decaying_tone(impulses, 360.0, 0.014, sample_rate_hz)
    edge_gate = np.clip((throttle - 0.16) / 0.30, 0.0, 1.0)
    edge_mono = 0.080 * edge_gate * (0.02 + 0.98 * throttle) * edge_env

    # Faint high-band turbo-compressor whistle — perceptual high-frequency
    # compensation (declared). Accel-gated, 1800 Hz, kept small so the
    # 1000-4000 Hz band share meets the reference (~0.016) without dominating.
    # Inside the validated 55-5459 Hz band; does not run at idle.
    hiband_env = decaying_tone(impulses, 1800.0, 0.012, sample_rate_hz)
    hiband_gate = np.clip((throttle - 0.16) / 0.30, 0.0, 1.0)
    hiband_mono = 0.012 * hiband_gate * (0.02 + 0.98 * throttle) * hiband_env

    # Mechanical: smooth I6, light accessory texture. Both the broadband
    # friction texture and the sub-20 Hz valvetrain tone are hard-gated at idle
    # (same gate as the edge/hiband) so the idle stays a deep, in-band rumble.
    # At accel the exhaust/edge/whistle/hiband stems dominate and the
    # mechanical whirr returns for character.
    mech_gate = np.clip((throttle - 0.16) / 0.30, 0.0, 1.0)
    texture = mechanical_texture(count, sample_rate_hz, 0.06, seed=4.4)
    valvetrain_mono = 0.009 * (rpm > 0.0) * (0.4 + 0.6 * load) * np.sin(2.0 * np.pi * phase * 1.0)
    mechanical_mono = mech_gate * (0.5 * valvetrain_mono + 0.0008 * texture)

    exhaust = to_stereo(exhaust_mono, 0.5)
    whistle = to_stereo(whistle_mono, 0.5)
    edge = to_stereo(edge_mono, 0.4)
    hiband = to_stereo(hiband_mono, 0.4)
    mechanical = to_stereo(mechanical_mono, 0.5)

    render = SourceRender(
        pressure=exhaust + whistle + edge + hiband + mechanical,
        stems={
            "exhaust": exhaust,
            "whistle": whistle,
            "edge": edge,
            "hiband": hiband,
            "mechanical": mechanical,
        },
        diagnostics={
            "vehicle_id": "supra_jza80",
            "scope": "synthetic; uncalibrated; not OEM reproduction",
            "engine": "2JZ-GTE 3.0L I6 twin-turbo",
            "firing": "inline6_even",
            "events_per_rev": 3.0,
            "identity": "smooth deep I6 rumble + 360 Hz racy edge + faint turbo whistle",
            "exhaust_fundamental_hz": 120.0,
            "turbo_boost_state_peak": float(np.max(turbo["boost_state"])),
            "hiband_compensation_hz": 1800.0,
        },
    )
    return render.validate()
