# S12 真车声音采集与闭环标定工作流

## Reference 等级

- **R1**：合法原始音频 + 明确车辆状态/改装状态 + mic/recording metadata + synchronized RPM/load/gear。可进入正式标定。
- **R2**：受治理但信息不完整的工程 reference，可做 comparator/diagnostic，不能称 OEM calibration。
- **R3**：公开视频/POV/私人诊断切片。允许 Human A/B 和明确标注的 diagnostic fitting；不可升 R1/R2，不作为产品音频资产。

## 收集优先级

1. dyno / controlled pull；2. track/autobahn onboard；3. stationary hot-idle/rev；4. public-video diagnostic only。

拒绝/降级：背景音乐/旁白、明显 clipping、激进 AGC、未知改装直排、无法判断场景、codec wall 严重。

## 标准场景

`afterfire, full_pull, hot_idle, idle_return, lift, shift, steady_high, steady_low, steady_mid, tip_in`。

每个 reference 记录 source URL/session、SHA256、start/end、sample rate、mic/AGC、stock/mod state、speech/music、RPM/load/gear availability、rights status。

## 闭环

```text
ReferenceCaseSet
→ canonical S12 render
→ RAW comparator
→ fixed absolute reference distance
→ source-causal bounded parameter update
→ re-render
→ plateau/target/max-iteration
→ package-wide monitor gain
→ Jovi Human A/B
```

Human PASS 才能形成 Engineering Profile；R1 仍是单独更高证据门。
