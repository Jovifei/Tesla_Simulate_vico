# Tesla Simulate Vico ESP32 固件子路线图（Deferred / Historical）

更新：2026-09-04

> **状态：DEFERRED_FUTURE_OPTION**
>
> 当前项目主线不是 ESP32。当前主线是 S12 声音真实性 → Human Gate → Android App 实时声浪。本文仅保留已有 ESP32 工程资产和未来可能的嵌入式简化路线，不得作为当前 blocker、优先级来源或“当前最终产品”描述。

## 历史已有资产

仓库已经存在：

- ESP-IDF baseline；
- TWAI CAN listen-only/parser baseline；
- I2S audio baseline；
- BLE GATT；
- SD JSON；
- encoder / throttle pot / WS2812；
- WiFi / MQTT / OTA / RuntimeStatus；
- 25 ms App tick；
- build/size/OpenSpec 相关工程设施。

这些内容说明历史固件骨架存在，但**当前不要求继续上板、不要求高级 S12 声音接入、不要求完成 BLE/WiFi/OTA/IRAM 验收**。

## 当前不执行

- board bring-up；
- BLE/WiFi/MQTT/OTA 板级验收；
- IRAM/PSRAM release hardening；
- CAN analyser no-TX 证明；
- advanced S12 sound port；
- I2S DAC/AMP/speaker 产品化；
- ESP32 vehicle pilot。

## 何时可以重新开启

只有满足以下前提并且用户明确重新开启 ESP32 路线时：

1. Android App 版声音真实性已经 Human accepted；
2. App 能稳定使用 speed + acceleration 驱动多车型实时声浪；
3. AudioParameterPackage / portable C++ 已稳定；
4. CPU/memory/latency/quality 已有真实数据；
5. 确实存在独立硬件运行的产品需求。

届时才可评估：

```text
Approved App/C++ runtime
→ resource reduction
→ ESP32 simplified runtime
→ I2S output
→ hardware validation
```

## 当前权威路线

请以以下文档为准：

- `03-current-app-product-direction.md`
- `02-project-master-roadmap.md`
- `../08-reports/10-project-status-20260904.md`
- `../knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md`
- `../09-backlog/02-project-master-backlog.md`

如果历史固件文档与这些 active 文档冲突，以 App-first active 文档为准。