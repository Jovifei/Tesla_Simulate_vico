# Tesla Simulate Vico

Language: [中文说明](#中文说明) | [English Overview](#english-overview)

## 中文说明

`Tesla Simulate Vico` 是一个面向 ESP32-S3 的车载声浪模拟固件工程。目标是在不向车辆 CAN 总线发送报文的前提下，监听 Tesla CAN/OBD-II 车辆状态，生成可调的模拟发动机声浪，并通过 BLE、SD 卡、WiFi/IoT/OTA 和本地外设完成配置、诊断和升级闭环。

当前工程已经具备可编译 ESP-IDF baseline，并完成 S7 架构迁移基线：BLE 作为配置入口，Network/Link 管 WiFi，IoT/MQTT 管云端上下行，OTA 管后台升级执行，App 保留 25 ms 车辆模拟主循环协调。

### 当前结论

| 范围 | 状态 | 说明 |
|---|---|---|
| CAN listen-only | 已实现 | TWAI listen-only，当前解析 `0x256` / `0x116` baseline，不提供 transmit API |
| I2S audio baseline | 已实现 | RPM 驱动的基础合成、音量、overspeed mute |
| BLE GATT | 已实现，待实机验收 | 主服务 `0xfff0`，兼容服务 `0xffe0`，`ffe1..ffee` 已挂载 |
| SD JSON 配置 | 已实现，待实机验收 | 保存 runtime config，缺卡或缺字段使用默认值 |
| 外设 | 已接入，待实机验收 | encoder、throttle pot、WS2812 |
| S7 Network/IoT/OTA | 代码基线已完成，待实机验收 | `status`、`network`、`iot`、`ota` 分层已存在 |
| IRAM release gate | 风险未关闭 | 当前 ESP-IDF size 报告 IRAM `16383 / 16384`，需实机压测或功能分档 |
| 声浪算法 | 未产品化 | 当前不是速度/加速度/负载差异化声浪模型，需要 MATLAB 或等效仿真定参 |

### 工程结构

| 路径 | 作用 |
|---|---|
| `main/` | ESP-IDF `app_main` 入口 |
| `components/app/` | 应用协调层，保留 25 ms 车辆模拟主循环 |
| `components/status/` | 统一运行状态镜像：WiFi/IoT/OTA/版本/分区/错误 |
| `components/network/` | WiFi STA、EventGroup、连接/重连/停止状态机 |
| `components/iot/` | MQTT 上下行、设备/车辆/OTA 进度发布、`ota_start` 下行解析 |
| `components/ota/` | HTTPS OTA worker、请求队列、进度和失败原因 |
| `components/ble/` | NimBLE GATT，`ffe8` 配置入口，`ffe5`/`ffea` 状态输出 |
| `components/config/` | pin map 和 `RuntimeConfig` |
| `components/storage/` | SD FATFS JSON 配置持久化 |
| `components/can/` | CAN parser 和 TWAI listen-only source |
| `components/audio/` | I2S PCM 输出和基础声浪合成 |
| `components/domain/` | 车辆状态与虚拟 RPM 模型 |
| `components/input/` | encoder 和 throttle potentiometer |
| `components/ui/` | WS2812 状态灯 |
| `docs/` | 公开文档入口，目录使用 `NN-english-kebab` 命名 |
| `openspec/` | 当前固件规格与变更提案 |
| `scripts/esp-idf.ps1` | Windows PowerShell ESP-IDF v5.3.2 环境脚本 |

### 文档入口

- [文档总入口](docs/README.md)
- [文档命名规则](docs/GUIDE.md)
- [固件完成路线图](docs/04-planning/01-firmware-roadmap.md)
- [固件待完成清单](docs/09-backlog/01-firmware-backlog.md)

### BLE 合约

BLE UUID 合约保持不变：

| UUID | 当前用途 |
|---|---|
| `0xfff0` | 主 BLE GATT 服务 |
| `0xffe0` | 历史兼容服务 |
| `ffe2` | 车辆状态快照 |
| `ffe5` | 诊断 JSON：version、partition、wifi_state、iot_state、ota_state、ota_progress、last_error |
| `ffe8` | WiFi / OTA / IoT 配置 JSON |
| `ffea` | live device status read/notify |

`ffe8` 写入只更新配置和待持久化状态，不在 BLE 写回调中直接执行 OTA。OTA 由启动配置或 MQTT 下行命令进入后台任务执行。

### 构建

普通 PowerShell 推荐使用项目脚本：

```powershell
cd E:\Tesla_speed\prj
.\scripts\esp-idf.ps1 build
```

常用验证命令：

```powershell
cd E:\Tesla_speed\prj
.\scripts\esp-idf.ps1 build
.\scripts\esp-idf.ps1 size
.\scripts\esp-idf.ps1 size-components
openspec validate --all --strict --json
```

烧录与串口：

```powershell
cd E:\Tesla_speed\prj
.\scripts\esp-idf.ps1 -p COMx flash monitor
```

如果 PowerShell 或 VSCode 输出 `Not using an unsupported version of tool ninja found in PATH: 1.13.0`，说明系统 PATH 里有比 ESP-IDF 自带版本更靠前的 Ninja。优先使用 `.\scripts\esp-idf.ps1 build`，该脚本会把 ESP-IDF v5.3.2 自带 Python、Ninja 1.12.1 和 CMake 放到 PATH 前面。

### 当前未完成项

- BLE 广播、连接、`ffe2`/`ffe5`/`ffe8`/`ffea` 读写需要 ESP32-S3 实机证明。
- WiFi join、MQTT 上线、MQTT 下行 `ota_start`、HTTPS OTA 成功/失败路径需要实机证明。
- IRAM release gate 仍有风险，当前 `size` 报告 `16383 / 16384`，需继续压测或形成明确接受记录。
- 产品级声浪算法尚未完成，缺少速度/加速度/负载分层模型、MATLAB 或等效仿真、听感样本和固件定点化验证。
- USB CDC 与高级调参工具推迟到 S8/S9。

## English Overview

`Tesla Simulate Vico` is an ESP32-S3 firmware project for in-car engine-sound simulation. It listens to Tesla CAN/OBD-II vehicle state in listen-only mode, generates a configurable engine-like sound over I2S, and exposes runtime configuration, diagnostics, and upgrade hooks through BLE, SD-card persistence, WiFi/IoT/OTA, and local peripherals.

The current project is a buildable ESP-IDF baseline. S7 aligns the firmware with Jovi's earlier project architecture: BLE remains the configuration entry point, Network/Link owns WiFi, IoT/MQTT owns cloud interaction, OTA owns upgrade execution, and App keeps the 25 ms vehicle simulation loop focused.

### Current Status

| Area | Status | Notes |
|---|---|---|
| CAN listen-only | Implemented | TWAI listen-only, current parser baseline covers `0x256` / `0x116`, no transmit API |
| I2S audio baseline | Implemented | RPM-based baseline synth, volume, overspeed mute |
| BLE GATT | Implemented, hardware pending | Primary service `0xfff0`, compatibility service `0xffe0`, `ffe1..ffee` exposed |
| SD JSON config | Implemented, hardware pending | Runtime config persistence with defaults for missing fields |
| Peripherals | Integrated, hardware pending | Encoder, throttle potentiometer, WS2812 |
| S7 Network/IoT/OTA | Code baseline complete, hardware pending | `status`, `network`, `iot`, and `ota` layers exist |
| IRAM release gate | Still risky | ESP-IDF size currently reports `16383 / 16384`; board stress testing or feature-tier acceptance is required |
| Sound model | Not product-complete | Current output is not yet a speed/acceleration/load layered sound model |

### Build

```powershell
cd E:\Tesla_speed\prj
.\scripts\esp-idf.ps1 build
```

Common verification:

```powershell
cd E:\Tesla_speed\prj
.\scripts\esp-idf.ps1 build
.\scripts\esp-idf.ps1 size
.\scripts\esp-idf.ps1 size-components
openspec validate --all --strict --json
```

Flash and monitor:

```powershell
cd E:\Tesla_speed\prj
.\scripts\esp-idf.ps1 -p COMx flash monitor
```

### Known Boundaries

- BLE, WiFi, MQTT, and OTA still require on-device acceptance evidence.
- IRAM remains a release-hardening risk until fresh board testing accepts it or the feature set is split.
- The production sound model still needs capture/modeling, MATLAB or equivalent simulation, firmware parameterization, and bench listening validation.
- USB CDC and advanced tuning tools are deferred to S8/S9.

### License

MIT, (c) 2026 JoviF
