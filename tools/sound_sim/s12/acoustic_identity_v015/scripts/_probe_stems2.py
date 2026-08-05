"""Probe per-STEM band shares for the 5 new vehicles at accel + idle.

Isolates which source stem contributes to the 20-250 / 250-1k / 1k-4k bands.

Boundary: synthetic; uncalibrated; not OEM reproduction.
"""

import sys
from pathlib import Path

import numpy as np

_S12 = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_S12))

from acoustic_identity_v015.acoustic_analysis.reference_feature_extractor import BAND_EDGES
from acoustic_identity_v015.render_realism_v10 import _scenario_trace
from acoustic_identity_v015.sources.lamborghini_v12_source import render_aventador_lp700
from acoustic_identity_v015.sources.lexus_v10_source import render_lfa
from acoustic_identity_v015.sources.mercedes_v8_source import render_c63_w204
from acoustic_identity_v015.sources.nissan_v6_turbo_source import render_gtr_r35
from acoustic_identity_v015.sources.toyota_i6_turbo_source import render_supra_jza80

RENDERERS = {
    "aventador_lp700": render_aventador_lp700,
    "c63_w204": render_c63_w204,
    "gtr_r35": render_gtr_r35,
    "lfa": render_lfa,
    "supra_jza80": render_supra_jza80,
}
SR = 48000


def _band_shares(audio, sr=SR):
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    n = mono.size
    spec = np.abs(np.fft.rfft(mono * np.hanning(n)))
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    total = float(spec.sum()) or 1e-15
    return [float(spec[(freqs >= lo) & (freqs < hi)].sum()) / total for lo, hi in BAND_EDGES]


def main():
    for vid, renderer in RENDERERS.items():
        print(f"\n===== {vid} =====")
        for clip in ("idle", "acceleration"):
            trace = _scenario_trace(vid, clip, 3.0)
            src = renderer(trace)
            print(f"  [{clip}]")
            for name, stem in src.stems.items():
                b = _band_shares(stem)
                print(f"    {name:12s} bands={[round(x,3) for x in b]}")


if __name__ == "__main__":
    main()
