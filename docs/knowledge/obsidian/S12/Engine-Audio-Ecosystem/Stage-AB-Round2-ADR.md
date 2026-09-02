---
stage: Stage-AB
type: adr
created: 2026-09-02
status: DRAFTED_PENDING_HUMAN
---

# Stage-AB Round2 ADR (pending Jovi feedback)

Round 2 **唯一一轮**，在 AB3 反馈绑定后才解锁。预登记约束：

- 候选 ≤3：AB-R2-A/B/C，每个 hypothesis 不同、可证伪。
- 全部 source-causal：禁 whole-mix gain；增益落显式 stem 或 transfer 阶段；
  `test_no_broad_mix_gain_in_round2_raw_candidate` 强制。
- 预登记方向（来自归因，待反馈确认/重排优先级）：
  - A：state-dependent combustion event energy（把 RMS/动态修复搬到源事件能量）；
  - B：pressure-AC 分离（p(t)=p0+p′，gain/transfer 只作用 p′，验 DC/finite/click/能量守恒 proxy）；
  - C：forced-induction balance 重整（blower identity vs carrier artifact，用 sideband/
    tracking 指标而非 sharpness 单指标）。
- Afterfire 反馈映射表已预置（爆竹→event amplitude distribution；太规律→inter-event
  interval/reservoir state；尾音不自然→path damping/cluster size），禁单旋钮粗调。
- 若 Jovi 直接认可 AA-C3：走 HUMAN_ACCEPTED_R2_DIAGNOSTIC_CANDIDATE，不强行出新代码。

相关：[[Broad-Pre-PTR-vs-Source-Causal-Gain]] · [[Hellcat-Human-V3-Feedback]]
