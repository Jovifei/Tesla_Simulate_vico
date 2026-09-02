---
stage: Stage-AB
type: negative-knowledge
created: 2026-09-02
status: ACCUMULATING
---

# Stage-AB Negative Knowledge

数字更好 ≠ 人耳更好；以下条目在未来迁移 Ferrari/RX-7 时必须复查：

1. **afterfire 过冲（未验证人耳）**：event-body 120–400 Hz 注入使 afterfire 峰值相对
   body 冲到 ~20 dB（Parent ~3 dB、Stage-Z ~3.7 dB）。若 Jovi 报“像爆竹/太响”，
   映射到 event-body 注入在 afterfire 场景的能量，而不是 `afterfire_gain -= x`。
2. **broad pre-PTR scale 不是 RMS 主因**：直觉以为是，实测 Shapley 只占 33.5%；
   event-body 注入占 66%。别按“去掉 broad scale 就会塌”的直觉做 Round 2。
3. **event-body 单独不成立**：P4 无 broad scale 时 centroid 塌到 591 Hz、sharpness 0.022
   ——两个因素强交互，单因子调参会误判。
4. **blower "carrier" 峰在 1200 Hz 滤波器拐角**（prominence 20–24 dB，sideband/carrier ~0.49，
   broadband 主导 >500×）：>1200 Hz suppression 抑制的是真实 blower identity 还是电子载波
   伪影，目前**无法**用 sharpness 下降单独判定，待 Jovi blower_identity 打分。
5. **broad scale 不会压平 idle→WOT**：P1/P5 的 idle→WOT delta 反而超过 Parent；
   真正的动态缺口在 complete-cycle envelope range（Parent 19.6 dB vs P5 10.5 dB）。
6. P6（combustion 差分局部 scaling）动态最像 Parent——如果 Round 2 走 source-causal，
   这条路线已有数值背书。

## AB-R 加固新增（2026-09-02，SUPERSEDES v1 validation semantics）

7. **高于 median 的比例 ≈0.5 不能当 persistence**：v1 `mean(env>median)` 对连续分布
   由构造即 ≈0.5，0.6/0.75 门槛不可达 → 全部旧 `boom_risk=OK` 作废
   （OLD_LF_GUARD_INVALIDATED）。v2 换 envelope-shape 统计后 P5 hot_idle = ELEVATED。
   详见 [[LF-Persistence-Metric-Failure]]。
8. **full − no_source 是 counterfactual total effect，不是真 source stem**：
   P6 改判 `COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE`，`source_causal_eligible=false`，
   只能做诊断归因，不得当 Round 2 候选。详见 [[Counterfactual-Residual-vs-True-Source-Stem]]。
9. **source 层 carrier ≠ audible post-PTR carrier**：v1 blower 审计 `del post_ptr`
   从未真正分析可听层，且只在 ≥1200 Hz 搜索。v2 分层后 hot_idle 741 Hz 双层都在
   （GENUINE_CARRIER_CANDIDATE），full_load/complete_cycle 仍 AMBIGUOUS。
   详见 [[Blower-Source-vs-Audible-Path]]。
10. **0 ms timing 可能只是窗口对齐**：tip_in latency 0.0 ms = acoustic 50% 穿越落在
   state onset 同一 10 ms 分析帧（离线渲染器按块消费 state、无传输延迟），是帧量化
   陈述，不是"发动机瞬时响应"；无数据一律 NOT_MEASURABLE。
   详见 [[Dynamic-Event-Aligned-Metrics]]。
11. **Stage-AA dynamic_range_db ≠ complete_cycle_envelope_range_db**：两个指标
   （≈9.37/3.58/5.75 vs ≈19.6/10.5）不得互相比较或混用名称，已登记在
   `metric_definition_registry.json`。
12. **remote truth 只认 `git ls-remote` + GitHub API**：local tracking ref 可能陈旧；
   f7ba 在 main 上但无 PR、无 CI run（MAIN_ADVANCED_TO_STAGE_AB_WITHOUT_PR），
   处置为 FORWARD_ONLY，不 reset、不 rewrite。

相关：[[AA-C3-Gain-Provenance]] · [[AA-C3-Gain-Provenance-v2]] · [[Hellcat-Human-V3-Feedback]] · [[Stage-AB-PreHuman-Hardening]]
