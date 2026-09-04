---
stage: S12-long-term-memory
type: canonical-project-memory
updated: 2026-09-04
status: ACTIVE
current_product_direction: APP_FIRST
esp32_status: DEFERRED_FUTURE_OPTION
---

# Tesla Simulate Vico / S12 项目长期记忆

> 目的：让后续 Agent、Codex、开发者在不依赖超长聊天上下文的情况下，快速恢复项目真正目标、历史演进、已完成工作、当前阻塞、声学风险、参考来源、负面知识和后续执行路线。
>
> **证据权重规则（用户明确指定）**：
>
> 1. `S12_Handoff_Package_2026-09-03`：约 **90% 主证据**；
> 2. 旧聊天/此前助手总结：约 **10% 补充证据**；
> 3. 对 SHA、PR、CI、分支、当前文件等“会变化的事实”，**现场 GitHub 远端真值优先于任何历史快照**；
> 4. 用户当前明确决策优先于历史规划。2026-09-04 已重新确认：**当前产品主线是 App，不是 ESP32**。
>
> `S12_Handoff_Package_2026-09-03` 的 7 个 Markdown 已于 2026-09-04 重新解压并与包内 `SHA256SUMS.json` 逐个校验一致。

---

# 1. 一句话理解项目

当前项目不是“ESP32 声浪盒子开发”，也不是“做几个 WAV”。

当前要做的是：

> **先把发动机声浪算法做到足够真实和车型可辨识，再把这套算法做成车内 Android App。App 实时获得车辆速度与加速度，内部计算虚拟 RPM / load / gear / shift 等发动机状态，用户选择 Hellcat / Ferrari / RX-7 等车型后，App 自己实时合成并播放声音。**

当前最小实时输入合同：

```text
speed + acceleration
```

未来 CAN / OBD / 真实 RPM / throttle / gear 可以作为更高精度输入源，但不是当前阶段前置条件。

ESP32 当前统一状态：

```text
ESP32 = DEFERRED_FUTURE_OPTION
```

仓库里的 ESP32-S3 代码保留，但不进入当前 P0/P1/P2，不阻塞声音算法和 App。

---

# 2. 最终目标

最终要得到一套**车辆运动状态驱动、持续状态、车型可区分、可以实时运行的发动机声浪系统**。

当前产品形态：

```text
车内 Android App
    ↓
采集/获得 speed
采集/计算 acceleration
    ↓
VehicleState Normalizer
    ↓
VirtualEngineState
    ├─ virtual RPM
    ├─ virtual load / throttle proxy
    ├─ virtual gear / shift
    ├─ tip-in / lift / overrun
    └─ transient lifecycle
    ↓
Vehicle Profile Selector
    ├─ Hellcat
    ├─ Ferrari 458
    ├─ RX-7 FD
    └─ future profiles
    ↓
Persistent Event-Domain Sound Engine
    ↓
Realtime PCM
    ↓
Android audio output
```

真正的产品目标不是“声音会随着速度变高”，而是：

1. 怠速有生命感和周期波动；
2. 低频 body / pressure 来自事件与声学路径，而不是事后 EQ 伪装；
3. 加速连续，virtual RPM/load 与车辆运动感一致；
4. tip-in、shift、lift、idle return、afterfire 有连续状态；
5. Hellcat / Ferrari / RX-7 有明显不同的车型身份；
6. 不用固定哨声、固定谐波、全局 gain 把“像”做出来；
7. Raw 分析证据与听感播放处理分离；
8. App 可实时运行，CPU / memory / latency / underrun 可接受；
9. App 暂停/恢复、音频焦点变化后持续相位和事件状态不崩；
10. 后续得到合法同步 R1 时，可以进行正式真实标定。

---

# 3. 项目成功标准：五个等级不能混

交付包明确要求把“完成”拆成不同证据等级。

## Level A — 软件正确

需要：

- persistent state；
- block continuity；
- snapshot/restore；
- deterministic；
- no clipping；
- no click/pop；
- tests / CI；
- Track-P frozen guard。

当前：**已经比较成熟**。

## Level B — 工程方法正确

需要：

