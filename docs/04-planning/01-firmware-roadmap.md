# Tesla Simulate Vico ESP32 固件子路线图（Deferred / Historical）

更新：2026-09-04

> **状态：DEFERRED_FUTURE_OPTION**。当前项目主线是 S12 声音真实性 → Human Gate → Android App 实时声浪。本文件仅保留已有 ESP32 工程资产和未来可能的嵌入式简化路线，不得作为当前 blocker、优先级来源或当前最终产品描述。

## 历史已有资产

ESP-IDF baseline、TWAI CAN parser、I2S baseline、BLE GATT、SD JSON、encoder/pot/WS2812、WiFi/MQTT/OTA/RuntimeStatus、25 ms App tick、build/size/OpenSpec 设施均保留。

## 当前不执行

board bring-up、BLE/WiFi/MQTT/OTA 板级验收、IRAM/PSRAM、CAN analyser、advanced S12 port、I2S DAC/AMP/speaker、ESP32 vehicle pilot。

## 重新开启条件

只有 Android App 已 Human accepted、speed+acceleration 多车型 realtime 稳定、AudioParameterPackage/C++ 稳定、资源和延迟数据明确，并且用户重新要求独立嵌入式版本时，才评估：

```text
Approved App/C++ runtime
→ resource reduction
→ ESP32 simplified runtime
→ hardware validation
```

当前权威路线见：

- `03-current-app-product-direction.md`
- `02-project-master-roadmap.md`
- `../knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md`
- `../09-backlog/02-project-master-backlog.md`
