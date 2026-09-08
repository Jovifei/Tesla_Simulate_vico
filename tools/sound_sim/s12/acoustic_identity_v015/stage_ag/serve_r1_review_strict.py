"""Strict Stage AG-R1 review server.

This launcher exists specifically to prevent stale Stage-AE/old-package pages from
being served accidentally during Jovi's A/B review.  Unlike the historical
``review_packages/serve_dashboards.py`` it fails closed on any port collision and
validates package identity, rich-dashboard HTML markers and candidate/reference
SHA-256 bindings before opening a socket.
"""
from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import socketserver
import threading
from pathlib import Path
from typing import Any, Mapping

from ..stage_af.package_integrity import canonical_json_bytes, sha256_file

VEHICLES = ("hellcat", "ferrari_458", "lfa", "gtr_r35")
EXPECTED_DIRS = {
    "hellcat": "s12-stage-ad-hellcat-closed-loop-v1",
    "ferrari_458": "s12-stage-ad-ferrari-458-closed-loop-v1",
    "lfa": "s12-stage-ad-lfa-closed-loop-v1",
    "gtr_r35": "s12-stage-ad-gtr-r35-closed-loop-v1",
}
RICH_HTML_REQUIRED_MARKERS = (
    "声源 A/B 瞬时无缝比对",
    "实时动态声学分析仪",
    "visualizerCanvas",
    "categoryAllLabel",
)
STALE_HTML_FORBIDDEN_MARKERS = (
    "package-wide gain",
    "canonical S12 renderer",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_manifest_self_hash(manifest: Mapping[str, Any], path: Path) -> None:
    recorded = str(manifest.get("manifest_sha256", ""))
    canonical = dict(manifest)
    canonical.pop("manifest_sha256", None)
    calculated = hashlib.sha256(canonical_json_bytes(canonical)).hexdigest()
    if not recorded or recorded != calculated:
        raise ValueError(f"manifest self-hash mismatch: {path}")


def _validate_html(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [marker for marker in RICH_HTML_REQUIRED_MARKERS if marker not in text]
    if missing:
        raise ValueError(
            f"dashboard is not the approved rich Ferrari-style A/B workbench: {path}; "
            f"missing markers={missing}"
        )
    stale = [marker for marker in STALE_HTML_FORBIDDEN_MARKERS if marker in text]
    if stale:
        raise ValueError(
            f"stale/simple Stage-AE dashboard detected: {path}; forbidden markers={stale}"
        )


def validate_package(
    package_root: Path,
    *,
    expected_mode: str,
    expected_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    package_root = package_root.resolve()
    manifest_path = package_root / "audition_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = _load_json(manifest_path)
    if manifest.get("schema") != "s12.stage_ag.package_manifest.v1":
        raise ValueError(f"unsupported Stage AG package schema: {manifest_path}")
    if manifest.get("identity_mode") != expected_mode:
        raise ValueError(
            f"wrong identity mode in {manifest_path}: {manifest.get('identity_mode')} != {expected_mode}"
        )
    _validate_manifest_self_hash(manifest, manifest_path)
    actual_manifest_sha = sha256_file(manifest_path)
    if expected_manifest_sha256 and actual_manifest_sha.lower() != expected_manifest_sha256.lower():
        raise ValueError(
            f"package manifest SHA mismatch: {actual_manifest_sha} != {expected_manifest_sha256}"
        )

    entries = {str(row.get("vehicle")): row for row in manifest.get("vehicles", [])}
    if set(entries) != set(VEHICLES):
        raise ValueError("Stage AG-R1 review package must contain exactly four vehicles")

    for vehicle in VEHICLES:
        entry = entries[vehicle]
        expected_dir = EXPECTED_DIRS[vehicle]
        if str(entry.get("directory")) != expected_dir:
            raise ValueError(
                f"unexpected vehicle directory for {vehicle}: {entry.get('directory')} != {expected_dir}"
            )
        vehicle_root = package_root / expected_dir
        html_path = vehicle_root / "index.html"
        contract_path = vehicle_root / "dashboard_contract.json"
        if not html_path.is_file() or not contract_path.is_file():
            raise FileNotFoundError(f"missing rich dashboard artifacts under {vehicle_root}")
        _validate_html(html_path)
        contract = _load_json(contract_path)
        if contract.get("identity_mode") != expected_mode:
            raise ValueError(
                f"dashboard contract mode mismatch for {vehicle}: {contract.get('identity_mode')}"
            )
        if contract.get("human_status") != "WAITING_FOR_JOVI_FEEDBACK":
            raise ValueError(f"unexpected Human status for {vehicle}")

        manifest_candidates = entry.get("candidate_pcm_sha256", {})
        contract_candidates = contract.get("candidate_pcm_sha256", {})
        if manifest_candidates != contract_candidates:
            raise ValueError(f"candidate SHA map mismatch between manifest and contract: {vehicle}")
        for filename, expected_sha in manifest_candidates.items():
            candidate = vehicle_root / "web_audio" / str(filename)
            actual = sha256_file(candidate)
            if actual.lower() != str(expected_sha).lower():
                raise ValueError(f"candidate WAV SHA mismatch: {vehicle}/{filename}")

        manifest_refs = entry.get("reference_sha256", {})
        contract_refs = contract.get("reference_sha256", {})
        if manifest_refs != contract_refs:
            raise ValueError(f"Reference SHA map mismatch between manifest and contract: {vehicle}")
        for filename, expected_sha in manifest_refs.items():
            reference = vehicle_root / "web_audio" / str(filename)
            actual = sha256_file(reference)
            if actual.lower() != str(expected_sha).lower():
                raise ValueError(f"Reference WAV SHA mismatch: {vehicle}/{filename}")

    return {
        "root": str(package_root),
        "identity_mode": expected_mode,
        "manifest_sha256": actual_manifest_sha,
        "source_git_head": manifest.get("source_receipt", {}).get("git_head"),
        "vehicles": list(VEHICLES),
    }


class StrictHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = False


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


def _make_server(directory: Path, port: int) -> StrictHTTPServer:
    def factory(*args, **kwargs):
        return NoCacheHandler(*args, directory=str(directory), **kwargs)

    try:
        return StrictHTTPServer(("127.0.0.1", int(port)), factory)
    except OSError as exc:
        raise RuntimeError(
            f"port {port} is already occupied. Stop the stale/old review server first; "
            "strict Stage AG-R1 serving refuses fallback."
        ) from exc


def serve_verified_pair(
    legacy_root: Path,
    r1_root: Path,
    *,
    legacy_port_base: int = 23380,
    r1_port_base: int = 23480,
    legacy_manifest_sha256: str | None = None,
    r1_manifest_sha256: str | None = None,
    preflight_only: bool = False,
) -> dict[str, Any]:
    legacy = validate_package(
        legacy_root,
        expected_mode="legacy",
        expected_manifest_sha256=legacy_manifest_sha256,
    )
    r1 = validate_package(
        r1_root,
        expected_mode="vehicle_identity_v1r1",
        expected_manifest_sha256=r1_manifest_sha256,
    )

    result = {"legacy": legacy, "r1": r1, "urls": {}}
    for index, vehicle in enumerate(VEHICLES):
        result["urls"][f"legacy:{vehicle}"] = f"http://localhost:{legacy_port_base + index}/"
        result["urls"][f"r1:{vehicle}"] = f"http://localhost:{r1_port_base + index}/"
    if preflight_only:
        return result

    servers: list[StrictHTTPServer] = []
    try:
        # Bind every port before starting any thread.  One collision aborts the
        # entire launch, preventing a mix of new and stale pages.
        for index, vehicle in enumerate(VEHICLES):
            legacy_dir = Path(legacy_root) / EXPECTED_DIRS[vehicle]
            r1_dir = Path(r1_root) / EXPECTED_DIRS[vehicle]
            servers.append(_make_server(legacy_dir, legacy_port_base + index))
            servers.append(_make_server(r1_dir, r1_port_base + index))
    except Exception:
        for server in servers:
            server.server_close()
        raise

    threads: list[threading.Thread] = []
    for server in servers:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        threads.append(thread)

    print("Stage AG-R1 STRICT VERIFIED REVIEW")
    print(f"Legacy manifest SHA: {legacy['manifest_sha256']}")
    print(f"R1 manifest SHA:     {r1['manifest_sha256']}")
    for key, url in result["urls"].items():
        print(f"{key:22s} {url}")
    print("Do NOT use the historical 8080/8088-8091 portal for this review.")
    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Strictly validate and serve the approved Stage AG-R1 rich A/B dashboards"
    )
    parser.add_argument("--legacy-package", required=True, type=Path)
    parser.add_argument("--r1-package", required=True, type=Path)
    parser.add_argument("--legacy-manifest-sha256")
    parser.add_argument("--r1-manifest-sha256")
    parser.add_argument("--legacy-port-base", type=int, default=23380)
    parser.add_argument("--r1-port-base", type=int, default=23480)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    if not 1024 <= args.legacy_port_base <= 65532:
        parser.error("legacy port base must leave room for four vehicles")
    if not 1024 <= args.r1_port_base <= 65532:
        parser.error("R1 port base must leave room for four vehicles")
    result = serve_verified_pair(
        args.legacy_package,
        args.r1_package,
        legacy_port_base=args.legacy_port_base,
        r1_port_base=args.r1_port_base,
        legacy_manifest_sha256=args.legacy_manifest_sha256,
        r1_manifest_sha256=args.r1_manifest_sha256,
        preflight_only=args.preflight_only,
    )
    if args.preflight_only:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
