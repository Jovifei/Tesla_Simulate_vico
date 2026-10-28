"""Prepare fixed 20 ms research texture frames for the v1.2 Simulink candidate."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path


SAMPLE_RATE = 48_000
FRAME_SAMPLES = 960
CROSSFADE_SAMPLES = round(0.12 * SAMPLE_RATE)


def read_f32le(path: Path) -> tuple[list[float], str]:
    data = path.read_bytes()
    if len(data) % 4:
        raise ValueError("F32LE source byte length must be divisible by four")
    values = list(struct.unpack(f"<{len(data) // 4}f", data))
    if not values or any(not (-1.0 <= value <= 1.0) for value in values):
        raise ValueError("texture source must be finite and bounded")
    return values, hashlib.sha256(data).hexdigest()


def _loop_sample(values: list[float], position: int, crossfade_samples: int) -> float:
    if crossfade_samples < 2 or len(values) <= crossfade_samples * 2:
        return values[position % len(values)]
    period = len(values) - crossfade_samples
    cursor = position % period
    if cursor < period - crossfade_samples:
        return values[cursor + crossfade_samples]
    blend_index = cursor - (period - crossfade_samples)
    tail = values[period + blend_index]
    head = values[blend_index]
    alpha = (blend_index + 1) / crossfade_samples
    return (1.0 - alpha) * tail + alpha * head


def frame_at(values: list[float], frame_index: int, crossfade_samples: int = CROSSFADE_SAMPLES) -> list[float]:
    if frame_index < 0:
        raise ValueError("frame_index must be non-negative")
    if len(values) < FRAME_SAMPLES:
        raise ValueError("texture source is shorter than one fixed frame")
    start = frame_index * FRAME_SAMPLES
    return [_loop_sample(values, start + offset, crossfade_samples) for offset in range(FRAME_SAMPLES)]


def source_receipt(path: Path, frame_count: int) -> dict:
    values, digest = read_f32le(path)
    if frame_count <= 0:
        raise ValueError("frame_count must be positive")
    return {
        "schema": "s12.v12.texture-frame-source.v1",
        "source": str(path),
        "source_sha256": digest,
        "sample_rate_hz": SAMPLE_RATE,
        "frame_samples": FRAME_SAMPLES,
        "frame_period_s": FRAME_SAMPLES / SAMPLE_RATE,
        "crossfade_samples": CROSSFADE_SAMPLES,
        "frame_count": frame_count,
        "source_frames": len(values),
        "state": "UNKNOWN",
        "purpose": "RESEARCH_ONLY_NOT_PRODUCT_AUDIO",
        "rpm_load_gear_phase": "UNKNOWN",
    }
