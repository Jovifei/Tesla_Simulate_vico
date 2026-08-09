"""S12 Phase 3 - publish low-frequency audition bundle (idle/cruise/acceleration).

Generates a 3-scene audition WAV per vehicle through the full stateful chain
(source -> idle -> afterfire -> low_frequency_body v2), measures low-frequency
metrics, and computes the distance to the Phase 1 real-recording acceleration
targets.
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
REAL_TARGETS = {
    "ferrari_458": {"bands": [0.356, 0.569, 0.068, 0.004], "centroid": 421.0},
    "hellcat": {"bands": [0.484, 0.488, 0.003, 0.000], "centroid": 265.0},
    "rx7_fd": {"bands": [0.936, 0.062, 0.002, 0.000], "centroid": 170.0},
}
BAND_EDGES = [(20.0, 250.0), (250.0, 1000.0), (1000.0, 4000.0), (4000.0, 12000.0)]
SCENES = {
    "idle": lambda t: (np.full(N, 850.0), np.full(N, 0.10), np.full(N, 0.05)),
    "cruise": lambda t: (np.full(N, 2500.0), np.full(N, 0.40), np.full(N, 0.40)),
    "acceleration": lambda t: (3000.0 + 4000.0 * t, 0.40 + 0.50 * t, 0.50 + 0.50 * t),
}


def make_trace(scene: str) -> VehicleStateTrace:
    t = np.arange(N) / SR
    progress = t / DURATION_S
    rpm, load, throttle = SCENES[scene](progress)
    return VehicleStateTrace(time_s=t, rpm=rpm, load=load, throttle=throttle, acceleration_mps2=np.full(N, 2.5))


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
    return {"crest_factor": crest, "spectral_centroid_hz": centroid, "band_shares": bands}


def distance_to_target(measured: dict, real: dict) -> float:
    band_dist = sum(abs(m - r) for m, r in zip(measured["band_shares"], real["bands"]))
    centroid_dist = abs(measured["spectral_centroid_hz"] - real["centroid"]) / max(real["centroid"], 1.0)
    return float(band_dist + centroid_dist)


def write_wav(path: Path, signal: np.ndarray, sr: int) -> None:
    peak = float(np.max(np.abs(signal))) or 1.0
    normalized = signal / peak * 0.9
    stereo = np.column_stack([normalized, 0.79 * normalized])
    pcm = np.clip(stereo * (1 << 23), -(1 << 23), (1 << 23) - 1).astype("<i4")
    raw = np.ascontiguousarray(pcm.reshape(-1).view(np.uint8).reshape(-1, 4)[:, :3]).tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(3)
        w.setframerate(sr)
        w.writeframes(raw)


def main() -> None:
    results = {}
    print("=== S12 Phase 3 low-frequency audition bundle ===\n")
    for vid, renderer in RENDERERS.items():
        results[vid] = {"scenes": {}}
        for scene in ("idle", "cruise", "acceleration"):
            trace = make_trace(scene)
            render = render_stateful(renderer, vid, trace)
            signal = render.pressure.mean(axis=1)
            m = measure(signal, SR)
            write_wav(OUT / f"{vid}_{scene}_v2.wav", signal, SR)
            results[vid]["scenes"][scene] = m
            print(f"{vid:12s} {scene:12s} 20-250={m['band_shares'][0]:.3f} 1-4k={m['band_shares'][2]:.3f} centroid={m['spectral_centroid_hz']:.0f}Hz crest={m['crest_factor']:.2f}")
        accel = results[vid]["scenes"]["acceleration"]
        results[vid]["accel_distance_to_real"] = distance_to_target(accel, REAL_TARGETS[vid])
        print(f"  -> acceleration distance to real target: {results[vid]['accel_distance_to_real']:.3f}\n")

    print("=== direction summary (acceleration) ===")
    lf = {v: results[v]["scenes"]["acceleration"]["band_shares"][0] for v in results}
    cent = {v: results[v]["scenes"]["acceleration"]["spectral_centroid_hz"] for v in results}
    print(f"low-freq:  Hellcat {lf['hellcat']:.3f} > Ferrari {lf['ferrari_458']:.3f} > RX-7 {lf['rx7_fd']:.3f}")
    print(f"centroid:  RX-7 {cent['rx7_fd']:.0f} > Ferrari {cent['ferrari_458']:.0f} > Hellcat {cent['hellcat']:.0f}Hz")

    report = {"phase": "S12_low_frequency_body_v2_audition", "scope": "synthetic; uncalibrated; not OEM reproduction", "sample_rate_hz": SR, "duration_s": DURATION_S, "real_targets": REAL_TARGETS, "vehicles": results}
    (OUT / "low_frequency_audition_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nreport -> {OUT / 'low_frequency_audition_report.json'}")


if __name__ == "__main__":
    main()
