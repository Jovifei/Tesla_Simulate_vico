"""Restore Stage-W historical raw-log bytes without changing their text.

The W9 receipt predates a workspace line-ending conversion.  This script only
rewrites a log when a deterministic newline/BOM representation of its current
Unicode text exactly matches the SHA-256 already recorded by W9.  It never
updates the receipt and never accepts a different logical log body.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

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


def _candidate_encodings(raw: bytes) -> list[tuple[str, bytes]]:
    """Return byte representations that preserve decoded text exactly."""
    candidates: list[tuple[str, bytes]] = [("current", raw)]
    decoders = (
        ("utf8", "utf-8"),
        ("utf8-sig", "utf-8-sig"),
        ("utf16le", "utf-16-le"),
    )
    for decoder_name, encoding in decoders:
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
    expected_logs = receipt.get("checks", {}).get("logs", {})
    results: dict[str, object] = {}
    unresolved: dict[str, object] = {}
    changed: list[str] = []
    for name, expected in expected_logs.items():
        path = LOG_ROOT / name
        if not path.is_file():
            unresolved[name] = {"status": "MISSING", "expected": expected}
            continue
        raw = path.read_bytes()
        observed = _sha(raw)
        if observed == expected:
            results[name] = {"status": "ALREADY_MATCHED", "sha256": observed}
            continue
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
                "status": "LOGICAL_CONTENT_OR_UNSUPPORTED_ENCODING_MISMATCH",
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
        "schema": "s12.stage_y.historical_log_byte_restore.v1",
        "receipt": str(RECEIPT.relative_to(ROOT).as_posix()),
        "apply": apply,
        "results": results,
        "unresolved": unresolved,
        "changed": changed,
        "passed": not unresolved,
        "policy": "receipt SHA is immutable; only text-preserving byte representations are accepted",
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
