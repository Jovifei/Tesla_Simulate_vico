"""Run the four bounded Hellcat candidates and record hard/soft evidence."""

from __future__ import annotations

from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable

import numpy as np

from ..stage_v.io import write_json
from ..stage_x.multi_reference_comparator import raw_dynamic_metrics, timbre_metrics
from ..stage_z.method_ablation import render_parent_scene
from .candidates import CANDIDATES, SCENE_NAMES, candidate_metrics, render_candidate, validate_candidate_gates
from .energy_budget import _band_metrics


REPO_ROOT = Path(__file__).resolve().parents[5]
OUTPUT = Path("tasks/reports/runtime/s12-stage-aa/candidate_audit.json")
REPORT = Path("tasks/reports/runtime/s12-stage-aa/candidate_review.md")
RECEIPT = Path("tasks/reports/runtime/s12-stage-aa/receipts/aa4-candidates.json")
DEFAULT_SCENES = ("hot_idle", "steady_1200", "steady_2000", "steady_3000", "tip_in", "full_load", "gear_shift", "lift", "afterfire", "idle_return", "complete_cycle")


def _parent_scene_name(scene: str) -> str:
    return SCENE_NAMES.get(scene, scene)


def _parent_metrics(scene: str, duration_s: float) -> dict[str, Any]:
    parent, _parent_raw, _parent_monitor = render_parent_scene(_parent_scene_name(scene), duration_s)
    dynamic = raw_dynamic_metrics(parent, 48000)
    timbre = timbre_metrics(np.mean(parent, axis=1), 48000)
    return {**{key: float(value) for key, value in dynamic.items() if key != "note"}, "spectral_centroid_hz": float(timbre["spectral_centroid_hz"]), "spectral_flux": float(timbre["spectral_flux"]), "roughness_proxy": float(timbre["roughness_proxy"]), "sharpness_proxy": float(timbre["sharpness_proxy"]), "tonality_proxy": float(timbre["tonality_proxy"]), "persistent_tone_ratio": float(timbre["persistent_tone_ratio"]), "low_frequency_body": float(_band_metrics(parent)["20_80_hz"]["power_share"] + _band_metrics(parent)["120_250_hz"]["power_share"] + _band_metrics(parent)["250_400_hz"]["power_share"])}


def _candidate_soft_dimensions(metrics: dict[str, Any], parent: dict[str, Any]) -> dict[str, float]:
    return {
        "idle_body": abs(metrics["low_frequency_body"] - parent["low_frequency_body"]),
        "low_frequency_pressure": abs(metrics["spectral_centroid_hz"] - parent["spectral_centroid_hz"]),
        "dynamic_range_error": abs(metrics["dynamic_range_db"] - parent["dynamic_range_db"]),
        "persistent_tone_penalty": max(0.0, metrics["persistent_tone_ratio"] - parent["persistent_tone_ratio"]),
        "mechanical_texture": abs(metrics["roughness_proxy"] - parent["roughness_proxy"]),
        "synthetic_artifact": max(0.0, metrics["sharpness_proxy"] - parent["sharpness_proxy"]),
        "rms_error_db": abs(metrics["rms_dbfs"] - parent["rms_dbfs"]),
    }


def _dominates(left: dict[str, float], right: dict[str, float]) -> bool:
    keys = tuple(left)
    return all(left[key] <= right[key] for key in keys) and any(left[key] < right[key] for key in keys)


