---
type: decision-history-negative-knowledge
updated: 2026-09-04
status: ACTIVE
---

# S12 关键决策历史与负面知识

> 目的：记录项目为什么走到今天、哪些路线已经证明不该重复、哪些术语曾经被误用、哪些测试/指标曾经给出误导性结论。后续 Agent 在提出“重新做一次”之前先查本文。
>
> Evidence：`S12_Handoff_Package_2026-09-03` ≈90%，旧聊天/此前总结 ≈10%；当前用户决策和 GitHub remote truth 优先。

## 1. 产品方向决策

### 决策 D-PRODUCT-01：当前产品载体 = Android App

当前：

```text
speed + acceleration
→ VirtualEngineState
→ Vehicle Profile
→ realtime S12 sound
→ Android playback
```

原因：当前阶段首先要证明声音真实性、车型身份和实时车内体验；手机有足够算力、调试能力和快速迭代能力。

### 决策 D-PRODUCT-02：ESP32 后移

`ESP32 = DEFERRED_FUTURE_OPTION`。

仓库已有 ESP32 资产不删除，但不再成为当前 blocker、P0/P1/P2 或“当前最终产品”描述。只有 App 路线成熟且用户明确重新开启独立硬件需求时才评估 simplified runtime。

### 决策 D-PRODUCT-03：当前 minimum input = speed + acceleration

真实 RPM/CAN/load/gear 不是当前前置条件。App 内部用 deterministic VirtualEngineState 产生 virtual RPM/load/gear/shift/lift/overrun；未来 CAN/OBD 是 richer adapter。

---

## 2. 声音架构决策

### D-AUDIO-01：从 fixed harmonic synth 转向 event-domain

早期 v0.9/v0.15 使用 fixed harmonics/resonators/procedural whine/LF EQ，问题是 idle 合成器感、LF body 假、车型身份弱。

因此选择：

```text
persistent crank/event
→ combustion/path/bank/collector
→ forced induction/mechanical/transients
→ pressure chain
→ frozen PTR/Radiation
```

### D-AUDIO-02：Persistent state 是硬要求

声音不是一帧一帧独立生成。必须保留 phase、path/filter、reservoir、boost/transient、snapshot state。

因此 one-shot 看起来好听但 block render 不连续的方案一律不合格。

### D-AUDIO-03：Track-P 与 Track-S 分离

Track-P/FVM/PTR/Radiation 是冻结物理/传播边界；Track-S 做 acoustic identity 和 authoring。

不能因为“听起来不够像”就随意修改 Track-P 数学。

### D-AUDIO-04：Raw analysis 与 Monitor/realtime playback 分离

用于指标的 Raw 不应被 AGC/monitor gain 污染；用于试听的 monitor 可以有受控播放处理，但不能把 monitor 处理宣称为 source repair。

---

## 3. 车型决策

### D-VEHICLE-01：三个深度锚点

1. Hellcat：cross-plane V8、LF body、supercharger、afterfire；
2. Ferrari 458：flat-plane V8、高转 order、mechanical/metallic texture；
3. RX-7 FD：rotary timing、housing buzz、sequential turbo/BOV。

当前先闭 Hellcat，再迁移方法到 Ferrari/RX-7。

### D-VEHICLE-02：不能用同一模板 + pitch/EQ 区分车型

每个 profile 必须有自己的 event topology、source identity、forced induction/rotary behavior、state mapping、transient rules。

---

## 4. Reference / Qualification 决策

### D-REF-01：R1/R2/R3 分层

- R3：公共/不同步 diagnostic；
- R2：来源权利较清楚但缺同步状态的 relative reference；
- R1：合法 raw audio + synchronized vehicle states + recording metadata。

### D-REF-02：Human PASS 不等于 R1

Human accepted Engineering Profile 可以先用于 App 产品化；但 `OEM_MATCH / CALIBRATED / PROFILE_FREEZE` 需要 R1 正式证据。

---

## 5. Stage Z 方法吸收决策

### D-RESEARCH-01：看过项目 ≠ 采用方法

采用必须有：

```text
Source → Method → Local implementation → Call path → Test → OFF/ON → PCM → Metric/Evidence
```

### D-RESEARCH-02：当前研究 breadth 已够

25-source registry 已建立。现在瓶颈是 Human Gate + App Runtime，不是继续搜索更多 engine-sound repository。

---

# 6. 已证伪/禁止重复的声学修复

## N-AUDIO-01：Global/master gain 不是真实性修复

