"""Idle-centroid optimizer for LFA and GT-R.

idle_dynamics is idle-gated (zero at accel), so sweeping it does NOT touch
accel bands. We monkeypatch idle_dynamics._PROFILES, render the real source at
idle, apply idle_dynamics, and minimize |idle_centroid - target|.

Boundary: synthetic; uncalibrated; not OEM reproduction.
"""

import sys
from pathlib import Path

import numpy as np

_S12 = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_S12))

from acoustic_identity_v015.acoustic_analysis.reference_feature_extractor import BAND_EDGES
from acoustic_identity_v015.acoustic_layers import apply_idle_dynamics, idle_dynamics
from acoustic_identity_v015.render_realism_v10 import _scenario_trace
from acoustic_identity_v015.sources.lexus_v10_source import render_lfa
from acoustic_identity_v015.sources.nissan_v6_turbo_source import render_gtr_r35

SR = 48000

TARGETS = {"lfa": 1365.65, "gtr_r35": 399.87}

RENDERERS = {"lfa": render_lfa, "gtr_r35": render_gtr_r35}

BASE = {
    "lfa": {"events_per_rev": 5.0, "seed": 2.2, "variation": 0.12, "jitter_ms": 0.30, "combustion_gain": 0.120, "combustion_decay_s": 0.028, "accessory_order": 1.2, "valve_hz": 2900.0, "valvetrain_gain": 0.0, "accessory_gain": 0.001, "crank_order": 1.5, "mechanical_texture": 0.02, "idle_crest_target": 7.34, "idle_modulation_peak_hz": 8.0},
    "gtr_r35": {"events_per_rev": 3.0, "seed": 8.8, "variation": 0.20, "jitter_ms": 2.0, "combustion_gain": 0.025, "combustion_decay_s": 0.022, "accessory_order": 1.8, "valve_hz": 440.0, "valvetrain_gain": 0.0, "crank_order": 1.2, "mechanical_texture": 0.005, "idle_crest_target": 7.72, "idle_modulation_peak_hz": 5.0},
}


def _centroid(audio):
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    spec = np.abs(np.fft.rfft(mono * np.hanning(mono.size)))
    freqs = np.fft.rfftfreq(mono.size, 1.0 / SR)
    total = float(spec.sum()) or 1e-15
    return float((freqs * spec).sum() / total)


def main():
    for vid in ("lfa", "gtr_r35"):
        print(f"\n===== {vid} (target {TARGETS[vid]}) =====")
        target = TARGETS[vid]
        best = None
        printed = 0
        for valve_hz in (200.0, 400.0, 800.0, 1400.0, 2000.0, 2900.0):
            for cg in (0.04, 0.08, 0.12, 0.18):
                for cd in (0.010, 0.018, 0.028, 0.045):
                    for mt in (0.005, 0.02, 0.06):
                        prof = dict(BASE[vid])
                        prof["valve_hz"] = valve_hz
                        prof["combustion_gain"] = cg
                        prof["combustion_decay_s"] = cd
                        prof["mechanical_texture"] = mt
                        idle_dynamics._PROFILES[vid] = prof
                        trace = _scenario_trace(vid, "idle", 3.0)
                        src = RENDERERS[vid](trace)
                        out = apply_idle_dynamics(src, vid, trace, SR)
                        c = _centroid(out.pressure)
                        dist = abs(c - target)
                        if best is None or dist < best[1]:
                            best = (prof.copy(), dist, c)
                        if dist < 40 and printed < 8:
                            print(f"  dist={dist:.1f} centroid={c:.0f} vh={valve_hz} cg={cg} cd={cd} mt={mt}")
                            printed += 1
        print(f"  BEST: dist={best[1]:.1f} centroid={best[2]:.0f}")
        print(f"    vh={best[0]['valve_hz']} cg={best[0]['combustion_gain']} cd={best[0]['combustion_decay_s']} mt={best[0]['mechanical_texture']}")


if __name__ == "__main__":
    main()
