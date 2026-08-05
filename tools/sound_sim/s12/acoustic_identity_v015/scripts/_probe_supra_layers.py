"""Decompose supra idle pipeline layer-by-layer to find the centroid lifter."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_S12 = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_S12))

from acoustic_identity_v015.acoustic_analysis.reference_feature_extractor import BAND_EDGES
from acoustic_identity_v015.acoustic_layers import apply_afterfire, apply_idle_dynamics, apply_low_frequency_body
from acoustic_identity_v015.render_realism_v10 import _scenario_trace
from acoustic_identity_v015.sources.toyota_i6_turbo_source import render_supra_jza80

SR = 48000


def band_shares(audio):
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    spec = np.abs(np.fft.rfft(mono * np.hanning(mono.size)))
    freqs = np.fft.rfftfreq(mono.size, 1.0 / SR)
    total = float(spec.sum()) or 1e-15
    return [round(float(spec[(freqs >= lo) & (freqs < hi)].sum()) / total, 4) for lo, hi in BAND_EDGES]


def centroid(audio):
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    spec = np.abs(np.fft.rfft(mono * np.hanning(mono.size)))
    freqs = np.fft.rfftfreq(mono.size, 1.0 / SR)
    total = float(spec.sum()) or 1e-15
    return float((freqs * spec).sum() / total)


trace = _scenario_trace("supra_jza80", "idle", 3.0)
s0 = render_supra_jza80(trace)
print("1) SOURCE            ", band_shares(s0.pressure), f"c={centroid(s0.pressure):.0f}")
s1 = apply_idle_dynamics(s0, "supra_jza80", trace, SR)
print("2) +idle_dynamics    ", band_shares(s1.pressure), f"c={centroid(s1.pressure):.0f}")
s2 = apply_afterfire(s1, "supra_jza80", trace, SR)
print("3) +afterfire        ", band_shares(s2.pressure), f"c={centroid(s2.pressure):.0f}")
s3 = apply_low_frequency_body(s2, "supra_jza80", trace, SR)
print("4) +low_frequency_body", band_shares(s3.pressure), f"c={centroid(s3.pressure):.0f}")
