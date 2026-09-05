# 发动机物理声学仿真可复用 Playbook

## 这次真正有效的经验

1. **事件先于音色**：先建立每缸/每转子的做功与 blowdown 事件，再谈 EQ、共振和听感。
2. **几何产生自然差异**：点火相位、bank assignment、primary length、collector topology 会自然形成 comb/interference，不要用固定高频纯音伪造车型身份。
3. **声速必须来自温度模型**：S12 主链已有 `sound_speed_mps(T)` 和 persistent fractional delay；不要再用 `np.roll(length/343)` 另造一套。
4. **IR 是 transfer，不是美容滤镜**：必须在 PTR 前、受 manifest/SHA/rights 管理；comparator 用 RAW，试听 gain 单独处理。
5. **整包一个增益**：一台车的 idle/cruise/WOT/afterfire 共用一个 attenuation-only package gain，绝不每段拉满。
6. **负反馈用固定尺子**：跨轮使用 `absolute_reference_distance`，Human feedback 只作 bounded guidance。
7. **Teacher ≠ production renderer**：实验脚本可以验证假设，但最终必须回收到 `PersistentEventDomainEngine`。

## 四车复用路线

```text
engine geometry hypothesis
→ event-domain config
→ deterministic state traces
→ canonical render
→ governed reference/R3 diagnostic
→ fixed-distance search
→ Human A/B
→ Engineering Profile
→ Golden Evidence
```

## 车型身份应该来自哪里

- Hellcat：cross-plane event/bank geometry + supercharger shaft/sidebands + large-displacement body。
- Ferrari 458：flat-plane even firing + short high-rev events + intake/exhaust transfer。
- LFA：10-cylinder 72° event spacing + high-rev short pulse + intake/path resonances。
- GT-R R35：6-cylinder 120° event spacing + turbo spool state + BOV transient + compact manifold path。

不要用“这车应该更尖/更粗”直接变成 5.6 kHz/8.4 kHz 固定 sine。
