"""Fixed-format PCM frames and bounded simulated PC audio output."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
import struct
from typing import Sequence


BLOCK_SAMPLES = 960


@dataclass(frozen=True)
class PCMFrame:
    sequence_index: int
    sample_rate_hz: int
    channels: int
    bits_per_sample: int
    normalized_samples: tuple[float, ...]
    pcm_s24le_stereo: bytes
    fallback_applied: bool = False
    runtime_mode: str = "IDLE"
    transition_progress: float = 1.0


class RuntimePcmRenderer:
    """Apply only the documented fixed output gain and pack stereo signed-24 PCM."""

    def __init__(self, renderer_profile: dict) -> None:
        self.sample_rate_hz = int(renderer_profile["sample_rate_hz"])
        self.gain_db = float(renderer_profile["gain_db"])
        self._gain = 10.0 ** (self.gain_db / 20.0)
        if self.sample_rate_hz != 48000 or BLOCK_SAMPLES != self.sample_rate_hz // 50:
            raise ValueError("runtime PCM contract is exactly 960 samples at 48 kHz")

    def render(self, pressure_samples: Sequence[float], sequence_index: int) -> PCMFrame:
        if len(pressure_samples) != BLOCK_SAMPLES or not all(math.isfinite(sample) for sample in pressure_samples):
            raise ValueError("runtime renderer requires one finite 20 ms pressure block")
        normalized = tuple(float(sample) * self._gain for sample in pressure_samples)
        if any(abs(sample) > 1.0 for sample in normalized):
            raise ValueError("runtime renderer refuses clipping; no limiter is applied")
        payload = b"".join(struct.pack("<i", round(sample * 8388607))[0:3] * 2 for sample in normalized)
        return PCMFrame(sequence_index, self.sample_rate_hz, 2, 24, normalized, payload)


class PcmRingBuffer:
    """Bounded PCM queue that fails on producer overrun instead of discarding audio."""

    def __init__(self, capacity_frames: int) -> None:
        if capacity_frames <= 0:
            raise ValueError("PCM queue capacity must be positive")
        self._frames: deque[PCMFrame] = deque()
        self.capacity_frames = capacity_frames
        self.max_depth = 0

    @property
    def depth(self) -> int:
        return len(self._frames)

    def push(self, frame: PCMFrame) -> None:
        if self.depth >= self.capacity_frames:
            raise BufferError("PCM queue overrun; runtime did not discard a frame")
        self._frames.append(frame)
        self.max_depth = max(self.max_depth, self.depth)

    def pop(self) -> PCMFrame | None:
        return self._frames.popleft() if self._frames else None


class SimulatedPcmSink:
    """PC-simulation sink: consumes PCM frames without accessing an audio device."""

    def __init__(self, block_duration_s: float) -> None:
        if block_duration_s <= 0.0:
            raise ValueError("PCM block duration must be positive")
        self.block_duration_s = block_duration_s
        self.underrun_count = 0
        self.consumed_frames = 0
        self.max_latency_s = 0.0
        self._latency_sum_s = 0.0

    @property
    def mean_latency_s(self) -> float:
        return self._latency_sum_s / self.consumed_frames if self.consumed_frames else 0.0

    def consume(self, queue: PcmRingBuffer) -> PCMFrame | None:
        frame = queue.pop()
        if frame is None:
            self.underrun_count += 1
            return None
        latency_s = queue.depth * self.block_duration_s
        self.max_latency_s = max(self.max_latency_s, latency_s)
        self._latency_sum_s += latency_s
        self.consumed_frames += 1
        return frame
