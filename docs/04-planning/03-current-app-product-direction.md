# 当前产品方向：App-first 实时声浪

日期：2026-09-04

> 本文覆盖旧的“当前阶段以 ESP32 为产品主线”理解。当前阶段的产品载体是车内 App；ESP32 仅保留为后期可选简化方案，不是当前 blocker，也不进入当前实施计划。

## 当前目标

当前项目要先完成**声音真实性算法 + App 实时运行**：

```text
车内 App
  ↓
采集/获得车辆速度 speed
采集/计算车辆加速度 acceleration
  ↓
VehicleState / VirtualEngineState
  ├─ virtual RPM
  ├─ virtual load / throttle proxy
  ├─ virtual gear / shift
  ├─ lift / overrun
  └─ transient state
  ↓
用户选择 Vehicle Profile
  ├─ Hellcat
  ├─ Ferrari 458
  ├─ RX-7 FD
  └─ 后续车型
  ↓
S12 实时声浪算法
  ↓
App 实时音频输出
```

当前最小必须输入是 **speed + acceleration**。RPM/load/gear 等可以由 App 内部虚拟发动机状态模型推导；以后如接入 CAN/OBD 或其他车辆接口，可以作为更高质量的 VehicleState input adapter，但不是当前算法阶段的前置条件。

## 当前阶段不做什么

- 不把 ESP32 作为当前产品主线；
- 不做 ESP32 advanced sound port；
- 不做 ESP32 板级 BLE/WiFi/MQTT/OTA/IRAM 验收作为当前 gate；
- 不因为仓库已有 ESP32 代码就让固件工作阻塞声音算法/App；
- 不要求当前 App 先依赖 Tesla CAN 才能运行。

仓库中的 ESP32-S3 固件、原理图和历史路线仍保留，作为**历史资产 / 未来可选简化 runtime**。只有 App 版声音真实性、实时性和车内体验稳定后，才重新评估是否需要嵌入式版本。

## 当前产品化顺序

```text
Stage-AC closeout
→ Jovi Hellcat V3 试听
→ AA-C3 接受或 ONE source-causal Round2
→ Hellcat Engineering Profile
→ Ferrari / RX-7 车型迁移
→ AudioParameterPackage
→ C++/Android realtime sound core
→ App speed/acceleration state adapter
→ App 车型选择 + 实时播放
→ 车内延迟/连续性/CPU/underrun 验收
→ 继续提高声音真实感与车型覆盖
→ R1 数据具备时做正式标定
→ ESP32 simplified runtime（仅后期可选）
```

## 当前成功标准

当前阶段真正完成必须满足：

1. 声音真实感经 Jovi 人耳接受；
2. 不同车型有可辨识身份；
3. speed/acceleration 连续变化时，虚拟 RPM/load/gear 和声音连续、自然；
4. tip-in / acceleration / shift / lift / afterfire / idle return 不出现跳变；
5. App 内可选择不同车型 profile；
6. App 实时播放 CPU、内存、延迟、underrun 达到可用水平；
7. App pause/resume、音频焦点、状态恢复不破坏持续相位/事件状态。

这就是当前项目主线。