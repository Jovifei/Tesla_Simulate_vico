"""Measure actual RMS amplitudes of each source stem at idle to understand the mix."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_S12 = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_S12))

from acoustic_identity_v015.render_realism_v10 import _scenario_trace
from acoustic_identity_v015.sources.toyota_i6_turbo_source import render_supra_jza80

SR = 48000


def rms(a):
    mono = a.mean(axis=1) if a.ndim == 2 else a
    return float(np.sqrt(np.mean(mono ** 2)))


trace = _scenario_trace("supra_jza80", "idle", 3.0)
src = render_supra_jza80(trace)
print("RMS of each stem (mono):")
for name, s in src.stems.items():
    print(f"  {name:16s} rms={rms(s):.5f}")
print(f"  FULL pressure rms={rms(src.pressure):.5f}")
# ratio mechanical/exhaust
mech = rms(src.stems["mechanical"])
exh = rms(src.stems["exhaust"])
print(f"  mech/exh rms ratio = {mech/exh:.4f}")


def centroid(a):
    mono = a.mean(axis=1) if a.ndim == 2 else a
    spec = np.abs(np.fft.rfft(mono * np.hanning(mono.size)))
    freqs = np.fft.rfftfreq(mono.size, 1.0 / SR)
    total = float(spec.sum()) or 1e-15
    return float((freqs * spec).sum() / total)


def band_shares(a):
    mono = a.mean(axis=1) if a.ndim == 2 else a
    spec = np.abs(np.fft.rfft(mono * np.hanning(mono.size)))
    freqs = np.fft.rfftfreq(mono.size, 1.0 / SR)
    total = float(spec.sum()) or 1e-15
    edges = [(20.0, 250.0), (250.0, 1000.0), (1000.0, 4000.0), (4000.0, 12000.0)]
    return [round(float(spec[(freqs >= lo) & (freqs < hi)].sum()) / total, 3) for lo, hi in edges]


print(f"  exhaust stem c={centroid(src.stems['exhaust']):.0f} bands={band_shares(src.stems['exhaust'])}")
print(f"  mechanical  c={centroid(src.stems['mechanical']):.0f} bands={band_shares(src.stems['mechanical'])}")
print(f"  FULL source c={centroid(src.pressure):.0f} bands={band_shares(src.pressure)}")
valve = rms(src.stems["exhaust"])
# inspect mechanical mono dominant freq
mech_mono = src.stems["mechanical"].mean(axis=1)
spec = np.abs(np.fft.rfft(mech_mono * np.hanning(mech_mono.size)))
freqs = np.fft.rfftfreq(mech_mono.size, 1.0 / SR)
k = int(np.argmax(spec))
print(f"  mechanical peak freq={freqs[k]:.1f} Hz")
exh_mono = src.stems["exhaust"].mean(axis=1)
spec2 = np.abs(np.fft.rfft(exh_mono * np.hanning(exh_mono.size)))
k2 = int(np.argmax(spec2))
print(f"  exhaust peak freq={freqs[k2]:.1f} Hz")