- 开源/论文方法被真正理解；
- clean-room / equivalent 实现；
- 许可证和媒体权利清楚；
- 方法进入真实 runtime call path；
- OFF/ON 或 ablation 可以证明因果作用。

当前：**已经比较成熟**。

## Level C — 声学有效

需要：

- 方法不只是“改变 PCM”；
- 还要让声音朝真实参考/人耳方向改善；
- low-frequency body、mechanical texture、blower、shift、afterfire、dynamic 等更合理。

当前：**部分完成**。

## Level D — 人耳通过

需要 Jovi 对盲听候选明确给出接受判断。

当前：**尚未完成，是当前真正产品门**。

## Level E — 正式标定

需要合法同步 R1：

- raw WAV/FLAC；
- rights receipt；
- RPM；
- load/throttle；
- gear/shift；
- mic position；
- recording chain；
- AGC/post-processing state。

当前：**R1 MISSING**。

因此永远不要写：

```text
CI PASS → SOUND REALISTIC
Human PASS → OEM CALIBRATED
```

---

# 4. 当前远端真值（2026-09-04 快照）

> 每个 Agent 执行前仍必须重新 fetch；以下只是长期记忆中的时间点快照。

```text
repository:
Jovifei/Tesla_Simulate_vico

main:
82c7cb77d26f446251e63d1a6899b08bf08be65b

PR #5:
S12 Stage AB pre-human validation hardening
state = MERGED
merged_at = 2026-09-04T13:51:52Z
qualified head = 021fe29480aadabd4d9ba4c20bbc111d1c386795

exact-head CI:
run = 33703659821
conclusion = SUCCESS

full S12:
1423 passed
10 skipped
232 subtests passed
1 warning

Track-P frozen guard:
PASS

CI artifact:
id = 9875918055
sha256 = 6d9892d60c6f9552aea790f91d9679a1739b77b4aa4fb0a01c5dc729560ea5ae
```

当前 Stage-AC 状态：

```text
AC0 PASS
AC1 PASS
AC2 PASS
AC3 PASS
AC4 PASS
AC5 PASS
AC6 PASS  ← exact-head remote qualification
AC7 PASS  ← PR #5 actually merged
AC8 PENDING ← post-merge pre-human smoke / receipt
```

当前整体软件状态：

```text
POST_MERGE_PREHUMAN_GATE_PENDING
```

---

# 5. 项目为什么会经历这么多 Stage

项目早期已经“能出声音”，但很快发现：

```text
能出声音
≠ 像发动机
≠ 像具体车型
≠ 动态连续
≠ 能被真实参考校准
≠ 能进入实时 App
```

所以路线逐步变成：

```text
声音原型
→ 事件域声源
→ persistent state
→ comparator/search
→ source layers
→ 开源方法吸收
→ 声学质量收口
→ provenance/causality
→ CI/measurability
→ Human Gate
→ Android Runtime
```

---

# 6. 历史阶段演进

## 6.1 v0.9 / v0.15：早期程序化声浪

主要方法：

- fixed harmonics；
- fixed resonators；
- procedural whine；
- artificial fillers；
- post-source LF EQ。

主要问题：

- acceleration 还能听；
- idle 很像合成器；
- low-frequency body 不真实；
- afterfire 像后贴 one-shot；
- Ferrari 太薄、太亮；
- Hellcat 虽有增压器身份，但 blower 偏电子；
- RX-7 很容易变成“高频合成器”。

历史结论：**继续堆谐波/EQ 不是最终路线。**

---

## 6.2 Stage V — Event-domain prototype

目标：吸收 Engine-Sim 的事件/机械状态思想，而不是复制其源码。

引入：

- `CrankPhasePLL`；
- cylinder / rotor event；
- reduced combustion packet；
- fractional delay path；
- localized afterfire；
- forced-induction state；
- Raw / Monitor 分离。

定位：

`P2_EVENT_DOMAIN_PROTOTYPE_BASELINE`

不足：

- event→torque 简化；
- streaming state 不完整；
- comparator/selector 较弱。

---

## 6.3 Stage W — Persistent architecture foundation

完成：

