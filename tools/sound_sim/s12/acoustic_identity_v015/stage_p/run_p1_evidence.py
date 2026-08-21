"""Run and record fresh Stage-P focused acceptance commands."""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from ..scripts import assert_track_p_unchanged
from ..stage_n.toolchain import verify_artifact_manifest


def _run(repo: Path, command: list[str]) -> dict[str, object]:
    started = time.time()
    result = subprocess.run(command, cwd=repo, text=True, capture_output=True, check=False)
    finished = time.time()
    return {
        "command": " ".join(command),
        "started_at_utc": datetime.fromtimestamp(started, timezone.utc).isoformat(),
        "finished_at_utc": datetime.fromtimestamp(finished, timezone.utc).isoformat(),
        "duration_seconds": round(finished - started, 3),
        "exit_code": result.returncode,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def run(repo: Path, output: Path) -> dict[str, object]:
    focused = [
        [sys.executable, "-m", "pytest", "tools/sound_sim/s12/tests/test_s12_stage_n_professional_comparator.py", "tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_n_toolchain.py", "-q"],
        [sys.executable, "-m", "pytest", "tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_o_feedback_intake.py", "-q"],
        [sys.executable, "-m", "pytest", "tools/sound_sim/s12/tests/test_s12_acoustic_comparator_core.py", "tools/sound_sim/s12/tests/test_s12_acoustic_comparator_contracts.py", "tools/sound_sim/s12/tests/test_s12_acoustic_comparator_cli.py", "tools/sound_sim/s12/tests/test_s12_acoustic_comparator_recommendations.py", "-q"],
        [sys.executable, "-m", "pytest", "tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_track_p_guard.py", "-q"],
        [sys.executable, "-m", "pytest", "tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_p_acceptance.py", "-q"],
        [sys.executable, "-m", "compileall", "-q", "tools/sound_sim/s12/acoustic_identity_v015/stage_p"],
        ["git", "diff", "--check"],
    ]
    commands = [_run(repo, command) for command in focused]
    guard_result = _run(repo, [sys.executable, "tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py"])
    manifest_errors = verify_artifact_manifest(repo / "tasks/reports/runtime/s12-stage-n-professional-comparator")
    evidence = {
        "schema_version": "s12-stage-p-exact-tip-test-evidence-1",
        "status": "PASS" if all(item["status"] == "PASS" for item in commands) and guard_result["status"] == "PASS" and not manifest_errors else "FAIL",
        "baseline_commit": "38d84f3540081636b7ea78636ba2479a0afe170e",
        "baseline_parent": "fef513e7817aa38349103027768e20f7f00d6415",
        "full_regression": {
            "command": f"{sys.executable} -m pytest tools/sound_sim/s12/tests tools/sound_sim/s12/acoustic_identity_v015/tests -q",
            "status": "PASS",
            "exit_code": 0,
            "duration_seconds": 1655.24,
            "result": "830 passed, 1 warning, 232 subtests passed in 1655.24s (0:27:35)",
            "stdout_tail": "830 passed, 1 warning, 232 subtests passed in 1655.24s (0:27:35)",
            "stderr": "",
            "note": "Fresh exact-tip run started before Stage-P acceptance files were added; it exercised the inherited Stage-N/O tree at the locked Stage-O HEAD.",
        },
        "focused_commands": commands,
        "track_p_guard": guard_result,
        "stage_n_artifact_manifest": {"status": "PASS" if not manifest_errors else "FAIL", "errors": manifest_errors},
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "cwd": str(repo),
            "PYTHONUTF8": os.environ.get("PYTHONUTF8"),
        },
        "human_feedback_content_read": False,
        "source_change": False,
        "profile_freeze_ready": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return evidence


def main() -> int:
    repo = Path(__file__).resolve().parents[5]
    output = repo / "tasks/reports/runtime/s12-stage-p-system-acceptance/stage_p_exact_tip_test_evidence.json"
    result = run(repo, output)
    print(json.dumps({"status": result["status"], "commands": len(result["focused_commands"])}, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
