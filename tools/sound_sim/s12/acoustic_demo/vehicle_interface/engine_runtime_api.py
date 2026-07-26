"""Two-packet v0.7 adapter for the frozen v0.6 runtime path."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import time

from engine_runtime import EngineSoundRuntime
from runtime_pcm import PCMFrame, PcmRingBuffer, SimulatedPcmSink
from vehicle_interface.packet import VehicleStatePacket


BLOCK_DURATION_S = 0.020


@dataclass(frozen=True)
class RuntimeApiResult:
    packet_index: int
    pcm_frame: PCMFrame | None
    fallback_applied: bool
    packet_to_pcm_ms: float | None


class EngineRuntimeApi:
    """Expose the v0.6 100 Hz ingestion and 20 ms rendering contract."""

    def __init__(self, queue_capacity_frames: int = 50) -> None:
        self._runtime = EngineSoundRuntime()
        self._queue = PcmRingBuffer(queue_capacity_frames)
        self._sink = SimulatedPcmSink(BLOCK_DURATION_S)
        self._audio_hash = hashlib.sha256()
        self._latencies_ms: list[float] = []
        self._transitions: list[dict[str, object]] = []
        self._last_mode: str | None = None
        self.packet_count = 0
        self.pcm_frame_count = 0
        self.clipping_count = 0

    @property
    def fallback_count(self) -> int:
        return self._runtime.fallback_count

    @property
    def underrun_count(self) -> int:
        return self._sink.underrun_count

    @property
    def pcm_sha256(self) -> str:
        return self._audio_hash.hexdigest()

    @property
    def frame_latencies_ms(self) -> tuple[float, ...]:
        return tuple(self._latencies_ms)

    @property
    def state_transitions(self) -> tuple[dict[str, object], ...]:
        return tuple(self._transitions)

    @property
    def queue_capacity_frames(self) -> int:
        return self._queue.capacity_frames

    @property
    def queue_max_depth_frames(self) -> int:
        return self._queue.max_depth

    def process_state(self, packet: VehicleStatePacket) -> RuntimeApiResult:
        """Ingest one packet; every second 100 Hz packet emits one PCM frame."""
        started = time.perf_counter()
        fallback_before = self._runtime.fallback_count
        self._runtime.update_vehicle_state(packet.to_runtime_state())
        self.packet_count += 1
        fallback_applied = self._runtime.fallback_count > fallback_before
        if self.packet_count % 2:
            return RuntimeApiResult(self.packet_count, None, fallback_applied, None)

        frame = self._runtime.audio_callback()
        fallback_applied = fallback_applied or frame.fallback_applied
        if any(abs(sample) > 1.0 for sample in frame.normalized_samples):
            self.clipping_count += 1
        self._queue.push(frame)
        consumed = self._sink.consume(self._queue)
        if consumed is None:
            raise RuntimeError("runtime PCM queue unexpectedly underrun")
        self._audio_hash.update(frame.pcm_s24le_stereo)
        self.pcm_frame_count += 1
        latency_ms = (time.perf_counter() - started) * 1000.0
        self._latencies_ms.append(latency_ms)
        if frame.runtime_mode != self._last_mode:
            self._transitions.append(
                {
                    "packet_index": self.packet_count,
                    "pcm_sequence_index": frame.sequence_index,
                    "mode": frame.runtime_mode,
                }
            )
            self._last_mode = frame.runtime_mode
        return RuntimeApiResult(self.packet_count, frame, fallback_applied, latency_ms)