- `PersistentEventDomainEngine`；
- 20 ms state continuity；
- snapshot/restore；
- per-cylinder path；
- bank / collector；
- waveguide；
- localized afterfire；
- timbre map；
- frozen PTR adapter；
- executable bakeoff。

形成核心架构：

```text
VehicleState
→ Persistent Crank/Event
→ Source Layers
→ Paths / Collector
→ Frozen PTR
→ Raw
→ Monitor
```

历史问题：当时还没有可靠 formal selection。

---

## 6.4 Stage X — Comparator / Search

完成：

- `ReferenceCaseSet`；
- multi-reference comparator；
- parameter reachability；
- candidate search；
- engineering/formal gate split；
- R2/R3 diagnostic selection contract。

暴露：

- reference evidence 质量不一致；
- 一些 metric 数学定义不够好；
- Human feedback 尚未真正进入闭环；
- 仍不能证明 Hellcat 更真实。

---

## 6.5 Stage Y — Source Layers + Closed Loop

完成：

- fitted harmonic timbre map；
- cycle-synchronous layer；
- state transients；
- dP/DC chain；
- source parameter reachability；
- corrected comparator；
- reference governance；
- hard-gate evidence；
- open-source mapping。

关键里程碑：

```text
fitted map 16/16 parameters bidirectional reachability
```

Stage Y 的真正意义：

> 从“读懂方法”进入“方法在本地工程真实可执行”。

---

## 6.6 Stage Z — Open-source Absorption Proof

建立方法追踪链：

```text
Source
→ Method
→ Local implementation
→ Runtime call path
→ Test
→ OFF/ON
→ PCM SHA
→ Metric
→ Evidence
```

这个阶段之后，不再接受：

> “我们参考了某个开源项目，所以我们实现了它。”

而必须证明：

> “哪一个 method，在本地哪个文件，以什么 call path 执行，OFF/ON 改了什么，PCM 和 metric 如何变化。”

详见：

- `docs/research/engine-audio-ecosystem/source_registry.json`
- `source_evidence_receipts.json`
- `source_coverage_matrix.json`
- `method_adoption_matrix_v2.json`
- `method_adoption_matrix_v3.json`

---

## 6.7 Stage AA — Hellcat Acoustic Quality Closure

Stage Z 当时主要问题：

```text
Final RMS 显著低于 Parent
Dynamic range 被压缩
Centroid 偏高
```

AA 做 energy budget，发现主要损失：

```text
transients → dp_dc ≈ -22 … -25 dB
frozen PTR ≈ -21 … -23 dB
```

`full_load` 还存在很大的 pressure DC mean，而 dP/DC 后 AC RMS 很小。

因此创建：

- AA-C0
- AA-C1
- AA-C2
- AA-C3

AA-C3 相对 Stage-Z 诊断均值：

| Metric | Parent | Stage-Z | AA-C3 |
|---|---:|---:|---:|
| RMS dBFS | -45.588 | -62.039 | -47.801 |
| Dynamic Range dB | 9.368 | 3.582 | 5.747 |
| Spectral Centroid Hz | 1683 | 4247 | 1830 |
| Roughness proxy | 0.546 | 0.580 | 0.517 |
| Sharpness proxy | 0.146 | 0.297 | 0.115 |
| Persistent Tone | 0.453 | 0.488 | 0.444 |

结论：

- AA-C3 数字上明显优于 Stage-Z；
- 但人耳还没通过；
- low-frequency body 可能过冲；
- afterfire 风险很高；
- 有 broad pre-PTR scaling；
- 因此不能 Profile Freeze。

生成 v3 blind audition package：

```text
E:\Tesla_speed\review_packages\s12-stage-aa-hellcat-quality-v3
manifest SHA256:
b1ea99d36179229ff7d31f30f4790b6b84d8af587c14d44398e8e595f5f0964f
```

v1/v2/v3 都要保留，禁止覆盖。

---

## 6.8 Stage AB — Gain Provenance / Human Gate

问题：AA-C3 的改善到底是 source 真实修复，还是 mix-level scaling？

建立 P0–P8 factorial + exact Shapley。

AA-C3 RMS recovery ≈ `+15.539 dB`：

