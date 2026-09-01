"""Combine AA energy, objective and reference evidence into Hellcat hypotheses."""

from __future__ import annotations

from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from ..stage_v.io import write_json
from .reference_contract import build_reference_diagnostic_contract


REPO_ROOT = Path(__file__).resolve().parents[5]
ENERGY_PATH = Path("tasks/reports/runtime/s12-stage-aa/energy_budget_trace.json")
OBJECTIVE_PATH = Path("tasks/reports/runtime/s12-stage-z/objective_before_after.json")
OUTPUT = Path("tasks/reports/runtime/s12-stage-aa/hellcat_root_cause.json")
REPORT = Path("tasks/reports/runtime/s12-stage-aa/hellcat_root_cause.md")
RECEIPT = Path("tasks/reports/runtime/s12-stage-aa/receipts/aa3-hellcat-root-cause.json")


def _load(repo_root: Path, path: Path) -> Any:
    return json.loads((repo_root / path).read_text(encoding="utf-8"))


def _mean_band(layers: Any, layer: str, names: tuple[str, ...]) -> float:
    values = []
    for scene in layers.values():
        bands = scene["layers"][layer]["bands"]
        values.append(sum(float(bands[name]["power_share"]) for name in names))
    return float(sum(values) / max(len(values), 1))


