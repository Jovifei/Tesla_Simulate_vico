"""Aventador accel-band optimizer (source + active low_frequency_body).

Sweep wail gain/decay, exhaust decay, and low_frequency_body pulse_gain to hit
target [0.383, 0.571, 0.040]. low_body adds low and proportionally trims
mid/high, so we lift mid via wail gain and trim high via longer wail decay.

Boundary: synthetic; uncalibrated; not OEM reproduction.
"""

import sys
from pathlib import Path

import numpy as np

_S12 = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_S12))

from acoustic_identity_v015.acoustic_analysis.reference_feature_extractor import BAND_EDGES
from acoustic_identity_v015.acoustic_layers import apply_low_frequency_body
from acoustic_identity_v015.acoustic_analysis.reference_feature_extractor import BAND_EDGES
from acoustic_identity_v015.contracts import VehicleStateTrace
from acoustic_identity_v015.synth_primitives import combustion_impulse_train, decaying_tone, mechanical_texture, to_stereo
from acoustic_identity_v015.render_realism_v10 import _scenario_trace

SR = 48000
TARGET = (0.383, 0.571, 0.040)


def _bands(audio):
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    n = mono.size
    spec = np.abs(np.fft.rfft(mono * np.hanning(n)))
    freqs = np.fft.rfftfreq(n, 1.0 / SR)
    total = float(spec.sum()) or 1e-15
    return [float(spec[(freqs >= lo) & (freqs < hi)].sum()) / total for lo, hi in BAND_EDGES]


def render(v, pulse_gain):
    trace = _scenario_trace("aventador_lp700", "acceleration", 3.0)
    ev = combustion_impulse_train(trace, SR, events_per_rev=6.0, pressure_exp=1.05, max_comp=1.8, timing_jitter=v["jit"], amp_variation=v["amp"])
    count, rpm, load, throttle, phase, impulses = ev["count"], ev["rpm"], ev["load"], ev["throttle"], ev["phase"], ev["impulses"]
    exhaust_env = decaying_tone(impulses, 92.0, v["exh_d"], SR)
    exhaust = 0.030 * exhaust_env * np.sin(2.0 * np.pi * phase * 1.0)
    wail_env = v["w540"] * decaying_tone(impulses, 400.0, v["w_d"], SR) + v["w540b"] * decaying_tone(impulses, 540.0, v["w_d"] * 0.85, SR)
    wail = v["wail_g"] * (0.15 + 0.85 * throttle) * wail_env
    intake_env = decaying_tone(impulses, 240.0, 0.022, SR)
    intake = 0.016 * (0.4 + 0.6 * throttle) * intake_env
    texture = mechanical_texture(count, SR, 0.03, seed=3.1)
    valvetrain = 0.010 * (rpm > 0.0) * (0.4 + 0.6 * load) * np.sin(2.0 * np.pi * phase * 1.0)
    mechanical = 0.5 * valvetrain + 0.004 * texture
    pressure = exhaust + wail + intake + mechanical
    # apply low_frequency_body with patched pulse_gain
    import acoustic_identity_v015.acoustic_layers.low_frequency_body as lfb
    lfb._PRESSURE_PROFILES["aventador_lp700"]["pulse_gain"] = pulse_gain
    final = apply_low_frequency_body(_as_render(pressure, trace), "aventador_lp700", trace, SR)
    b = _bands(final.pressure)
    dist = abs(b[0] - TARGET[0]) + abs(b[1] - TARGET[1]) + abs(b[2] - TARGET[2])
    return b, dist


def _as_render(pressure, trace):
    from acoustic_identity_v015.contracts import SourceRender
    stereo = np.column_stack((pressure, pressure))
    return SourceRender(pressure=stereo, stems={"exhaust": stereo, "mechanical": stereo, "_tmp": stereo}, diagnostics={})


def main():
    best = None
    printed = 0
    for wail_g in (0.090, 0.105, 0.120):
        for w_d in (0.035, 0.050, 0.070):
            for exh_d in (0.050, 0.070):
                for jit, amp in ((0.10, 0.12), (0.25, 0.25), (0.40, 0.40)):
                    for pg in (1.55, 1.8, 2.2, 2.6):
                        v = {"w540": 0.6, "w540b": 0.4, "wail_g": wail_g, "w_d": w_d, "exh_d": exh_d, "jit": jit, "amp": amp}
                    b, dist = render(v, pg)
                    if best is None or dist < best[1]:
                        best = (v, pg, dist, b)
                    if dist < 0.04 and printed < 10:
                        print(f"dist={dist:.4f} bands={[round(x,3) for x in b]} pg={pg} {v}")
                        printed += 1
    print("\nBEST:")
    print(f"  dist={best[2]:.4f} bands={[round(x,3) for x in best[3]]} pg={best[1]} {best[0]}")


if __name__ == "__main__":
    main()
