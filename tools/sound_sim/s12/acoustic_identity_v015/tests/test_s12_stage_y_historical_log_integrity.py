"""Diagnostic contract for Stage-W historical raw-log byte integrity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]


def test_stage_w_named_raw_logs_match_historical_receipt_with_filename() -> None:
    receipt = (
        ROOT
        / "tasks"
        / "reports"
        / "runtime"
        / "s12-stage-w"
        / "phase_receipts"
        / "W9_FINAL_QUALIFICATION.json"
    )
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    mismatches: dict[str, dict[str, str]] = {}
    for name, expected in payload.get("checks", {}).get("logs", {}).items():
        path = ROOT / "tasks" / "reports" / "runtime" / "s12-stage-w" / "logs" / name
        if not path.is_file():
            mismatches[name] = {"expected": expected, "observed": "MISSING"}
            continue
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
        if observed != expected:
            mismatches[name] = {"expected": expected, "observed": observed}
    assert not mismatches, json.dumps(mismatches, indent=2, sort_keys=True)
