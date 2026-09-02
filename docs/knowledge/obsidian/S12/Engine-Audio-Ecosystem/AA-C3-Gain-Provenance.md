---
stage: Stage-AB
type: provenance-audit
created: 2026-09-02
status: DIAGNOSTIC_ONLY
---

# AA-C3 Gain Provenance

**分类结论**：AA-C1/C2/C3 的 `pressure_scale` 作用于**整个 pre_ptr 复合层**
（`candidates.py:90-108`；pre_ptr 成分见 `persistent_engine.py:694-708`：combustion + forced
+ mechanical + sync + transients + dp_dc + transfer_ir）。
分类 = **STATE_DEPENDENT_BROAD_PRE_PTR_SCALING**，不是 source-pressure-AC repair。
`global_gain_changed=false`（无常量 master gain）≠ stem-local。

**精确 Shapley 归因**（2³ 全因子 P0–P5/P7/P8，11 场景均值，封闭性精确）：

| 指标 | 总效应 | broad scale | event-body | carrier |
|---|---|---|---|---|
| RMS | +15.54 dB | +5.20 dB (33.5%) | **+10.25 dB (66%)** | +0.09 |
| centroid | −2359 Hz | +573 Hz | −2881 Hz | −51 |
| dynamic range | +1.80 dB | +0.33 | +1.33 | +0.14 |

- RMS 修复主因是 **event-body 注入**（stem-derived），不是 broad scale；
- 但 P4（无 broad scale）centroid 塌到 591 Hz、sharpness 0.022 → **频谱修正单靠 event/carrier 不成立**；
- P5 与 AA-C3 raw PCM **bit-exact**（测试验证）。

**P6 source-causal diagnostic**：combustion 差分信号
（`pre_ptr(full) − pre_ptr(event_energy=0)`，精确因果差分法）单独施加 (2+2·load)，
其余 stem 不动。仅诊断用，**不是** feedback 前的试听 winner。

相关：[[Broad-Pre-PTR-vs-Source-Causal-Gain]] · [[Stage-AB-Negative-Knowledge]]