- event-body ≈ `+10.247 dB`，约 66%；
- broad scale ≈ `+5.202 dB`，约 33%；
- carrier suppression ≈ `+0.090 dB`。

重要结论：

> RMS 恢复主要来自 event-body，但 broad pre-PTR scaling 仍承担约三分之一，因此 AA-C3 不能被描述成纯 source-local 修复。

---

## 6.9 Stage AB-R — Validation Semantics Hardening

这一阶段留下了非常重要的“负面知识”。

### P6 不是真实 source stem

旧分类：

`STEM_LOCAL_GAIN`

正确分类：

`COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE`

原因：

```text
Y(Uc) - Y(Uc=0)
```

是 intervention 对所有下游路径的总效应，不是独立源 stem。

所以：

```text
source_causal_eligible = false
```

### LF persistence v1 数学无效

旧方法：

```text
mean(env > median(env))
```

对连续分布天然约等于 0.5，0.6/0.75 threshold 几乎不可达。

v2 改用：

- envelope crest；
- contiguity；
- coefficient of variation；
- fluctuation depth；
- pulse density；

并用 sine / burst / AM / noise / silence 验证。

### Blower v1 实际没分析 audible post-PTR

旧代码：

- 收到 `post_ptr`；
- 实际 `del post_ptr`；
- 搜索又从 ≥1200 Hz 开始。

v2：

- source；
- audible；
- contribution；
- 600–4000 Hz；
- cutoff sweep 900→1500 Hz。

### Dynamic timing v1 会假造 0 ms

v2 规定：

- ≥250 ms pre；
- ≥500 ms post；
- 没有 isolated event → `NOT_MEASURABLE`；
- 0 ms 只表示落在 10 ms frame 量化内，不是“物理瞬时响应”。

---

## 6.10 Stage AC — CI / Measurability / Product Baseline Gate

完成：

```text
AC0 remote truth                 PASS
AC1 regression root cause        PASS
AC2 cross-platform hermeticity   PASS
AC3 Track-P guard repair         PASS
AC4 fixture isolation            PASS
AC5 dynamic measurability        PASS
AC6 remote qualification         PASS
AC7 PR #5 merge                  PASS
AC8 post-merge prehuman          PENDING
```

AC5 isolated fixtures：

- tip_in；
- gear_shift；
- high_rpm_lift；
- afterfire eligible；
- afterfire ineligible。

这些 fixtures 只用于可测性，不改变 production PCM。

---

# 7. 当前声学架构心智模型

```text
VehicleState / VirtualEngineState
  │
  ├── RPM / load / throttle proxy / acceleration / gear-state
  │
  ▼
PersistentEventDomainEngine
  │
  ├── Crank / phase
  ├── Combustion event
  ├── Per-cylinder path
  ├── Bank / collector
  ├── Forced induction
  ├── Mechanical
  ├── Cycle sync
  ├── Tip-in / shift / lift / BOV / afterfire
  │
  ▼
PressureAudioChain
  │
  ├── DC handling
  ├── dP
  ├── fractional delay / persistent state
  │
  ▼
Frozen PTR / Radiation adapter
  │
  ├── Raw analysis PCM
  └── Audition / realtime output PCM
```

当前 App 产品化后，`VehicleState` 的最小真实输入来自 speed + acceleration，其它 engine state 在 App 内派生。

---

# 8. 当前 Hellcat 必须重点听的风险

## 8.1 Afterfire

AA-C3 / P5：

```text
afterfire peak vs engine body ≈ 20.064 dB
Parent ≈ 2.989 dB
```

状态：`RED FLAG`

人耳问题：

- 是真实 exhaust pop？
- 还是鞭炮/枪声？
- 是否明显像后期贴上去？
- 是否和 lift/overrun 时机一致？

如果坏：优先调 reservoir / event energy / location/path / decay / bandwidth / trigger timing，而不是 `master gain -8 dB`。

## 8.2 Hot-idle Low Frequency

v2 guard：

```text
P5 hot_idle = ELEVATED
```

重点：

- 是大排量 body/pressure？
- 还是持续 boom？
- 低频是否“粘住”不呼吸？

如果坏：优先 event variation / bank timing / path/collector / LF mode decay，而不是全局 low-shelf。

