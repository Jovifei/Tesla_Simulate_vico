# 项目总待办 / Master Backlog

日期：2026-09-04

> 当前 backlog 只追踪**声音真实性 + App 产品化**。ESP32 单独标记 Deferred，不作为当前 P0/P1/P2 工作。
>
> 项目历史知识以 `S12_Handoff_Package_2026-09-03` 为约 90% 主证据，旧聊天/此前总结约 10% 补充；当前 GitHub remote truth 与用户当前明确决策优先。

## P0 当前立即项

| ID | 工作 | 状态 | 完成证据 |
|---|---|---|---|
| P0-01 | Stage AC post-merge AC8 | Pending | post-merge smoke / Track-P guard / exact receipt |
| P0-02 | Jovi V3 blind audition | Blocked by human | raw feedback + SHA |
| P0-03 | Human feedback binding | Blocked by P0-02 | reveal only after SHA + binding receipt |
| P0-04 | AA-C3 human decision | Waiting | scene-level accept/reject |

## P1 Hellcat closure

| ID | 工作 | 状态 | 完成证据 |
|---|---|---|---|
| H-01 | Source-causal Round2（若需要） | Blocked | one round / ≤3 candidates / no broad gain |
| H-02 | Professional finalist | Blocked | objective/professional receipt |
| H-03 | V4 blind audition（若需要） | Blocked | immutable package + decision |
| H-04 | Hellcat Engineering Profile | Blocked | human accepted + manifest |

## P2 车型迁移

| ID | 工作 | 状态 | 完成证据 |
|---|---|---|---|
| V-01 | Ferrari 458 profile migration | Frozen | source-specific identity + human/regression |
| V-02 | RX-7 FD profile migration | Frozen | rotary-specific identity + human/regression |
| V-03 | Multi-vehicle profile schema | Not started | versioned vehicle profile contract |
| V-04 | App vehicle selector data model | Not started | profile list / selection / persistence |

## P3 App VehicleState / VirtualEngineState

| ID | 工作 | 状态 | 完成证据 |
|---|---|---|---|
| APPSTATE-01 | speed input contract | Not started | units/freshness/filter/test traces |
| APPSTATE-02 | acceleration input/filter | Not started | stable acceleration trace |
| APPSTATE-03 | virtual RPM model | Not started | continuous v/a→RPM mapping |
| APPSTATE-04 | virtual load/throttle proxy | Not started | acceleration/load response tests |
| APPSTATE-05 | virtual gear/shift state | Not started | no chatter + natural shift events |
| APPSTATE-06 | lift/overrun/braking state | Not started | decel/transient tests |
| APPSTATE-07 | pause/resume state restore | Not started | state continuity receipt |
| APPSTATE-08 | offline trace replay | Not started | deterministic state replay |

## P4 Runtime Contract

| ID | 工作 | 状态 | 完成证据 |
|---|---|---|---|
| RT-01 | AudioParameterPackage schema | Not started | versioned schema + SHA |
| RT-02 | Golden speed/acceleration traces | Not started | deterministic traces |
| RT-03 | Golden VirtualEngineState traces | Not started | mapped state receipts |
| RT-04 | Golden PCM/metrics | Not started | manifests + reopened PCM |
| RT-05 | Portable C++ core | Not started | unit/stream/snapshot tests |
| RT-06 | Python↔C++ equivalence | Not started | bounded diffs |

## P5 Android App Runtime

| ID | 工作 | 状态 | 完成证据 |
|---|---|---|---|
| APP-01 | Native C++ integration | Not started | Android build + tests |
| APP-02 | AAudio/Oboe 48 kHz output | Not started | realtime playback |
| APP-03 | realtime-safe callback | Not started | no heap alloc / callback timing |
| APP-04 | state ring/double buffer | Not started | race-free stress tests |
| APP-05 | vehicle profile selector UI | Not started | Hellcat/Ferrari/RX-7 selection |
| APP-06 | package/profile persistence | Not started | restart retains selection/config |
| APP-07 | latency measurement | Not started | input→audio latency report |
| APP-08 | underrun metrics | Not started | long-run zero/acceptable underrun |
| APP-09 | CPU/memory/battery/thermal | Not started | in-car long-run report |
| APP-10 | pause/resume/audio focus | Not started | state/audio recovery |
| APP-11 | in-car driving validation | Not started | scenario checklist + Jovi listening |

## P6 Optional richer vehicle inputs

这些不是当前 blocker：

| ID | 工作 | 状态 |
|---|---|---|
| INPUT-01 | GPS/phone sensor refinement | Future enhancement |
| INPUT-02 | OBD/CAN richer state adapter | Future enhancement |
| INPUT-03 | real RPM/load/gear override | Future enhancement |

核心算法必须在 speed + acceleration 最小输入下可运行。

## P7 R1 正式标定

| ID | 工作 | 状态 |
|---|---|---|
| R1-01 | 合法原始录音 | Blocked external |
| R1-02 | 同步真实状态 | Blocked external |
| R1-03 | recording metadata | Blocked external |
| R1-04 | formal Order-RPM/calibration | Blocked by R1 |
| R1-05 | higher-level Profile Freeze | Not authorized |

## Deferred — ESP32

以下全部从当前 active backlog 移除：

- ESP32 advanced sound port；
- ESP32 board bring-up；
- BLE/WiFi/MQTT/OTA 板级验收；
- IRAM/PSRAM 优化；
- CAN analyser no-TX；
- I2S DAC/AMP/speaker 产品链；
- ESP32 vehicle pilot。

统一状态：`DEFERRED_FUTURE_OPTION`。

只有 App 版本稳定后，用户明确重新开启嵌入式路线时，才恢复这些任务。

## 禁止用来替代完成度

- tests green ≠ human sound pass；
- human pass ≠ R1/OEM calibration；
- desktop PCM ≠ Android realtime；
- Android realtime ≠ 车内动态体验通过；
- 仓库存在 ESP32 代码 ≠ 当前需要做 ESP32。