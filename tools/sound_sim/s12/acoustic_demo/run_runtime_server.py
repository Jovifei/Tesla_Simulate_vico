"""Run the localhost-only v0.8 WebSocket runtime server for the Android demo."""

from __future__ import annotations

import time
import argparse

from runtime_server.websocket_server import VehicleRuntimeWebSocketServer
from vehicle_interface.engine_runtime_api import EngineRuntimeApi


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the S12 v0.8 localhost WebSocket runtime server.")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with VehicleRuntimeWebSocketServer(EngineRuntimeApi(), port=args.port) as server:
        print(f"S12 v0.8 runtime server: {server.url}")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("S12 v0.8 runtime server stopped")


if __name__ == "__main__":
    main()
