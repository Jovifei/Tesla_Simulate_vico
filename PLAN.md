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

App 内部需要将 speed / acceleration 映射为 virtual RPM、load/throttle proxy、virtual gear/shift、tip-in/lift/overrun、transient lifecycle 和 continuous phase/event state。

未来 CAN/OBD 可以作为更高质量输入源，但不是当前 App 算法阶段的必备前提。

## Delivered S12 Work

已走过：`V → W → X → Y → Z → AA → AB / AB-R → AC`。

已具备 persistent event state、source/path/bank/collector、forced induction、mechanical/transients、state-gated afterfire、comparator/reference governance、Track-P guard、Hellcat AA-C3、v3 blind package、provenance/causality hardening 和 exact-head remote CI closure。

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

1. Stage-AC post-merge AC8 closeout；
2. Hellcat V3 Human Gate；
3. AA-C3 accept 或 ONE source-causal Round2；
4. Hellcat Engineering Profile；
5. Ferrari / RX-7 migration。

## App Productization

之后：

```text
AudioParameterPackage
→ Golden speed/acceleration + VirtualEngineState traces
→ Golden PCM
→ Portable C++ runtime
→ Python↔C++ equivalence
→ Android NDK + AAudio/Oboe
→ speed/acceleration input/filter
→ vehicle profile selector
→ in-car validation
```

Android App 是当前产品载体。

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

ESP32-S3 和其 board/CAN/BLE/WiFi/OTA/I2S hardware line 统一标记：

`DEFERRED_FUTURE_OPTION`

它们不阻塞当前声音算法和 App 产品化。只有 App 路线成熟后，再决定是否重新开启嵌入式简化版。

## Evidence Boundaries

- CI green ≠ Human PASS；
- Human PASS ≠ R1/OEM calibration；
- current App Engineering Profile 可以先于 R1 形成；
- ESP32 历史代码存在 ≠ 当前产品路线必须使用 ESP32。