"""S12 Phase 3 - verify low-frequency body v2 retuning against real targets.

Renders a 3-second acceleration scene per vehicle through the full stateful
chain (source -> idle -> afterfire -> low_frequency_body v2), measures the
20-250Hz / 250-1kHz / centroid / crest, and compares against the Phase 1
real-recording acceleration stock_median to confirm the retuning moved
Ferrari and RX-7 away from excessive low-frequency weight.
"""

from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np

_S12 = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_S12))

from acoustic_identity_v015.sources.flat_plane_v8_source import render_ferrari_458
from acoustic_identity_v015.sources.supercharged_hemi_source import render_hellcat
from acoustic_identity_v015.sources.rotary_turbo_source import render_rx7_fd
from acoustic_identity_v015.acoustic_layers import apply_idle_dynamics, apply_afterfire, apply_low_frequency_body
from acoustic_identity_v015.contracts import VehicleStateTrace

SR = 48000
DURATION_S = 3.0
N = int(SR * DURATION_S)
OUT = Path(r"E:\Tesla_speed\tasks\reports\runtime\s12-low-frequency-body-v1")
OUT.mkdir(parents=True, exist_ok=True)

RENDERERS = {"ferrari_458": render_ferrari_458, "hellcat": render_hellcat, "rx7_fd": render_rx7_fd}

# Phase 1 real-recording acceleration stock_median
REAL_TARGETS = {
    "ferrari_458": {"bands": [0.356, 0.569, 0.068, 0.004], "centroid": 421.0, "crest": 6.10},
    "hellcat": {"bands": [0.484, 0.488, 0.003, 0.000], "centroid": 265.0, "crest": 3.52},
    "rx7_fd": {"bands": [0.936, 0.062, 0.002, 0.000], "centroid": 170.0, "crest": 3.87},
}
BAND_EDGES = [(20.0, 250.0), (250.0, 1000.0), (1000.0, 4000.0), (4000.0, 12000.0)]


def make_accel_trace() -> VehicleStateTrace:
    t = np.arange(N) / SR
    progress = t / DURATION_S
    return VehicleStateTrace(
        time_s=t,
        rpm=3000.0 + 4000.0 * progress,
        load=0.40 + 0.50 * progress,
        throttle=0.50 + 0.50 * progress,
        acceleration_mps2=np.full(N, 2.5),
    )


def render_stateful(renderer, vehicle_id: str, trace: VehicleStateTrace) -> object:
    source = renderer(trace)
    idle = apply_idle_dynamics(source, vehicle_id, trace, SR)
    afterfire = apply_afterfire(idle, vehicle_id, trace, SR)
    return apply_low_frequency_body(afterfire, vehicle_id, trace, SR)


def measure(signal: np.ndarray, sr: int) -> dict:
    rms = float(np.sqrt(np.mean(np.square(signal))) or 1e-15)
    crest = float(np.max(np.abs(signal)) / rms)
    window = np.hanning(N)
    spectrum = np.square(np.abs(np.fft.rfft(signal * window)))
    freqs = np.fft.rfftfreq(N, 1.0 / sr)
    total = float(spectrum.sum()) or 1e-15
    centroid = float(np.sum(freqs * spectrum) / total)
    bands = [float(spectrum[(freqs >= lo) & (freqs <= hi)].sum() / total) for lo, hi in BAND_EDGES]
    return {"crest_factor": crest, "spectral_centroid_hz": centroid, "band_shares": bands, "rms_dbfs": float(20.0 * np.log10(max(rms, 1e-15)))}


def write_wav(path: Path, signal: np.ndarray, sr: int) -> None:
    peak = float(np.max(np.abs(signal))) or 1.0
    normalized = signal / peak * 0.9
    stereo = np.column_stack([normalized, 0.79 * normalized])
    pcm = np.clip(stereo * (1 << 23), -(1 << 23), (1 << 23) - 1).astype("<i4")
    flat = pcm.reshape(-1)
    raw = np.ascontiguousarray(flat.view(np.uint8).reshape(-1, 4)[:, :3]).tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(3)
        w.setframerate(sr)
        w.writeframes(raw)


def main() -> None:
    trace = make_accel_trace()
    results = {}
    print("=== S12 Phase 3 low-frequency body v2 verification (acceleration) ===\n")
    print(f"{'vehicle':12s} {'20-250':>7s} {'250-1k':>7s} {'1-4k':>7s} {'centroid':>9s} {'crest':>6s} | real_20-250 real_centroid")
    for vid, renderer in RENDERERS.items():
        render = render_stateful(renderer, vid, trace)
        signal = render.pressure.mean(axis=1)
        m = measure(signal, SR)
        rt = REAL_TARGETS[vid]
        results[vid] = {"measured": m, "real_target": rt, "diagnostics": {k: v for k, v in render.diagnostics.items() if k.startswith(("pressure_", "low_frequency_"))}}
        write_wav(OUT / f"{vid}_accel_v2.wav", signal, SR)
        print(f"{vid:12s} {m['band_shares'][0]:7.3f} {m['band_shares'][1]:7.3f} {m['band_shares'][2]:7.3f} {m['spectral_centroid_hz']:9.0f}Hz {m['crest_factor']:6.2f} | {rt['bands'][0]:7.3f} {rt['centroid']:7.0f}Hz")

    print("\n=== direction checks ===")
    lf = {v: results[v]["measured"]["band_shares"][0] for v in results}
    cent = {v: results[v]["measured"]["spectral_centroid_hz"] for v in results}
    print(f"low-freq(20-250): Hellcat {lf['hellcat']:.3f} vs Ferrari {lf['ferrari_458']:.3f} vs RX-7 {lf['rx7_fd']:.3f}")
    print(f"  hellcat>ferrari: {lf['hellcat'] > lf['ferrari_458']}  hellcat>rx7: {lf['hellcat'] > lf['rx7_fd']}")
    print(f"centroid: Ferrari {cent['ferrari_458']:.0f} > Hellcat {cent['hellcat']:.0f} > RX-7 {cent['rx7_fd']:.0f}")
    print(f"  ferrari>hellcat: {cent['ferrari_458'] > cent['hellcat']}  hellcat>rx7: {cent['hellcat'] > cent['rx7_fd']}")

    report = {"phase": "S12_low_frequency_body_v2", "scope": "synthetic; uncalibrated; not OEM reproduction", "scene": "acceleration_3s", "vehicles": results}
    (OUT / "low_frequency_v2_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nreport -> {OUT / 'low_frequency_v2_report.json'}")
    print(f"WAVs -> {OUT}/*.wav")


if __name__ == "__main__":
    main()
