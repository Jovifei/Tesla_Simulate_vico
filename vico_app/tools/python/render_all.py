#!/usr/bin/env python3
"""
render_all.py - 批量渲染所有车型预览 WAV (0->redline 扫频, 3s)
用法: python render_all.py
输出: ref_wav/<key>.wav
"""

import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vico_vehicle_synth import load_profile, render, write_wav

VEHICLES = [
    "v8_crossplane",
    "v8_flatplane",
    "v10",
    "v12",
    "v6",
    "inline4",
    "inline6",
    "boxer4",
    "vtwin",
    "diesel_i6",
    "ev_motor",
    "classic_muscle_v8",
    "classic_british_i6",
    "classic_italian_v12",
    "classic_flat6",
    "classic_rotary",
    "classic_hirev_i4",
    "classic_truck_v8",
]

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BASE = os.path.join(ROOT, "Project", "android", "app", "src", "main", "assets", "vehicles")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ref_wav")
SR = 44100
DUR = 3.0

print(f"=== rendering {len(VEHICLES)} vehicles ===")
for k, key in enumerate(VEHICLES):
    path = os.path.join(BASE, key + ".json")
    try:
        p = load_profile(path)
        N = int(DUR * SR)
        rpm_seq = [p["idleRpm"] + (p["redlineRpm"] - p["idleRpm"]) * i / (N - 1) for i in range(N)]
        samples = render(p, rpm_seq, throttle=0.5, accel=0.5, brake=False, sample_rate=SR)
        out = os.path.join(OUT, key + ".wav")
        write_wav(out, samples, SR)
        peak = max(abs(s) for s in samples) if samples else 0
        print(f"[{k + 1:2d}/{len(VEHICLES)}] OK   {key:22s} peak={peak:5d}  [{p['name']}]")
    except Exception as e:
        print(f"[{k + 1:2d}/{len(VEHICLES)}] FAIL {key:22s} {e}")
print(f"=== done. WAVs in {OUT} ===")
