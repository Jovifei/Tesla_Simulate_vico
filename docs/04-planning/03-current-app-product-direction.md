# 当前产品方向：App-first 实时声浪

日期：2026-09-04

> 当前阶段的产品载体是车内 App。ESP32 仅保留为后期可选简化方案，不是当前 blocker，也不进入当前实施计划。
>
> 主证据：`S12_Handoff_Package_2026-09-03` ≈ 90%；旧聊天/此前总结 ≈ 10%；用户当前明确方向优先。

## 当前目标

```text
车内 App
→ speed + acceleration
→ VehicleState / VirtualEngineState
   ├─ virtual RPM
   ├─ virtual load / throttle proxy
   ├─ virtual gear / shift
   ├─ lift / overrun
   └─ transient state
→ Vehicle Profile (Hellcat / Ferrari / RX-7 / ...)
→ S12 实时声浪算法
→ App 实时音频输出
```

当前最小必须输入是 **speed + acceleration**。其它发动机状态由 App 内部推导；CAN/OBD 是 future richer input adapter，不是当前前置条件。

## 当前阶段不做

- ESP32 current mainline；
- ESP32 advanced sound port；
- ESP32 BLE/WiFi/MQTT/OTA/IRAM board gates；
- App 前置 Tesla CAN。

## 当前产品化顺序

```text
AC8
→ Jovi Hellcat V3 blind audition
→ AA-C3 accept OR ONE source-causal Round2
→ Hellcat Engineering Profile
→ Ferrari / RX-7
→ AudioParameterPackage
→ speed/acceleration → VirtualEngineState
→ Golden traces / PCM
→ portable C++
→ Python ↔ C++ equivalence
→ Android App realtime
→ vehicle selector + playback
→ in-car validation
→ R1 formal calibration when available
→ ESP32 only if later explicitly reopened
```

## 当前成功标准

声音 Human accepted、车型可辨识、speed/acceleration 驱动自然、状态连续、App 可实时稳定播放、车型可选择、latency/underrun/CPU/memory 达标、车内体验通过。
