"""Measure the fixed diagnostic; outputs are uncalibrated engineering evidence."""
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

import numpy as np
from scipy import signal


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def energy_db(power):
    return 10 * math.log10(max(float(power), np.finfo(float).tiny))


def measure(path, expected_hash, rpm):
    if digest(path) != expected_hash:
        raise ValueError(f"Hash mismatch: {path}")
    samples = np.fromfile(path, dtype="<f8")
    if len(samples) != 144000 or not np.isfinite(samples).all():
        raise ValueError(f"Invalid 3-second float64 signal: {path}")
    analysis = samples[48000:144000]
    frequencies, density = signal.welch(
        analysis, fs=48000, nperseg=48000, noverlap=24000, window="hann"
    )
    delta = frequencies[1] - frequencies[0]

    def power(mask):
        return float(np.sum(density[mask]) * delta)

    bands = {}
    for low, high in ((20, 80), (80, 250)):
        bands[f"{low}_{high}_hz_dbfs"] = energy_db(
            power((frequencies >= low) & (frequencies < high))
        )
    orders = {}
    for order in (2, 4, 8):
        center = order * rpm / 60
        orders[str(order)] = {
            "center_hz": center,
            "power_dbfs": energy_db(power(np.abs(frequencies - center) <= 1)),
        }
    region = (frequencies >= 20) & (frequencies < 1000)
    harmonic = np.zeros(frequencies.shape, dtype=bool)
    for index in range(1, int(1000 / (rpm / 120)) + 1):
        harmonic |= np.abs(frequencies - index * rpm / 120) <= 1
    harmonic_power = power(region & harmonic)
    residual_power = power(region & ~harmonic)
    return {
        "sample_count": len(samples),
        "measurement_window_s": [1, 3],
        "rms_dbfs": energy_db(np.mean(analysis * analysis)),
        "peak_dbfs": energy_db(np.max(np.abs(samples)) ** 2),
        "clip_count": int(np.count_nonzero(np.abs(samples) >= 1)),
        "bands": bands,
        "orders": orders,
        "order_to_residual_db": energy_db(harmonic_power) - energy_db(residual_power),
        "residual_definition": "20-1000 Hz excluding +/-1 Hz around half-order harmonics; includes leakage",
    }


def true_peak(path):
    process = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-filter_complex",
         "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    )
    matches = re.findall(r"(?m)^\s*Peak:\s*(-?[\d.]+)\s*dBFS\s*$", process.stderr)
    if not matches:
        raise ValueError(f"FFmpeg did not report true peak: {path}")
    return float(matches[-1])


def main(root):
    root = Path(root)
    receipt_path = root / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt["status"] != "SYNTHETIC_DIAGNOSTIC_SIMULINK_PASS":
        raise ValueError("Missing successful Simulink diagnostic")
    result = {
        "qualification": "SYNTHETIC_ENGINEERING_MEASUREMENTS_NOT_FORMAL_M2",
        "source_receipt_sha256": digest(receipt_path),
        "method": "Welch Hann 1 s, 50% overlap, unweighted; no EQ or loudness normalization",
        "true_peak_method": "FFmpeg ebur128 peak=true, 0.1 dB report precision",
        "conditions": [],
    }
    for condition in receipt["conditions"]:
        rpm = condition["rpm"]
        item = {"rpm": rpm, "load": condition["load"]}
        for name in ("source", "frozen", "combined"):
            item[name] = measure(Path(condition[f"{name}_path"]), condition[f"{name}_sha256"], rpm)
        wav = Path(condition["wav_path"])
        if digest(wav) != condition["wav_sha256"]:
            raise ValueError(f"WAV hash mismatch: {wav}")
        item["combined"]["true_peak_dbtp"] = true_peak(wav)
        item["combined"]["sample_headroom_db"] = -item["combined"]["peak_dbfs"]
        item["combined"]["true_peak_headroom_db"] = -item["combined"]["true_peak_dbtp"]
        result["conditions"].append(item)
    destination = root / "analysis.json"
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(f"SYNTHETIC_ANALYSIS_PASS {destination}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: analyze_synthetic_diagnostic.py ABSOLUTE_RUN_ROOT")
    main(sys.argv[1])
