"""Independent PCM24, continuity, bands, coherent differences and loudness checks."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import integrate, signal

LAB = Path(__file__).resolve().parent
FS = 48000
BANDS = ((20, 80), (80, 250), (250, 500), (500, 1000), (1000, 2000), (2000, 5000))


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def read_pcm(path):
    flat = np.fromfile(path, dtype="<f8")
    if not flat.size or flat.size % 2:
        raise ValueError("PCM must contain nonempty interleaved stereo doubles")
    data = flat.reshape(-1, 2)
    if not np.isfinite(data).all() or not np.any(data) or np.max(np.abs(data)) > 1:
        raise ValueError("PCM finite/nonempty/peak gate failed")
    return data


def inspect_pair(pcm_path, wav_path):
    pcm = read_pcm(pcm_path)
    info = sf.info(wav_path)
    wav, fs = sf.read(wav_path, always_2d=True, dtype="float64")
    if fs != FS or info.subtype != "PCM_24" or wav.shape != pcm.shape:
        raise ValueError("PCM24 WAV format or shape differs")
    error = float(np.max(np.abs(wav - pcm)))
    if error > 2**-23 + np.finfo(float).eps:
        raise ValueError("PCM24 WAV does not decode to the saved PCM")
    jumps = np.abs(np.diff(pcm, axis=0))
    sample_jump = float(jumps.max(initial=0))
    frame_jump = float(jumps[959::960].max(initial=0))
    if sample_jump > 0.25 or frame_jump > 0.0269080675:
        raise ValueError("PCM continuity gate failed")
    return {"samples_per_channel": len(pcm), "pcm24_max_error": error,
            "sample_jump": sample_jump, "frame_jump": frame_jump,
            "peak": float(np.max(np.abs(pcm))), "pcm_sha256": digest(pcm_path),
            "wav_sha256": digest(wav_path)}


def band_powers(samples):
    samples = np.asarray(samples, dtype=np.float64)
    if samples.ndim == 1:
        samples = samples[:, None]
    f, psd = signal.welch(samples, fs=FS, nperseg=min(FS, len(samples)),
                          noverlap=min(FS, len(samples)) // 2, axis=0)
    mean_psd = np.mean(psd, axis=1)
    return {f"{lo}-{hi}": float(integrate.trapezoid(mean_psd[(f >= lo) & (f < hi)], f[(f >= lo) & (f < hi)]))
            for lo, hi in BANDS}


def cross_term(left, right):
    return float(2 * np.mean(np.asarray(left) * np.asarray(right)))


def measure_loudness(path, log_path):
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-i", str(path),
               "-filter_complex", "ebur128=peak=true", "-f", "null", "-"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    with Path(log_path).open("x", encoding="utf-8") as output:
        output.write(result.stdout + result.stderr)
    if result.returncode:
        raise ValueError(f"FFmpeg loudness measurement failed; see {log_path}")
    loudness = re.findall(r"\bI:\s*(-?(?:\d+(?:\.\d+)?|inf))\s+LUFS", result.stderr)
    peaks = re.findall(r"\bPeak:\s*(-?(?:\d+(?:\.\d+)?|inf))\s+dBFS", result.stderr)
    if not loudness or not peaks:
        raise ValueError(f"FFmpeg did not report loudness and true peak; see {log_path}")
    return {"lufs": float(loudness[-1]), "true_peak_dbtp": float(peaks[-1])}


def run(root):
    root = Path(root).resolve()
    if not root.is_relative_to(LAB.resolve()) or not (root / "full.json").is_file():
        raise ValueError("run root must contain this candidate's successful full.json")
    full = json.loads((root / "full.json").read_text(encoding="utf-8"))
    if full["status"] != "FULL_PASS_COLD_AND_AUDITION_NOT_RUN":
        raise ValueError("full run is not in the expected completed-render state")
    output = root / "independent-analysis"
    output.mkdir(exist_ok=False)
    metrics = {"qualification": "DIGITAL_ONLY_HUMAN_AND_DEVICE_NOT_ACCEPTED", "cases": {},
               "cold": "NOT_RUN" if not (root / "cold.json").exists() else "SEE_COLD_RECEIPT"}
    receipts = sorted(root.glob("*/receipt.json"))
    for index, receipt in enumerate(receipts, 1):
        case = receipt.parent.name
        print(f"ANALYZE [{index}/{len(receipts)}] {case}", flush=True)
        expected = json.loads(receipt.read_text(encoding="utf-8"))
        pcm_path, wav_path = receipt.parent / "candidate.pcm.f64le", receipt.parent / "candidate.wav"
        item = inspect_pair(pcm_path, wav_path)
        if item["pcm_sha256"] != expected["pcm_sha256"] or item["wav_sha256"] != expected["wav_sha256"]:
            raise ValueError(f"{case}: receipt SHA differs")
        data = read_pcm(pcm_path)
        item["bands_mean_square"] = band_powers(data)
        item["loudness"] = measure_loudness(wav_path, output / f"{case}.ffmpeg.log")
        metrics["cases"][case] = item
    tracks = {name: read_pcm(root / name / "candidate.pcm.f64le") for name in ("N", "M", "D", "MD")}
    if len({x.shape for x in tracks.values()}) != 1:
        raise ValueError("comparison tracks have different lengths")
    metrics["contrasts"] = {}
    for left, right in (("M", "N"), ("D", "N"), ("MD", "D"), ("MD", "M")):
        difference = tracks[left] - tracks[right]
        metrics["contrasts"][f"{left}-{right}"] = {"rms": float(np.sqrt(np.mean(difference**2))),
                                                       "bands_mean_square": band_powers(difference)}
    mechanical, bank = tracks["M"] - tracks["N"], tracks["D"] - tracks["N"]
    interaction = tracks["MD"] - tracks["M"] - tracks["D"] + tracks["N"]
    metrics["cross_term_mn_dn"] = cross_term(mechanical, bank)
    metrics["interaction_rms"] = float(np.sqrt(np.mean(interaction**2)))
    metrics["order_envelope_decay"] = "NOT_ANALYZED_REQUIRES_PHASE_AND_PATH_CAPTURE"
    with (output / "analysis.json").open("x", encoding="utf-8") as target:
        json.dump(metrics, target, ensure_ascii=False, indent=2, allow_nan=False)
    return output / "analysis.json"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", type=Path)
    print(run(parser.parse_args().run_root))
