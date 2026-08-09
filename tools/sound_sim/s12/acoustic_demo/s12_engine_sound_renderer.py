"""Deterministic signed 24-bit stereo WAV renderer."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import wave

from s12_engine_sound_design import DesignedStereoTrace


@dataclass(frozen=True)
class EngineSoundRenderResult:
    wav_path: Path
    metadata_path: Path
    clipping_count: int
    dc: dict[str, float]
    max_adjacent_step: float


def _pcm24(sample: float) -> bytes:
    if not math.isfinite(sample) or not -1.0 <= sample <= 1.0:
        raise ValueError("24-bit PCM input must be finite and inside [-1, 1]")
    value = round(sample * 8388607)
    return value.to_bytes(3, byteorder="little", signed=True)


def _maximum_step(channels: tuple[list[float], list[float]]) -> float:
    maximum = 0.0
    for channel in channels:
        maximum = max(maximum, abs(channel[0]), abs(channel[-1]))
        maximum = max(
            maximum,
            max(
                (abs(current - previous) for previous, current in zip(channel, channel[1:])),
                default=0.0,
            ),
        )
    return maximum


def render_designed_wav(
    trace: DesignedStereoTrace,
    output_path: Path,
    metadata_path: Path,
) -> EngineSoundRenderResult:
    if trace.sample_rate_hz != 48000 or not trace.left or len(trace.left) != len(trace.right):
        raise ValueError("renderer requires matching nonempty 48 kHz stereo channels")
    channels = (trace.left, trace.right)
    dc = {
        "left": sum(trace.left) / len(trace.left),
        "right": sum(trace.right) / len(trace.right),
    }
    max_step = _maximum_step(channels)
    if max(abs(value) for value in dc.values()) > trace.max_dc_limit:
        raise ValueError("designed trace exceeds the DC acceptance threshold")
    if max_step > trace.max_adjacent_step_limit:
        raise ValueError("designed trace exceeds the discontinuity threshold")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    frames = b"".join(_pcm24(left) + _pcm24(right) for left, right in zip(trace.left, trace.right))
    with wave.open(str(output_path), "wb") as writer:
        writer.setnchannels(2)
        writer.setsampwidth(3)
        writer.setframerate(48000)
        writer.writeframes(frames)

    load_value: float | list[float]
    if trace.load_range[0] == trace.load_range[1]:
        load_value = trace.load_range[0]
    else:
        load_value = list(trace.load_range)
    metadata = {
        "channels": 2,
        "clipping_count": 0,
        "dc": dc,
        "fixed_output_gain": trace.fixed_output_gain,
        "generator_version": trace.generator_version,
        "labels": list(trace.labels),
        "load": load_value,
        "max_adjacent_step": max_step,
        "order_spectrum_rms": trace.order_spectrum_rms,
        "parameter_ledger_sha256": trace.parameter_ledger_sha256,
        "profile_sha256": trace.profile_sha256,
        "rpm_range": list(trace.rpm_range),
        "sample_rate_hz": trace.sample_rate_hz,
        "sample_width": 3,
        "source_hash": trace.source_hash,
        "source_component_rms": trace.source_component_rms,
        "synthetic": True,
        "transient_rms": trace.transient_rms,
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return EngineSoundRenderResult(output_path, metadata_path, 0, dc, max_step)
