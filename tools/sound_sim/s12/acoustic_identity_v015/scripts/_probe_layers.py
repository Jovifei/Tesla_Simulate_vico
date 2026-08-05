"""Probe per-layer band shares for the 5 new vehicles.

Isolates how source -> idle_dynamics -> afterfire -> low_frequency_body
contributes to each band, so tuning can target the right layer.

Boundary: synthetic; uncalibrated; not OEM reproduction.
"""

import sys
from pathlib import Path

import numpy as np

_S12 = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_S12))

from acoustic_identity_v015.acoustic_analysis.reference_feature_extractor import BAND_EDGES
from acoustic_identity_v015.acoustic_layers import apply_afterfire, apply_idle_dynamics, apply_low_frequency_body
from acoustic_identity_v015.contracts import VehicleStateTrace
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


def _centroid(audio, sr=SR):
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    spec = np.abs(np.fft.rfft(mono * np.hanning(mono.size)))
    freqs = np.fft.rfftfreq(mono.size, 1.0 / sr)
    total = float(spec.sum()) or 1e-15
    return float((freqs * spec).sum() / total)


def main():
    for vid, renderer in RENDERERS.items():
        print(f"\n===== {vid} =====")
        for clip in ("idle", "acceleration"):
            trace = _scenario_trace(vid, clip, 3.0)
            src = renderer(trace)
            s_b = _band_shares(src.pressure)
            s_c = _centroid(src.pressure)
            idle = apply_idle_dynamics(src, vid, trace, SR)
            i_b = _band_shares(idle.pressure)
            i_c = _centroid(idle.pressure)
            after = apply_afterfire(idle, vid, trace, SR)
            a_b = _band_shares(after.pressure)
            a_c = _centroid(after.pressure)
            final = apply_low_frequency_body(after, vid, trace, SR)
            f_b = _band_shares(final.pressure)
            f_c = _centroid(final.pressure)
            print(f"  [{clip}]")
            print(f"    source    bands={[round(b,3) for b in s_b]} c={s_c:6.0f}")
            print(f"    idle_dyn  bands={[round(b,3) for b in i_b]} c={i_c:6.0f}")
            print(f"    afterfire bands={[round(b,3) for b in a_b]} c={a_c:6.0f}")
            print(f"    low_body  bands={[round(b,3) for b in f_b]} c={f_c:6.0f}")


if __name__ == "__main__":
    main()
