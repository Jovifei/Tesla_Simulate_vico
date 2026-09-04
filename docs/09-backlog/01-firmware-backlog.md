# Tesla Simulate Vico ESP32 固件待完成清单（Deferred）

更新：2026-09-04

> **状态：DEFERRED_FUTURE_OPTION**
>
> 本文件不再是当前 active backlog。当前 active backlog 是 `02-project-master-backlog.md`，主线为声音真实性 + Android App 实时声浪。

## 保留但不执行的历史待办

以下任务全部暂停：

- 实机 flash/boot；
- BLE advertising/read/write/notify；
- SD JSON 板级读写；
- I2S 板级输出；
- encoder/pot/WS2812；
- WiFi/MQTT/HTTPS OTA；
- IRAM/PSRAM/heap stress；
- CAN analyser zero-TX；
- ESP32 advanced S12 sound adapter；
- embedded quality/resource tuning；
- DAC/AMP/speaker hardware chain；
- ESP32 vehicle pilot。

这些不是当前 blocker，也不应出现在当前 Agent 的 P0/P1 执行列表中。

## 当前 active backlog

请转到：

`docs/09-backlog/02-project-master-backlog.md`

当前优先级是：

```text
AC8
→ Jovi Hellcat V3 audition
→ Engineering Profile
→ Ferrari / RX-7
→ speed + acceleration VehicleState
→ AudioParameterPackage
→ portable C++
→ Android realtime App
→ vehicle selector / realtime playback
→ in-car validation
```

## 重新开启条件

只有 App 路线完成并且用户明确要求独立嵌入式版本时，才把本文件重新激活。

在此之前统一标记：

`ESP32_ACTIVE_BACKLOG = false`
