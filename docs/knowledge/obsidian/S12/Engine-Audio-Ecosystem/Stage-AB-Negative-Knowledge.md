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

相关：[[AA-C3-Gain-Provenance]] · [[Hellcat-Human-V3-Feedback]]
