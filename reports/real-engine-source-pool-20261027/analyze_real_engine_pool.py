"""Read-only feature analysis for the public vehicle recording pool."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np


POOL = Path(r"E:\Claude_allow\Download\vico-real-engine-source-pool-20261027")
OUT = Path(__file__).resolve().parent
TARGET_RATE = 48_000
WINDOW_S = 1.0
ENVELOPE_WINDOW_S = 0.1


def probe(path: Path) -> dict:
    command = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration,size:stream=codec_name,sample_rate,channels",
        "-of", "json", str(path),
    ]
    return json.loads(subprocess.check_output(command, text=True))


def decode_mono(path: Path) -> np.ndarray:
    command = [
        "ffmpeg", "-v", "error", "-i", str(path), "-ac", "1",
        "-ar", str(TARGET_RATE), "-f", "f32le", "-y",
    ]
    with tempfile.NamedTemporaryFile(suffix=".f32le", delete=False) as handle:
        temp = Path(handle.name)
    try:
        subprocess.run(command + [str(temp)], check=True)
        return np.fromfile(temp, dtype="<f4")
    finally:
        temp.unlink(missing_ok=True)


def windows(samples: np.ndarray, size: int) -> np.ndarray:
    count = len(samples) // size
    if count == 0:
        return np.empty((0, size), dtype=np.float32)
    return samples[: count * size].reshape(count, size)


def spectral_centroids(blocks: np.ndarray) -> np.ndarray:
    if not len(blocks):
        return np.empty(0)
    window = np.hanning(blocks.shape[1])
    spectrum = np.abs(np.fft.rfft(blocks * window, axis=1))
    frequencies = np.fft.rfftfreq(blocks.shape[1], 1 / TARGET_RATE)
    return (spectrum * frequencies).sum(axis=1) / np.maximum(spectrum.sum(axis=1), 1e-12)


def envelope_modulation(envelope: np.ndarray) -> dict:
    if len(envelope) < 16:
        return {"peakHz": None, "peakMagnitude": None, "bandHz": [0.5, 5.0]}
    centered = envelope - envelope.mean()
    spectrum = np.abs(np.fft.rfft(centered * np.hanning(len(centered))))
    frequencies = np.fft.rfftfreq(len(centered), ENVELOPE_WINDOW_S)
    band = (frequencies >= 0.5) & (frequencies <= 5.0)
    if not band.any():
        return {"peakHz": None, "peakMagnitude": None, "bandHz": [0.5, 5.0]}
    indices = np.flatnonzero(band)
    index = indices[np.argmax(spectrum[band])]
    return {"peakHz": float(frequencies[index]), "peakMagnitude": float(spectrum[index]), "bandHz": [0.5, 5.0]}


def autocorrelation_candidates(envelope: np.ndarray) -> list[dict]:
    if len(envelope) < 32:
        return []
    centered = envelope - envelope.mean()
    denominator = float(np.dot(centered, centered))
    if denominator <= 1e-18:
        return []
    correlations = np.correlate(centered, centered, mode="full")[len(centered) - 1:] / denominator
    min_lag = max(1, round(0.1 / ENVELOPE_WINDOW_S))
    max_lag = min(len(correlations) - 1, round(10.0 / ENVELOPE_WINDOW_S))
    candidates = []
    for lag in range(min_lag + 1, max_lag):
        if correlations[lag] >= correlations[lag - 1] and correlations[lag] >= correlations[lag + 1]:
            candidates.append({"lagS": lag * ENVELOPE_WINDOW_S, "correlation": float(correlations[lag])})
    return sorted(candidates, key=lambda item: item["correlation"], reverse=True)[:5]


def analyze(path: Path) -> dict:
    metadata = probe(path)
    samples = decode_mono(path)
    one_second = windows(samples, TARGET_RATE)
    envelope_blocks = windows(samples, round(TARGET_RATE * ENVELOPE_WINDOW_S))
    envelope = np.sqrt(np.mean(envelope_blocks.astype(np.float64) ** 2, axis=1)) if len(envelope_blocks) else np.empty(0)
    centroids = spectral_centroids(one_second)
    return {
        "file": path.name,
        "sourceSha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
        "ffprobe": metadata,
        "analysisDecode": {"sampleRate": TARGET_RATE, "channels": 1, "frames": int(len(samples)), "durationS": float(len(samples) / TARGET_RATE)},
        "global": {"rms": float(np.sqrt(np.mean(samples.astype(np.float64) ** 2))), "peak": float(np.max(np.abs(samples)))},
        "oneSecondWindows": {
            "count": int(len(one_second)),
            "rmsMin": float(np.min(np.sqrt(np.mean(one_second.astype(np.float64) ** 2, axis=1)))) if len(one_second) else None,
            "rmsMedian": float(np.median(np.sqrt(np.mean(one_second.astype(np.float64) ** 2, axis=1)))) if len(one_second) else None,
            "rmsMax": float(np.max(np.sqrt(np.mean(one_second.astype(np.float64) ** 2, axis=1)))) if len(one_second) else None,
            "spectralCentroidMedianHz": float(np.median(centroids)) if len(centroids) else None,
            "spectralCentroidP10Hz": float(np.percentile(centroids, 10)) if len(centroids) else None,
            "spectralCentroidP90Hz": float(np.percentile(centroids, 90)) if len(centroids) else None,
        },
        "envelope100ms": {
            "count": int(len(envelope)),
            "rmsMin": float(np.min(envelope)) if len(envelope) else None,
            "rmsMedian": float(np.median(envelope)) if len(envelope) else None,
            "rmsMax": float(np.max(envelope)) if len(envelope) else None,
            "modulation": envelope_modulation(envelope),
            "autocorrelationCandidates": autocorrelation_candidates(envelope),
        },
        "qualification": {"rpm": "UNKNOWN", "load": "UNKNOWN", "gear": "UNKNOWN", "phase720": "UNKNOWN", "holdout": "NOT_AVAILABLE", "status": "RESEARCH_ONLY"},
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [analyze(path) for path in sorted(POOL.glob("*.ogg"))]
    receipt = {"schema": "vico.real-engine-pool.analysis.v1", "method": "ffmpeg mono 48 kHz; 1 s spectral windows; 100 ms energy envelope; no gain or time manipulation", "rows": rows}
    (OUT / "analysis.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
