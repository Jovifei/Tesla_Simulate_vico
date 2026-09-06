"""One-click multi-port server for the existing four-vehicle A/B workbench.

Generated WAV/Base64 vehicle packages are intentionally no longer versioned in
Git. Car dashboards default to ``E:\\Tesla_speed\\review_packages`` when that
local review root exists; the lightweight portal itself always comes from this
versioned repository directory. Set ``S12_REVIEW_ROOT`` to override the local
vehicle-package root.
"""

from __future__ import annotations

import http.server
import os
from pathlib import Path
import socketserver
import threading

REPO_REVIEW_ROOT = Path(__file__).resolve().parent
DEFAULT_EXTERNAL_ROOT = Path(r"E:\Tesla_speed\review_packages")
VEHICLE_ROOT = Path(os.environ.get("S12_REVIEW_ROOT", "")) if os.environ.get("S12_REVIEW_ROOT") else (
    DEFAULT_EXTERNAL_ROOT if DEFAULT_EXTERNAL_ROOT.exists() else REPO_REVIEW_ROOT
)
try:
    REVIEW_PORT_BASE = int(os.environ.get("S12_REVIEW_PORT_BASE", "8088"))
except ValueError as exc:
    raise ValueError("S12_REVIEW_PORT_BASE must be an integer") from exc
if not 1024 <= REVIEW_PORT_BASE <= 65532:
    raise ValueError("S12_REVIEW_PORT_BASE must leave room for four vehicle ports")

SERVERS = [
    {"name": "Unified Portal", "dir": REPO_REVIEW_ROOT, "port": 8080},
    {"name": "Dodge Hellcat", "dir": VEHICLE_ROOT / "s12-stage-ad-hellcat-closed-loop-v1", "port": REVIEW_PORT_BASE},
    {"name": "Ferrari 458", "dir": VEHICLE_ROOT / "s12-stage-ad-ferrari-458-closed-loop-v1", "port": REVIEW_PORT_BASE + 1},
    {"name": "Lexus LFA", "dir": VEHICLE_ROOT / "s12-stage-ad-lfa-closed-loop-v1", "port": REVIEW_PORT_BASE + 2},
    {"name": "Nissan GT-R", "dir": VEHICLE_ROOT / "s12-stage-ad-gtr-r35-closed-loop-v1", "port": REVIEW_PORT_BASE + 3},
]


class ReusableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = True


class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()


def run_server(name: str, directory: Path, port: int) -> None:
    def handler_factory(*args, **kwargs):
        return CustomHandler(*args, directory=str(directory), **kwargs)

    try:
        with ReusableTCPServer(("", port), handler_factory) as httpd:
            print(f"[{name}] http://localhost:{port}/ -> {directory}")
            httpd.serve_forever()
    except OSError as exc:
        print(f"[{name}] port {port} unavailable: {exc}")


def main() -> None:
    print("=" * 72)
    print("S12 物理声学引擎 · 现有四车型 A/B 评审服务")
    print(f"Versioned portal: {REPO_REVIEW_ROOT}")
    print(f"Generated vehicle packages: {VEHICLE_ROOT}")
    print("=" * 72)
    threads: list[threading.Thread] = []
    for server in SERVERS:
        directory = server["dir"]
        if not directory.exists():
            print(f"[missing] {server['name']}: {directory}")
            continue
        thread = threading.Thread(
            target=run_server,
            args=(server["name"], directory, server["port"]),
            daemon=True,
        )
        thread.start()
        threads.append(thread)
    if len(threads) <= 1:
        print("尚未找到车型评审包。请先运行 Stage-AF build_existing_dashboards.py。")
    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        print("\n停止所有评审服务。")


if __name__ == "__main__":
    main()
