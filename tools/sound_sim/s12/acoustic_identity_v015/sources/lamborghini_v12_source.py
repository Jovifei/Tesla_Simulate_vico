"""Synthetic, uncalibrated Lamborghini Aventador LP700 V12 (L539 6.5L NA) source.

Even-fire 12-cylinder voice: smooth, dense, high-frequency "operatic wail"
rather than a lumpy V8 rumble. Mid-dominant spectrum (per reference: accel
250-1k = 0.571) with a restrained low end supplied by the low-frequency
body layer. No forced induction (pure NA V12). Target idle centroid ~648 Hz.

Band-safety design: the exhaust fundamental is carried only at the 1st engine
order (<= ~850 Hz at 8500 rpm, never spills into 1-4 kHz). The wail and
intake are *fixed-center* decaying tones (no engine-order modulation), so their
energy stays in 250-1k at every rpm. Always-on timing jitter + amplitude
variation smears the harmonic comb so energy does not pile into 1-4 kHz at high
rpm. Mid identity layers are softened at idle (target idle centroid ~650 Hz).

Boundary: synthetic; uncalibrated; not OEM reproduction.
"""

from __future__ import annotations

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace
from ..synth_primitives import combustion_impulse_train, decaying_tone, mechanical_texture, to_stereo


def render_aventador_lp700(trace: VehicleStateTrace, sample_rate_hz: int = 48000) -> SourceRender:
    """Render finite stereo pre-PTR pressure; this is not OEM reproduction."""
    trace.validate()
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    ev = combustion_impulse_train(
        trace, sample_rate_hz, events_per_rev=6.0, pressure_exp=1.05, max_comp=1.8,
        timing_jitter=0.10, amp_variation=0.12,
    )
    count = ev["count"]
    rpm = ev["rpm"]
    load = ev["load"]
    throttle = ev["throttle"]
    phase = ev["phase"]
    impulses = ev["impulses"]
    high_rpm = np.clip((rpm - 2500.0) / 5500.0, 0.0, 1.0)

    # Even-fire exhaust: low fundamental only, modulated at the 1st engine order
    # (stays <= ~850 Hz at redline). Short decay so the periodic retrigger stays tight.
    # Slightly trimmed so the idle low band does not over-dominate (idle is mid per ref).
    exhaust_env = decaying_tone(impulses, 92.0, 0.050, sample_rate_hz)
    exhaust_mono = 0.030 * exhaust_env * np.sin(2.0 * np.pi * phase * 1.0)

    # The "operatic wail" — fixed-center mid tones (400/540 Hz), longer decay, no
    # engine-order modulation. Kept below 1 kHz so energy stays in the 250-1k mid
    # band (reference accel mid = 0.571) instead of spilling into 1-4 kHz. The
    # longer decay makes the wail a near-continuous tone so the impulse AM
    # sidebands collapse into the 250-1k mid band (less 1-4 kHz spill). Louder
    # overall to lift the mid share; softer idle floor so the idle centroid stays ~648.
    wail_env = (
        0.6 * decaying_tone(impulses, 400.0, 0.060, sample_rate_hz)
        + 0.4 * decaying_tone(impulses, 540.0, 0.051, sample_rate_hz)
    )
    wail_mono = 0.118 * (0.15 + 0.85 * throttle) * wail_env

    # Intake roar — 12 individual throttle bodies behind the cabin (fixed mid center).
    intake_env = decaying_tone(impulses, 240.0, 0.022, sample_rate_hz)
    intake_mono = 0.016 * (0.4 + 0.6 * throttle) * intake_env

    # Valvetrain + accessory mechanical texture (V12 is mechanically busy but smooth).
    # Kept low so the broadband tail does not inflate the 1-4 kHz high band; trimming
    # it also lifts the relative mid/low shares toward the reference accel mid (0.571).
    texture = mechanical_texture(count, sample_rate_hz, 0.03, seed=3.1)
    valvetrain_mono = 0.010 * (rpm > 0.0) * (0.4 + 0.6 * load) * np.sin(2.0 * np.pi * phase * 1.0)
    mechanical_mono = 0.5 * valvetrain_mono + 0.001 * texture

    exhaust = to_stereo(exhaust_mono, 0.5)
    wail = to_stereo(wail_mono, 0.35)
    intake = to_stereo(intake_mono, 0.55)
    mechanical = to_stereo(mechanical_mono, 0.5)

    render = SourceRender(
        pressure=exhaust + wail + intake + mechanical,
        stems={
            "exhaust": exhaust,
            "wail": wail,
            "intake": intake,
            "mechanical": mechanical,
        },
        diagnostics={
            "vehicle_id": "aventador_lp700",
            "scope": "synthetic; uncalibrated; not OEM reproduction",
            "engine": "L539 6.5L V12 NA",
            "firing": "even_fire_12_cylinder",
            "events_per_rev": 6.0,
            "identity": "smooth dense operatic wail, mid-dominant, NA",
            "exhaust_fundamental_hz": 92.0,
            "wail_band": "mid (520-760 Hz)",
        },
    )
    return render.validate()
