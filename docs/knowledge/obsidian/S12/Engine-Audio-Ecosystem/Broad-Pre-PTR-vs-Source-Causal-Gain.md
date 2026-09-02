---
stage: Stage-AB
type: adr
created: 2026-09-02
status: ACCEPTED_FOR_ROUND2_DESIGN
---

# Broad Pre-PTR vs Source-Causal Gain (ADR)

## 背景

AA-C3 用 `base_pre_ptr * (2 + 2*load)` 恢复 RMS。Stage-AB 归因显示它贡献约 1/3 RMS，
并承担频谱再平衡（+573 Hz centroid）；event-body 注入贡献约 2/3 RMS 但会把频谱拉暗。

## 决策

1. **Round 2 raw candidate 禁止 whole-mix gain**（pre_ptr / post_ptr / PCM 整体乘增益），
   增益必须落到显式 stem（combustion_event / pressure_ac / mechanical / forced_induction /
   afterfire / body_path）或显式 transfer 阶段；hard gate 检查 route 结构 + 数值隔离，
   不是 grep 参数名（`route_is_stem_local` + `assert_no_broad_mix_gain_in_round2_raw_candidate`）。
2. broad scale 残余效应向上游迁移：combustion event amplitude vs load、event pulse energy、
   pressure-AC 分离（p(t)=p0+p′，音频主体用 p′）、collector/path transmission、forced induction balance。
3. event-body +4.0 固定 overlay 应改为 state-dependent event-derived body energy
   （并检查 afterfire 场景过冲）。
4. Round 2 只允许一轮、最多 3 个候选（AB-R2-A/B/C），每个 hypothesis 明确不同。

## 备选与取舍

- 继续调 broad scale：数字最快见效，但属于 mix scaling，掩盖 source 能量缺失 → 否决。
- P6（combustion 差分局部 scaling）：保留为 in-repo 预览方向，dynamic 指标最接近 Parent
  （idle→WOT +10.64 dB vs Parent +9.37；afterfire 3.16 dB vs Parent 2.99）。

相关：[[AA-C3-Gain-Provenance]] · [[Stage-AB-Round2-ADR]]
