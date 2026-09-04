# Tesla Simulate Vico ESP32 固件待完成清单（Deferred / Historical）

更新：2026-09-04

> **状态：DEFERRED_FUTURE_OPTION**
>
> 本文件不再是当前 active backlog。当前 active backlog 是 `02-project-master-backlog.md`，主线为声音真实性 + Android App 实时声浪。

## 保留但不执行的历史待办

以下任务全部暂停：flash/boot、BLE、SD、I2S、encoder/pot/WS2812、WiFi/MQTT/OTA、IRAM/PSRAM、CAN analyser、ESP32 advanced sound adapter、embedded tuning、DAC/AMP/speaker、ESP32 vehicle pilot。

这些不是当前 blocker，也不应出现在当前 Agent 的 P0/P1 执行列表中。

## 当前 active backlog

`docs/09-backlog/02-project-master-backlog.md`

当前顺序：

```text
AC8
→ Jovi Hellcat V3 audition
→ Engineering Profile
→ Ferrari / RX-7
→ speed + acceleration → VirtualEngineState
→ AudioParameterPackage
→ portable C++
→ Android realtime App
→ vehicle selector / realtime playback
→ in-car validation
```

## 重新开启条件

只有 App 路线完成并且用户明确要求独立嵌入式版本时，才重新激活本文件。

```text
ESP32_ACTIVE_BACKLOG = false
ESP32_BLOCKS_CURRENT_PRODUCT = false
```