def build_hellcat_root_cause_report(*, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    energy = _load(repo_root, ENERGY_PATH)
    objective = _load(repo_root, OBJECTIVE_PATH)
    reference = build_reference_diagnostic_contract(repo_root=repo_root)
    scenes = energy["scenes"]
    full = scenes["full_load"]["layers"]
    pre = full["pre_transients"]
    dp = full["dp_dc"]
    post = full["post_ptr_raw"]
    afterfire_diag = scenes["afterfire"]["diagnostics"]["engine"]
    aggregate = objective["aggregate"]
    findings = [
        {
            "id": "low_frequency_body",
            "severity": "HIGH",
            "hypothesis": "absolute event pressure baseline dominates the source; DC/dP removes most of the body before PTR",
            "evidence": {"full_load_pre_transients_dc_mean": pre["dc_mean"], "full_load_pre_transients_ac_rms": pre["ac_rms"], "full_load_dp_dc_rms_dbfs": dp["rms_dbfs"], "mean_20_80_share_pre_transients": _mean_band(scenes, "pre_transients", ("20_80_hz",)), "mean_20_80_share_post_ptr": _mean_band(scenes, "post_ptr_raw", ("20_80_hz",))},
            "next_test": "event-derived AC pressure/body repair; do not add a master gain",
        },
        {
            "id": "pressure_120_400",
            "severity": "HIGH",
            "hypothesis": "the desired pressure attack exists in the source but is attenuated by the pressure chain rather than created by post-EQ",
            "evidence": {"full_load_120_400_share_pre_transients": sum(pre["bands"][name]["power_share"] for name in ("120_250_hz", "250_400_hz")), "full_load_120_400_share_dp_dc": sum(dp["bands"][name]["power_share"] for name in ("120_250_hz", "250_400_hz")), "full_load_dp_dc_rms_dbfs": dp["rms_dbfs"]},
            "next_test": "bounded source/event pressure propagation with 120–400 Hz and click guards",
        },
        {
            "id": "blower_tonal_artifact",
            "severity": "MEDIUM",
            "hypothesis": "forced-induction/high-band content becomes disproportionately dominant after the pressure/PTR stages",
            "evidence": {"aggregate_centroid_parent_hz": aggregate["spectral_centroid_hz"]["parent"], "aggregate_centroid_final_hz": aggregate["spectral_centroid_hz"]["final"], "aggregate_persistent_tone_parent": aggregate["persistent_tone_ratio"]["parent"], "aggregate_persistent_tone_final": aggregate["persistent_tone_ratio"]["final"], "full_load_post_ptr_4_8k_share": post["bands"]["4000_8000_hz"]["power_share"]},
            "next_test": "reduce carrier dominance only through load-linked sideband/broadband hypotheses; no fixed-tone filler",
        },
        {
            "id": "dynamic_range",
            "severity": "HIGH",
            "hypothesis": "raw dynamic contrast is lost by pressure/PTR attenuation and is not a monitor-only issue",
            "evidence": {"aggregate_dynamic_range_parent_db": aggregate["dynamic_range_db"]["parent"], "aggregate_dynamic_range_final_db": aggregate["dynamic_range_db"]["final"], "aggregate_rms_parent_dbfs": aggregate["rms_dbfs"]["parent"], "aggregate_rms_final_dbfs": aggregate["rms_dbfs"]["final"]},
            "next_test": "compare idle-to-WOT raw contract before/after every candidate",
        },
        {
            "id": "afterfire_naturalness",
            "severity": "MEDIUM",
            "hypothesis": "afterfire scheduling is present, but its audible naturalness cannot be inferred from event count alone",
            "evidence": {"afterfire_event_count": afterfire_diag["afterfire_event_count"], "afterfire_route": afterfire_diag.get("afterfire_route"), "reference_status": reference["r1_status"]},
            "next_test": "preserve eligibility/latch and assess afterfire tail in the dynamic candidate package",
        },
    ]
    return {
        "schema": "s12.stage_aa.hellcat_root_cause.v1",
        "status": "DIAGNOSTIC_ONLY",
        "vehicle": "hellcat",
        "primary_root_cause": "PRESSURE_BASELINE_REMOVAL_PLUS_FROZEN_PTR_ATTENUATION",
        "parameter_changes_applied": False,
        "energy_trace": str(ENERGY_PATH).replace("\\", "/"),
        "objective": str(OBJECTIVE_PATH).replace("\\", "/"),
        "reference_contract": {"path": "tasks/reports/runtime/s12-stage-aa/reference_diagnostic_contract.json", "r1_status": reference["r1_status"], "order_gate": reference["order_gate"]},
        "findings": findings,
        "candidate_boundary": {"hellcat_only": True, "master_gain": False, "ptr_radiation_track_p": "UNCHANGED", "r1": "MISSING"},
    }


def render_report(payload: dict[str, Any], *, main_head: str) -> str:
    lines = ["# S12 Stage AA Hellcat 根因报告", "", f"- main head: `{main_head}`", "- status: `DIAGNOSTIC_ONLY`", "- parameter changes applied: `false`", "", "| Finding | Severity | Hypothesis | Next bounded test |", "| --- | --- | --- | --- |"]
    for item in payload["findings"]:
        lines.append(f"| `{item['id']}` | {item['severity']} | {item['hypothesis']} | {item['next_test']} |")
    lines.extend(["", "## 结论", "", "Energy ledger 将问题定位为压力绝对基线主导：dP/DC 去掉大部分 body，随后 frozen PTR 继续施加固定衰减。候选只能在 event/pressure propagation、局部 source-layer balance、transient 或明确 monitor contract 内验证；不得用 master gain 恢复数字 RMS。", "", "Reference 仍为 R2/R3 diagnostic，未提供同步 RPM/state 的 R1；因此任何方向判断都保持诊断性，不能生成 OEM、Profile Freeze 或 Human PASS。", ""])
    return "\n".join(lines)


def publish_hellcat_root_cause(*, main_head: str, tested_head: str, command: list[str] | None = None, log_path: str | None = None, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    payload = build_hellcat_root_cause_report(repo_root=repo_root)
    payload["main_head"] = main_head
    payload["tested_head"] = tested_head
    output = repo_root / OUTPUT
    report = repo_root / REPORT
    write_json(output, payload)
    report.write_text(render_report(payload, main_head=main_head), encoding="utf-8", newline="\n")
    ended = datetime.now(timezone.utc)
    receipt = {"schema": "s12.stage_aa.hellcat_root_cause_receipt.v1", "status": "PASS", "main_head": main_head, "tested_head": tested_head, "output_path": str(OUTPUT).replace("\\", "/"), "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "report_path": str(REPORT).replace("\\", "/"), "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(), "command": command or [], "started_at_utc": started.isoformat().replace("+00:00", "Z"), "ended_at_utc": ended.isoformat().replace("+00:00", "Z"), "exit_code": 0, "log_path": log_path, "log_sha256": hashlib.sha256(Path(log_path).read_bytes()).hexdigest() if log_path and Path(log_path).is_file() else None, "primary_root_cause": payload["primary_root_cause"]}
    write_json(repo_root / RECEIPT, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-head", required=True)
    parser.add_argument("--tested-head", required=True)
    parser.add_argument("--log-path")
    args = parser.parse_args()
    receipt = publish_hellcat_root_cause(main_head=args.main_head, tested_head=args.tested_head, log_path=args.log_path, command=sys.argv)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_hellcat_root_cause_report", "publish_hellcat_root_cause", "render_report"]
