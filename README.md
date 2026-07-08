# Tesla Simulate Vico

Language: [中文介绍](#中文介绍) | [English Overview](#english-overview)

---

## 中文介绍

`Tesla Simulate Vico` 是一个面向 ESP32-S3 的车载声浪模拟固件工程。项目目标是在不向车辆 CAN 总线发送任何报文的前提下，监听 Tesla OBD-II / CAN 车辆状态，生成可调的模拟发动机声浪，并通过 BLE、SD 卡和本地外设完成配置、状态显示与后续 OTA 升级。

当前工程已经进入可编译的固件 baseline 阶段：CAN listen-only、基础车速/扭矩帧解析、I2S 音频输出、BLE GATT 配置、SD JSON 持久化、编码器、油门电位器、WS2812 状态灯和 WiFi OTA 代码骨架都已经接入。需要特别说明的是，当前声浪算法仍是 RPM 驱动的基础合成路径，不是已经完成的产品级速度/加速度分层声浪模型；BLE、WiFi 和 OTA 的完整运行闭环仍需要上板验证。

### 项目目标

- 安全监听 Tesla CAN 数据，固件不暴露 CAN transmit API。
- 将车速、油门和虚拟 RPM 转换为 I2S 音频输出。
- 通过 BLE GATT 暴露配置、状态、诊断和 OTA 参数。
- 将运行时配置保存到 SD 卡 JSON 文件。
- 支持本地外设：旋钮编码器、油门电位器、WS2812 状态灯。
- 为下一阶段 WiFi HTTPS OTA、USB CDC 调试和高级声浪调参保留扩展入口。

### 当前硬件目标

| 项目 | 说明 |
|---|---|
| MCU | ESP32-S3-WROOM-1-N16R8 |
| Framework | ESP-IDF v5.3.2 |
| Audio DAC | PCM5102A-class I2S DAC |
| CAN | ESP32-S3 TWAI listen-only path |
| Config storage | SD card JSON |
| BLE stack | ESP-IDF NimBLE |
| Pin map | `components/config/include/config/pin_map.h` |

### 工程结构

| 路径 | 作用 |
|---|---|
| `main/` | ESP-IDF `app_main` 入口 |
| `components/app/` | 应用协调层：加载配置、推进 tick、连接 CAN/audio/BLE/storage/OTA |
| `components/config/` | pin map 与 `RuntimeConfig` |
| `components/domain/` | 纯逻辑模型：车辆状态、虚拟 RPM 计算 |
| `components/can/` | Tesla CAN frame parser 与 TWAI listen-only source |
| `components/audio/` | I2S 声音合成、音量缩放、overspeed mute |
| `components/ble/` | NimBLE GATT 服务、状态读写、OTA 参数配置 |
| `components/storage/` | SD JSON 配置读写 |
| `components/input/` | 编码器与油门电位器 |
| `components/ui/` | WS2812 状态灯 |
| `components/ota/` | WiFi STA、HTTPS OTA、版本/分区/错误状态 |
| `openspec/specs/` | 当前固件主规格 |
| `scripts/esp-idf.ps1` | Windows PowerShell 下的一键 ESP-IDF 环境激活与命令转发脚本 |

### 已实现功能

- CAN receive: TWAI listen-only 接收，不提供 transmit API。
- Tesla frame parsing: 当前 baseline 覆盖 `0x256` / `0x116` 解析路径。
- Engine model: 当前根据 `speed_kph` 和 `throttle` 生成 `virtual_rpm`。
- Audio output: I2S 输出基础 RPM tone，支持运行时音量与 overspeed mute。
- BLE services: 主服务 `0xfff0`，兼容服务 `0xffe0`。
- BLE characteristics: `ffe2` 状态快照、`ffe5` 诊断 JSON、`ffe8` OTA 设置 JSON、`ffea` live status。
- Persistence: SD JSON 保存运行时配置。
- Peripherals: 编码器、油门电位器、WS2812 状态灯已接入主流程。
- OTA baseline: OTA 分区表、WiFi/HTTPS OTA 组件、BLE OTA 配置入口已接入。

### 当前未完成 / 未实机证明

- BLE 广播、建链、读写回读仍需要实体 ESP32-S3 验收。
- WiFi 入网与 HTTPS OTA 下载、分区切换、失败回滚仍需要上板验证。
- IRAM release gate 仍未完全关闭；最新记录仍为 `16383 / 16384`。
- 产品级声浪算法尚未完成：还没有速度/加速度/负载分层声浪模型，也没有 MATLAB 或等价仿真探针定参后的固件移植。
- USB CDC 调试通道和高级调参工具仍属于后续阶段。

### 构建

推荐在普通 PowerShell 中使用项目脚本：

```powershell
cd E:\Tesla_speed\prj
.\scripts\esp-idf.ps1 build
```

该脚本会为本机 ESP-IDF v5.3.2 安装设置：

- `IDF_PATH=E:\project\ESP_IDF_support\v5.3.2\esp-idf`
- `IDF_TOOLS_PATH=E:\project\ESP_IDF_support\tools`
- `IDF_PYTHON_ENV_PATH=E:\project\ESP_IDF_support\tools\python_env\idf5.3_py3.14_env`

如果已经在 VSCode ESP-IDF 插件终端或 ESP-IDF Terminal 中，也可以直接运行：

```powershell
idf.py build
```

### 常用验证命令

```powershell
cd E:\Tesla_speed\prj
.\scripts\esp-idf.ps1 build
.\scripts\esp-idf.ps1 size
.\scripts\esp-idf.ps1 size-components
openspec validate --all --strict --json
```

当前已记录的验证快照：

- `openspec validate --all --strict --json`: `5/5` pass
- `.\scripts\esp-idf.ps1 build`: pass
- `.\scripts\esp-idf.ps1 size`: pass
- `.\scripts\esp-idf.ps1 size-components`: pass
- app image fits OTA app partition with large flash margin
- IRAM still needs release-hardening attention

### 烧录与串口监视

```powershell
cd E:\Tesla_speed\prj
.\scripts\esp-idf.ps1 -p COMx flash monitor
```

将 `COMx` 替换为实际 ESP32-S3 串口号。

### BLE 合约摘要

| UUID | 当前用途 |
|---|---|
| `0xfff0` | 主 BLE GATT 服务 |
| `0xffe0` | 历史兼容服务 |
| `ffe2` | 车辆状态快照读取 |
| `ffe5` | 诊断 JSON，包含版本、分区、WiFi/OTA 状态 |
| `ffe8` | OTA 设置 JSON：SSID、password、OTA URL、auto check |
| `ffea` | live device status read / notify |

OTA 相关 BLE 写入只更新并持久化配置，不会在写入瞬间触发升级；OTA 检查在下次启动后按配置执行。

### 安全边界

- CAN 只监听，不主动发包。
- overspeed mute 默认保护高速场景。
- 音量会被 clamp 到 `0..100` 后再作用到 PCM sample。
- OTA baseline 可编译，但还没有完成硬件级成功/失败路径验收。

### 下一步建议

1. 完成 BLE 实机验收：广播、连接、`ffe2` 读取、至少一个可写特征回读。
2. 完成 WiFi 入网和 HTTPS OTA 实机验收。
3. 针对 IRAM `1` byte margin 做进一步 release hardening 或形成明确风险接受记录。
4. 单独启动声浪算法阶段：采样/建模、MATLAB 或等价仿真、参数定点化、固件集成。
5. S8 再推进 USB CDC 与高级调参工具。

### License

MIT, (c) 2026 JoviF

---

## English Overview

`Tesla Simulate Vico` is an ESP32-S3 firmware project for in-car engine sound simulation. The firmware is designed to listen to Tesla OBD-II / CAN vehicle state in listen-only mode, synthesize a configurable engine-like sound over I2S, and expose runtime configuration and telemetry through BLE, SD-card persistence, local inputs, and a future OTA workflow.

The project is currently a buildable firmware baseline. CAN listen-only reception, basic Tesla frame parsing, I2S audio output, BLE GATT configuration, SD JSON persistence, encoder input, throttle potentiometer input, WS2812 status LED output, and a WiFi OTA baseline are already integrated. The current sound algorithm is still an RPM-driven baseline synthesizer, not a finished production-grade speed/acceleration sound model. BLE, WiFi, and OTA runtime acceptance still require hardware validation.

### Project Goals

- Safely listen to Tesla CAN data without exposing any CAN transmit API.
- Convert speed, throttle, and virtual RPM into I2S audio output.
- Expose configuration, telemetry, diagnostics, and OTA settings over BLE GATT.
- Persist runtime configuration to SD-card JSON.
- Support local peripherals: rotary encoder, throttle potentiometer, and WS2812 status LED.
- Keep clean extension points for WiFi HTTPS OTA, USB CDC diagnostics, and advanced sound tuning.

### Hardware Target

| Item | Description |
|---|---|
| MCU | ESP32-S3-WROOM-1-N16R8 |
| Framework | ESP-IDF v5.3.2 |
| Audio DAC | PCM5102A-class I2S DAC |
| CAN | ESP32-S3 TWAI listen-only path |
| Config storage | SD-card JSON |
| BLE stack | ESP-IDF NimBLE |
| Pin map | `components/config/include/config/pin_map.h` |

### Repository Layout

| Path | Purpose |
|---|---|
| `main/` | ESP-IDF `app_main` entry point |
| `components/app/` | Application coordinator for config, tick loop, CAN, audio, BLE, storage, and OTA |
| `components/config/` | Pin map and `RuntimeConfig` |
| `components/domain/` | Pure vehicle-state and virtual-RPM logic |
| `components/can/` | Tesla CAN frame parser and TWAI listen-only source |
| `components/audio/` | I2S synthesis, runtime volume scaling, and overspeed mute |
| `components/ble/` | NimBLE GATT service, state readback, config writes, and OTA settings |
| `components/storage/` | SD-card JSON config store |
| `components/input/` | Rotary encoder and throttle potentiometer |
| `components/ui/` | WS2812 status LED |
| `components/ota/` | WiFi STA, HTTPS OTA, version/partition/error status |
| `openspec/specs/` | Active firmware specifications |
| `scripts/esp-idf.ps1` | Windows PowerShell helper for ESP-IDF environment activation and command forwarding |

### Implemented Features

- CAN receive: TWAI listen-only mode, with no transmit API.
- Tesla frame parsing: current baseline covers `0x256` / `0x116`.
- Engine model: maps `speed_kph` and `throttle` into `virtual_rpm`.
- Audio output: basic RPM tone over I2S, runtime volume, and overspeed mute.
- BLE services: primary service `0xfff0`, compatibility service `0xffe0`.
- BLE characteristics: `ffe2` state snapshot, `ffe5` diagnostics JSON, `ffe8` OTA settings JSON, `ffea` live status.
- Persistence: SD-card JSON runtime config.
- Peripherals: encoder, throttle potentiometer, and WS2812 status LED wired into the app flow.
- OTA baseline: OTA partition table, WiFi/HTTPS OTA component, and BLE OTA config entry are integrated.

### Not Finished / Not Yet Proven On Hardware

- BLE advertising, connection, and read/write round-trip acceptance still need device testing.
- WiFi join, HTTPS OTA download, partition swap, and rollback/failure behavior still need device testing.
- IRAM release gate is still open; the latest recorded snapshot is `16383 / 16384`.
- Production sound modeling is not complete: there is no speed/acceleration/load layered model yet, and no MATLAB or equivalent probe-tuned model has been ported into firmware.
- USB CDC diagnostics and advanced tuning tools are deferred to a later phase.

### Build

Recommended from a normal PowerShell terminal:

```powershell
cd E:\Tesla_speed\prj
.\scripts\esp-idf.ps1 build
```

The helper script configures the local ESP-IDF v5.3.2 environment:

- `IDF_PATH=E:\project\ESP_IDF_support\v5.3.2\esp-idf`
- `IDF_TOOLS_PATH=E:\project\ESP_IDF_support\tools`
- `IDF_PYTHON_ENV_PATH=E:\project\ESP_IDF_support\tools\python_env\idf5.3_py3.14_env`

Inside a VSCode ESP-IDF terminal or a pre-activated ESP-IDF shell, the raw command also works:

```powershell
idf.py build
```

### Common Verification Commands

```powershell
cd E:\Tesla_speed\prj
.\scripts\esp-idf.ps1 build
.\scripts\esp-idf.ps1 size
.\scripts\esp-idf.ps1 size-components
openspec validate --all --strict --json
```

Current recorded verification snapshot:

- `openspec validate --all --strict --json`: `5/5` pass
- `.\scripts\esp-idf.ps1 build`: pass
- `.\scripts\esp-idf.ps1 size`: pass
- `.\scripts\esp-idf.ps1 size-components`: pass
- app image fits the OTA app partition with large flash margin
- IRAM still needs release-hardening attention

### Flash And Monitor

```powershell
cd E:\Tesla_speed\prj
.\scripts\esp-idf.ps1 -p COMx flash monitor
```

Replace `COMx` with the actual ESP32-S3 serial port.

### BLE Contract Summary

| UUID | Current Purpose |
|---|---|
| `0xfff0` | Primary BLE GATT service |
| `0xffe0` | Legacy compatibility service |
| `ffe2` | Vehicle-state snapshot read |
| `ffe5` | Diagnostics JSON with version, partition, WiFi/OTA status |
| `ffe8` | OTA settings JSON: SSID, password, OTA URL, auto check |
| `ffea` | Live device status read / notify |

OTA-related BLE writes only update and persist configuration. They do not trigger an immediate OTA update; OTA checks run on the next boot when enabled by config.

### Safety Boundaries

- CAN is listen-only and never transmits frames.
- Overspeed mute protects high-speed conditions.
- Runtime volume is clamped to `0..100` before scaling PCM samples.
- The OTA baseline builds, but hardware success/failure-path acceptance is not yet complete.

### Recommended Next Steps

1. Complete BLE hardware acceptance: advertising, connection, `ffe2` read, and one writable characteristic readback.
2. Prove WiFi join and HTTPS OTA on hardware.
3. Further reduce the IRAM `1` byte margin or document an explicit risk acceptance.
4. Start a separate sound-modeling phase: capture/model, MATLAB or equivalent simulation, fixed-point parameterization, and firmware integration.
5. Continue S8 with USB CDC and advanced tuning tools.

### License

MIT, (c) 2026 JoviF
