"""RED contracts for the final Stage-W-C remediation wave."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[5]


def test_stage_w_raw_logs_have_scoped_opaque_attributes() -> None:
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "tasks/reports/runtime/s12-stage-w/logs/*.log" in attributes
    assert "-text" in attributes
    assert "-diff" in attributes
    assert "-whitespace" in attributes


def test_final_track_p_guard_is_clean_after_committed_log_attributes() -> None:
    guard = ROOT / "tools" / "sound_sim" / "s12" / "acoustic_identity_v015" / "scripts" / "assert_track_p_unchanged.py"
    result = subprocess.run(["python", str(guard)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_w9_named_raw_log_bytes_are_not_rewritten() -> None:
    receipt = ROOT / "tasks" / "reports" / "runtime" / "s12-stage-w" / "phase_receipts" / "W9_FINAL_QUALIFICATION.json"
    import json
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    for name, expected in payload.get("checks", {}).get("logs", {}).items():
        path = ROOT / "tasks" / "reports" / "runtime" / "s12-stage-w" / "logs" / name
        if path.is_file():
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
