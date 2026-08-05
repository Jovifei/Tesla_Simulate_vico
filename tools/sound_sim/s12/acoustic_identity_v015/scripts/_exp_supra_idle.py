"""Idle-centroid optimizer for Supra JZA80.

idle_dynamics is idle-gated (zero at accel), so sweeping it does NOT touch
accel bands (already good: [0.710, 0.247, 0.025]). We monkeypatch
idle_dynamics._PROFILES, render the FULL pipeline at idle, and minimize a
cost = |idle_centroid - 117.63| + 2.0*max(0, 0.90 - low_band) so we land
both deep (centroid ~118) and low-dominant (low >= ~0.90).

Boundary: synthetic; uncalibrated; not OEM reproduction.
"""
import sys
from pathlib import Path

import numpy as np

_S12 = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_S12))

from acoustic_identity_v015.acoustic_analysis.reference_feature_extractor import BAND_EDGES
from acoustic_identity_v015.acoustic_layers import idle_dynamics
from acoustic_identity_v015.render_realism_v10 import _render_stateful, _scenario_trace
from acoustic_identity_v015.sources.toyota_i6_turbo_source import render_supra_jza80

SR = 48000
TARGET_C = 117.63
TARGET_LOW = 0.975

BASE = {
    "supra_jza80": {"events_per_rev": 3.0, "seed": 4.4, "variation": 0.28, "jitter_ms": 3.5, "combustion_gain": 0.020, "combustion_decay_s": 0.014, "accessory_order": 1.5, "valve_hz": 150.0, "valvetrain_gain": 0.001, "accessory_gain": 0.001, "crank_order": 0.5, "mechanical_texture": 0.01, "idle_crest_target": 7.11, "idle_modulation_peak_hz": 5.0},
}


def _band_low(audio):
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    spec = np.abs(np.fft.rfft(mono * np.hanning(mono.size)))
    freqs = np.fft.rfftfreq(mono.size, 1.0 / SR)
    total = float(spec.sum()) or 1e-15
    lo, hi = BAND_EDGES[0]
    return float(spec[(freqs >= lo) & (freqs < hi)].sum()) / total


def _centroid(audio):
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    spec = np.abs(np.fft.rfft(mono * np.hanning(mono.size)))
    freqs = np.fft.rfftfreq(mono.size, 1.0 / SR)
    total = float(spec.sum()) or 1e-15
    return float((freqs * spec).sum() / total)


def main():
    vid = "supra_jza80"
    target_c = TARGET_C
    best = None
    printed = 0
    for valve_hz in (60.0, 100.0, 150.0, 250.0, 400.0):
        for cg in (0.005, 0.015, 0.030, 0.050, 0.080, 0.120):
            for cd in (0.010, 0.025, 0.045):
                for mt in (0.0, 0.005):
                    for ag in (0.0, 0.001, 0.003):
                        for vg in (0.0, 0.001):
                            prof = dict(BASE[vid])
                            prof["valve_hz"] = valve_hz
                            prof["combustion_gain"] = cg
                            prof["combustion_decay_s"] = cd
                            prof["mechanical_texture"] = mt
                            prof["accessory_gain"] = ag
                            prof["valvetrain_gain"] = vg
                            idle_dynamics._PROFILES[vid] = prof
                            trace = _scenario_trace(vid, "idle", 3.0)
                            out = _render_stateful(render_supra_jza80, vid, trace)
                            c = _centroid(out.pressure)
                            low = _band_low(out.pressure)
                            cost = abs(c - target_c) + 1.5 * max(0.0, 0.95 - low)
                            if best is None or cost < best[0]:
                                best = (cost, prof.copy(), c, low)
                            if cost < 50 and printed < 10:
                                print(f"  cost={cost:.1f} c={c:.0f} low={low:.3f} vh={valve_hz} cg={cg} cd={cd} mt={mt} ag={ag} vg={vg}")
                                printed += 1
    print(f"\nBEST: cost={best[0]:.1f} centroid={best[2]:.0f} low={best[3]:.3f}")
    p = best[1]
    print(f"  valve_hz={p['valve_hz']} cg={p['combustion_gain']} cd={p['combustion_decay_s']} mt={p['mechanical_texture']} ag={p['accessory_gain']}")


if __name__ == "__main__":
    main()
