# Tesla Simulate Vico 固件完成路线图

日期：2026-07-08

## 目标

从当前可编译 ESP-IDF baseline 推进到最初设计需求：安全 CAN 监听、可信声浪模拟、BLE/SD/WiFi/IoT/OTA 配置闭环、硬件实机验收和可交付固件包。

当前主线是 S7“旧工程逻辑对齐”：参考 `wifi_esp32_ct`、`smart-controller-esp32s3`、`smart-controller-gd32f4` 的分层状态机，把网络、MQTT、OTA 从 App 主循环中拆出去。

## 固定决策

- BLE UUID 不变：主服务 `0xfff0`，兼容服务 `0xffe0`。
- `ffe8` 继续承载 WiFi / OTA / IoT JSON 配置。
- CAN 继续 listen-only，不新增 transmit。
- `App::tick()` 保持 25 ms，不执行 WiFi/MQTT/OTA 阻塞工作。
- OTA 使用 HTTPS，证书由固件/构建资源提供，不从 BLE 明文注入。
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
| S7 分层 | 代码迁移中 | `components/status`, `network`, `iot`, `ota` |
| IRAM | 风险未关闭 | 历史记录 `16383 / 16384` |
| 声浪算法 | 未产品化 | 当前缺少加速度/负载分层与 MATLAB 定参 |

## 阶段计划

| 阶段 | 目标 | 完成标准 | 状态 |
|---|---|---|---|
| S7.0 文档与架构对齐 | 写清旧工程到 Tesla_speed 的模块映射 | README/PLAN/docs/OpenSpec 口径一致 | 进行中 |
| S7.1 状态与配置模型 | 引入统一状态和 WiFi/OTA/IoT 配置 | `RuntimeStatus`、`RuntimeConfig`、SD load/save 通过构建 | 进行中 |
| S7.2 Link/WiFi | 独立 WiFi STA 与重连状态机 | WiFi 状态可复制到 BLE 诊断，主循环不阻塞 | 进行中 |
| S7.3 IoT/MQTT | MQTT 上下行与 OTA 命令 | `ota_start` 可转成 OTA request，状态可上报 | 进行中 |
| S7.4 OTA | 后台 OTA worker | boot/config/cloud request 均走后台任务 | 进行中 |
| S7.5 App 集成验证 | App 只协调状态和车辆模拟 | build/size/OpenSpec 通过，硬件项单独标记 | 进行中 |
| S8 声浪算法 | 速度/加速度/负载差异化模型 | MATLAB/仿真参数 + bench listening + 固件集成 | 待开始 |
| S9 USB CDC/调参 | 主机侧诊断和参数调试 | host 可读写状态/配置并保存 | 待开始 |
| S10 交付 | release 包和验收报告 | bin/分区/bootloader/测试记录/风险清单齐全 | 待开始 |

## S7 执行顺序

1. 代码核查与修复：状态合并、BLE 配置流、OTA request、MQTT downlink。
2. 文档核查与修复：README、PLAN、OpenSpec、docs 计划与待办。
3. 静态门禁：`build`、`size`、`size-components`、`openspec validate --all --strict --json`。
4. 硬件验收：BLE、WiFi、MQTT、OTA、SD、I2S、CAN。
5. 风险收口：IRAM margin 和 BLE controller flash placement 压力测试。

## Release Gate

S10 之前不能宣称“达到最初设计需求”，除非以下证据齐全：

- build/size/size-components/OpenSpec 全部通过。
- 实机 boot/flash/monitor 通过。
- BLE 广播、连接、读写回读通过。
- WiFi join、MQTT 上下行、HTTPS OTA 成功/失败路径通过。
- CAN listen-only 在真实或可信模拟输入下通过。
- I2S 声音输出通过听感或示波器验证。
- 声浪算法包含速度/加速度/负载差异化，并有 MATLAB 或等价模型记录。
- IRAM 风险已解决或被明确接受。
- README、PLAN、OpenSpec、docs、测试记录与代码一致。
