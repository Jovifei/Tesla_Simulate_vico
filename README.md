# Tesla Simulate Vico

Language: [中文说明](#中文说明) | [English Overview](#english-overview)

## 中文说明

`Tesla Simulate Vico` 是一个面向 Tesla/电动车的**实时发动机声浪模拟产品工程**。仓库同时包含：

1. 已经存在的 ESP32-S3 车端产品壳（CAN、BLE、SD、WiFi/MQTT/OTA、I2S、UI/输入）；
2. S12 声学研发与验证体系（persistent event-domain source、车型 identity、reference/comparator、human gate）；
3. 后续把 approved sound profile 变成 portable C++、Android/desktop realtime proof，再移植回 ESP32-S3 的产品化路线。

最终产品硬规则：**车辆 CAN 只监听，不提供产品 transmit 路径。**

### 当前整体状态（2026-09-04）

| 范围 | 状态 | 说明 |
|---|---|---|
| ESP32-S3 产品壳 | Implemented | CAN/I2S/BLE/SD/input/UI/network/iot/ota 代码基线存在 |
| ESP32 板级验收 | Blocked | BLE/WiFi/MQTT/OTA/SD/I2S/CAN no-TX 等待实机证据 |
| S12 声音架构 | Verified in software | Stage V→AC persistent source / comparator / frozen Track-P / CI 已建立 |
| Hellcat AA-C3 | Engineering candidate | 自动指标改善，尚未 Human accepted |
| PR #5 hardening | Merged | PR head `021fe294...` 已通过 run `33703659821`; current `main=82c7cb77...` |
| V3 blind audition | Package verified | 等待 Jovi 试听 |
| R1 | Missing | 无同步合法 R1，不得称 OEM calibration |
| Portable C++ runtime | Not started | Human Engineering Profile 后启动 |
| Android/desktop realtime | Not started | 用作跨语言 realtime/equivalence proof |
| ESP32 advanced sound port | Not started | C++/resource characterization 后启动 |
| Vehicle pilot | Not started | 需要硬件/CAN/安全/热/EMC/延迟证据 |

### 统一产品架构

```text
Tesla CAN/OBD (listen-only)
        ↓
VehicleState
        ↓
S12 authoritative sound model
        ↓
Reference + Human qualification
        ↓
AudioParameterPackage + Golden Evidence
        ↓
Portable C++ realtime core
        ↓
Android/desktop realtime proof
        ↓
ESP32-S3 resource-reduced adapter
        ↓
I2S → DAC/AMP/Speaker
        ↓
Controlled vehicle pilot
```

现有 ESP32 firmware 并不会被 Android 取代。Android/desktop 是高级声音模型冻结后的**中间实时验证宿主**，最终仍要把受控的实时子集接入现有 ESP32-S3 产品壳。

### 当前最近关卡

截至 2026-09-04 远端复核：

```text
main = 82c7cb77d26f446251e63d1a6899b08bf08be65b
PR #5 = MERGED at 2026-09-04T13:51:52Z
PR #5 head = 021fe29480aadabd4d9ba4c20bbc111d1c386795
CI 33703659821 = SUCCESS on exact PR head
full S12 = 1423 passed / 10 skipped / 232 subtests passed
Track-P frozen guard = PASS
```

因此当前不是继续排查 CI，而是：

```text
Stage-AC post-merge truth reconciliation
→ AC8 pre-human smoke/receipt
→ WAITING_FOR_JOVI_AUDITION
→ feedback SHA/binding
→ accept AA-C3 OR one source-causal Round 2
```

V3 package：

`E:\Tesla_speed\review_packages\s12-stage-aa-hellcat-quality-v3`

manifest SHA-256：

`b1ea99d36179229ff7d31f30f4790b6b84d8af587c14d44398e8e595f5f0964f`

当前明确禁止：反馈前调音/揭盲、whole-mix/master gain Round2、提前扩 Ferrari/RX-7、把 CI green 写成 Human PASS、在 R1 missing 时声称 OEM calibration/Profile Freeze。

### 工程结构

| 路径 | 作用 |
|---|---|
| `components/app/` | ESP32 应用协调层 |
| `components/status/` | 统一运行状态 |
| `components/network/` | WiFi 状态机 |
| `components/iot/` | MQTT 上下行 |
| `components/ota/` | HTTPS OTA worker |
| `components/ble/` | NimBLE GATT |
| `components/config/` | pin/runtime config |
| `components/storage/` | SD JSON |
| `components/can/` | CAN parser + TWAI listen-only |
| `components/audio/` | I2S + 当前基础合成；未来接 advanced sound adapter |
| `components/domain/` | VehicleState / virtual RPM baseline |
| `components/input/` | encoder / throttle pot |
| `components/ui/` | WS2812 |
| `tools/sound_sim/s12/` | S12 声学模型、validation、comparator、reports tooling |
| `tasks/reports/runtime/` | S12 机器证据/receipts/runtime reports |
| `docs/` | 公开架构、计划、报告、backlog |

### 文档入口

- [文档总入口](docs/README.md)
- [统一系统架构](docs/01-architecture/01-project-system-architecture.md)
- [项目总路线图](docs/04-planning/02-project-master-roadmap.md)
- [2026-09-04 项目整体状态](docs/08-reports/10-project-status-20260904.md)
- [项目总 Backlog](docs/09-backlog/02-project-master-backlog.md)
- [ESP32 固件子路线](docs/04-planning/01-firmware-roadmap.md)

### Evidence boundary

当前允许说：

- software verified；
- engineering candidate；
- R2/R3 diagnostic；
- waiting for human audition。

当前不允许说：

- OEM match/reproduction；
- calibrated；
- human passed；
- profile freeze；
- vehicle pilot ready。

## English Overview

`Tesla Simulate Vico` is a vehicle-state-driven engine-sound product project with two existing tracks: an ESP32-S3 embedded product shell and the S12 acoustic-authoring/validation system.

The final embedded target remains ESP32-S3 with listen-only CAN, I2S audio, BLE/SD/WiFi/IoT/OTA and safe mute/fallback behavior. The S12 sound model is currently a PC/Python engineering authority. After human acceptance, the plan is to freeze a versioned `AudioParameterPackage`, implement a portable C++ realtime core, prove Python/C++ behavior and realtime constraints on desktop/Android, and then integrate a resource-bounded runtime into the existing ESP32 firmware shell.

### Current Status

- ESP32 product shell: implemented in code, board acceptance pending.
- S12 acoustic stack: software-verified through the pre-human Hellcat closure stages.
- Hellcat AA-C3: engineering candidate, not human accepted.
- PR #5: merged on 2026-09-04; exact-head CI run `33703659821` succeeded before merge; current `main=82c7cb77...`.
- R1 synchronized real-reference data: missing.
- Portable C++ / Android realtime / advanced ESP32 sound runtime: not started.
- Vehicle pilot: not started.

### Immediate Path

```text
Stage-AC post-merge closure
→ Jovi V3 blind audition
→ feedback binding
→ accept AA-C3 or one bounded source-causal Round 2
→ Engineering Profile
→ AudioParameterPackage / Golden Evidence
→ portable C++ / Android-desktop realtime proof
→ ESP32 integration
→ board and vehicle validation
```

### License

MIT, (c) 2026 JoviF
