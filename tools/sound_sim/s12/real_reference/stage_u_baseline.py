"""Stage U exact-baseline audit; no renderer or frozen-core mutation."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


STAGE_U_BASELINE_COMMIT = "b1d500c7c37a71728020c39e6dc115a0cd6743d5"


class StageUBaselineError(ValueError):
    """Raised when Stage U cannot prove its declared baseline."""


def _git(repo_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise StageUBaselineError(result.stderr.strip() or f"git command failed: {' '.join(arguments)}")
    return result.stdout.strip()


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StageUBaselineError(f"cannot read baseline artifact: {path}") from exc
    if not isinstance(value, dict):
        raise StageUBaselineError(f"baseline artifact must be an object: {path}")
    return value


def audit_stage_u_baseline(repo_root: Path) -> dict[str, Any]:
    """Record the exact pre-Stage-U candidate state from the declared baseline."""

    root = Path(repo_root).resolve()
    dashboard = root / "tasks" / "reports" / "runtime" / "S12_Professional_Comparison_Dashboard_v1"
    results = _json(dashboard / "r2_diagnostic_candidate_results.json")
    rx7 = _json(dashboard / "rx7_topic_r2_results.json")
    anchors = {str(row.get("vehicle_id")): row for row in results.get("anchors", []) if isinstance(row, dict)}
    if set(("ferrari_458", "hellcat", "rx7_fd")) - set(anchors):
        raise StageUBaselineError("R2 diagnostic result is missing an anchor vehicle")
    expected_execution = "SPECIFICATIONS_ONLY_NOT_RENDERED"
    for vehicle_id in ("ferrari_458", "hellcat"):
        if anchors[vehicle_id].get("evaluated_count") != 0 or results.get("candidate_execution") != expected_execution:
            raise StageUBaselineError(f"{vehicle_id} no longer matches the Stage U unrendered baseline")
    rx7_candidate = rx7.get("candidate")
    if not isinstance(rx7_candidate, dict) or rx7_candidate.get("parameter_changes") != 1 or rx7_candidate.get("source_modified") is not False:
        raise StageUBaselineError("RX-7 manual diagnostic candidate baseline is missing or modified")
    head = _git(root, "rev-parse", "HEAD")
    return {
        "schema_version": "s12-stage-u-baseline-audit-v1",
        "status": "STAGE_U_BASELINE_AUDITED",
        "baseline_commit": STAGE_U_BASELINE_COMMIT,
        "head_commit": head,
        "baseline_is_ancestor": subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", STAGE_U_BASELINE_COMMIT, "HEAD"],
            check=False,
        ).returncode == 0,
        "branch": _git(root, "branch", "--show-current"),
        "track_p": {"baseline": "S12 Track-P Baseline v3", "mutation": "NOT_PERFORMED"},
        "objective_before_after_claim": str(results.get("objective_before_after_claim")),
        "ferrari_458": {
            "candidate_audio_rendered": False,
            "candidate_execution": results.get("candidate_execution"),
            "evaluated_count": anchors["ferrari_458"].get("evaluated_count"),
        },
        "hellcat": {
            "candidate_audio_rendered": False,
            "candidate_execution": results.get("candidate_execution"),
            "evaluated_count": anchors["hellcat"].get("evaluated_count"),
        },
        "rx7_fd": {
            "manual_candidate_present": True,
            "source_modified": False,
            "candidate_result_status": rx7.get("status"),
            "candidate_profile_sha256": rx7_candidate.get("candidate_profile_sha256"),
        },
        "r1_status": "NOT_R1_QUALIFIED",
        "profile_freeze": "NOT_PROFILE_FREEZE_READY",
    }


def render_stage_u_baseline_report(audit: dict[str, Any]) -> str:
    """Render a concise evidence-led Markdown baseline audit."""

    return "\n".join((
        "# S12 Stage U Baseline Audit",
        "",
        f"- Baseline commit: `{audit['baseline_commit']}`",
        f"- Current HEAD: `{audit['head_commit']}`",
        f"- Branch: `{audit['branch']}`",
        f"- Baseline ancestor: `{audit['baseline_is_ancestor']}`",
        f"- Track-P: `{audit['track_p']['baseline']}` / `{audit['track_p']['mutation']}`",
        "",
        "| Vehicle | Candidate audio rendered | Source modified | Evidence |",
        "| --- | --- | --- | --- |",
        f"| Ferrari 458 | `{audit['ferrari_458']['candidate_audio_rendered']}` | `False` | `{audit['ferrari_458']['candidate_execution']}` |",
        f"| Hellcat | `{audit['hellcat']['candidate_audio_rendered']}` | `False` | `{audit['hellcat']['candidate_execution']}` |",
        f"| RX-7 FD | `{audit['rx7_fd']['manual_candidate_present']}` (manual candidate) | `{audit['rx7_fd']['source_modified']}` | `{audit['rx7_fd']['candidate_result_status']}` |",
        "",
        f"Objective before/after claim: `{audit['objective_before_after_claim']}`.",
        "",
    ))


__all__ = ["STAGE_U_BASELINE_COMMIT", "StageUBaselineError", "audit_stage_u_baseline", "render_stage_u_baseline_report"]
