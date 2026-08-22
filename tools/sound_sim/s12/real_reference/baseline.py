"""Stage R waiting-state outputs and the qualified-reference entry point."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .qualification import qualify_r1_reference, require_r1_reference


METRIC_GROUPS = (
    "order",
    "spectrum",
    "idle",
    "transient",
    "psychoacoustics",
    "human_feedback",
)


def build_stage_r_waiting_result(q_inventory: dict[str, Any]) -> dict[str, Any]:
    records = q_inventory.get("recordings", [])
    gates = [qualify_r1_reference(record) for record in records]
    return {
        "schema_version": "s12-stage-r-real-sound-difference-v1",
        "stage": "R",
        "status": "BLOCKED_REFERENCE_QUALIFICATION",
        "stop_state": "WAITING_FOR_REAL_REFERENCE_DATA",
        "reference_database_status": q_inventory.get("status"),
        "metric_groups": list(METRIC_GROUPS),
        "qualified_cases": [],
        "reference_gates": gates,
        "limitations": [
            "没有 R1 参考，因此不输出阶次资格、自动调参目标或真实性百分比。",
            "未校准 SPL 只能在 R1/R2 合同满足后做 digital-domain relative 指标。",
            "试听响度匹配副本与原始分析信号必须分离；当前未生成试听副本。",
        ],
    }


def build_stage_r_waiting_recommendations() -> dict[str, Any]:
    return {
        "schema_version": "s12-stage-r-parameter-recommendations-v1",
        "stage": "R",
        "status": "WITHHELD_MISSING_R1_REFERENCE",
        "recommendations": [],
        "reason": "在合法真实参考、同步 RPM/state 和可审计差异指标到位前，禁止生成参数方向。",
    }


def write_stage_r_waiting_outputs(q_inventory: dict[str, Any], out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / "stage_r_real_vs_synthetic_results.json"
    recommendation_path = out_dir / "stage_r_parameter_recommendations.json"
    result_path.write_text(json.dumps(build_stage_r_waiting_result(q_inventory), indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    recommendation_path.write_text(json.dumps(build_stage_r_waiting_recommendations(), indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    report = out_dir / "S12_Stage_R_Real_Sound_Difference_Report.md"
    report.write_text(
        "\n".join(
            [
                "# S12 Stage R 真实声浪差异基线报告",
                "",
                "状态：`BLOCKED_REFERENCE_QUALIFICATION / WAITING_FOR_REAL_REFERENCE_DATA`",
                "",
                "当前没有任何 R1 资格参考，因此本文件是等待态合同，不是声学差异结论。不会输出单个真实性百分比，不会把 synthetic parent 当作真实车辆，也不会生成车型参数建议。",
                "",
                "待真实资料满足 Q 门后，逐车逐工况计算：阶次、20–60/60–120/120–250/250–400/400–1000/1–4k/4–5.5k/5.5–12kHz 频带、怠速调制、换挡/收油瞬态、响度/尖锐度/粗糙度/波动度/音调，以及参考不确定性。",
                "",
                "试听副本必须与未经增益/EQ/AGC 的原始分析信号分离。R1 之前所有建议保持 `WITHHELD`。",
                "",
                "原始音频不会复制进 Git；本报告只绑定 Stage Q manifest、外部路径和 SHA-256。",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    return {"results": result_path, "recommendations": recommendation_path, "report": report}


__all__ = [
    "METRIC_GROUPS",
    "build_stage_r_waiting_recommendations",
    "build_stage_r_waiting_result",
    "require_r1_reference",
    "write_stage_r_waiting_outputs",
]
