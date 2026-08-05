"""Probe supra idle: decompose the mechanical stem to find the high-band source."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_S12 = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_S12))

from acoustic_identity_v015.acoustic_analysis.reference_feature_extractor import BAND_EDGES
from acoustic_identity_v015.contracts import VehicleStateTrace
from acoustic_identity_v015.synth_primitives import combustion_impulse_train, mechanical_texture
from acoustic_identity_v015.render_realism_v10 import _scenario_trace

SR = 48000


def band_shares(audio, sr=SR):
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    win = np.hanning(mono.size)
    spec = np.abs(np.fft.rfft(mono * win))
    freqs = np.fft.rfftfreq(mono.size, 1.0 / sr)
    total = float(spec.sum()) or 1e-15
    return [float(spec[(freqs >= lo) & (freqs < hi)].sum()) / total for lo, hi in BAND_EDGES]


def peak_f(stem, sr=SR):
    mono = stem.mean(axis=1) if stem.ndim == 2 else stem
    spec = np.abs(np.fft.rfft(mono * np.hanning(mono.size)))
    freqs = np.fft.rfftfreq(mono.size, 1.0 / sr)
    k = int(np.argmax(spec))
    return float(freqs[k]), float(spec[k] / (spec.sum() or 1e-15))


trace = _scenario_trace("supra_jza80", "idle", 3.0)
ev = combustion_impulse_train(trace, SR, events_per_rev=3.0, pressure_exp=1.25, max_comp=2.0)
rpm, load = ev["rpm"], ev["load"]
phase = ev["phase"]

valvetrain_mono = 0.009 * (rpm > 0.0) * (0.4 + 0.6 * load) * np.sin(2.0 * np.pi * phase * 1.0)
texture = mechanical_texture(ev["count"], SR, 0.06, seed=4.4)
print("texture peak f", peak_f(texture))
print("texture bands", [round(b, 4) for b in band_shares(texture)])
print("valvetrain peak f", peak_f(valvetrain_mono))
print("valvetrain bands", [round(b, 4) for b in band_shares(valvetrain_mono)])
mech = 0.5 * valvetrain_mono + 0.003 * texture
mech_s = np.column_stack((mech, 0.5 * mech))
print("MECH combined bands", [round(b, 4) for b in band_shares(mech_s)], "peak f", peak_f(mech_s))
# phase-driven tone frequency
print("idle rpm mean", rpm.mean(), "-> engine order1 Hz =", rpm.mean()/60.0)
