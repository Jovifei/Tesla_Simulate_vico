"""Render PTR/radiation pressure traces without post-PTR sound design.

DC removal, endpoint crossfade, and fixed gain are output-format operations
only. This layer must not add orders, EQ, limiter behavior, or synthesis.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import struct
import wave

from s12_acoustic_audition import PressureTrace


RENDERER_VERSION = "S12 Product Renderer v0.1"


def renderer_profile_from_library(library) -> dict:
    profile = library.raw["renderer_profile"]
    return {
        "sample_rate_hz": int(profile["sample_rate_hz"]["value"]),
        "gain_db": float(profile["gain_db"]["value"]),
        "edge_fade_s": float(profile["edge_fade_s"]["value"]),
    }


def _edge_crossfade(samples: list[float], frame_count: int) -> list[float]:
    result = list(samples)
    for index in range(min(frame_count, len(result))):
        weight = index / max(1, frame_count - 1)
        result[index] *= weight
        result[-1 - index] *= weight
    return result


def _linear_resample(samples: list[float], source_rate_hz: int, target_rate_hz: int) -> list[float]:
    if source_rate_hz <= 0 or target_rate_hz <= 0 or not samples:
        raise ValueError("resampling requires non-empty positive-rate audio")
    if source_rate_hz == target_rate_hz:
        return list(samples)
    frame_count = max(1, round(len(samples) * target_rate_hz / source_rate_hz))
    output = []
    for frame in range(frame_count):
        position = frame * source_rate_hz / target_rate_hz
        lower = min(len(samples) - 1, int(position))
        upper = min(len(samples) - 1, lower + 1)
        fraction = position - lower
        output.append(samples[lower] + (samples[upper] - samples[lower]) * fraction)
    return output


def render_product_wav(
    trace: PressureTrace, wav_path: Path, metadata_path: Path, renderer_profile: dict
) -> dict:
    """Write fixed-format stereo PCM from existing PTR/radiation pressure only."""
    sample_rate_hz = int(renderer_profile["sample_rate_hz"])
    if trace.sample_rate_hz is None:
        raise ValueError("renderer requires a uniform source trace")
    gain_db = float(renderer_profile["gain_db"])
    gain = 10.0 ** (gain_db / 20.0)
    resampled = _linear_resample(trace.pressure_pa, trace.sample_rate_hz, sample_rate_hz)
    dc_free = [sample - sum(resampled) / len(resampled) for sample in resampled]
    samples = _edge_crossfade(
        dc_free, round(float(renderer_profile["edge_fade_s"]) * sample_rate_hz)
    )
    samples = [sample * gain for sample in samples]
    if any(abs(sample) > 1.0 for sample in samples):
        raise ValueError("renderer refuses clipping; no limiter is applied")
    pcm = [round(sample * 8388607) for sample in samples]
    frames = b"".join(struct.pack("<i", sample)[0:3] * 2 for sample in pcm)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(wav_path), "wb") as writer:
        writer.setnchannels(2)
        writer.setsampwidth(3)
        writer.setframerate(sample_rate_hz)
        writer.writeframes(frames)
    metadata = {
        "clipping_count": 0,
        "gain_db": gain_db,
        "peak": max(abs(sample) for sample in samples),
        "post_ptr_processing_contract": "output_format_only_no_order_eq_limiter_or_synthesis",
        "processing": ["linear_resampling", "dc_removal", "edge_crossfade", "fixed_gain"],
        "renderer_version": RENDERER_VERSION,
        "rms": math.sqrt(sum(sample * sample for sample in samples) / len(samples)),
        "resampled_from_hz": trace.sample_rate_hz,
        "sample_rate": sample_rate_hz,
        "source_hash": trace.source_identity_sha256,
        "synthetic": True,
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return metadata
