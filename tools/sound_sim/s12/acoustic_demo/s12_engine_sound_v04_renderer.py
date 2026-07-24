"""Fixed-format renderer for v0.4 PTR/radiation output; no post-PTR sound design."""

from __future__ import annotations

import json
import math
from pathlib import Path
import struct
import wave

from s12_acoustic_audition import PressureTrace


def render_ptr_trace_wav(trace: PressureTrace, wav_path: Path, metadata_path: Path, sample_rate_hz: int, renderer_gain: float, fade_s: float) -> dict:
    if trace.sample_rate_hz != sample_rate_hz:
        raise ValueError("v0.4 renderer requires contracted PTR sample rate")
    mono = [sample - sum(trace.pressure_pa) / len(trace.pressure_pa) for sample in trace.pressure_pa]
    fade_frames = max(1, round(fade_s * trace.sample_rate_hz))
    for index in range(min(fade_frames, len(mono))):
        weight = index / max(1, fade_frames - 1)
        mono[index] *= weight
        mono[-1 - index] *= weight
    samples = [value * renderer_gain for value in mono]
    if any(abs(value) > 1.0 for value in samples):
        raise ValueError("v0.4 renderer refuses clipping; no limiter is applied")
    pcm = [round(value * 8388607) for value in samples]
    frames = b"".join(struct.pack("<i", value)[0:3] * 2 for value in pcm)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(wav_path), "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(3)
        audio.setframerate(trace.sample_rate_hz)
        audio.writeframes(frames)
    return {
        "architecture": "excitation_to_ptr_to_radiation",
        "calibrated": False,
        "clipping_count": 0,
        "dc": sum(samples) / len(samples),
        "peak": max(abs(value) for value in samples),
        "ptr_hash": trace.source_identity_sha256,
        "renderer": "fixed_gain_dc_remove_edge_fade_only",
        "rms": math.sqrt(sum(value * value for value in samples) / len(samples)),
        "sample_rate": trace.sample_rate_hz,
        "synthetic": True,
    }
