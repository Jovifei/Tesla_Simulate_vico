"""Stage T fail-closed Profile Candidate handoff."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_stage_t_waiting_gate(q_inventory: dict[str, Any], r_result: dict[str, Any], s_gate: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "s12-stage-t-profile-candidate-gate-v1",
        "stage": "T",
        "status": "BLOCKED_PROFILE_CANDIDATE_NOT_READY",
        "profile_candidate_ready": False,
        "profile_freeze_authorized": False,
        "golden_handoff_ready": False,
        "anchor_vehicles": list(q_inventory.get("anchor_vehicles", [])),
        "required_states": {
            "stage_q": q_inventory.get("status"),
            "stage_r": r_result.get("status"),
            "stage_s": s_gate.get("status"),
        },
        "reasons": [
            "Stage Q 没有 R1 真实参考。",
            "Stage R 没有合格的真实 vs synthetic 差异基线。",
            "Stage S 没有真实 Jovi 听审 receipt。",
            "因此不生成 approved_profile_candidate，不修改 Profile，不进入产品线。",
        ],
    }


def write_stage_t_waiting_outputs(q_inventory: dict[str, Any], r_result: dict[str, Any], s_gate: dict[str, Any], out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    gate = build_stage_t_waiting_gate(q_inventory, r_result, s_gate)
    gate_path = out_dir / "stage_t_profile_candidate_gate.json"
    gate_path.write_text(json.dumps(gate, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    report_path = out_dir / "S12_Stage_T_Profile_Candidate_Handoff.md"
    report_path.write_text(
        "\n".join([
            "# S12 Stage T Profile Candidate 交接",
            "",
            "状态：`BLOCKED_PROFILE_CANDIDATE_NOT_READY`",
            "",
            "当前不生成任何 `approved_profile_candidate/` 文件，不写入 `APPROVED_PROFILE`、`PROFILE_FREEZE` 或 `PRODUCT_READY`。只有三个锚点车型完成 R1 真实参考、客观 hard gates 和真实 Jovi 听审后，才能建立候选参数包。",
            "",
            "本分支也不修改 Simulink、Runtime、Android、ESP32 或 CAN；产品交接保持关闭。",
            "",
        ]),
        encoding="utf-8",
        newline="\n",
    )
    return {"gate": gate_path, "report": report_path}


__all__ = ["build_stage_t_waiting_gate", "write_stage_t_waiting_outputs"]
