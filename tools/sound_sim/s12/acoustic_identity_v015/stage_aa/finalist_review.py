"""Professional-tool bounded review for the small Stage AA finalist set."""

from __future__ import annotations

from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from ..stage_v.io import write_json


REPO_ROOT = Path(__file__).resolve().parents[5]
AUDIT_PATH = Path("tasks/reports/runtime/s12-stage-aa/candidate_audit.json")
OUTPUT = Path("tasks/reports/runtime/s12-stage-aa/finalist_review.json")
REPORT = Path("tasks/reports/runtime/s12-stage-aa/finalist_review.md")
RECEIPT = Path("tasks/reports/runtime/s12-stage-aa/receipts/aa5-finalist-review.json")
FINALISTS = ("AA-C1", "AA-C2", "AA-C3")


def _professional_summary(scene_records: list[dict[str, Any]]) -> dict[str, float]:
    def mean(name: str) -> float:
        return float(sum(float(item["metrics"][name]) for item in scene_records) / max(len(scene_records), 1))

    return {
        "loudness_rms_dbfs": mean("rms_dbfs"),
        "sharpness": mean("sharpness_proxy"),
        "roughness": mean("roughness_proxy"),
        "fluctuation_proxy": mean("spectral_flux"),
        "tonality": mean("tonality_proxy"),
        "prominence_proxy": float(sum(float(item["metrics"]["tonality_proxy"]) * float(item["metrics"]["persistent_tone_ratio"]) for item in scene_records) / max(len(scene_records), 1)),
        "dynamic_range_db": mean("dynamic_range_db"),
    }


def build_finalist_review(*, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    audit = json.loads((repo_root / AUDIT_PATH).read_text(encoding="utf-8"))
    by_id = {item["candidate_id"]: item for item in audit["candidates"]}
    metrics = {candidate_id: _professional_summary(by_id[candidate_id]["scenes"]) for candidate_id in FINALISTS}
    try:
        import mosqito  # type: ignore[import-not-found]
    except ImportError:
        mosqito_status = "NOT_INSTALLED_LOCAL"
    else:
        mosqito_status = f"AVAILABLE_{getattr(mosqito, '__version__', 'UNKNOWN')}_API_NOT_RUN"
    return {
        "schema": "s12.stage_aa.professional_finalist_review.v1",
        "status": "DIAGNOSTIC_ONLY",
        "vehicle": "hellcat",
        "finalists": list(FINALISTS),
        "diagnostic_preference_from_bounded_audit": audit["diagnostic_preference"],
        "metrics": metrics,
        "metric_provenance": "candidate_audit raw PCM metrics; no loudness flattening in Dynamic domain",
        "matlab": {"status": "MATLAB_FINALIST_RECEIPT_PENDING", "reason": "No stable human-open MATLAB session was verified; do not launch matlab -batch or a new session."},
        "mosqito": {"status": mosqito_status, "metrics_requested": ["loudness", "sharpness", "roughness", "fluctuation"]},
        "reference": {"contract": "tasks/reports/runtime/s12-stage-aa/reference_diagnostic_contract.json", "r1": "MISSING", "order_gate": "NOT_QUALIFIED"},
        "human_approval": "PENDING",
        "scope": "Hellcat synthetic; uncalibrated; finalist diagnostic only",
    }


def render_report(payload: dict[str, Any], *, main_head: str) -> str:
    lines = ["# S12 Stage AA Hellcat Finalist Review", "", f"- main head: `{main_head}`", "- finalists: `AA-C1`, `AA-C2`, `AA-C3`", "- MATLAB: `MATLAB_FINALIST_RECEIPT_PENDING`", "", "| Candidate | RMS dBFS | Dynamic dB | Sharpness | Roughness | Flux | Tonality |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for candidate_id in payload["finalists"]:
        item = payload["metrics"][candidate_id]
        lines.append(f"| `{candidate_id}` | {item['loudness_rms_dbfs']:.3f} | {item['dynamic_range_db']:.3f} | {item['sharpness']:.4f} | {item['roughness']:.4f} | {item['fluctuation_proxy']:.5f} | {item['tonality']:.4f} |")
    lines.extend(["", "这些是候选 raw PCM 的工程/心理声学代理量，不是总分，也不是 Jovi 的人耳结论。R1 缺失，MATLAB session 未验证，因此这里只保留 Python 结果和显式 pending。", ""])
    return "\n".join(lines)


def publish_finalist_review(*, main_head: str, tested_head: str, command: list[str] | None = None, log_path: str | None = None, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    payload = build_finalist_review(repo_root=repo_root)
    payload["main_head"] = main_head
    payload["tested_head"] = tested_head
    output = repo_root / OUTPUT
    report = repo_root / REPORT
    write_json(output, payload)
    report.write_text(render_report(payload, main_head=main_head), encoding="utf-8", newline="\n")
    ended = datetime.now(timezone.utc)
    receipt = {"schema": "s12.stage_aa.finalist_review_receipt.v1", "status": "PASS", "main_head": main_head, "tested_head": tested_head, "output_path": str(OUTPUT).replace("\\", "/"), "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "report_path": str(REPORT).replace("\\", "/"), "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(), "finalists": list(FINALISTS), "matlab_status": payload["matlab"]["status"], "command": command or [], "started_at_utc": started.isoformat().replace("+00:00", "Z"), "ended_at_utc": ended.isoformat().replace("+00:00", "Z"), "exit_code": 0, "log_path": log_path, "log_sha256": hashlib.sha256(Path(log_path).read_bytes()).hexdigest() if log_path and Path(log_path).is_file() else None}
    write_json(repo_root / RECEIPT, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-head", required=True)
    parser.add_argument("--tested-head", required=True)
    parser.add_argument("--log-path")
    args = parser.parse_args()
    receipt = publish_finalist_review(main_head=args.main_head, tested_head=args.tested_head, log_path=args.log_path, command=sys.argv)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_finalist_review", "publish_finalist_review", "render_report"]
