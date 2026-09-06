"""One-click multi-port server for the existing four-vehicle A/B workbench.

Generated WAV/Base64 review packages are intentionally no longer versioned in
Git.  By default this launcher serves ``E:\\Tesla_speed\\review_packages`` when
that local review root exists; otherwise it falls back to this repository's
``review_packages`` directory.  Set ``S12_REVIEW_ROOT`` to override.
"""

from __future__ import annotations

import http.server
import os
from pathlib import Path
import socketserver
import threading

REPO_REVIEW_ROOT = Path(__file__).resolve().parent
DEFAULT_EXTERNAL_ROOT = Path(r"E:\Tesla_speed\review_packages")
BASE_DIR = Path(os.environ.get("S12_REVIEW_ROOT", "")) if os.environ.get("S12_REVIEW_ROOT") else (
    DEFAULT_EXTERNAL_ROOT if DEFAULT_EXTERNAL_ROOT.exists() else REPO_REVIEW_ROOT
)

SERVERS = [
    {"name": "Unified Portal", "dir": BASE_DIR, "port": 8080},
    {"name": "Dodge Hellcat", "dir": BASE_DIR / "s12-stage-ad-hellcat-closed-loop-v1", "port": 8088},
    {"name": "Ferrari 458", "dir": BASE_DIR / "s12-stage-ad-ferrari-458-closed-loop-v1", "port": 8089},
    {"name": "Lexus LFA", "dir": BASE_DIR / "s12-stage-ad-lfa-closed-loop-v1", "port": 8090},
    {"name": "Nissan GT-R", "dir": BASE_DIR / "s12-stage-ad-gtr-r35-closed-loop-v1", "port": 8091},
]


class ReusableTCPServer(socketserver.TCPServer):
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
    print(f"Review root: {BASE_DIR}")
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
    if not threads:
        print("没有找到评审包。请先运行 Stage-AF build_existing_dashboards.py。")
        return
    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        print("\n停止所有评审服务。")


if __name__ == "__main__":
    main()
