"""Read-only feature summary for the public real-engine source pool."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np


POOL = Path(r"E:\Claude_allow\Download\vico-real-engine-source-pool-20261027")
OUT = Path("reports/real-engine-source-pool-20261027")


def decode(path: Path) -> tuple[np.ndarray, int]:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate,channels", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    stream = json.loads(probe.stdout)["streams"][0]
    source_rate = int(stream["sample_rate"])
    source_channels = int(stream["channels"])
    with tempfile.NamedTemporaryFile(suffix=".f32le", delete=False) as tmp:
        raw_path = Path(tmp.name)
    try:
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "48000", "-f", "f32le", "-y", str(raw_path)],
            check=True,
        )
        return np.fromfile(raw_path, dtype="<f4"), source_rate * 1000000 + source_channels
    finally:
        raw_path.unlink(missing_ok=True)


def features(samples: np.ndarray) -> dict[str, object]:
    rate = 48000
    finite = np.isfinite(samples)
    samples = samples[finite]
    windows = samples[: len(samples) // rate * rate].reshape(-1, rate)
    rms = np.sqrt(np.mean(np.square(samples, dtype=np.float64)))
    abs_samples = np.abs(samples)
    window_rms = np.sqrt(np.mean(np.square(windows, dtype=np.float64), axis=1)) if len(windows) else np.array([])
    crossing = np.count_nonzero(samples[1:] * samples[:-1] < 0) / max(len(samples) - 1, 1)
    centroid = []
    for window in windows[: min(len(windows), 16)]:
        spectrum = np.abs(np.fft.rfft(window * np.hanning(len(window))))
        freqs = np.fft.rfftfreq(len(window), 1 / rate)
        centroid.append(float(np.sum(freqs * spectrum) / max(np.sum(spectrum), 1e-12)))
    candidate_lags = []
    decimated = samples[::4]
    max_lag = min(len(decimated) // 2, 60000)
    for seconds in np.arange(0.25, 5.01, 0.25):
        lag = int(seconds * rate / 4)
        if lag <= 0 or lag >= max_lag:
            continue
        a = decimated[:-lag]
        b = decimated[lag:]
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        corr = float(np.dot(a, b) / denom) if denom else 0.0
        candidate_lags.append({"lagS": round(seconds, 2), "correlation": corr})
    best = max(candidate_lags, key=lambda row: row["correlation"]) if candidate_lags else None
    return {
        "decodedRate": rate,
        "decodedChannels": 1,
        "frames": int(len(samples)),
        "durationS": len(samples) / rate,
        "finite": bool(np.all(finite)),
        "rms": float(rms),
        "peak": float(np.max(abs_samples)) if len(samples) else 0.0,
        "windowRmsMin": float(np.min(window_rms)) if len(window_rms) else None,
        "windowRmsMax": float(np.max(window_rms)) if len(window_rms) else None,
        "windowRmsCv": float(np.std(window_rms) / max(np.mean(window_rms), 1e-12)) if len(window_rms) else None,
        "zeroCrossingRate": float(crossing),
        "spectralCentroidMedianHz": float(np.median(centroid)) if centroid else None,
        "spectralCentroidP10Hz": float(np.percentile(centroid, 10)) if centroid else None,
        "spectralCentroidP90Hz": float(np.percentile(centroid, 90)) if centroid else None,
        "candidateAutocorrelation": candidate_lags,
        "bestCandidate": best,
        "state": "UNKNOWN",
    }


def main() -> None:
    manifest = json.loads((POOL / "manifest.json").read_text(encoding="utf-8-sig"))
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in manifest:
        source = POOL / item["file"]
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != item["sha256"]:
            raise RuntimeError(f"source hash mismatch: {source.name}")
        samples, source_signature = decode(source)
        source_rate, source_channels = divmod(source_signature, 1000000)
        row = {"id": item["id"], "file": item["file"], "sourceSha256": digest,
               "sourceRate": source_rate, "sourceChannels": source_channels,
               "declaredDurationS": item["declaredDurationS"], "license": item["license"],
               "author": item["author"], **features(samples)}
        rows.append(row)
    result = {"schema": "vico.real-engine-pool.analysis.v1", "method":
              "ffmpeg mono 48 kHz F32LE; 1 s windows; no gain/time manipulation; decimated autocorrelation candidates",
              "sourceDirectory": str(POOL), "rows": rows}
    (OUT / "analysis.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = ["# Public real-engine pool: read-only feature analysis", "", result["method"], ""]
    lines.append("| ID | duration | RMS | peak | 1 s RMS CV | centroid median | best candidate lag | corr | state |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in rows:
        best = row["bestCandidate"] or {}
        lines.append(f"| `{row['id']}` | {row['durationS']:.2f} s | {row['rms']:.5f} | {row['peak']:.5f} | {row['windowRmsCv']:.3f} | {row['spectralCentroidMedianHz']:.1f} Hz | {best.get('lagS', 'n/a')} s | {best.get('correlation', 0):.4f} | `UNKNOWN` |")
    lines += ["", "Candidate autocorrelation is a texture diagnostic only; it is not RPM, engine order, or 720-degree phase evidence."]
    (OUT / "ANALYSIS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"files": len(rows), "output": str(OUT), "status": "PASS"}, indent=2))


if __name__ == "__main__":
    main()
