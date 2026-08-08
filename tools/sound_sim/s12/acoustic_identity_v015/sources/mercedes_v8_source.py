"""Synthetic, uncalibrated Mercedes C63 AMG W204 (M156 6.2L V8 NA) source.

Cross-plane crank (irregular firing, "potato-potato" cadence) like the
Hellcat source, but naturally aspirated: no supercharger whine, just instant
NA response, a deep muscular idle rumble and the famous AMG "blip-bark"
crack on throttle. Mid-dominant acceleration (reference: accel 250-1k = 0.587,
1-4k = 0.222) with a deep but not Hellcat-heavy low end. Target idle centroid
~178 Hz (deep rumble).

Band-safety design: exhaust raised to a mid-low fundamental (140/180 Hz, 1st
engine order only) so it does not dominate the low band; the AMG bark is a
*fixed-center* mid tone (540/700 Hz, no engine-order modulation) hard-gated at
idle so the idle stays deep, and loud under throttle to carry the mid band.

Boundary: synthetic; uncalibrated; not OEM reproduction.
"""

from __future__ import annotations

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace
from ..synth_primitives import combustion_impulse_train, decaying_tone, mechanical_texture, to_stereo


def render_c63_w204(trace: VehicleStateTrace, sample_rate_hz: int = 48000) -> SourceRender:
    """Render finite stereo pre-PTR pressure; this is not OEM reproduction."""
    trace.validate()
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    ev = combustion_impulse_train(
        trace, sample_rate_hz, events_per_rev=4.0,
        bank_pattern=(0, 1, 0, 1, 1, 0, 1, 0), pressure_exp=1.2, max_comp=2.0,
    )
    count = ev["count"]
    rpm = ev["rpm"]
    load = ev["load"]
    throttle = ev["throttle"]
    phase = ev["phase"]
    impulses = ev["impulses"]
    left = ev["left_impulses"]
    right = ev["right_impulses"]

    # Cross-plane exhaust: mid-low fundamental (140/180 Hz), 1st engine order only.
    # Raised gain so the combustion low band (20-250 Hz) carries the reference
    # accel_low (~0.18); exhaust scales with load via the impulse amplitude, so
    # this also stays restrained at idle (keeps idle centroid from sinking).
    left_env = decaying_tone(left, 140.0, 0.040, sample_rate_hz)
    right_env = decaying_tone(right, 180.0, 0.034, sample_rate_hz)
    exhaust_left_bank = 0.072 * to_stereo(left_env * np.sin(2.0 * np.pi * phase * 1.0), 0.48)
    exhaust_right_bank = 0.072 * to_stereo(right_env * np.sin(2.0 * np.pi * phase * 1.0 + 0.2), 0.48)
    exhaust = exhaust_left_bank + exhaust_right_bank

    # AMG "blip-bark": fixed-center tone stack. The 1100/1500 Hz components are
    # emphasized (and 540/820 trimmed) because higher-freq resonators ring louder
    # (sin(w) onset gain), moving accel energy from the swollen mid band into the
    # high band. 1500 Hz is a perceptual high-band compensation (upstream only;
    # radiation >5.5 kHz unvalidated). The lower throttle-slope + higher floor
    # lifts the idle bark (and thus idle centroid) without changing accel much.
    bark_env = (
        0.50 * decaying_tone(impulses, 540.0, 0.045, sample_rate_hz)
        + 0.40 * decaying_tone(impulses, 820.0, 0.038, sample_rate_hz)
        + 0.42 * decaying_tone(impulses, 1100.0, 0.034, sample_rate_hz)
        + 0.10 * decaying_tone(impulses, 1500.0, 0.030, sample_rate_hz)
    )
    bark_mono = 0.125 * (0.60 + 0.40 * throttle) * bark_env
    bark = to_stereo(bark_mono, 0.4)

    # Intake roar (NA, immediate) — low-band center (200 Hz), load-gated so it
    # adds accel_low without dragging the idle centroid down.
    intake_env = decaying_tone(impulses, 200.0, 0.022, sample_rate_hz)
    intake_mono = 0.040 * (0.1 + 0.9 * throttle) * intake_env
    intake = to_stereo(intake_mono, 0.55)

    # Mechanical: valvetrain + accessory, lighter than Hellcat (no blower).
    texture = mechanical_texture(count, sample_rate_hz, 0.08, seed=5.9)
    valvetrain_mono = 0.009 * (rpm > 0.0) * (0.4 + 0.6 * load) * np.sin(2.0 * np.pi * phase * 1.0)
    mechanical_mono = 0.5 * valvetrain_mono + 0.004 * texture
    mechanical = to_stereo(mechanical_mono, 0.5)

    render = SourceRender(
        pressure=exhaust + bark + intake + mechanical,
        stems={
            "exhaust": exhaust,
            "exhaust_left_bank": exhaust_left_bank,
            "exhaust_right_bank": exhaust_right_bank,
            "bark": bark,
            "intake": intake,
            "mechanical": mechanical,
        },
        diagnostics={
            "vehicle_id": "c63_w204",
            "scope": "synthetic; uncalibrated; not OEM reproduction",
            "engine": "M156 6.2L V8 NA",
            "firing": "cross_plane_irregular",
            "events_per_rev": 4.0,
            "identity": "deep muscular NA V8, AMG blip-bark, mid-dominant",
            "exhaust_fundamental_hz": 140.0,
            "bark_band": "mid-high (540-1500 Hz)",
        },
    )
    return render.validate()
