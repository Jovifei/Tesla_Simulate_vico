"""S12 Phase 1 - generate the reference database index and update feature targets.

Reads the three per-vehicle reference_targets.json files, writes a human-readable
index document, and upgrades realism_feature_targets.json with the full metric set.
"""

from __future__ import annotations

import json
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "reference_database"
TARGETS = Path(__file__).resolve().parent.parent / "targets" / "realism_feature_targets.json"

VEHICLES = [
    ("ferrari_458", "Ferrari 458 Italia", "ferrari_458_reference_targets.json"),
    ("rx7_fd", "Mazda RX-7 FD (13B-REW)", "rx7_fd_reference_targets.json"),
    ("hellcat", "Dodge Challenger SRT Hellcat", "hellcat_reference_targets.json"),
]

CHARACTER = {
    "ferrari_458": "clean naturally aspirated flat-plane V8 attack that becomes increasingly metallic and high-order at high RPM",
    "rx7_fd": "non-piston rotary event texture with turbo inertia, boost onset, and release",
    "hellcat": "large-displacement low-frequency exhaust pressure plus boost/load-dependent mechanical whine",
}


def _seg_metrics(ref: dict, seg: str) -> dict:
    sm = ref["stock_median"]
    result: dict[str, object] = {"band_shares": sm.get(f"{seg}_band_shares", [])}
    for m in [
        "spectral_flux", "modulation_depth", "modulation_peak_hz", "modulation_energy",
        "pulse_amplitude_cv", "pulse_interval_cv", "crest_factor", "dropout_ratio",
        "spectral_centroid_hz",
    ]:
        result[m] = sm.get(f"{seg}_{m}", 0.0)
    return result


