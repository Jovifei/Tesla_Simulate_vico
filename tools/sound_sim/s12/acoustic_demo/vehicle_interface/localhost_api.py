"""Localhost-only HTTP ingress for synthetic S12 vehicle-state packets."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import RLock, Thread
from typing import Any

from vehicle_interface.engine_runtime_api import EngineRuntimeApi
from vehicle_interface.packet import VehicleStatePacket


class _VehicleHttpServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], api: EngineRuntimeApi) -> None:
        super().__init__(address, _VehicleRequestHandler)
        self.api = api
        self.api_lock = RLock()


class _VehicleRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _respond(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, allow_nan=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        self._respond(405, {"error": "method_not_allowed"})

    def do_POST(self) -> None:
        if self.path != "/vehicle_state":
            self._respond(404, {"error": "not_found"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            packet = VehicleStatePacket.from_mapping(payload)
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
            self._respond(400, {"error": "invalid_packet"})
            return
        with self.server.api_lock:
            result = self.server.api.process_state(packet)
        frame = result.pcm_frame
        self._respond(
            200,
            {
                "packet_index": result.packet_index,
                "fallback_applied": result.fallback_applied,
                "pcm_available": frame is not None,
                "pcm_sequence_index": None if frame is None else frame.sequence_index,
                "packet_to_pcm_ms": result.packet_to_pcm_ms,
            },
        )


class LocalhostVehicleStateServer:
    """Lifecycle wrapper that never listens beyond the local loopback interface."""

    def __init__(self, api: EngineRuntimeApi, port: int = 0) -> None:
        self.api = api
        self._server = _VehicleHttpServer(("127.0.0.1", port), api)
        self._thread: Thread | None = None

    @property
    def url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> str:
        if self._thread is None:
            self._thread = Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
        return self.url

    def shutdown(self) -> None:
        if self._thread is None:
            return
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5.0)
        self._thread = None

    def __enter__(self) -> "LocalhostVehicleStateServer":
        self.start()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.shutdown()
