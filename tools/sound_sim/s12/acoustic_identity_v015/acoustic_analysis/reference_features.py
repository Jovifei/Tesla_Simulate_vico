"""Relative STFT and transient extraction for externally held R2 recordings."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import wave

import numpy as np


def analyze_reference_wav(
    audio_path: str | Path, segments: Mapping[str, tuple[float, float]], frame_size: int = 4096, hop_size: int = 1024
) -> dict[str, object]:
    """Return recording-dependent features, never an OEM acoustic calibration."""
    path = Path(audio_path)
    sample_rate_hz, audio = _read_pcm_wav(path)
    result: dict[str, object] = {"analysis_domain": "relative_recording_features_only", "sample_rate_hz": sample_rate_hz, "stft": {"window": "hann", "frame_size": frame_size, "hop_size": hop_size}, "segments": {}}
    for name, (start_s, end_s) in segments.items():
        if not 0.0 <= start_s < end_s <= audio.size / sample_rate_hz:
            raise ValueError(f"invalid segment {name!r}")
        start = int(round(start_s * sample_rate_hz))
        end = int(round(end_s * sample_rate_hz))
        segment = audio[start:end]
        frequencies, energy = _mean_stft_energy(segment, sample_rate_hz, frame_size, hop_size)
        total = float(energy.sum())
        frame_rms = _frame_rms(segment, max(sample_rate_hz // 100, 1))
        threshold = float(np.median(frame_rms) + 2.5 * np.std(frame_rms))
        result["segments"][name] = {
            "duration_s": float((end - start) / sample_rate_hz),
            "rms_dbfs": _dbfs(float(np.sqrt(np.mean(np.square(segment))))),
            "spectral_centroid_hz": float(np.sum(frequencies * energy) / total) if total else 0.0,
            "band_energy_fraction": {"40_200hz": _band_fraction(energy, frequencies, 40.0, 200.0), "200_500hz": _band_fraction(energy, frequencies, 200.0, 500.0), "gt_1200hz": _band_fraction(energy, frequencies, 1200.0, None)},
            "transient_event_count": int(np.count_nonzero((frame_rms[1:] > threshold) & (frame_rms[:-1] <= threshold))),
        }
    return result


def _read_pcm_wav(path: Path) -> tuple[int, np.ndarray]:
    with wave.open(str(path), "rb") as stream:
        channels = stream.getnchannels()
        width = stream.getsampwidth()
        sample_rate_hz = stream.getframerate()
        raw = stream.readframes(stream.getnframes())
    if channels < 1 or width not in {1, 2, 3, 4}:
        raise ValueError("only 8/16/24/32-bit PCM WAV is supported")
    if width == 1:
        values = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    elif width == 2:
        values = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    elif width == 3:
        packed = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        values = (packed[:, 0].astype(np.int32) | (packed[:, 1].astype(np.int32) << 8) | (packed[:, 2].astype(np.int32) << 16))
        values = np.where(values & (1 << 23), values - (1 << 24), values).astype(np.float64) / (1 << 23)
    else:
        values = np.frombuffer(raw, dtype="<i4").astype(np.float64) / (1 << 31)
    return sample_rate_hz, values.reshape(-1, channels).mean(axis=1)


def _mean_stft_energy(audio: np.ndarray, sample_rate_hz: int, frame_size: int, hop_size: int) -> tuple[np.ndarray, np.ndarray]:
    size = min(frame_size, audio.size)
    if size < 64:
        raise ValueError("segment is too short for STFT")
    starts = np.arange(0, audio.size - size + 1, max(hop_size, 1), dtype=int)
    if starts.size == 0:
        starts = np.array([0])
    window = np.hanning(size)
    energy = np.mean([np.square(np.abs(np.fft.rfft(audio[start:start + size] * window))) for start in starts], axis=0)
    return np.fft.rfftfreq(size, 1.0 / sample_rate_hz), energy


def _frame_rms(audio: np.ndarray, frame_size: int) -> np.ndarray:
    return np.array([np.sqrt(np.mean(np.square(audio[index:index + frame_size]))) for index in range(0, audio.size - frame_size + 1, frame_size)])


def _band_fraction(energy: np.ndarray, frequencies: np.ndarray, low_hz: float, high_hz: float | None) -> float:
    mask = frequencies >= low_hz
    if high_hz is not None:
        mask &= frequencies <= high_hz
    total = float(energy.sum())
    return float(energy[mask].sum() / total) if total else 0.0


def _dbfs(value: float) -> float:
    return float(20.0 * np.log10(max(value, 1e-15)))
