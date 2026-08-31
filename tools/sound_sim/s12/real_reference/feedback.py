"""Stage S Chinese listening-study contract, without placeholder audio."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CHINESE_DIMENSIONS = {
    "vehicle_identity": "车型身份",
    "realism": "真实感",
    "low_frequency_weight": "低频重量",
    "mechanical_character": "机械感",
    "idle_life": "怠速生命感",
    "acceleration_aggression": "加速攻击性",
    "shift_realism": "换挡真实感",
    "afterfire_naturalness": "回火自然度",
    "synthetic_artifact_freedom": "合成器感/伪影少",
    "preference": "偏好",
    "identity_guess": "车型猜测",
}


def build_stage_s_chinese_contract(q_inventory: dict[str, Any], r_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "s12-stage-s-chinese-listening-contract-v1",
        "stage": "S",
        "locale": "zh-CN",
        "status": "WAITING_FOR_REAL_REFERENCE_DATA",
        "study_type": "webMUSHRA_or_AB",
        "vehicle_scope": list(q_inventory.get("anchor_vehicles", [])),
        "ui_text": {
            "test_name": "S12 真实声浪对比与调音听审",
            "playback_level": "请先设置舒适且不失真的播放音量。不要使用系统响度增强、均衡器或自动增益。",
            "instruction": "请在相同工况和循环区间内比较匿名声音。当前结果只有在真实参考、候选 SHA 和听审元数据绑定后才有效。",
            "finish": "提交前请确认听者编号、播放设备、系统音量、输出端点和系统音效设置。",
        },
        "dimensions": [{"id": key, "label_zh": label, "scale": [0, 25, 50, 75, 100]} for key, label in CHINESE_DIMENSIONS.items()],
        "feedback_binding": {
            "required": [
                "package_sha256",
                "test_id",
                "file_id",
                "candidate_sha256",
                "listener_id",
                "playback_device",
                "windows_volume",
                "playback_endpoint",
                "system_audio_effects",
            ],
            "fixture_is_human_feedback": False,
            "synthetic_reference_is_real_reference": False,
        },
        "audio_materialization": {
            "status": "NOT_MATERIALIZED",
            "reason": "Stage Q 没有 R1 真实参考；禁止生成占位音频或把 synthetic parent 当作真实参考。",
            "analysis_signal": "unaltered_analysis_signal",
            "audition_signal": "loudness_matched_audition_signal_separate",
        },
        "upstream_ui_note": "研究包导出器会附带 webmushra_zh_cn_nls.js，并提供幂等脚本把它加载到官方 nls.js 之后；应用覆盖前，固定按钮仍不能声称为中文。",
        "ui_localization_status": "PACKAGE_CONFIG_ZH_CN_AND_UPSTREAM_NLS_PATCH_AVAILABLE",
        "r_status": r_result.get("status"),
    }


def write_stage_s_waiting_outputs(q_inventory: dict[str, Any], r_result: dict[str, Any], out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    contract = build_stage_s_chinese_contract(q_inventory, r_result)
    contract_path = out_dir / "stage_s_chinese_listening_contract.json"
    gate_path = out_dir / "stage_s_feedback_gate.json"
    contract_path.write_text(json.dumps(contract, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    gate_path.write_text(json.dumps({
        "schema_version": "s12-stage-s-feedback-gate-v1",
        "stage": "S",
        "status": "WAITING_FOR_JOVI_HUMAN_FEEDBACK",
        "real_reference_status": q_inventory.get("status"),
        "feedback_rows": 0,
        "parameter_changes": 0,
        "profile_candidate_ready": False,
        "reason": "真实参考和真实 Jovi 听审均未到位；当前不读取、不生成、不提升任何反馈内容。",
    }, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    report_path = out_dir / "S12_Stage_S_Human_Calibration_Report.md"
    report_path.write_text(
        "\n".join([
            "# S12 Stage S 反馈驱动调音报告",
            "",
            "状态：`WAITING_FOR_REAL_REFERENCE_DATA` / `WAITING_FOR_JOVI_HUMAN_FEEDBACK`",
            "",
            "已建立中文听审合同，但没有生成占位音频，也没有把 Stage P fixture 结果当作真实反馈。正式 webMUSHRA/A-B 包必须绑定 Stage Q 的合法真实参考、Stage R 的候选 SHA 和完整播放元数据。",
            "",
            "一次只允许修改一个车型、一个场景问题和一个参数组；自动指标改善且人耳不退步后，才能进入下一轮。所有调音都必须在独立 sound-fix 分支进行，当前分支不修改车型 source。",
            "",
            "中文评分维度已写入 `stage_s_chinese_listening_contract.json`。正式研究包会附带 `webmushra_zh_cn_nls.js` 和幂等应用脚本；未应用该覆盖前，不能声称上游固定按钮已全中文。",
            "",
        ]),
        encoding="utf-8",
        newline="\n",
    )
    return {"contract": contract_path, "gate": gate_path, "report": report_path}


__all__ = ["CHINESE_DIMENSIONS", "build_stage_s_chinese_contract", "write_stage_s_waiting_outputs"]
