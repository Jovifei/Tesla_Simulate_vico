"""Raw dynamic review contract for the Stage AA v3 package."""

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
PACKAGE_OBJECTIVE = Path("E:/Tesla_speed/review_packages/s12-stage-aa-hellcat-quality-v3/objective_before_after_v3.json")
OUTPUT = Path("tasks/reports/runtime/s12-stage-aa/raw_dynamic_contract.json")
RECEIPT = Path("tasks/reports/runtime/s12-stage-aa/receipts/aa6-raw-dynamic-contract.json")


def _variant_metrics(rows: list[dict[str, Any]], name: str) -> dict[str, Any]:
    by_scene = {row["scene"]: row[name] for row in rows}
    hot = by_scene["hot_idle"]
    wot = by_scene["full_load"]
    steady = by_scene["steady_1200"]
    tip = by_scene["tip_in"]
    shift = by_scene["gear_shift"]
    lift = by_scene["lift"]
    idle_return = by_scene["idle_return"]
    return {
        "idle_to_wot_rms_delta": float(wot["rms_dbfs"] - hot["rms_dbfs"]),
        "idle_to_wot_peak_delta": float(wot["peak_dbfs"] - hot["peak_dbfs"]),
        "tip_in_attack": float(tip["rms_dbfs"] - steady["rms_dbfs"]),
        "shift_attack": float(shift["transient_event_density_per_s"]),
        "lift_decay": float(lift["rms_dbfs"] - wot["rms_dbfs"]),
        "idle_return_time": float(idle_return.get("transient_event_density_per_s", 0.0)),
        "loudness_matching": False,
        "source_domain": "published raw PCM; no fast AGC, whole-cycle equalization or loudness flattening",
    }


def build_raw_dynamic_contract(*, package_objective: Path | None = None) -> dict[str, Any]:
    objective_path = package_objective or (REPO_ROOT / PACKAGE_OBJECTIVE)
    objective = json.loads(objective_path.read_text(encoding="utf-8"))
    rows = objective["rows"]
    return {
        "schema": "s12.stage_aa.raw_dynamic_contract.v1",
        "status": "DIAGNOSTIC_ONLY",
        "package_objective": str(PACKAGE_OBJECTIVE).replace("\\", "/"),
        "loudness_matching": False,
        "variants": {name: _variant_metrics(rows, name) for name in ("parent", "stage_z_final", "aa_c3")},
        "definitions": {
            "idle_to_wot_rms_delta": "full_load.rms_dbfs - hot_idle.rms_dbfs",
            "idle_to_wot_peak_delta": "full_load.peak_dbfs - hot_idle.peak_dbfs",
            "tip_in_attack": "tip_in.rms_dbfs - steady_1200.rms_dbfs",
            "shift_attack": "gear_shift.transient_event_density_per_s",
            "lift_decay": "lift.rms_dbfs - full_load.rms_dbfs",
            "idle_return_time": "idle_return transient-event proxy; exact time requires synchronized capture",
        },
        "boundaries": {"r1_reference": "MISSING", "order_gate": "NOT_QUALIFIED", "monitor_excluded": True, "global_gain": False},
    }


def publish_raw_dynamic_contract(*, main_head: str, tested_head: str, command: list[str] | None = None, log_path: str | None = None, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    payload = build_raw_dynamic_contract()
    payload["main_head"] = main_head
    payload["tested_head"] = tested_head
    output = repo_root / OUTPUT
    write_json(output, payload)
    ended = datetime.now(timezone.utc)
    receipt = {"schema": "s12.stage_aa.raw_dynamic_contract_receipt.v1", "status": "PASS", "main_head": main_head, "tested_head": tested_head, "output_path": str(OUTPUT).replace("\\", "/"), "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "command": command or [], "started_at_utc": started.isoformat().replace("+00:00", "Z"), "ended_at_utc": ended.isoformat().replace("+00:00", "Z"), "exit_code": 0, "log_path": log_path, "log_sha256": hashlib.sha256(Path(log_path).read_bytes()).hexdigest() if log_path and Path(log_path).is_file() else None}
    write_json(repo_root / RECEIPT, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-head", required=True)
    parser.add_argument("--tested-head", required=True)
    parser.add_argument("--log-path")
    args = parser.parse_args()
    receipt = publish_raw_dynamic_contract(main_head=args.main_head, tested_head=args.tested_head, log_path=args.log_path, command=sys.argv)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_raw_dynamic_contract", "publish_raw_dynamic_contract"]