## 8.3 Blower

hot idle：

```text
carrier ≈ 741 Hz
source prominence ≈ 68 dB
audible prominence ≈ 27.3 dB
verdict = GENUINE_CARRIER_CANDIDATE
```

重点：

- 像机械增压器？
- 还是固定电子蜂鸣？

如果坏：优先 carrier dominance / sidebands / broadband / casing-intake / boost envelope，不是简单 notch 741 Hz 后宣称真实。

## 8.4 Dynamic

P5：

```text
idle→WOT RMS delta ≈ 12.77 dB
complete-cycle envelope range ≈ 10.50 dB
Parent complete-cycle envelope ≈ 19.59 dB
```

动态仍比 Parent 压缩，需要人耳判断 acceleration continuity 和 load contrast。

---

# 9. Round 2 的硬边界

只有收到 Jovi feedback 后才允许；最多：

```text
ONE round
max 3 candidates
```

禁止：

- whole `pre_ptr` gain；
- master/global gain；
- broad mix scaling；
- P6 counterfactual residual scaling；
- monitor gain 假装 source repair。

允许优先从：

- `combustion_event`；
- per-cylinder / per-path；
- collector/path transfer；
- forced induction；
- mechanical；
- afterfire reservoir/location/energy；
- transient source。

每个候选必须有：

```text
parameter intervention
→ OFF/ON
→ layer capture
→ first_changed_layer
→ downstream PCM
→ target metric
→ guard
```

已有真实 source-local 示例：

```text
combustion_event.event_energy OFF/ON
first_changed_layer = combustion_event
SOURCE_LOCAL_MODULATION_DEMONSTRATED
```

如果 first changed layer 是：

```text
pre_ptr / post_ptr / monitor / whole_pcm
```

则不能称 source-causal。

---

# 10. 已解决的历史 blocker：不要重复调查

以下问题已经解决，除非新的证据表明回归，否则不要重新花几小时复盘：

1. Ubuntu CI 看不到 Windows review package；
2. Track-P guard 对 ancient base 做全仓库 whitespace 扫描造成误报；
3. generated evidence CRLF；
4. stage receipt 强制 `base == current merge_base` 的错误规则；
5. “97 errors”错误归因，真实远端曾是 4 failures / 0 errors；
6. P6 被误称 source stem；
7. LF persistence v1 数学定义错误；
8. blower v1 没有真正分析 audible post-PTR；
9. dynamic timing 在缺 isolated event 时假造 0 ms；
10. 用 CI PASS 代替 human sound pass 的治理错误。

---

# 11. 当前真正 blocker

按顺序：

## P0 — AC8 post-merge pre-human receipt

只需要：

- 远端 ancestry；
- qualified head → current main 差异确认；
- 最小充分 smoke；
- Track-P frozen guard；
- exact post-merge receipt。

然后状态进入：

`WAITING_FOR_JOVI_AUDITION`

## P1 — Jovi V3 blind audition

这是当前真正声学产品门。

反馈前：

- 不改 AA-C3；
- 不揭盲；
- 不 Round2；
- 不扩车型。

## P2 — App runtime 尚未产品化

需要后续完成：

- speed/acceleration input；
- VirtualEngineState mapper；
- AudioParameterPackage；
- Golden traces；
- portable C++；
- Python↔C++ equivalence；
- Android AAudio/Oboe；
- profile selector；
- realtime metrics；
- in-car validation。

## P3 — R1

R1 缺失不阻塞 Engineering Profile / App 开发，但阻塞 OEM calibration / higher-level Profile Freeze。

---

# 12. 当前 App 产品架构

## 12.1 Input Layer

当前最小输入：

```text
speed
acceleration
```

要求明确：

- units；
- timestamps；
- freshness；
- filtering；
- invalid/missing behavior；
- offline replay trace。

## 12.2 VirtualEngineState Mapper

从车辆运动状态派生：

```text
virtual RPM
virtual load
throttle proxy
virtual gear
shift state
tip-in
lift/coast
afterfire eligibility
idle / launch / overspeed
```

核心要求：

