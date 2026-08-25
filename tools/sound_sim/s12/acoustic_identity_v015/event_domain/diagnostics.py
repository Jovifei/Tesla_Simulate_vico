"""Small source-domain and parent/candidate diagnostics."""
from __future__ import annotations
import numpy as np

def measure_audio(audio: np.ndarray, sample_rate_hz: int = 48000) -> dict[str, float | bool]:
    samples = np.asarray(audio, dtype=np.float64)
    if samples.ndim != 2 or samples.shape[1] != 2:
        raise ValueError("audio must be stereo")
    finite = bool(np.all(np.isfinite(samples)))
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(samples)))) if samples.size else 0.0
    mono = samples.mean(axis=1) if samples.size else np.zeros(1)
    spectrum = np.abs(np.fft.rfft(mono))
    frequencies = np.fft.rfftfreq(mono.size, 1.0 / sample_rate_hz)
    centroid = float(np.sum(frequencies * spectrum) / max(np.sum(spectrum), 1e-12))
    return {"finite": finite, "peak": peak, "rms": rms, "dc": float(np.mean(samples)), "clipping": int(np.sum(np.abs(samples) >= 1.0)), "spectral_centroid_hz": centroid, "duration_s": float(samples.shape[0] / sample_rate_hz)}

def compare_parent_candidate(parent: np.ndarray, candidate: np.ndarray, sample_rate_hz: int = 48000) -> dict[str, float]:
    p = np.asarray(parent, dtype=np.float64)
    c = np.asarray(candidate, dtype=np.float64)
    if p.shape != c.shape:
        raise ValueError("parent and candidate shapes differ")
    if np.array_equal(p, c):
        raise ValueError("identical parent and candidate")
    delta = c - p
    return {"difference_rms": float(np.sqrt(np.mean(np.square(delta)))), "parent_rms": float(np.sqrt(np.mean(np.square(p)))), "candidate_rms": float(np.sqrt(np.mean(np.square(c)))), "sample_count": float(p.shape[0])}
