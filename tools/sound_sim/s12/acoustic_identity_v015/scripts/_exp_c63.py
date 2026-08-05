"""C63 accel-band optimizer (source-only; low_frequency_body is a no-op at accel).

Sweep bark gain / decay / top-carrier to hit target [0.181, 0.587, 0.222].
Longer bark decay -> higher Q -> less 1-4k comb spill (lower high); more mid
carrier weight lifts mid.

Boundary: synthetic; uncalibrated; not OEM reproduction.
"""

import sys
from pathlib import Path

import numpy as np

_S12 = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_S12))

from acoustic_identity_v015.acoustic_analysis.reference_feature_extractor import BAND_EDGES
from acoustic_identity_v015.contracts import VehicleStateTrace
from acoustic_identity_v015.synth_primitives import combustion_impulse_train, decaying_tone, mechanical_texture, to_stereo
from acoustic_identity_v015.render_realism_v10 import _scenario_trace

SR = 48000
TARGET = (0.181, 0.587, 0.222)


def _bands(audio):
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    n = mono.size
    spec = np.abs(np.fft.rfft(mono * np.hanning(n)))
    freqs = np.fft.rfftfreq(n, 1.0 / SR)
    total = float(spec.sum()) or 1e-15
    return [float(spec[(freqs >= lo) & (freqs < hi)].sum()) / total for lo, hi in BAND_EDGES]


def render(v):
    trace = _scenario_trace("c63_w204", "acceleration", 3.0)
    ev = combustion_impulse_train(trace, SR, events_per_rev=4.0, bank_pattern=(0, 1, 0, 1, 1, 0, 1, 0), pressure_exp=1.2, max_comp=2.0)
    count, rpm, load, throttle, phase, impulses = ev["count"], ev["rpm"], ev["load"], ev["throttle"], ev["phase"], ev["impulses"]
    left, right = ev["left_impulses"], ev["right_impulses"]
    left_env = decaying_tone(left, 140.0, 0.040, SR)
    right_env = decaying_tone(right, 180.0, 0.034, SR)
    exhaust = 0.021 * to_stereo(left_env * np.sin(2.0 * np.pi * phase * 1.0), 0.48) + 0.021 * to_stereo(right_env * np.sin(2.0 * np.pi * phase * 1.0 + 0.2), 0.48)
    d = v["decay"]
    bark_env = (
        v["w540"] * decaying_tone(impulses, 540.0, d, SR)
        + v["w820"] * decaying_tone(impulses, 820.0, d * 0.85, SR)
        + v["wtop"] * decaying_tone(impulses, v["topf"], d * 0.75, SR)
    )
    bark_mono = v["gain"] * (0.50 + 0.50 * throttle) * bark_env
    bark = to_stereo(bark_mono, 0.4)
    intake_env = decaying_tone(impulses, 220.0, 0.022, SR)
    intake = to_stereo(0.018 * (0.1 + 0.9 * throttle) * intake_env, 0.55)
    texture = mechanical_texture(count, SR, 0.08, seed=5.9)
    valvetrain = 0.009 * (rpm > 0.0) * (0.4 + 0.6 * load) * np.sin(2.0 * np.pi * phase * 1.0)
    mechanical = to_stereo(0.5 * valvetrain + 0.004 * texture, 0.5)
    pressure = exhaust + bark + intake + mechanical
    b = _bands(pressure)
    dist = abs(b[0] - TARGET[0]) + abs(b[1] - TARGET[1]) + abs(b[2] - TARGET[2])
    return b, dist


def main():
    best = None
    printed = 0
    for decay in (0.030, 0.045, 0.060, 0.080):
        for gain in (0.090, 0.105, 0.120):
            for w540, w820, wtop in ((0.6, 0.45, 0.30), (0.7, 0.5, 0.25), (0.7, 0.55, 0.20), (0.8, 0.6, 0.15)):
                for topf in (1100, 1300, 1500):
                    v = {"decay": decay, "gain": gain, "w540": w540, "w820": w820, "wtop": wtop, "topf": topf}
                    b, dist = render(v)
                    if best is None or dist < best[1]:
                        best = (v, dist, b)
                    if dist < 0.06 and printed < 10:
                        print(f"dist={dist:.4f} bands={[round(x,3) for x in b]} {v}")
                        printed += 1
    print("\nBEST:")
    print(f"  dist={best[1]:.4f} bands={[round(x,3) for x in best[2]]} {best[0]}")


if __name__ == "__main__":
    main()
