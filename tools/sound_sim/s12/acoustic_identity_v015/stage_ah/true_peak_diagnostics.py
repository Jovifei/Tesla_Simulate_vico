"""Stage AI-4A: reconstructive true-peak diagnostics for blocked candidates.

This module does NOT change audio. It reproduces the existing 4x gate and adds
higher-rate convergence/local spectral evidence so a repair can be chosen from
measured behavior instead of by relaxing the gate or reducing gain blindly.

The estimates are engineering diagnostics, not an ITU/EBU certified meter.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy import signal
from scipy.io import wavfile

DEFAULT_SR = 48_000
UPSAMPLE_FACTORS = (2, 4, 8, 16)


def _pcm_float(values: np.ndarray) -> np.ndarray:
    a = np.asarray(values)
    if a.dtype == np.uint8:
        a = (a.astype(np.float64) - 128.0) / 128.0
    elif np.issubdtype(a.dtype, np.signedinteger):
        a = a.astype(np.float64) / float(-np.iinfo(a.dtype).min)
    elif np.issubdtype(a.dtype, np.floating):
        a = a.astype(np.float64)
    else:
        raise ValueError("unsupported PCM dtype")
    if a.ndim == 1:
        a = a[:, None]
    if a.ndim != 2 or a.shape[1] not in (1, 2) or len(a) < 64:
        raise ValueError("expected >=64 mono/stereo PCM frames")
    if not np.all(np.isfinite(a)):
        raise ValueError("non-finite PCM")
    if np.max(np.abs(a)) > 1.0 + 1e-7:
        raise ValueError("input PCM already exceeds digital full scale")
    return a


def _sha_pcm(values: np.ndarray) -> str:
    a = np.ascontiguousarray(_pcm_float(values), dtype="<f8")
    return hashlib.sha256(str(a.shape).encode() + a.tobytes()).hexdigest()


def _longest_run(mask: np.ndarray, factor: int, sr: int) -> dict[str, Any]:
    best = {"samples_upsampled": 0, "seconds": 0.0, "channel": None,
            "start_upsampled": None, "end_upsampled_exclusive": None,
            "start_time_s": None, "end_time_s": None}
    for ch in range(mask.shape[1]):
        idx = np.flatnonzero(mask[:, ch])
        if not len(idx):
            continue
        for run in np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1):
            start, end = int(run[0]), int(run[-1] + 1)
            if end - start > best["samples_upsampled"]:
                best = {"samples_upsampled": end-start,
                        "seconds": (end-start)/(sr*factor), "channel": ch,
                        "start_upsampled": start, "end_upsampled_exclusive": end,
                        "start_time_s": start/(sr*factor), "end_time_s": end/(sr*factor)}
    return best


def _local_spectrum(a: np.ndarray, center_sample: int, sr: int, *, window_s: float = .04) -> dict[str, Any]:
    half = max(32, int(round(window_s * sr / 2)))
    start, stop = max(0, center_sample-half), min(len(a), center_sample+half)
    x = a[start:stop]
    if len(x) < 64:
        raise ValueError("local spectrum window too short")
    x = x - np.mean(x, axis=0, keepdims=True)
    win = np.hanning(len(x))[:, None]
    spectrum = np.mean(np.abs(np.fft.rfft(x*win, axis=0))**2, axis=1)
    freq = np.fft.rfftfreq(len(x), 1/sr)
    usable = np.flatnonzero((freq >= 20) & (freq <= min(20_000, sr/2)))
    top = sorted(usable, key=lambda k: spectrum[k], reverse=True)[:8]
    total = max(float(np.sum(spectrum[usable])), 1e-30)
    centroid = float(np.sum(freq[usable]*spectrum[usable]) / np.sum(spectrum[usable]))
    return {"window_start_sample": start, "window_end_sample_exclusive": stop,
            "window_start_time_s": start/sr, "window_end_time_s": stop/sr,
            "bin_hz": float(sr/len(x)), "centroid_hz": centroid,
            "top_bins_hz": [float(freq[k]) for k in top],
            "top_bins_relative_power": [float(spectrum[k]/total) for k in top]}


def analyze_true_peak(values: np.ndarray, *, sample_rate: int = DEFAULT_SR,
                      threshold: float = 1.0) -> dict[str, Any]:
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, (int, np.integer)) or sample_rate < 8_000:
        raise ValueError("invalid sample rate")
    if not math.isfinite(float(threshold)) or not 0 < threshold <= 1.2:
        raise ValueError("invalid threshold")
    a = _pcm_float(values)
    saved = a.copy()
    sample_abs = np.abs(a)
    flat = int(np.argmax(sample_abs))
    sample_index, sample_channel = np.unravel_index(flat, sample_abs.shape)
    factors = {}
    worst = None
    for factor in UPSAMPLE_FACTORS:
        up = signal.resample_poly(a, factor, 1, axis=0, window=("kaiser", 5.0), padtype="line")
        absolute = np.abs(up)
        flat = int(np.argmax(absolute))
        index, channel = np.unravel_index(flat, absolute.shape)
        peak = float(absolute[index, channel])
        row = {"factor": factor, "peak": peak,
               "peak_dbfs": float(20*np.log10(max(peak, 1e-30))),
               "channel": int(channel), "upsampled_index": int(index),
               "time_s": float(index/(sample_rate*factor)),
               "exceedance_count": int(np.count_nonzero(absolute > threshold + 1e-12)),
               "longest_exceedance_run": _longest_run(absolute > threshold + 1e-12, factor, sample_rate)}
        factors[str(factor)] = row
        if worst is None or peak > worst["peak"]:
            worst = row
    center = min(len(a)-1, max(0, int(round(worst["time_s"]*sample_rate))))
    sample_peak = float(sample_abs[sample_index, sample_channel])
    report = {"schema": "s12.stage_ai.true_peak_diagnostic.v1",
              "sample_rate_hz": int(sample_rate), "frame_count": int(len(a)),
              "channels": int(a.shape[1]), "pcm_sha256": _sha_pcm(a),
              "sample_peak": sample_peak,
              "sample_peak_dbfs": float(20*np.log10(max(sample_peak, 1e-30))),
              "sample_peak_channel": int(sample_channel), "sample_peak_sample": int(sample_index),
              "sample_peak_time_s": float(sample_index/sample_rate),
              "threshold": float(threshold), "factors": factors,
              "worst_factor": int(worst["factor"]), "worst_peak": float(worst["peak"]),
              "worst_peak_dbfs": float(worst["peak_dbfs"]),
              "overshoot_over_sample_db": float(20*np.log10(max(worst["peak"],1e-30)/max(sample_peak,1e-30))),
              "local_spectrum": _local_spectrum(a, center, sample_rate),
              "classification": ("INTERSAMPLE_OVERSHOOT_BLOCKED" if sample_peak <= threshold and worst["peak"] > threshold
                                 else "SAMPLE_AND_INTERSAMPLE_BLOCKED" if sample_peak > threshold else "WITHIN_THRESHOLD"),
              "method": "scipy.signal.resample_poly factors 2/4/8/16; kaiser beta 5; line boundary",
              "standard": "ENGINEERING_DIAGNOSTIC_NOT_ITU_EBU_CERTIFIED",
              "audio_modified": False}
    if not np.array_equal(a, saved):
        raise AssertionError("diagnostic modified input")
    return report


def analyze_wav(path: Path, *, expected_sha256: str | None = None) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    file_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected_sha256 and file_sha.lower() != expected_sha256.lower():
        raise ValueError("WAV file SHA mismatch")
    sr, audio = wavfile.read(path)
    report = analyze_true_peak(audio, sample_rate=int(sr))
    report.update(wav_path=str(path), wav_sha256=file_sha)
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wav", type=Path, required=True)
    p.add_argument("--expected-sha256")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    result = analyze_wav(args.wav, expected_sha256=args.expected_sha256)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        f.write("\n")
    print(json.dumps({k: result[k] for k in ("classification", "sample_peak", "worst_peak", "worst_factor")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