- RPM 连续；
- gear 不 chatter；
- acceleration 能影响 load；
- deceleration 能产生 lift/overrun；
- 车型可以拥有不同 gear/RPM/load mapping；
- 声音算法不绑定某个 GPS/CAN implementation。

## 12.3 Vehicle Profile

第一阶段：

```text
Hellcat
Ferrari 458
RX-7 FD
```

profile 至少包含：

- engine identity；
- cycle/event topology；
- source parameters；
- forced-induction / rotary parameters；
- virtual RPM/load mapping；
- transient rules；
- path/timbre parameters；
- monitor/output configuration；
- version/SHA/provenance。

## 12.4 Native Runtime

建议：

- C++17；
- Android NDK；
- AAudio / Oboe；
- 48 kHz；
- realtime-safe callback；
- callback 内不 heap allocate；
- state double buffer / ring buffer；
- persistent state；
- snapshot/restore；
- underrun counter；
- callback time / latency metric。

## 12.5 App UI

当前真正需要的 UI 不必一开始复杂：

- 车型选择；
- start/stop；
- volume；
- current speed/acceleration；
- current virtual RPM/gear/load；
- runtime health / underrun；
- debug trace recording。

高级调音 UI 后置。

---

# 13. App 产品化执行路线

```text
AC8
→ Jovi Hellcat V3 Human Gate
→ AA-C3 accept OR ONE source-causal Round2
→ Hellcat Engineering Profile
→ Ferrari 458 migration
→ RX-7 FD migration
→ Vehicle Profile schema
→ AudioParameterPackage v1
→ speed/acceleration → VirtualEngineState contract
→ Golden traces
→ Golden PCM / metrics
→ portable C++ realtime core
→ Python ↔ C++ equivalence
→ Android NDK integration
→ AAudio/Oboe realtime output
→ vehicle profile selector
→ in-car dynamic validation
→ R1 formal calibration when available
```

当前不要提前跳到 Android tuning hack；App 必须消费版本化 profile 和可回归的 C++ core。

---

# 14. Android 实时验收建议

至少验证：

- 48 kHz 稳定；
- callback worst-case duration；
- underrun；
- input→state latency；
- state→audio latency；
- overall motion→audio subjective latency；
- CPU；
- memory；
- battery；
- thermal；
- long drive；
- pause/resume；
- background/foreground；
- audio focus interruption；
- screen off；
- profile switching；
- invalid sensor data fallback。

场景：

- stationary idle；
- low-speed roll；
- cruise；
- gentle acceleration；
- hard acceleration；
- virtual shift；
- lift/coast；
- afterfire；
- stop / idle return。

---

# 15. R1 / OEM / Freeze 长期边界

当前：

```text
R1 = MISSING
OEM_CALIBRATION = NOT_AUTHORIZED
PROFILE_FREEZE = NOT_AUTHORIZED
```

没有 R1 时允许：

- synthetic / vehicle-inspired；
- engineering candidate；
- human accepted engineering profile；
- R2/R3 diagnostic；
- App 产品化。

没有 R1 时禁止：

- OEM_MATCH；
- OEM_REPRODUCTION；
- CALIBRATED；
- formal Order-RPM qualified；
- OEM Profile Freeze。

---

# 16. ESP32 历史资产的正确定位

仓库包含历史 ESP32：

- CAN/TWAI；
- I2S；
- BLE；
- SD；
- input/UI；
- WiFi/MQTT/OTA；
- RuntimeStatus；
- App tick。

这些资产不删除，但当前：

```text
ESP32_ACTIVE_BACKLOG = false
ESP32_PRODUCT_GATE = false
ESP32_BLOCKS_APP = false
```

只有 App 路线成熟后、用户明确重新开启独立硬件需求，才评估 simplified runtime。

---

# 17. 研究来源长期规则

研究不是“越多项目越好”。Stage Z 以后已经形成足够的 source registry。

当前瓶颈已经变成：

```text
声音是否真正更真实
+
Human 是否接受
+
App Runtime 是否产品化
```

所以不要为了显示工作量继续无限搜索新的 engine-sound repo。

所有来源必须区分：

- method idea；
- source code；
- audio asset；
- model weights；
- commercial binary；
- licensing rights。

