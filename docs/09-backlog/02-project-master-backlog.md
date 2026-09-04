# 项目总待办 / Master Backlog

日期：2026-09-04

> `01-firmware-backlog.md` 继续跟踪 ESP32 固件与硬件子系统；本文跟踪整个项目从 S12 声音到产品化的关键剩余工作。

## P0 当前立即项

| ID | 工作 | 状态 | 完成证据 |
|---|---|---|---|
| P0-01 | PR #5 exact-head qualification | PASS | run `33703659821` success on `021fe294...` |
| P0-02 | PR #5 merge | PASS | merged 2026-09-04; head is ancestor of current main |
| P0-03 | Stage AC post-merge truth | Pending | record AC6 PASS / AC7 PASS; run AC8 smoke + receipt on current main |
| P0-04 | Jovi V3 blind audition | Blocked by human | feedback 文件 + SHA |
| P0-05 | Human feedback binding | Blocked by P0-04 | blind reveal after hash + binding receipt |

## P1 Hellcat closure

| ID | 工作 | 状态 | 完成证据 |
|---|---|---|---|
| H-01 | AA-C3 human decision | Waiting | accept/reject scene-level feedback |
| H-02 | Source-causal Round2（若需要） | Blocked | ≤3 candidates / one round / no broad gain |
| H-03 | Professional finalist | Blocked | objective + MATLAB/MoSQITo/available professional receipt |
| H-04 | V4 blind audition（若需要） | Blocked | immutable package + human decision |
| H-05 | Hellcat Engineering Profile | Blocked | human accepted + package manifest |

## P2 车型迁移

| ID | 工作 | 状态 | 完成证据 |
|---|---|---|---|
| V-01 | Ferrari 458 diagnostic migration | Frozen | source-specific identity + regression |
| V-02 | RX-7 FD diagnostic migration | Frozen | rotary-specific identity + regression |
| V-03 | 其余车型 | Frozen | profile architecture + per-vehicle evidence |

## P3 Runtime contract

| ID | 工作 | 状态 | 完成证据 |
|---|---|---|---|
| RT-01 | AudioParameterPackage schema | Not started | versioned schema + examples + SHA |
| RT-02 | Golden VehicleState traces | Not started | deterministic traces |
| RT-03 | Golden PCM/metrics | Not started | reopened PCM + metrics + manifests |
| RT-04 | Portable C++17 core | Not started | unit tests + deterministic streaming |
| RT-05 | Python↔C++ equivalence | Not started | bounded block/long-stream/snapshot diffs |
| RT-06 | Android/desktop realtime host | Not started | CPU/memory/latency/underrun report |

## P4 ESP32 高级声音集成

| ID | 工作 | 状态 | 完成证据 |
|---|---|---|---|
| E-01 | Embedded profile reduction | Not started | quality/resource tier decision |
| E-02 | C++ core ESP32 adapter | Not started | compile + I2S playback |
| E-03 | Realtime CPU/heap/PSRAM/IRAM | Not started | runtime measurements |
| E-04 | DMA/underrun/latency | Not started | long-duration bench log |
| E-05 | Startup/mute/pop | Not started | waveform/audio proof |

## P5 现有 ESP32 产品壳硬件验收

沿用 `01-firmware-backlog.md`，尤其：

- flash/boot；
- BLE；
- SD；
- I2S；
- input/UI；
- WiFi/MQTT/OTA；
- IRAM stress；
- CAN listen-only analyser proof。

## P6 Vehicle integration

| ID | 工作 | 状态 | 完成证据 |
|---|---|---|---|
| CAN-01 | Tesla signal现场确认 | Pending | CAN capture + DBC/signal receipt |
| CAN-02 | VehicleState freshness/fallback | Pending | disconnect/reconnect tests |
| CAN-03 | No transmit hardware proof | Pending | analyser shows zero TX |
| CAR-01 | Controlled vehicle pilot | Pending | scene checklist + logs |
| CAR-02 | Power/thermal/EMC | Pending | bench/vehicle records |

## P7 R1 正式标定

| ID | 工作 | 状态 | 完成证据 |
|---|---|---|---|
| R1-01 | 合法原始录音 | Blocked external | rights + SHA |
| R1-02 | 同步 RPM/load/throttle/gear/shift | Blocked external | aligned state trace |
| R1-03 | recording chain metadata | Blocked external | mic/AGC/processing record |
| R1-04 | formal Order-RPM / calibration | Blocked by R1 | professional receipt |
| R1-05 | high-level Profile Freeze | Not authorized | R1 + human + regression |

## 禁止作为“完成”的替代物

- tests green ≠ human sound pass；
- human pass ≠ R1/OEM calibration；
- desktop PCM ≠ realtime runtime；
- realtime Android ≠ ESP32 resource fit；
- ESP32 bench ≠ CAN/vehicle safety；
- downloadable public audio ≠ licensed R1。
