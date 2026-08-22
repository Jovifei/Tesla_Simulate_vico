"""Waiting-state final report for the S12 Q–T closed loop."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def render_waiting_final_report(
    q_inventory: dict[str, Any],
    r_result: dict[str, Any],
    s_gate: dict[str, Any],
    t_gate: dict[str, Any],
    *,
    branch: str,
    commit: str,
    working_tree_dirty: bool,
    pushed: bool = False,
    remote_sha: str | None = None,
) -> str:
    lines = [
        "# S12 真实声浪闭环总报告",
        "",
        "状态：`WAITING_FOR_REAL_REFERENCE_DATA`",
        "",
        "> 本报告是当前 HEAD 的等待态审计，不是“本地声浪与真实声浪比较、反馈和调优闭环已完成”的声明。",
        "",
        "## 阶段状态",
        "",
        "| 阶段 | 当前状态 | 已完成内容 | 未完成内容 |",
        "| --- | --- | --- | --- |",
        f"| Q 真实参考 | `{q_inventory.get('status')}` | 15 条候选和未登记媒体已登记，保留路径/SHA/格式/缺口 | 合法授权、R1 元数据和同步 RPM/state |",
        f"| R 差异基线 | `{r_result.get('status')}` | R1/R2 资格门、报告模板和 withheld 推荐 | 未运行合格真实比较 |",
        f"| S 反馈调音 | `{s_gate.get('status')}` | 中文听审合同和 SHA/file-ID 绑定合同 | 没有真实 Jovi 听审和调音轮次 |",
        f"| T Profile Candidate | `{t_gate.get('status')}` | Profile Candidate 阻断门和交接模板 | 没有候选参数包或产品交接 |",
        "",
        "## 八车型与工况",
        "",
        "当前八车型全部没有 R1 资格；已有文件只能作为未授权/未对齐候选，不能进入自动调参。",
        "",
        "| 车型 | 已登记候选 | R1 | 可资格指标 |",
        "| --- | ---: | ---: | --- |",
    ]
    for vehicle in q_inventory.get("evidence_matrix", {}).get("vehicles", []):
        lines.append(
            f"| {vehicle['vehicle_name_zh']} | {vehicle['recording_count']} | {vehicle['r1_eligible_count']} | 无；待授权和状态绑定 |"
        )
    lines.extend(
        [
            "",
            "已识别的工况提示包括 idle、steady/acceleration、full_pull、shift、lift/afterfire 等；当前窗口均为文件名或旧注释推断，未达到场景资格。",
            "",
            "## 指标与人耳边界",
            "",
            "- 阶次 / Order-RPM：`NOT_QUALIFIED`，没有同步 RPM。",
            "- 频谱、响度、心理声学：当前没有授权 R2；不复用旧报告数字。",
            "- 瞬态：没有同步 Gear/shift/state；不进入自动门。",
            "- 人耳：真实 Jovi 反馈行数为 0；Stage P fixture 不算人耳反馈。",
            "- 真实性百分比：禁止输出。",
            "",
            "## 调音与交接",
            "",
            "- 调音轮次：0。",
            "- 车型 source/profile 参数修改：0。",
            "- `approved_profile_candidate/`：未生成。",
            "- Profile Freeze：未授权。",
            "- Simulink、Runtime、Android、ESP32、CAN、实车部署：未进入。",
            "- Track-P：按边界未修改。",
            "",
            "## 当前提交与 Git 状态",
            "",
            f"- 分支：`{branch}`",
            f"- 报告绑定代码提交：`{commit}`",
            f"- working tree dirty：`{str(working_tree_dirty).lower()}`",
            f"- push：{'是' if pushed else '否'}",
            *( [f"- 远端分支 SHA：`{remote_sha}`"] if remote_sha else [] ),
            "- merge：否",
            "- PR：否",
            "",
            "## 必须补齐的输入",
            "",
            "1. 合法可使用的真实车辆原始录音；",
            "2. 精确车型/配置/原厂状态、场景和麦克风位置；",
            "3. 同步 RPM、Load/Throttle、Gear/shift、时间窗口；",
            "4. 采样率、通道、设备和 AGC/后处理合同；",
            "5. 真实 Jovi 中文听审结果及播放元数据。",
            "",
            "所有产物继续声明：`synthetic`、`uncalibrated`、`vehicle-inspired`、`not OEM reproduction`。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_waiting_final_report(
    q_inventory: dict[str, Any],
    r_result: dict[str, Any],
    s_gate: dict[str, Any],
    t_gate: dict[str, Any],
    path: Path,
    *,
    branch: str,
    commit: str,
    working_tree_dirty: bool,
    pushed: bool = False,
    remote_sha: str | None = None,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_waiting_final_report(
            q_inventory,
            r_result,
            s_gate,
            t_gate,
            branch=branch,
            commit=commit,
            working_tree_dirty=working_tree_dirty,
            pushed=pushed,
            remote_sha=remote_sha,
        ),
        encoding="utf-8",
        newline="\n",
    )
    return path


__all__ = ["render_waiting_final_report", "write_waiting_final_report"]
