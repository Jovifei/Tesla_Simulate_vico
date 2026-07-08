# Tesla Simulate Vico 固件完成路线图

日期：2026-07-09

## 目标

从当前可编译 ESP-IDF baseline 推进到最初设计需求：安全 CAN 监听、可信声浪模拟、BLE/SD/WiFi/IoT/OTA 配置闭环、硬件实机验收和可交付固件包。

当前主线是 S7 “旧工程逻辑对齐”：参考 `wifi_esp32_ct`、`smart-controller-esp32s3`、`smart-controller-gd32f4` 的分层状态机，把网络、MQTT、OTA 从 `App` 主循环中拆出。

## 固定决策

- BLE UUID 不变：主服务 `0xfff0`，兼容服务 `0xffe0`。
- `ffe8` 继续承载 WiFi / OTA / IoT JSON 配置。
- CAN 继续 listen-only，不新增 transmit。
- `App::tick()` 保持 25 ms，不执行 WiFi/MQTT/OTA 阻塞工作。
- OTA 使用 HTTPS，证书由固件或构建资源提供，不从 BLE 明文注入。
- USB CDC、高级调参和 MATLAB 声浪建模不纳入 S7，后移到 S8/S9。

## 当前基线

| 范围 | 当前状态 | 证据 |
|---|---|---|
| CAN listen-only | 已实现 | `components/can/` |
| CAN frame parser | 已实现 `0x256` / `0x116` baseline | `components/can/include/can/CanFrames.h` |
| I2S audio | 已实现 RPM baseline | `components/audio/` |
| BLE GATT | 已实现，待实机验收 | `components/ble/` |
| SD JSON | 已实现，待实机验收 | `components/storage/` |
| 外设 | 已接入，待实机验收 | `components/input/`, `components/ui/` |
| S7 分层 | 已迁移到代码 baseline | `components/status`, `components/network`, `components/iot`, `components/ota` |
| IRAM | 风险未关闭 | 历史记录 `16383 / 16384` |
| 声浪算法 | 未产品化 | 缺少加速度/负载分层与 MATLAB 定参 |

## 阶段计划

| 阶段 | 目标 | 完成标准 | 状态 |
|---|---|---|---|
| S7.0 文档与架构对齐 | 写清旧工程到 Tesla_speed 的模块映射 | README/PLAN/docs/OpenSpec 口径一致 | 进行中 |
| S7.1 状态与配置模型 | 引入统一状态和 WiFi/OTA/IoT 配置 | `RuntimeStatus`、`RuntimeConfig`、SD load/save 通过构建 | 进行中 |
| S7.2 Link/WiFi | 独立 WiFi STA 与重连状态机 | WiFi 状态可复制到 BLE 诊断，主循环不阻塞 | 进行中 |
| S7.3 IoT/MQTT | MQTT 上下行与 OTA 命令 | `ota_start` 可转为 OTA request，状态可上报 | 进行中 |
| S7.4 OTA | 后台 OTA worker | boot/config/cloud request 均走后台任务 | 进行中 |
| S7.5 App 集成验证 | App 只协调状态和车辆模拟 | build/size/OpenSpec 通过，硬件项单独标记 | 进行中 |
| S8 声浪算法 | 速度/加速度/负载差异化模型 | MATLAB/仿真参数 + bench listening + 固件集成 | 待开始 |
| S9 USB CDC/调参 | 主机侧诊断和参数调试 | host 可读写状态和配置并保存 | 待开始 |
| S10 交付 | release 包和验收报告 | bin/分区/bootloader/测试记录/风险清单齐全 | 待开始 |

## S7 执行顺序

1. 关闭文档和 OpenSpec 漂移。
2. 完成 BLE `ffe8` 配置写入到 SD 持久化的闭环。
3. 验证 network/iot/ota 只在后台任务运行。
4. 重跑 `build`、`size`、`size-components`、`openspec validate --all --strict --json`。
5. 上板执行 BLE/WiFi/MQTT/OTA 验收。
6. 把实机结果写入 `06-testing`，把剩余项写入 `09-backlog`。

## Release Gate

S7 只能在以下条件满足后归档：

- ESP-IDF build 和 OpenSpec 均通过。
- BLE 广播和 `ffe2`/`ffe8` 读写在实机验证通过。
- WiFi 能使用 BLE 写入的配置联网。
- MQTT 能完成最小上线、上报和 `ota_start` 下行。
- HTTPS OTA 成功路径和失败保护路径都有记录。
- IRAM 风险被解决，或有明确的实机压力测试接受记录。
