"""LFA accel-band sweep v2: fixed-center SINUSOIDS (pure mid tone).

LFA reference accel [0.001,0.974,0.023] is a near-pure mid tone. The
impulse-excited decaying_tone can't reach it (DC skirt + comb harmonics).
The angel's cry is a fixed-center resonance, so fixed-center sinusoids are
the correct match. Sweep centers/weights; verify bands hit target.

Boundary: synthetic; uncalibrated; not OEM reproduction.
"""

import sys
from pathlib import Path

import numpy as np

_S12 = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_S12))

from acoustic_identity_v015.acoustic_analysis.reference_feature_extractor import BAND_EDGES
from acoustic_identity_v015.render_realism_v10 import _scenario_trace

SR = 48000
TARGET = (0.001, 0.974, 0.023)


def _bands(audio):
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    n = mono.size
    spec = np.abs(np.fft.rfft(mono * np.hanning(n)))
    freqs = np.fft.rfftfreq(n, 1.0 / SR)
    total = float(spec.sum()) or 1e-15
    return [float(spec[(freqs >= lo) & (freqs < hi)].sum()) / total for lo, hi in BAND_EDGES]


def render(v):
    trace = _scenario_trace("lfa", "acceleration", 3.0)
    count, t = trace.time_s.size, trace.time_s
    load, throttle = trace.load, trace.throttle
    # fixed-center sinusoids
    c = v["c"]
    w = v["w"]
    exhaust = 0.060 * sum(wi * np.sin(2.0 * np.pi * ci * t) for ci, wi in zip(c, w))
    scream = 0.110 * (0.5 + 0.5 * throttle) * (0.6 * np.sin(2.0 * np.pi * c[1] * t) + 0.4 * np.sin(2.0 * np.pi * (c[1] + 120) * t))
    intake = 0.014 * (0.5 + 0.5 * load) * np.sin(2.0 * np.pi * c[0] * t)
    tex = v["tex"]
    if tex > 0:
        rng = np.random.default_rng(2)
        noise = rng.uniform(-1, 1, count)
        co = max(int(SR / 60), 1)
        k = np.ones(co) / co
        texture = np.convolve(noise, k, mode="same")
        texture = texture / (texture.max() or 1)
        mechanical = 0.002 * tex * texture
    else:
        mechanical = np.zeros(count)
    pressure = exhaust + scream + intake + mechanical
    b = _bands(pressure)
    dist = abs(b[0] - TARGET[0]) + abs(b[1] - TARGET[1]) + abs(b[2] - TARGET[2])
    return b, dist


def main():
    best = None
    printed = 0
    for c in ((480, 600, 760), (520, 640, 780), (560, 680, 800), (600, 720, 840)):
        for w in ((0.5, 1.0, 0.7), (0.4, 1.0, 0.8), (0.3, 1.0, 0.9)):
            for tex in (0.0, 0.003):
                v = {"c": c, "w": w, "tex": tex}
                b, dist = render(v)
                if best is None or dist < best[1]:
                    best = (v, dist, b)
                if dist < 0.06 and printed < 12:
                    print(f"dist={dist:.4f} bands={[round(x,3) for x in b]} {v}")
                    printed += 1
    print("\nBEST:")
    print(f"  dist={best[1]:.4f} bands={[round(x,3) for x in best[2]]} {best[0]}")


if __name__ == "__main__":
    main()