数字 RMS 变接近不能证明 source 正确。Round2 禁止用 whole-mix/master/broad pre-PTR gain 作为 repair。

## N-AUDIO-02：P6 不是 source stem

`pre_ptr(full) - pre_ptr(event_energy=0)` 是 counterfactual total downstream effect，不是独立 source stem。

正确分类：`COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE`；`source_causal_eligible=false`。

## N-AUDIO-03：固定 tone/carrier 不能直接当车型身份

例如 Hellcat blower ~741 Hz carrier 是“真实 carrier candidate”，不是自动合格。人耳仍要判断 mechanical whine 还是 electronic whistle。

## N-AUDIO-04：Afterfire 不能是后贴 firecracker

Afterfire 必须受 lift/fuel/oxygen/temperature/cooldown/reservoir/path 状态约束。AA-C3 ~20 dB above body 是明显 human red flag。

## N-AUDIO-05：低频更多不等于更真实

hot-idle LF `ELEVATED` 可以是大排量 body，也可能是 boom。不能用 low-shelf/整体 LF boost 代替 event/path/body 结构修复。

---

# 7. 已证伪/修正的指标与测试方法

## N-METRIC-01：LF persistence v1 数学无效

`mean(env > median(env))` 对连续分布自然接近 0.5，旧阈值不可用。

替换：crest、contiguity、CV、fluctuation depth、pulse density；用 synthetic fixtures 验证。

## N-METRIC-02：Blower v1 没真正测 audible post-PTR

旧实现接收 `post_ptr` 后丢弃，并从 ≥1200 Hz 搜索，漏掉 ~741 Hz。

v2 必须区分 source/audible/contribution，600–4000 Hz。

## N-METRIC-03：0 ms 不是“物理瞬时响应”

没有合规 isolated event 就必须 `NOT_MEASURABLE`。tip-in 0 ms 只能解释为 10 ms frame quantization 内 state-to-audio onset。

## N-METRIC-04：不同 dynamic metric 不能混名

`dynamic_range_db` 与 `complete_cycle_envelope_range_db` 是不同定义，必须经过 metric registry 明确区分。

---

# 8. 已解决的工程/CI 问题

以下除非出现新回归，不应重新当根因：

1. Ubuntu CI 无法访问 Windows review-package path；
2. Track-P ancient-base whitespace false positive；
3. generated evidence CRLF；
4. receipt 必须等于 current merge-base 的错误假设；
5. “97 errors”错误叙事；
6. shared fixture/order systemic failure 误判；
7. Stage-AC cross-platform hermeticity；
8. Track-P frozen guard semantics。

原则：远端 exact-head CI 事实优先于旧日志摘要。

---

# 9. Human feedback 决策纪律

V3 blind package 在 feedback 前 byte-immutable。

```text
feedback verbatim
→ SHA256
→ verify package SHA
→ reveal B/C
→ binding receipt
→ scene/source/metric/hypothesis
```

不得先揭盲再补写“盲听反馈”。

---

# 10. Round2 决策纪律

最多一次、最多 3 candidates。

每个 candidate 必须是独立 source-causal hypothesis，并能回答：

- 改了什么参数；
- first_changed_layer 是哪里；
- 哪个场景/指标预期改善；
- 哪些 guard 不能退化。

失败后允许：`MODEL_REDESIGN_REQUIRED`，而不是无限参数搜索。

---

# 11. App 产品化不可重复踩坑

1. 不在 Android callback 重新发明另一套声音算法；
2. 不把 Python scene-specific hack 直接搬进 App；
3. 不在 callback heap allocate；
4. 不以 UI frame rate 驱动 audio engine；
5. speed/acceleration sensor noise 必须先做 state-layer filtering/hysteresis；
6. profile switch 不能 reset 音频状态导致 pop；
7. pause/resume/audio focus 需要 snapshot/recovery；
8. mobile performance 优化不能改变 sound truth，必须由 Golden traces 回归。

---

# 12. 当前最重要的决策结论

```text
Research breadth is sufficient.
Software architecture is largely sufficient.
Current bottleneck = Human realism judgment + App realtime productization.
```

后续如果一个任务不能直接帮助：

- AC8；
- Jovi Human Gate；
- source-causal Hellcat repair；
- Ferrari/RX-7 profile；
- speed+acceleration state model；
- AudioParameterPackage/Golden evidence；
- Android realtime；

就应该质疑它是否属于当前主线。
