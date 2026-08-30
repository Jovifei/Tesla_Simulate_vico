"""Restore Stage-W historical raw-log bytes from their receipt-bound commit.

The W9 receipt records both the historical source commit and SHA-256 for each
raw log. This script retrieves the exact Git blob from that commit and writes
it back only when the blob hash equals the immutable receipt hash. It never
updates expected hashes and never guesses replacement content.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[5]
RECEIPT = (
    ROOT
    / "tasks"
    / "reports"
    / "runtime"
    / "s12-stage-w"
    / "phase_receipts"
    / "W9_FINAL_QUALIFICATION.json"
)
LOG_ROOT = ROOT / "tasks" / "reports" / "runtime" / "s12-stage-w" / "logs"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_blob(commit: str, relative_path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{commit}:{relative_path}"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def _candidate_encodings(raw: bytes) -> list[tuple[str, bytes]]:
    """Fallback byte representations that preserve decoded text exactly."""
    candidates: list[tuple[str, bytes]] = [("current", raw)]
    for decoder_name, encoding in (
        ("utf8", "utf-8"),
        ("utf8-sig", "utf-8-sig"),
        ("utf16le", "utf-16-le"),
    ):
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        for newline_name, newline in (("lf", "\n"), ("crlf", "\r\n"), ("cr", "\r")):
            body = normalized.replace("\n", newline)
            for output_name, output_encoding in (
                ("utf8", "utf-8"),
                ("utf8-bom", "utf-8-sig"),
                ("utf16le", "utf-16-le"),
            ):
                candidates.append(
                    (
                        f"{decoder_name}->{output_name}-{newline_name}",
                        body.encode(output_encoding),
                    )
                )
    unique: dict[str, tuple[str, bytes]] = {}
    for label, data in candidates:
        unique.setdefault(_sha(data), (label, data))
    return list(unique.values())


def restore(*, apply: bool) -> dict[str, object]:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    historical_head = str(
        receipt.get("head")
        or receipt.get("audit_provenance", {}).get("tested_code_evidence_head")
        or ""
    )
    expected_logs = receipt.get("checks", {}).get("logs", {})
    results: dict[str, object] = {}
    unresolved: dict[str, object] = {}
    changed: list[str] = []
    for name, expected in expected_logs.items():
        path = LOG_ROOT / name
        relative = path.relative_to(ROOT).as_posix()
        if not path.is_file():
            unresolved[name] = {"status": "MISSING", "expected": expected}
            continue
        raw = path.read_bytes()
        observed = _sha(raw)
        if observed == expected:
            results[name] = {"status": "ALREADY_MATCHED", "sha256": observed}
            continue

        match: tuple[str, bytes] | None = None
        historical = _git_blob(historical_head, relative) if historical_head else None
        if historical is not None and _sha(historical) == expected:
            match = (f"git_blob:{historical_head}", historical)
        if match is None:
            match = next(
                (
                    (label, data)
                    for label, data in _candidate_encodings(raw)
                    if _sha(data) == expected
                ),
                None,
            )
        if match is None:
            unresolved[name] = {
                "status": "RECEIPT_BOUND_GIT_BLOB_NOT_FOUND",
                "historical_head": historical_head,
                "expected": expected,
                "observed": observed,
            }
            continue

        label, data = match
        results[name] = {
            "status": "RESTORABLE" if not apply else "RESTORED",
            "representation": label,
            "before_sha256": observed,
            "after_sha256": expected,
        }
        if apply:
            path.write_bytes(data)
            if _sha(path.read_bytes()) != expected:
                raise RuntimeError(f"post-write SHA mismatch: {name}")
            changed.append(name)
    return {
        "schema": "s12.stage_y.historical_log_byte_restore.v2",
        "receipt": str(RECEIPT.relative_to(ROOT).as_posix()),
        "historical_head": historical_head,
        "apply": apply,
        "results": results,
        "unresolved": unresolved,
        "changed": changed,
        "passed": not unresolved,
        "policy": "receipt and hashes are immutable; only the receipt-bound Git blob is authoritative",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    global RECEIPT
    if args.receipt is not None:
        RECEIPT = args.receipt.resolve()
    result = restore(apply=args.apply)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
