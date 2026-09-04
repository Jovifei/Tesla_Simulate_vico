# Tesla Simulate Vico ESP32 固件子路线图

更新：2026-09-04

> 本文只负责 ESP32-S3 产品壳、硬件与嵌入式集成路线。全项目主路线见 `02-project-master-roadmap.md`。旧版本把“S8 声浪算法”写成待开始已经过时：S12 PC/Python 声学研发已推进到 Hellcat pre-human gate，但**高级声浪尚未进入 ESP32 runtime**。

## 目标

把当前可编译 ESP-IDF 产品壳推进到：

- 安全 CAN listen-only；
- 稳定 VehicleState；
- BLE/SD/WiFi/IoT/OTA 配置与诊断；
- 高级 approved sound runtime；
- I2S / DAC / AMP / speaker；
- 板级与实车验收。

## 固定决策

- CAN 永远 listen-only，不新增产品 transmit API；
- BLE 主服务 `0xfff0`、兼容服务 `0xffe0` 保持稳定；
- `ffe8` 承载 WiFi / OTA / IoT 配置；
- `App::tick()` 保持非阻塞协调职责；
- OTA 后台执行；
- 声音算法的权威模型来自 S12，不在 ESP32 上重新发明另一套车型算法；
- 平台适配前先有 `AudioParameterPackage` + portable C++ equivalence。

## 当前固件基线

| 范围 | 状态 | 证据/说明 |
|---|---|---|
| CAN listen-only | Implemented | `components/can/` |
| CAN frame parser | Implemented | 当前 `0x256` / `0x116` baseline |
| I2S audio baseline | Implemented | 当前 RPM/基础合成，非 S12 高级模型 |
| BLE GATT | Implemented / board blocked | `components/ble/` |
| SD JSON | Implemented / board blocked | `components/storage/` |
| input / UI | Implemented / board blocked | encoder / pot / WS2812 |
| Network/IoT/OTA | Implemented / board blocked | `status/network/iot/ota` |
| IRAM | Risk open | 历史 size 接近上限，需要 fresh build + board stress |
| S12 advanced sound | Verified on PC/Python only | Hellcat AA-C3 pre-human; 未接入 firmware |

## 固件阶段

### F0 — S0–S7 product shell baseline

代码已完成；硬件证明未完成。

### F1 — Board bring-up / S7 acceptance

必须验证：

1. flash/boot；
2. BLE advertising/read/write/notify；
3. SD load/save；
4. I2S output；
5. encoder/pot/WS2812；
6. WiFi join/reconnect；
7. MQTT uplink/downlink；
8. HTTPS OTA success/failure；
9. 25 ms app coordination 不被后台任务阻塞；
10. CAN analyser 证明无发送。

### F2 — Resource/release hardening

- fresh `idf.py size` / `size-components`；
- BLE + WiFi + OTA + I2S + LED 并发；
- heap/PSRAM/IRAM；
- watchdog；
- OTA 时 audio/UI 降级策略；
- thermal/long-run。

### F3 — Advanced sound contract integration

**只有 Hellcat Human PASS / Engineering Profile 后启动。**

依赖：

```text
AudioParameterPackage
+ Golden VehicleState
+ Golden PCM/metrics
+ portable C++ runtime
+ Python↔C++ equivalence
```

然后：

```text
components/domain/VehicleState
→ ESP32 sound adapter
→ components/audio/I2S
```

### F4 — Embedded optimization

根据 ESP32-S3 实测资源：

- source layer reduction；
- LUT / fixed-point；
- filter/order simplification；
- block/DMA strategy；
- PSRAM policy；
- quality tier；
- underrun/latency gate。

### F5 — Vehicle pilot

- Tesla CAN signal truth；
- state freshness/fallback；
- no-TX hardware proof；
- startup/fault/overspeed mute；
- external speaker chain；
- real driving scene validation；
- power/thermal/EMC。

## 与 S12 声学主线的接口

ESP32 固件不直接消费 Python implementation detail，而消费受版本控制的产品合同：

```text
AudioParameterPackage
VehicleState schema
Golden traces
Realtime C++ core
```

这样可以避免：

- PC 一套算法、Android 一套算法、ESP32 又一套算法；
- 声学修复被平台特供 hack 吞掉；
- 无法复现试听 winner。

## 当前正确执行顺序

1. 保持现有固件 shell 可构建；
2. 在独立硬件工作流完成 F1/F2；
3. 声学主线先关闭 Stage-AC post-merge truth + Human Hellcat；
4. Human PASS 后定义 cross-language runtime contract；
5. C++/Android/desktop 实时证明；
6. 再做 ESP32 advanced sound port；
7. 最后进入 controlled vehicle pilot。
