"""Decompose final pressure into per-stem band contributions for the 5 vehicles.

Bands: 0=20-250, 1=250-1000, 2=1000-4000, 3=4000-12000 Hz.
For each (car, clip) we print the band shares of each named stem individually
(linear approximation) so we can see which stem drives which band.
"""
import sys
from pathlib import Path

import numpy as np

_S12 = Path(r"E:\Tesla_speed\worktrees\s12-v12\tools\sound_sim\s12")
sys.path.insert(0, str(_S12))

from acoustic_identity_v015.acoustic_analysis.reference_feature_extractor import BAND_EDGES
from acoustic_identity_v015.contracts import VehicleStateTrace
from acoustic_identity_v015.render_realism_v10 import _render_stateful, _scenario_trace

RENDERERS = {
    "aventador_lp700": __import__("acoustic_identity_v015.sources.lamborghini_v12_source", fromlist=["render_aventador_lp700"]).render_aventador_lp700,
    "c63_w204": __import__("acoustic_identity_v015.sources.mercedes_v8_source", fromlist=["render_c63_w204"]).render_c63_w204,
    "gtr_r35": __import__("acoustic_identity_v015.sources.nissan_v6_turbo_source", fromlist=["render_gtr_r35"]).render_gtr_r35,
    "lfa": __import__("acoustic_identity_v015.sources.lexus_v10_source", fromlist=["render_lfa"]).render_lfa,
    "supra_jza80": __import__("acoustic_identity_v015.sources.toyota_i6_turbo_source", fromlist=["render_supra_jza80"]).render_supra_jza80,
}
SR = 48000


def _shares(audio):
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    spec = np.abs(np.fft.rfft(mono * np.hanning(mono.size)))
    freqs = np.fft.rfftfreq(mono.size, 1.0 / SR)
    total = float(spec.sum()) or 1e-15
    return [float(spec[(freqs >= lo) & (freqs < hi)].sum()) / total for lo, hi in BAND_EDGES]


def _centroid(audio):
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    spec = np.abs(np.fft.rfft(mono * np.hanning(mono.size)))
    freqs = np.fft.rfftfreq(mono.size, 1.0 / SR)
    total = float(spec.sum()) or 1e-15
    return float((freqs * spec).sum() / total)


for vid, renderer in RENDERERS.items():
    for clip in ("idle", "acceleration"):
        trace = _scenario_trace(vid, clip, 3.0)
        render = _render_stateful(renderer, vid, trace)
        print(f"\n### {vid} / {clip}  (total centroid={_centroid(render.pressure):.0f})")
        print(f"  TOTAL bands: {[round(b,3) for b in _shares(render.pressure)]}")
        # per-stem
        rows = []
        for name, stem in render.stems.items():
            s = np.asarray(stem, dtype=np.float64)
            if s.shape[0] != render.pressure.shape[0]:
                continue
            rows.append((name, _shares(s), float(np.max(np.abs(s)))))
        rows.sort(key=lambda r: -max(r[1]))
        for name, sh, pk in rows:
            print(f"    {name:28s} bands={[round(b,3) for b in sh]} pk={pk:.3f}")
