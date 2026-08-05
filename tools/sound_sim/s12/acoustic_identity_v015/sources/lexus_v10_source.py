"""Synthetic, uncalibrated Lexus LFA (1LR-GUE 4.8L V10 NA) source.

Even-fire V10 with a high, clean, "angel's cry" tone (Yamaha acoustic design,
F1-like, ~9000 rpm). Reference: acceleration 20-250 Hz = 0.001, 250-1k =
0.974 — essentially no low end, a dominant clean mid scream. The
low-frequency body layer is tuned to nearly zero gain for this car so the
low band stays empty; the source carries the mid-dominant scream. Target idle
centroid ~1366 Hz (the scream is present even at idle).

Band-safety design: the LFA reference accel is a NEAR-PURE MID TONE
([0.001, 0.974, 0.023]). An impulse-excited decaying_tone cannot reach that
target: its resonator has a ~17x DC skirt (leaks into 20-250 Hz) and the
combustion impulse comb throws harmonics at k·f_event (1466/2200 Hz) into the
1-4 kHz band. The angel's cry is a FIXED-CENTER resonance (not an engine
order), so the source models it with fixed-center sinusoids — a pure mid tone
with ~zero low and ~zero high. Always-on light mechanical texture is kept
broadband-but-low (cutoff sr/60 ≈ 800 Hz) so it does not re-introduce the high
band. This matches the reference band structure without touching the shared
synth_primitives module (which the three reviewed core cars depend on).

Boundary: synthetic; uncalibrated; not OEM reproduction.
"""

from __future__ import annotations

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace
from ..synth_primitives import mechanical_texture, to_stereo


def render_lfa(trace: VehicleStateTrace, sample_rate_hz: int = 48000) -> SourceRender:
    """Render finite stereo pre-PTR pressure; this is not OEM reproduction."""
    trace.validate()
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    count = int(round((trace.time_s[-1] - trace.time_s[0]) * sample_rate_hz)) + 1
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    load = np.interp(time_s, trace.time_s, trace.load)
    throttle = np.interp(time_s, trace.time_s, trace.throttle)
    t = time_s
    phase = np.cumsum(rpm) / (60.0 * sample_rate_hz)

    # Fixed-center mid "angel's cry": a near-pure mid tone (480/600/760 Hz).
    # No engine-order modulation, no low 130 Hz partial, no 1-4 kHz AM
    # sidebands — exactly the reference's near-zero low and near-zero high.
    exhaust_env = (
        0.50 * np.sin(2.0 * np.pi * 480.0 * t)
        + 1.00 * np.sin(2.0 * np.pi * 600.0 * t)
        + 0.70 * np.sin(2.0 * np.pi * 760.0 * t)
    )
    exhaust_mono = 0.060 * exhaust_env

    # The scream: clean, smooth mid tone, present at idle (target idle centroid
    # ~1366 Hz). Fixed-center so it stays mid-dominant across rpm.
    scream_env = (
        0.6 * np.sin(2.0 * np.pi * 600.0 * t)
        + 0.4 * np.sin(2.0 * np.pi * 720.0 * t)
    )
    scream_mono = 0.110 * (0.5 + 0.5 * throttle) * scream_env

    # Intake roar (individual throttle bodies) — fixed-center mid.
    intake_env = np.sin(2.0 * np.pi * 480.0 * t)
    intake_mono = 0.014 * (0.5 + 0.5 * load) * intake_env

    # Mechanical: light, refined (Yamaha precision). Valvetrain tone kept
    # near-zero; texture broadband but low-passed (cutoff sr/60) so it does not
    # spill into the 1-4 kHz band.
    texture = mechanical_texture(count, sample_rate_hz, 0.002, seed=2.2)
    valvetrain_mono = 0.0003 * (rpm > 0.0) * (0.4 + 0.6 * load) * np.sin(2.0 * np.pi * phase * 1.0)
    mechanical_mono = 0.5 * valvetrain_mono + 0.0015 * texture

    exhaust = to_stereo(exhaust_mono, 0.45)
    scream = to_stereo(scream_mono, 0.3)
    intake = to_stereo(intake_mono, 0.5)
    mechanical = to_stereo(mechanical_mono, 0.5)

    render = SourceRender(
        pressure=exhaust + scream + intake + mechanical,
        stems={
            "exhaust": exhaust,
            "scream": scream,
            "intake": intake,
            "mechanical": mechanical,
        },
        diagnostics={
            "vehicle_id": "lfa",
            "scope": "synthetic; uncalibrated; not OEM reproduction",
            "engine": "1LR-GUE 4.8L V10 NA",
            "firing": "even_fire_v10",
            "events_per_rev": 5.0,
            "identity": "clean high mid scream, angel's cry, near-zero low end",
            "exhaust_fundamental_hz": 600.0,
            "scream_band": "mid (480-760 Hz)",
        },
    )
    return render.validate()
