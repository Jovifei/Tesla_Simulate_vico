"""Localhost-only v0.8 WebSocket ingress for the existing PC runtime."""

from __future__ import annotations

import json
import math
from threading import RLock, Thread
import time
from typing import Any

from websockets.sync.server import ServerConnection, serve

from vehicle_interface.engine_runtime_api import EngineRuntimeApi
from vehicle_interface.packet import VehicleStatePacket
from vehicle_state_runtime.stream import UPDATE_HZ


class VehicleRuntimeWebSocketServer:
    """Serve C/synthetic vehicle state at ``ws://127.0.0.1:<port>/state``."""

    def __init__(self, api: EngineRuntimeApi, port: int = 0) -> None:
        self.api = api
        self._api_lock = RLock()
        self._last_protocol_packet: VehicleStatePacket | None = None
        self._server = serve(self._handle_connection, "127.0.0.1", port)
        self._thread: Thread | None = None

    @property
    def url(self) -> str:
        host, port = self._server.socket.getsockname()[:2]
        return f"ws://{host}:{port}/state"

    @staticmethod
    def _encode(payload: dict[str, Any]) -> str:
        return json.dumps(payload, allow_nan=False, separators=(",", ":"))

    def _handle_connection(self, connection: ServerConnection) -> None:
        if connection.request.path != "/state":
            connection.close(code=1008, reason="state endpoint required")
            return
        for raw_message in connection:
            ingress_started_s = time.perf_counter()
            try:
                if not isinstance(raw_message, str):
                    raise ValueError("text JSON required")
                payload = json.loads(raw_message)
                if not isinstance(payload, dict):
                    raise ValueError("JSON object required")
                packet = VehicleStatePacket.from_mapping(payload)
            except (TypeError, ValueError, json.JSONDecodeError):
                connection.send(self._encode({"error": "invalid_packet"}))
                continue
            with self._api_lock:
                gap_fallback_applied = self._fill_missing_packets(packet, ingress_started_s)
                result = self.api.process_state(packet, ingress_started_s=ingress_started_s)
                if math.isfinite(packet.timestamp_s):
                    self._last_protocol_packet = packet
            frame = result.pcm_frame
            timestamp = packet.timestamp_s if math.isfinite(packet.timestamp_s) else None
            connection.send(
                self._encode(
                    {
                        "status": "ok",
                        "timestamp": timestamp,
                        "fallback_applied": gap_fallback_applied or result.fallback_applied,
                        "gap_fallback_applied": gap_fallback_applied,
                        "pcm_available": frame is not None,
                        "pcm_sequence_index": None if frame is None else frame.sequence_index,
                        "packet_to_pcm_ms": result.packet_to_pcm_ms,
                        "server_received_monotonic_ms": ingress_started_s * 1000.0,
                        "pcm_ready_server_monotonic_ms": (
                            None
                            if result.packet_to_pcm_ms is None
                            else ingress_started_s * 1000.0 + result.packet_to_pcm_ms
                        ),
                    }
                )
            )

    def _fill_missing_packets(self, packet: VehicleStatePacket, ingress_started_s: float) -> bool:
        previous = self._last_protocol_packet
        if (
            previous is None
            or not math.isfinite(previous.timestamp_s)
            or not math.isfinite(packet.timestamp_s)
        ):
            return False
        interval_s = 1.0 / UPDATE_HZ
        next_timestamp_s = previous.timestamp_s + interval_s
        gap_fallback_applied = False
        if packet.timestamp_s - next_timestamp_s > interval_s * 0.5:
            fallback_mapping = previous.as_mapping()
            fallback_mapping["timestamp"] = next_timestamp_s
            fallback_mapping["rpm"] = -1.0
            self.api.process_state(
                VehicleStatePacket.from_mapping(fallback_mapping),
                ingress_started_s=ingress_started_s,
            )
            gap_fallback_applied = True
        return gap_fallback_applied

    def start(self) -> str:
        if self._thread is None:
            self._thread = Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
        return self.url

    def shutdown(self) -> None:
        if self._thread is None:
            return
        self._server.shutdown()
        self._thread.join(timeout=5.0)
        self._thread = None

    def __enter__(self) -> "VehicleRuntimeWebSocketServer":
        self.start()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.shutdown()
