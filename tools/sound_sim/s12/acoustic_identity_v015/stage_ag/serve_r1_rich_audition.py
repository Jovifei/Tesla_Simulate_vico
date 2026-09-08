"""Serve only a validated Stage AG-R1 rich audition view.

Unlike the generic review server this launcher has no fallback/default package root.
It refuses to serve if the rich-view receipt, source manifest identity, or rich UI
markers do not match the caller's exact expectations.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import socketserver
import threading
from pathlib import Path
from typing import Any

from .build_r1_rich_audition_view import (
    VEHICLES,
    VIEW_SCHEMA,
    validate_rich_page,
)

DIR_NAMES = {
    "hellcat": "s12-stage-ad-hellcat-closed-loop-v1",
    "ferrari_458": "s12-stage-ad-ferrari-458-closed-loop-v1",
    "lfa": "s12-stage-ad-lfa-closed-loop-v1",
    "gtr_r35": "s12-stage-ad-gtr-r35-closed-loop-v1",
}
DISPLAY_NAMES = {
    "hellcat": "Dodge Challenger SRT Hellcat",
    "ferrari_458": "Ferrari 458 Italia",
    "lfa": "Lexus LFA",
    "gtr_r35": "Nissan GT-R R35",
}


class ReusableThreadingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = True


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()


def validate_view_root(
    view_root: Path,
    *,
    expected_source_manifest_sha256: str,
    expected_identity_mode: str,
) -> dict[str, Any]:
    view_root = view_root.resolve()
    receipt_path = view_root / "rich_view_receipt.json"
    if not receipt_path.is_file():
        raise FileNotFoundError(receipt_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema") != VIEW_SCHEMA:
        raise ValueError("not a Stage AG-R1 rich view")
    if receipt.get("status") != "VIEW_ONLY / NOT_EVIDENCE_PACKAGE":
        raise ValueError("rich view status mismatch")
    if str(receipt.get("source_manifest_file_sha256", "")).lower() != expected_source_manifest_sha256.lower():
        raise ValueError("rich view source manifest SHA mismatch")
    if receipt.get("source_identity_mode") != expected_identity_mode:
        raise ValueError("rich view identity mode mismatch")
    if receipt.get("audio_policy") != "EXACT_BYTE_COPY_NO_RENDER_NO_NORMALIZATION":
        raise ValueError("rich view audio policy mismatch")

    for vehicle in VEHICLES:
        directory = view_root / DIR_NAMES[vehicle]
        if not directory.is_dir():
            raise FileNotFoundError(directory)
        validate_rich_page(directory / "index.html")
        validate_rich_page(directory / "index_standalone.html")
    return receipt


def _serve(directory: Path, port: int, label: str) -> None:
    handler = functools.partial(NoCacheHandler, directory=str(directory))
    with ReusableThreadingServer(("127.0.0.1", int(port)), handler) as httpd:
        print(f"[{label}] http://localhost:{port}/ -> {directory}", flush=True)
        httpd.serve_forever()


def serve_view(
    view_root: Path,
    *,
    expected_source_manifest_sha256: str,
    expected_identity_mode: str,
    port_base: int,
) -> None:
    if not 1024 <= int(port_base) <= 65532:
        raise ValueError("port_base must leave room for four vehicle ports")
    receipt = validate_view_root(
        view_root,
        expected_source_manifest_sha256=expected_source_manifest_sha256,
        expected_identity_mode=expected_identity_mode,
    )
    print("=" * 86)
    print("S12 Stage AG-R1 · FAIL-CLOSED RICH AUDITION WORKBENCH")
    print(f"view root      : {view_root.resolve()}")
    print(f"source package : {receipt.get('source_package_id')}")
    print(f"identity mode  : {receipt.get('source_identity_mode')}")
    print(f"manifest SHA   : {receipt.get('source_manifest_file_sha256')}")
    print(f"source git     : {receipt.get('source_git_head')}")
    print("audio policy   : EXACT_BYTE_COPY_NO_RENDER_NO_NORMALIZATION")
    print("=" * 86)

    threads: list[threading.Thread] = []
    for index, vehicle in enumerate(VEHICLES):
        port = int(port_base) + index
        directory = view_root.resolve() / DIR_NAMES[vehicle]
        thread = threading.Thread(
            target=_serve,
            args=(directory, port, DISPLAY_NAMES[vehicle]),
            daemon=True,
        )
        thread.start()
        threads.append(thread)
    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        print("\n停止 Stage AG-R1 rich audition servers.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Serve an exact, validated screenshot-1-style Stage AG-R1 rich workbench"
    )
    parser.add_argument("--view-root", required=True, type=Path)
    parser.add_argument("--expected-source-manifest-sha256", required=True)
    parser.add_argument(
        "--expected-identity-mode",
        required=True,
        choices=("legacy", "vehicle_identity_v1r1"),
    )
    parser.add_argument("--port-base", required=True, type=int)
    args = parser.parse_args(argv)
    serve_view(
        args.view_root,
        expected_source_manifest_sha256=args.expected_source_manifest_sha256,
        expected_identity_mode=args.expected_identity_mode,
        port_base=args.port_base,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