def build_candidate_audit(*, duration_s: float = 1.0, scenes: Iterable[str] = DEFAULT_SCENES) -> dict[str, Any]:
    selected = tuple(scenes)
    candidate_records: list[dict[str, Any]] = []
    for spec in CANDIDATES:
        print(f"[AA4] candidate {spec.candidate_id}", flush=True)
        scene_records = []
        for scene in selected:
            candidate = render_candidate(spec.candidate_id, scene, duration_s)
            parent = _parent_metrics(scene, duration_s)
            metrics = candidate_metrics(candidate)
            metrics["low_frequency_body"] = float(sum(_band_metrics(candidate.raw_pcm)[name]["power_share"] for name in ("20_80_hz", "120_250_hz", "250_400_hz")))
            scene_records.append({"scene": scene, "raw_pcm_sha256": hashlib.sha256(candidate.raw_pcm.tobytes()).hexdigest(), "monitor_pcm_sha256": hashlib.sha256(candidate.monitor_pcm.tobytes()).hexdigest(), "metrics": metrics, "parent_metrics": parent, "soft_dimensions": _candidate_soft_dimensions(metrics, parent), "hard_gates": validate_candidate_gates(candidate), "parameter_consumed": candidate.parameter_consumed})
        candidate_records.append({"candidate_id": spec.candidate_id, "hypothesis": spec.hypothesis, "local_parameter_family": spec.local_parameter_family, "scenes": scene_records, "hard_gates": {"passed": all(item["hard_gates"]["passed"] for item in scene_records), "global_gain_changed": spec.global_gain_changed, "fixed_tone_filler": spec.fixed_tone_filler}, "global_gain_changed": spec.global_gain_changed, "fixed_tone_filler": spec.fixed_tone_filler})
    soft_by_candidate = {item["candidate_id"]: {key: float(np.mean([scene["soft_dimensions"][key] for scene in item["scenes"]])) for key in item["scenes"][0]["soft_dimensions"]} for item in candidate_records}
    frontier = [candidate_id for candidate_id, dimensions in soft_by_candidate.items() if not any(_dominates(other, dimensions) for other_id, other in soft_by_candidate.items() if other_id != candidate_id)]
    diagnostic_preference = min(frontier, key=lambda candidate_id: (soft_by_candidate[candidate_id]["rms_error_db"], soft_by_candidate[candidate_id]["dynamic_range_error"], soft_by_candidate[candidate_id]["low_frequency_pressure"]))
    return {"schema": "s12.stage_aa.candidate_audit.v1", "status": "DIAGNOSTIC_ONLY", "candidate_ids": [item.candidate_id for item in CANDIDATES], "duration_s": float(duration_s), "scenes": list(selected), "candidates": candidate_records, "soft_dimensions_mean": soft_by_candidate, "pareto_frontier": frontier, "diagnostic_preference": diagnostic_preference, "candidate_boundary": {"hellcat_only": True, "master_gain": False, "ptr_radiation_track_p": "UNCHANGED", "human_acceptance": "PENDING"}}


def render_candidate_report(payload: dict[str, Any], *, main_head: str) -> str:
    lines = ["# S12 Stage AA Hellcat 有界候选复核", "", f"- main head: `{main_head}`", "- status: `DIAGNOSTIC_ONLY`", "- 候选数量：4（AA-C0…AA-C3）", "", "| Candidate | Hard gates | Pareto | Diagnostic preference |", "| --- | --- | --- | --- |"]
    for item in payload["candidates"]:
        lines.append(f"| `{item['candidate_id']}` | `{item['hard_gates']['passed']}` | `{item['candidate_id'] in payload['pareto_frontier']}` | `{item['candidate_id'] == payload['diagnostic_preference']}` |")
    lines.extend(["", "## 解释", "", "AA-C1 只使用负载相关的 pressure-AC 局部缩放；AA-C2 在其上加入 event-derived 120–400 Hz body；AA-C3 仅抑制 forced-induction 的高频 carrier。三者都不修改 master gain、PTR、Radiation 或 Track-P。", "", "`diagnostic_preference` 只是进入 v3 试听的工程候选，不是人耳验收或 Profile Freeze 决策；所有软指标仍受 R1 缺失限制。", ""])
    return "\n".join(lines)


def publish_candidate_audit(*, main_head: str, tested_head: str, duration_s: float = 1.0, log_path: str | None = None, command: list[str] | None = None, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    payload = build_candidate_audit(duration_s=duration_s)
    payload["main_head"] = main_head
    payload["tested_head"] = tested_head
    output = repo_root / OUTPUT
    report = repo_root / REPORT
    write_json(output, payload)
    report.write_text(render_candidate_report(payload, main_head=main_head), encoding="utf-8", newline="\n")
    ended = datetime.now(timezone.utc)
    receipt = {"schema": "s12.stage_aa.candidate_audit_receipt.v1", "status": "PASS" if all(item["hard_gates"]["passed"] for item in payload["candidates"]) else "REJECTED_CANDIDATE_PRESENT", "main_head": main_head, "tested_head": tested_head, "output_path": str(OUTPUT).replace("\\", "/"), "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "report_path": str(REPORT).replace("\\", "/"), "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(), "candidate_count": len(payload["candidates"]), "diagnostic_preference": payload["diagnostic_preference"], "command": command or [], "started_at_utc": started.isoformat().replace("+00:00", "Z"), "ended_at_utc": ended.isoformat().replace("+00:00", "Z"), "exit_code": 0, "log_path": log_path, "log_sha256": hashlib.sha256(Path(log_path).read_bytes()).hexdigest() if log_path and Path(log_path).is_file() else None}
    write_json(repo_root / RECEIPT, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-head", required=True)
    parser.add_argument("--tested-head", required=True)
    parser.add_argument("--duration-s", type=float, default=1.0)
    parser.add_argument("--log-path")
    args = parser.parse_args()
    receipt = publish_candidate_audit(main_head=args.main_head, tested_head=args.tested_head, duration_s=args.duration_s, log_path=args.log_path, command=sys.argv)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_candidate_audit", "publish_candidate_audit", "render_candidate_report"]
