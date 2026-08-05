"""S12 Phase 2 - verify idle realism direction and publish idle audition bundle.

Generates a 3-second idle scene for each vehicle, applies the upgraded idle_dynamics
v2 layer, measures the resulting crest factor / spectral centroid / band shares /
modulation peak, and compares them against the Phase 1 real-recording idle targets
to confirm the identity direction is preserved.

Also writes 48 kHz / 24-bit stereo idle WAVs for human audition.
"""

from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np

_S12 = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_S12))

from acoustic_identity_v015.contracts import SourceRender, VehicleStateTrace
from acoustic_identity_v015.acoustic_layers.idle_dynamics import apply_idle_dynamics

SR = 48000
DURATION_S = 3.0
N = int(SR * DURATION_S)
OUT = Path(r"E:\Tesla_speed\tasks\reports\runtime\s12-idle-realism-v1")
OUT.mkdir(parents=True, exist_ok=True)

# Phase 1 real-recording idle stock_median targets (for direction comparison)
REAL_TARGETS = {
    "ferrari_458": {"crest": 10.41, "centroid_hz": 980.0, "bands": [0.009, 0.521, 0.467, 0.002], "mod_peak_hz": 5.0},
    "hellcat": {"crest": 15.91, "centroid_hz": 290.0, "bands": [0.698, 0.258, 0.04, 0.003], "mod_peak_hz": 5.0},
    "rx7_fd": {"crest": 2.78, "centroid_hz": 156.0, "bands": [0.968, 0.032, 0.0, 0.0], "mod_peak_hz": 60.0},
}
BAND_EDGES = [(20.0, 250.0), (250.0, 1000.0), (1000.0, 4000.0), (4000.0, 12000.0)]


def make_idle_trace() -> VehicleStateTrace:
    t = np.arange(N) / SR
    return VehicleStateTrace(
        time_s=t,
        rpm=np.full(N, 850.0),
        load=np.full(N, 0.10),
        throttle=np.full(N, 0.05),
        acceleration_mps2=np.zeros(N),
    )


def make_empty_render() -> SourceRender:
    pressure = np.zeros((N, 2), dtype=np.float64)
    return SourceRender(pressure=pressure, stems={"base": pressure.copy()}, diagnostics={})


def measure(signal: np.ndarray, sr: int) -> dict:
    rms = float(np.sqrt(np.mean(np.square(signal))) or 1e-15)
    crest = float(np.max(np.abs(signal)) / rms)
    window = np.hanning(N)
    spectrum = np.square(np.abs(np.fft.rfft(signal * window)))
    freqs = np.fft.rfftfreq(N, 1.0 / sr)
    total = float(spectrum.sum()) or 1e-15
    centroid = float(np.sum(freqs * spectrum) / total)
    bands = [float(spectrum[(freqs >= lo) & (freqs <= hi)].sum() / total) for lo, hi in BAND_EDGES]
    env = np.abs(signal)
    env = env - np.mean(env)
    env_spec = np.abs(np.fft.rfft(env))
    env_freqs = np.fft.rfftfreq(env.size, 1.0 / sr)
    mask = (env_freqs >= 5.0) & (env_freqs <= 500.0)
    mod_peak = float(env_freqs[mask][np.argmax(env_spec[mask])]) if np.any(mask) else 0.0
    return {"crest_factor": crest, "spectral_centroid_hz": centroid, "band_shares": bands, "modulation_peak_hz": mod_peak, "rms_dbfs": float(20.0 * np.log10(max(rms, 1e-15)))}


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
    trace = make_idle_trace()
    results = {}
    print("=== S12 Phase 2 idle realism verification ===\n")
    print(f"{'vehicle':12s} {'crest':>7s} {'centroid':>9s} {'mod_peak':>9s} {'20-250':>7s} {'1-4k':>7s} | real_crest real_centroid")
    for vid in ["ferrari_458", "hellcat", "rx7_fd"]:
        render = make_empty_render()
        result = apply_idle_dynamics(render, vid, trace, SR)
        idle_signal = result.pressure.mean(axis=1)
        m = measure(idle_signal, SR)
        rt = REAL_TARGETS[vid]
        results[vid] = {"measured": m, "real_target": rt, "diagnostics": {k: v for k, v in result.diagnostics.items() if k.startswith("idle_")}}
        wav_path = OUT / f"{vid}_idle_v2.wav"
        write_wav(wav_path, idle_signal, SR)
        print(f"{vid:12s} {m['crest_factor']:7.2f} {m['spectral_centroid_hz']:9.0f}Hz {m['modulation_peak_hz']:8.0f}Hz {m['band_shares'][0]:7.3f} {m['band_shares'][2]:7.3f} | {rt['crest']:7.2f} {rt['centroid_hz']:7.0f}Hz")
    # direction checks
    crests = {v: results[v]["measured"]["crest_factor"] for v in results}
    centroids = {v: results[v]["measured"]["spectral_centroid_hz"] for v in results}
    print("\n=== direction checks (synthetic vs real target order) ===")
    print(f"crest order:  Hellcat {crests['hellcat']:.2f} > Ferrari {crests['ferrari_458']:.2f} > RX-7 {crests['rx7_fd']:.2f}")
    print(f"  real order: Hellcat 15.91 > Ferrari 10.41 > RX-7 2.78")
    print(f"  hellcat>ferrari: {crests['hellcat'] > crests['ferrari_458']}  ferrari>rx7: {crests['ferrari_458'] > crests['rx7_fd']}")
    print(f"centroid order: Ferrari {centroids['ferrari_458']:.0f} > Hellcat {centroids['hellcat']:.0f} > RX-7 {centroids['rx7_fd']:.0f}")
    print(f"  real order: Ferrari 980 > Hellcat 290 > RX-7 156")
    print(f"  ferrari>hellcat: {centroids['ferrari_458'] > centroids['hellcat']}  hellcat>rx7: {centroids['hellcat'] > centroids['rx7_fd']}")
    report = {"phase": "S12_idle_realism_v2", "scope": "synthetic; uncalibrated; not OEM reproduction", "sample_rate_hz": SR, "duration_s": DURATION_S, "vehicles": results,
              "direction_checks": {"crest_hellcat_gt_ferrari": crests["hellcat"] > crests["ferrari_458"], "crest_ferrari_gt_rx7": crests["ferrari_458"] > crests["rx7_fd"],
                                   "centroid_ferrari_gt_hellcat": centroids["ferrari_458"] > centroids["hellcat"], "centroid_hellcat_gt_rx7": centroids["hellcat"] > centroids["rx7_fd"]}}
    (OUT / "idle_realism_v2_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nreport -> {OUT / 'idle_realism_v2_report.json'}")
    print(f"WAVs -> {OUT}/*.wav")


if __name__ == "__main__":
    main()
