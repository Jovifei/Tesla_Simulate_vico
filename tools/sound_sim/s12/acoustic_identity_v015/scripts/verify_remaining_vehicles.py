"""S12 Acoustic Realism - verify the 5 remaining vehicle models.

Renders idle/cruise/acceleration for each new vehicle through the same
idle -> afterfire -> low-frequency-body chain, measures the band energy
shares and spectral centroid, compares them to the real-recording
reference stock_median, and writes 24-bit audition WAVs plus a comparison
JSON.

Boundary: synthetic; uncalibrated; not OEM reproduction.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import wave

_S12 = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_S12))

from acoustic_identity_v015.acoustic_analysis.reference_feature_extractor import BAND_EDGES
from acoustic_identity_v015.acoustic_layers import apply_afterfire, apply_idle_dynamics, apply_low_frequency_body
from acoustic_identity_v015.contracts import VehicleStateTrace
from acoustic_identity_v015.render_realism_v10 import _render_stateful, _scenario_trace
from acoustic_identity_v015.sources.lamborghini_v12_source import render_aventador_lp700
from acoustic_identity_v015.sources.lexus_v10_source import render_lfa
from acoustic_identity_v015.sources.mercedes_v8_source import render_c63_w204
from acoustic_identity_v015.sources.nissan_v6_turbo_source import render_gtr_r35
from acoustic_identity_v015.sources.toyota_i6_turbo_source import render_supra_jza80
from acoustic_identity_v015.sources.flat_plane_v8_source import render_ferrari_458
from acoustic_identity_v015.sources.supercharged_hemi_source import render_hellcat
from acoustic_identity_v015.sources.rotary_turbo_source import render_rx7_fd

# All 8 vehicles verified through the same source-domain pressure chain.
NEW_VEHICLES = {
    "aventador_lp700": render_aventador_lp700,
    "c63_w204": render_c63_w204,
    "gtr_r35": render_gtr_r35,
    "lfa": render_lfa,
    "supra_jza80": render_supra_jza80,
    "ferrari_458": render_ferrari_458,
    "hellcat": render_hellcat,
    "rx7_fd": render_rx7_fd,
}
REF_DIR = Path(__file__).resolve().parent.parent / "reference_database"
OUT_DIR = Path(r"E:\Tesla_speed\tasks\reports\runtime\s12-remaining-vehicles-v1")
CLIPS = ("idle", "acceleration", "deceleration")
_SAMPLE_RATE_HZ = 48000


def _band_shares(audio: np.ndarray, sr: int) -> list[float]:
    """4-band energy fractions using the POWER spectrum (|FFT|^2).

    Must match ``reference_feature_extractor._mean_stft_energy`` which also
    uses the power spectrum, so distances-to-target stay consistent.
    """
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    n = mono.size
    win = np.hanning(n)
    spec = np.square(np.abs(np.fft.rfft(mono * win)))
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    total = float(spec.sum()) or 1e-15
    shares = []
    for lo, hi in BAND_EDGES:
        mask = (freqs >= lo) & (freqs < hi)
        shares.append(float(spec[mask].sum()) / total)
    return shares


def _centroid(audio: np.ndarray, sr: int) -> float:
    # Power spectrum (|FFT|^2) to stay consistent with the reference extractor.
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    spec = np.square(np.abs(np.fft.rfft(mono * np.hanning(mono.size))))
    freqs = np.fft.rfftfreq(mono.size, 1.0 / sr)
    total = float(spec.sum()) or 1e-15
    return float((freqs * spec).sum() / total)


# Acceptance gates (handover §4.2 — supersedes the old plan §6 0.03/5.0 gates):
#   accel per-band absolute error  <= 0.05
#   idle centroid absolute error   <= max(25 Hz, target * 10%)
# These are the automated coarse-metric gates. Identity separation and human
# audition (Stage D) are gated separately and are NOT asserted here.
_ACCEL_BAND_GATE = 0.05
_IDLE_CENTROID_FLOOR_HZ = 25.0
_IDLE_CENTROID_REL = 0.10


def _idle_threshold(target_hz: float) -> float:
    """§4.2 idle centroid gate: max(25 Hz, 10% of the target centroid)."""
    return max(_IDLE_CENTROID_FLOOR_HZ, target_hz * _IDLE_CENTROID_REL)


# Pre-tuning baseline distances (remaining_vehicles_report.json before this
# coarse-pass tuning campaign). Used to report improvement % per §4.2.
_BASELINE_DIST = {
    "aventador_lp700": {"accel_low": 0.0159, "accel_mid": 0.0079, "accel_high": 0.0394, "idle_centroid": 423.4},
    "c63_w204":        {"accel_low": 0.1034, "accel_mid": 0.2139, "accel_high": 0.115,  "idle_centroid": 111.7},
    "gtr_r35":         {"accel_low": 0.2704, "accel_mid": 0.1913, "accel_high": 0.0766, "idle_centroid": 306.8},
    "lfa":             {"accel_low": 0.0011, "accel_mid": 0.0255, "accel_high": 0.0235, "idle_centroid": 618.1},
    "supra_jza80":     {"accel_low": 0.2246, "accel_mid": 0.2106, "accel_high": 0.0161, "idle_centroid": 64.4},
    "ferrari_458":     {"accel_low": 0.1483, "accel_mid": 0.4824, "accel_high": 0.3381, "idle_centroid": 854.1},
    "hellcat":         {"accel_low": 0.4242, "accel_mid": 0.4105, "accel_high": 0.0031, "idle_centroid": 154.4},
    "rx7_fd":          {"accel_low": 0.5349, "accel_mid": 0.343,  "accel_high": 0.0589, "idle_centroid": 957.6},
}


def _write_wav(path: Path, signal: np.ndarray, sr: int) -> None:
    peak = float(np.max(np.abs(signal))) or 1.0
    normalized = signal / peak * 0.9
    stereo = np.column_stack([normalized, 0.79 * normalized])
    pcm = np.clip(stereo * (1 << 23), -(1 << 23), (1 << 23) - 1).astype("<i4")
    raw = np.empty((pcm.size, 3), dtype=np.uint8)
    byte_view = np.ascontiguousarray(pcm).view(np.uint8).reshape(pcm.size, 4)
    raw[:, 0] = byte_view[:, 0]
    raw[:, 1] = byte_view[:, 1]
    raw[:, 2] = byte_view[:, 2]
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(3)
        w.setframerate(sr)
        w.writeframes(raw.tobytes())


def _load_ref_shares(vehicle_id: str) -> dict:
    path = REF_DIR / f"{vehicle_id}_reference_targets.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    sm = data.get("stock_median", {})
    return {
        "accel_low": sm.get("acceleration_band_shares", [0, 0, 0, 0])[0],
        "accel_mid": sm.get("acceleration_band_shares", [0, 0, 0, 0])[1],
        "accel_high": sm.get("acceleration_band_shares", [0, 0, 0, 0])[2],
        "idle_centroid": sm.get("idle_spectral_centroid_hz", 0.0),
        "idle_low": sm.get("idle_band_shares", [0, 0, 0, 0])[0],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {}
    for vid, renderer in NEW_VEHICLES.items():
        print(f"\n=== {vid} ===")
        ref = _load_ref_shares(vid)
        vehicle_dir = OUT_DIR / vid
        vehicle_dir.mkdir(parents=True, exist_ok=True)
        per_clip = {}
        for clip in CLIPS:
            trace = _scenario_trace(vid, clip, 3.0)
            render = _render_stateful(renderer, vid, trace)
            audio = render.pressure
            shares = _band_shares(audio, _SAMPLE_RATE_HZ)
            centroid = _centroid(audio, _SAMPLE_RATE_HZ)
            _write_wav(vehicle_dir / f"{clip}.wav", audio, _SAMPLE_RATE_HZ)
            per_clip[clip] = {"band_shares": [round(b, 4) for b in shares], "centroid_hz": round(centroid, 1)}
            print(f"  {clip:12s} bands={[round(b,3) for b in shares]} centroid={centroid:.0f}Hz")
        # distance to reference (accel low/mid/high + idle centroid)
        accel = per_clip.get("acceleration", {}).get("band_shares", [0, 0, 0, 0])
        idle_c = per_clip.get("idle", {}).get("centroid_hz", 0.0)
        dist = {
            "accel_low": round(abs(accel[0] - ref.get("accel_low", 0.0)), 4),
            "accel_mid": round(abs(accel[1] - ref.get("accel_mid", 0.0)), 4),
            "accel_high": round(abs(accel[2] - ref.get("accel_high", 0.0)), 4),
            "idle_centroid": round(abs(idle_c - ref.get("idle_centroid", 0.0)), 1),
        }
        idle_threshold = _idle_threshold(ref.get("idle_centroid", 0.0))
        acceptance = {
            "accel_low": bool(dist["accel_low"] <= _ACCEL_BAND_GATE),
            "accel_mid": bool(dist["accel_mid"] <= _ACCEL_BAND_GATE),
            "accel_high": bool(dist["accel_high"] <= _ACCEL_BAND_GATE),
            "idle_centroid": bool(dist["idle_centroid"] <= idle_threshold),
        }
        # §4.2 improvement vs pre-tuning baseline: 1 - current/baseline.
        base = _BASELINE_DIST.get(vid, {})
        improvement = {
            k: (round(1.0 - dist[k] / base[k], 4) if base.get(k) else None)
            for k in ("accel_low", "accel_mid", "accel_high", "idle_centroid")
        }
        report[vid] = {
            "clips": per_clip,
            "reference": ref,
            "distance_to_reference": dist,
            "baseline_distance": base,
            "improvement_vs_baseline": improvement,
            "acceptance_thresholds": {
                "accel_low": _ACCEL_BAND_GATE,
                "accel_mid": _ACCEL_BAND_GATE,
                "accel_high": _ACCEL_BAND_GATE,
                "idle_centroid": idle_threshold,
            },
            "acceptance_pass": acceptance,
        }
        # Canonical per-vehicle verify JSON (kept in sync with the unified report).
        doc_path = Path(__file__).resolve().parent.parent / "docs" / f"{vid}_verify.json"
        # newline="\n": on Windows the default would translate to CRLF, which makes
        # `git diff --check` flag every line as trailing whitespace and trips the
        # Track-P assertion (see docs/S12_TrackP_Baseline_v3.md).
        doc_path.write_text(
            json.dumps(report[vid], indent=2, ensure_ascii=False),
            encoding="utf-8",
            newline="\n",
        )
        print(f"  ref accel low/mid/high = {ref.get('accel_low'):.3f}/{ref.get('accel_mid'):.3f}/{ref.get('accel_high'):.3f}")
        print(f"  distance: {dist}")
        print(f"  improvement vs baseline: {improvement}")
        print(f"  acceptance (idle gate {idle_threshold:.1f}Hz, accel gate {_ACCEL_BAND_GATE}): "
              f"{'PASS' if all(acceptance.values()) else 'FAIL'} {acceptance}")
    (OUT_DIR / "remaining_vehicles_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n"
    )
    print(f"\nreport -> {OUT_DIR / 'remaining_vehicles_report.json'}")


if __name__ == "__main__":
    main()
