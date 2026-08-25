"""Bounded audition-only gain; never mutates analysis raw audio."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class MonitorRender:
    audio: np.ndarray
    gain_trace_db: np.ndarray
    max_gain_db: float
    max_attenuation_db: float
    peak_ceiling_dbfs: float

def render_audition_monitor(raw_audio: np.ndarray, sample_rate_hz: int = 48000, target_rms: float = 0.08, attack_s: float = 0.12, release_s: float = 1.20, max_makeup_db: float = 9.0, max_attenuation_db: float = -12.0, peak_ceiling_dbfs: float = -1.2) -> MonitorRender:
    raw = np.asarray(raw_audio, dtype=np.float64)
    if raw.ndim != 2 or raw.shape[1] != 2 or not np.all(np.isfinite(raw)) or np.any(np.abs(raw) >= 1.0):
        raise ValueError("raw_audio must be finite stereo")
    if sample_rate_hz <= 0 or target_rms <= 0.0 or attack_s <= 0.0 or release_s <= 0.0 or max_attenuation_db > 0.0 or max_makeup_db < 0.0 or not (-1.5 <= peak_ceiling_dbfs <= -1.0):
        raise ValueError("invalid bounded monitor parameters")
    frame = max(1, int(round(0.10 * sample_rate_hz)))
    frame_count = int(np.ceil(raw.shape[0] / frame))
    desired = np.empty(frame_count, dtype=np.float64)
    for i in range(frame_count):
        chunk = raw[i * frame:(i + 1) * frame]
        rms = float(np.sqrt(np.mean(np.square(chunk)))) if chunk.size else 0.0
        desired[i] = np.clip(20.0 * np.log10(target_rms / max(rms, 1e-9)), max_attenuation_db, max_makeup_db)
    smoothed = np.empty(frame_count, dtype=np.float64)
    current = float(desired[0])
    frame_s = frame / sample_rate_hz
    for i, target in enumerate(desired):
        time_constant = attack_s if target > current else release_s
        alpha = 1.0 - np.exp(-frame_s / time_constant)
        current += alpha * (target - current)
        smoothed[i] = np.clip(current, max_attenuation_db, max_makeup_db)
    trace = np.interp(np.arange(raw.shape[0]), np.arange(frame_count) * frame, smoothed)
    audio = raw * np.power(10.0, trace[:, None] / 20.0)
    ceiling = 10.0 ** (peak_ceiling_dbfs / 20.0)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > ceiling:
        peak_gain = 20.0 * np.log10(ceiling / peak)
        trace = np.maximum(trace + peak_gain, max_attenuation_db)
        audio = raw * np.power(10.0, trace[:, None] / 20.0)
    return MonitorRender(audio, trace, float(np.max(trace)) if trace.size else 0.0, float(np.min(trace)) if trace.size else 0.0, peak_ceiling_dbfs)
