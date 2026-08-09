"""Fixed-format PCM frames and bounded simulated PC audio output."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import math
import os
import struct
import time
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


class _WaveFormatEx(ctypes.Structure):
    _fields_ = [
        ("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD),
        ("nSamplesPerSec", wintypes.DWORD), ("nAvgBytesPerSec", wintypes.DWORD),
        ("nBlockAlign", wintypes.WORD), ("wBitsPerSample", wintypes.WORD),
        ("cbSize", wintypes.WORD),
    ]


class _WaveHeader(ctypes.Structure):
    _fields_ = [
        ("lpData", ctypes.c_char_p), ("dwBufferLength", wintypes.DWORD),
        ("dwBytesRecorded", wintypes.DWORD), ("dwUser", ctypes.c_size_t),
        ("dwFlags", wintypes.DWORD), ("dwLoops", wintypes.DWORD),
        ("lpNext", ctypes.c_void_p), ("reserved", ctypes.c_size_t),
    ]


class WindowsWaveOutSink:
    """Optional Windows default-device sink for queued signed-24 PCM frames."""

    WAVE_MAPPER = 0xFFFFFFFF
    WHDR_DONE = 0x00000001

    @staticmethod
    def is_supported() -> bool:
        try:
            ctypes.WinDLL("winmm")
            return os.name == "nt"
        except (AttributeError, OSError):
            return False

    def __init__(self, max_pending_frames: int = 3) -> None:
        if not self.is_supported() or max_pending_frames <= 0:
            raise RuntimeError("Windows waveOut audio output is unavailable")
        self.max_pending_frames = max_pending_frames
        self._winmm = ctypes.WinDLL("winmm")
        self._handle = ctypes.c_void_p()
        self._pending: list[tuple[ctypes.Array, _WaveHeader]] = []
        format_ex = _WaveFormatEx(1, 2, 48000, 48000 * 2 * 3, 2 * 3, 24, 0)
        result = self._winmm.waveOutOpen(ctypes.byref(self._handle), self.WAVE_MAPPER, ctypes.byref(format_ex), 0, 0, 0)
        if result != 0:
            raise OSError(f"waveOutOpen failed with MMRESULT={result}")

    @property
    def pending_frames(self) -> int:
        self._reap_completed()
        return len(self._pending)

    def _reap_completed(self) -> None:
        remaining = []
        for buffer, header in self._pending:
            if header.dwFlags & self.WHDR_DONE:
                self._winmm.waveOutUnprepareHeader(self._handle, ctypes.byref(header), ctypes.sizeof(header))
            else:
                remaining.append((buffer, header))
        self._pending = remaining

    def wait_for_capacity(self) -> None:
        while self.pending_frames >= self.max_pending_frames:
            time.sleep(0.001)

    def submit(self, frame: PCMFrame) -> None:
        if (frame.sample_rate_hz, frame.channels, frame.bits_per_sample) != (48000, 2, 24):
            raise ValueError("waveOut sink accepts only the runtime PCM contract")
        self.wait_for_capacity()
        buffer = ctypes.create_string_buffer(frame.pcm_s24le_stereo)
        header = _WaveHeader(ctypes.cast(buffer, ctypes.c_char_p), len(frame.pcm_s24le_stereo), 0, 0, 0, 0, None, 0)
        result = self._winmm.waveOutPrepareHeader(self._handle, ctypes.byref(header), ctypes.sizeof(header))
        if result != 0:
            raise OSError(f"waveOutPrepareHeader failed with MMRESULT={result}")
        result = self._winmm.waveOutWrite(self._handle, ctypes.byref(header), ctypes.sizeof(header))
        if result != 0:
            self._winmm.waveOutUnprepareHeader(self._handle, ctypes.byref(header), ctypes.sizeof(header))
            raise OSError(f"waveOutWrite failed with MMRESULT={result}")
        self._pending.append((buffer, header))

    def drain_and_close(self) -> None:
        while self.pending_frames:
            time.sleep(0.001)
        self._winmm.waveOutClose(self._handle)
