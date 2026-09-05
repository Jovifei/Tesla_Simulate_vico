# Tesla Simulate Vico / S12 项目总路线图

更新：2026-09-05
状态：`ACTIVE_AUTHORITY`

## 当前主线

```text
Stage AD reference-driven acoustic loop
→ Jovi diagnostic listening / formal Human gate
→ Hellcat Engineering Profile
→ Ferrari 458 / RX-7 FD migration
→ AudioParameterPackage + Golden Evidence
→ portable C++
→ Python↔C++ equivalence
→ Android realtime App
→ in-car validation
→ R1 formal calibration when available
```

## M0 — Remote / governance closeout

- PR #6：App-first canonical docs；
- PR #7：Stage AD implementation；
- latest exact-head CI 必须完成；
- Stage-AC AC8 仍需正式 post-merge pre-human receipt。

Stage AD diagnostic 可以和 AC8 治理收口并行，但不能因此自动 promotion。

## M1 — Stage AD Hellcat loop

- 使用 governed local Reference；
- AA-C3-aware；
- body → blower → afterfire；
- fixed reference distance；
- output independent Stage-AD monitor WAV；
- Jovi 试听。

公网 extractor 只用于明确授权下的 R3 human A/B，不进入默认 optimizer。

## M2 — Human closure

结合官方 V3 blind evidence 与 Stage AD diagnostic feedback：接受 AA-C3/Stage-AD candidate，或执行**最多一轮、最多三个 source-causal hypothesis** 的最终 bounded tuning。失败则 `MODEL_REDESIGN_REQUIRED`，不无限搜参数。

## M3 — Vehicle profiles

Hellcat 形成 versioned Engineering Profile 后迁移 Ferrari 458、RX-7 FD。迁移 source/event/state 方法，不复制统一 EQ/pitch。

## M4 — Product contracts

冻结 Vehicle Profile schema、AudioParameterPackage、speed+acceleration→VirtualEngineState contract、Golden state/PCM/metrics。

## M5 — Portable C++ / Android

实现 realtime subset、Python↔C++ regression、NDK + Oboe/AAudio、vehicle selector、input conditioning、lifecycle、latency/xrun/CPU/memory/thermal gates。

## M6 — In-car validation

覆盖 idle、低速、cruise、gentle/hard acceleration、shift、lift/coast、afterfire、idle return、sensor gap、profile switch、长时间运行。

## M7 — R1

合法同步真实数据到位后，才做正式 Order-RPM/OEM-level calibration。

## Deferred

ESP32、board/BLE/WiFi/OTA/CAN-analyser/external amplifier 全部后移；只有 App 路线成熟且用户重新开启独立硬件需求时评估。