def build_index() -> str:
    lines = [
        "# S12 真实录音参考数据库索引 v1",
        "",
        "> Phase 1 产物。从外部 R2 真实录音提取的相对特征，用于驱动 Phase 2-5 声学真实度优化。",
        "> 边界：synthetic; uncalibrated; not OEM reproduction。原始音轨不入库，仅保存派生数值。",
        "> 所有指标随录音设备/AGC/距离/改装而变，仅作相对方向参考。",
        "",
        "## 提取指标（对齐 Hellcat v6 reference_targets schema）",
        "",
        "| 指标 | 含义 |",
        "| --- | --- |",
        "| band_shares | 4 段能量占比 [20-250, 250-1000, 1k-4k, 4k-12k] Hz |",
        "| spectral_flux | 相邻 STFT 帧正谱差均值（瞬态变化强度）|",
        "| modulation_depth | 包络 AC_rms/DC（燃烧脉冲周期性强度，0-1）|",
        "| modulation_peak_hz | 5-500Hz 包络主调制频率（燃烧脉冲基频）|",
        "| pulse_amplitude_cv | 检测脉冲幅度变异系数 |",
        "| pulse_interval_cv | 检测脉冲间隔变异系数 |",
        "| crest_factor | 峰值/RMS |",
        "| dropout_ratio | 低于静默阈值的帧占比 |",
        "",
        "## 三车型 stock_median 聚合目标",
        "",
    ]

    for vid, name, fname in VEHICLES:
        ref = json.loads((DB / fname).read_text(encoding="utf-8"))
        sm = ref["stock_median"]
        n_src = len(ref["sources"])
        lines.append(f"### {name} ({vid}) — {n_src} 条录音")
        lines.append("")
        lines.append(f"声学身份：{CHARACTER[vid]}")
        lines.append("")
        lines.append("| 工况 | 20-250Hz | 250-1kHz | 1-4kHz | 4-12kHz | flux | mod_depth | mod_peak | crest | pulse_amp_cv |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for seg in ["idle", "acceleration", "afterfire"]:
            m = _seg_metrics(ref, seg)
            b = m["band_shares"]
            peak_key = "idle_modulation_peak_hz" if seg == "idle" else f"{seg}_modulation_peak_hz"
            peak = sm.get(peak_key, 0.0)
            lines.append(
                f"| {seg} | {b[0]:.3f} | {b[1]:.3f} | {b[2]:.3f} | {b[3]:.3f} | "
                f"{m['spectral_flux']:.4f} | {m['modulation_depth']:.3f} | {peak:.0f}Hz | "
                f"{m['crest_factor']:.2f} | {m['pulse_amplitude_cv']:.3f} |"
            )
        lines.append("")
        lines.append(f"录音来源：")
        for s in ref["sources"]:
            lines.append(f"- `{s['id']}` [{s['setup']}]({s['url']})")
        lines.append("")

    lines.extend([
        "## 三车型声学身份差异（数值证据）",
        "",
        "| 维度 | Ferrari 458 | Hellcat | RX-7 FD |",
        "| --- | --- | --- | --- |",
        "| 加速低频(20-250Hz)占比 | 中（0.356）| 中高（0.484）| 极高（0.936）|",
        "| 加速高频(1-4kHz)占比 | 低（0.068）| 极低（0.003）| 极低（0.002）|",
        "| 加速调制深度 | 高（0.791）| 中（0.484）| 中（0.643）|",
        "| 加速调制峰频 | 71Hz（V8 燃烧）| 81Hz（V8 燃烧）| 59Hz（转子）|",
        "| 回火高频占比 | 高（0.183）| 极低（0.005）| 极低（0.003）|",
        "| 怠速谱重心 | 980Hz（高频金属）| 290Hz（低频机械）| 156Hz（低频转子）|",
        "",
        "**身份方向结论**：",
        "- Ferrari：中频为主 + 加速高频增长 + 回火中高频瞬态 → 高转 NA V8 金属尖叫方向",
        "- Hellcat：低频+中频双峰 + 中等调制 + 低 crest → 大排量 V8 低频重量 + 机械增压方向",
        "- RX-7：极低频主导 + 转子调制 59Hz + 低 crest → 转子时间结构 + 涡轮方向",
        "",
        "## 文件清单",
        "",
        "| 文件 | 内容 |",
        "| --- | --- |",
        "| `ferrari_458_reference_targets.json` | Ferrari 458 完整参考目标 + stock_median |",
        "| `rx7_fd_reference_targets.json` | RX-7 FD 完整参考目标 + stock_median |",
        "| `hellcat_reference_targets.json` | Hellcat 三录音完整参考目标 + stock_median |",
        "| `reference_database_build_summary.json` | 构建摘要 |",
        "| `vehicle_records.json` | 三车型拓扑 + 公开视频定性观察（原有）|",
        "| `vehicle_sound_character_matrix.md` | 声学特征矩阵（原有）|",
    ])
    return "\n".join(lines) + "\n"


def update_feature_targets() -> None:
    targets = json.loads(TARGETS.read_text(encoding="utf-8"))
    for vid, _name, fname in VEHICLES:
        ref = json.loads((DB / fname).read_text(encoding="utf-8"))
        sm = ref["stock_median"]
        new_features = {
            "provenance": "B/R2 extracted from external recording; microphone/AGC/configuration dependent; full metric set v1",
            "schema": "s12.realism_feature_targets.full_v1",
            "idle": _seg_metrics(ref, "idle"),
            "acceleration": _seg_metrics(ref, "acceleration"),
            "afterfire": _seg_metrics(ref, "afterfire"),
        }
        targets["vehicles"][vid]["r2_recording_dependent_features"] = new_features
        targets["vehicles"][vid]["reference_provenance"] = "B/R2 full-metric extraction v1; relative recording features only; not a calibrated recording target"
    targets["schema_version"] = "s12-acoustic-realism-targets-1.1"
    targets["metric_set"] = "full_v1: band_shares(4) + spectral_flux + modulation_depth/peak_hz/energy + pulse_amplitude_cv/interval_cv + crest_factor + dropout_ratio"
    TARGETS.write_text(json.dumps(targets, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    index = build_index()
    idx_path = DB / "real_recording_targets_index.md"
    idx_path.write_text(index, encoding="utf-8")
    print(f"index -> {idx_path}")
    update_feature_targets()
    print(f"updated -> {TARGETS}")


if __name__ == "__main__":
    main()