代码是 MIT 不代表仓库中的 WAV 也能用于产品。

详见：

`Research-Sources-And-Adoption-History.md`

---

# 18. 关键代码/证据导航

## Persistent engine

`tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py`

## Event domain

`tools/sound_sim/s12/acoustic_identity_v015/event_domain/`

## Waveguide

`tools/sound_sim/s12/acoustic_identity_v015/stage_w/waveguide.py`

## Timbre map

```text
tools/sound_sim/s12/acoustic_identity_v015/stage_w/timbre_map.py
tools/sound_sim/s12/acoustic_identity_v015/stage_y/harmonic_map_fit.py
```

## State transients

`tools/sound_sim/s12/acoustic_identity_v015/stage_y/state_transients.py`

## dP/DC

`tools/sound_sim/s12/acoustic_identity_v015/stage_y/audio_chain_dp.py`

## Stage AA candidates

`tools/sound_sim/s12/acoustic_identity_v015/stage_aa/candidates.py`

## Provenance

```text
tools/sound_sim/s12/acoustic_identity_v015/stage_aa/provenance.py
tools/sound_sim/s12/acoustic_identity_v015/stage_aa/run_provenance_audit_v2.py
```

## Stage AC

搜索：

```text
stage_aa/isolated_events.py
stage_aa/run_isolated_dynamic_audit.py
test_s12_stage_ac_isolated_dynamic.py
```

## Frozen guard

`tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py`

## Runtime evidence

```text
tasks/reports/runtime/s12-stage-aa/
tasks/reports/runtime/s12-stage-ab/
tasks/reports/runtime/s12-stage-ac/
```

---

# 19. Human feedback 流程

v3 包必须 byte-immutable。

收到反馈：

```text
raw feedback
→ save verbatim
→ feedback SHA256
→ verify package/manifest SHA
→ reveal blind identity
→ write binding receipt
→ map feedback to scene/source/metric/hypothesis
```

在 hash 之前不得 reveal。

反馈字段至少：

- vehicle identity；
- realism；
- idle life；
- LF pressure；
- mechanical texture；
- blower identity；
- acceleration continuity；
- shift；
- lift/decel；
- afterfire；
- synthetic artifact；
- overall preference；
- free text；
- playback device/environment。

---

# 20. Professional finalist 规则

Round2 只保留 2–3 finalists。

Python comparator 持续使用。

MoSQITo：本地可用时使用。

MATLAB：历史约束是 existing-session-only；不要自动启动新的 MATLAB，也不要 `matlab -batch` 形成不受控环境。

如果后续工具策略改变，需要明确记录新的工程决策。

---

# 21. 允许停止与不允许停止

允许真正 Stop：

```text
WAITING_FOR_JOVI_AUDITION
WAITING_FOR_R1
MODEL_REDESIGN_REQUIRED
COMMERCIAL_LICENSE_REQUIRED
FROZEN_BOUNDARY_REVIEW_REQUIRED
```

普通问题不能成为长期 Stop：

```text
ordinary bug
CI bug
test bug
path portability
stale status
receipt mismatch
```

这些应直接修复。

---

# 22. 后续 Agent 开始工作前的固定动作

1. 读本文件；
2. 读 `Research-Sources-And-Adoption-History.md`；
3. fetch GitHub current main/PR/CI；
4. 读 `tasks/reports/runtime/s12-stage-ac/execution_state.json`；
5. 不相信聊天中的旧 SHA；
6. 不把 ESP32 重新提升为当前主线；
7. 如果 AC8 未闭合，先闭 AC8；
8. 如果已经在 Human Gate，停止自动调音，等待/处理 Jovi feedback；
9. Human PASS 后按 App-first roadmap 产品化。

---

# 23. 当前一句话状态

```text
S12 的开源方法吸收、persistent sound architecture、comparator、provenance、CI/Track-P 软件基础已经达到工程可用水平；PR #5 已合并；当前先关闭 AC8，再由 Jovi 对 Hellcat v3 做人耳判断；之后最多一轮 source-causal Round2；Hellcat 通过后迁移 Ferrari/RX-7，并把通过的声音做成 speed+acceleration 驱动的 Android App；ESP32 明确后移。
```
