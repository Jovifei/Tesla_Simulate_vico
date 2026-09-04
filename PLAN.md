# Tesla Simulate Vico Engineering Plan

> Status snapshot: 2026-09-04. 当前主线是 **S12 声音真实性 → Jovi 人耳闭环 → Android App 实时声浪**。ESP32 不属于当前实施阶段，保留为后期可选简化 runtime。
>
> Canonical memory：`docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md`。
>
> 研究来源索引：`docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Research-Sources-And-Adoption-History.md`。

## Goal

当前产品目标：在车内运行一个 App，由 App 获得车辆速度和加速度，内部计算连续的虚拟发动机状态，用户选择不同车型后，App 实时生成并播放对应发动机声浪。

```text
speed + acceleration
→ VirtualEngineState
→ selected Vehicle Profile
→ realtime S12 sound engine
→ App playback
```

App 内部需要将 speed / acceleration 映射为：

- virtual RPM；
- load / throttle proxy；
- virtual gear / shift；
- tip-in / lift / overrun；
- transient lifecycle；
- continuous phase/event state。

未来 CAN/OBD 可以作为更高质量输入源，但不是当前 App 算法阶段的必备前提。

## Current Sound Architecture

```text
VehicleState(speed, acceleration, derived states)
→ PersistentEventDomainEngine
→ source/path/transient layers
→ pressure/dP chain
→ frozen PTR/Radiation boundary
→ realtime PCM
→ Android audio output
```

Track-P / PTR / Radiation 保持冻结；Track-S 负责车型身份与听感。

## Delivered S12 Work

已走过：

`V → W → X → Y → Z → AA → AB / AB-R → AC`

已具备：

- persistent crank/event state；
- block continuity / snapshot restore；
- combustion / path / bank / collector；
- forced induction / mechanical / transient layers；
- state-gated afterfire；
- comparator / reference governance；
- frozen Track-P guard；
- Hellcat AA-C3；
- v3 blind audition package；
- provenance / causality / measurement hardening；
- exact-head remote CI closure。

## Current Remote Truth

```text
main = 82c7cb77d26f446251e63d1a6899b08bf08be65b
PR #5 = MERGED
qualified head = 021fe29480aadabd4d9ba4c20bbc111d1c386795
CI 33703659821 = SUCCESS
full S12 = 1423 passed / 10 skipped / 232 subtests passed
Track-P = PASS
R1 = MISSING
AC8 = PENDING
```

## Immediate Phase

### 1. Stage-AC Post-Merge Closeout

- 核对 `021fe294... → 82c7cb77...` 仅为治理/状态元数据；
- 完成最小充分 post-merge smoke / Track-P guard；
- 写 AC8 receipt；
- 进入 `WAITING_FOR_JOVI_AUDITION`；
- 不改 PCM/profile。

### 2. Hellcat V3 Human Gate

Package：

`E:\Tesla_speed\review_packages\s12-stage-aa-hellcat-quality-v3`

manifest：

`b1ea99d36179229ff7d31f30f4790b6b84d8af587c14d44398e8e595f5f0964f`

反馈前：不调音、不揭盲、不扩车型。

收到反馈后：

`raw feedback → SHA → reveal → binding → accept AA-C3 OR ONE source-causal Round2`

Round2：最多 3 个候选，禁止 whole-mix/master/broad-pre-PTR gain。

### 3. Vehicle Profile Closure

Hellcat Human PASS 后：

1. 冻结 Hellcat Engineering Profile；
2. 迁移 Ferrari 458；
3. 迁移 RX-7 FD；
4. 定义统一 Vehicle Profile schema。

## App Productization

### 4. AudioParameterPackage

冻结跨语言合同：

- profile id / vehicle identity；
- source parameters；
- event/cycle parameters；
- transient rules；
- speed/acceleration operating axes；
- virtual RPM/load/gear mapping；
- filter/path/monitor parameters；
- schema version / SHA / provenance。

### 5. Golden Evidence

- deterministic speed/acceleration traces；
- derived VirtualEngineState traces；
- Golden PCM / metrics；
- block/snapshot cases；
- exact package/render SHA。

### 6. Portable C++ Runtime

实现 Android 真正需要的 realtime subset：

- persistent phase/event；
- source layers；
- reduced path/waveguide；
- transient state machine；
- dP/DC；
- frozen boundary equivalent adapter；
- monitor/output；
- snapshot/restore。

不把完整 CFD/teacher 系统放入 App runtime。

### 7. Python ↔ C++ Equivalence

同一 speed/acceleration trace + 同一 profile：

- block outputs bounded；
- streaming continuity；
- snapshot/restore deterministic；
- 无错误重置/爆音/状态断层。

### 8. Android App

当前 App 是产品载体，需要完成：

- speed input adapter；
- acceleration input/filtering；
- VirtualEngineState mapper；
- vehicle profile selector；
- realtime C++ sound core；
- AAudio/Oboe；
- 48 kHz realtime-safe callback；
- no heap allocation in audio callback；
- state double-buffer/ring-buffer；
- CPU / memory / latency / underrun metrics；
- pause/resume/audio-focus/snapshot recovery；
- 车内试听与长时间运行。

## Current Success Criteria

当前阶段完成不是“ESP32 上板”，而是：

1. Hellcat/Ferrari/RX-7 车型身份明显；
2. Jovi 人耳接受；
3. speed/acceleration 驱动连续自然；
4. App 实时稳定播放；
5. latency/underrun/CPU/memory 可接受；
6. 用户可在 App 中选择车型；
7. 车内动态体验通过。

## Deferred / Future

ESP32-S3、CAN 硬件、BLE/WiFi/OTA 板级验收、I2S 外置功放等全部标记：

`DEFERRED_FUTURE_OPTION`

它们不阻塞当前声音算法和 App 产品化。只有 App 路线成熟后，再决定是否做 ESP32 simplified runtime。

## Evidence Boundaries

- CI green ≠ Human PASS；
- Human PASS ≠ R1/OEM calibration；
- R1 仍需合法同步真实数据；
- current App Engineering Profile 可以先于 R1 形成；
- ESP32 历史代码存在 ≠ 当前产品路线必须使用 ESP32。