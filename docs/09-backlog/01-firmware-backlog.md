# Tesla Simulate Vico ESP32 固件待完成清单

更新：2026-09-04

> 本文件只追踪 ESP32 固件/硬件子系统。全项目剩余工作见 `02-project-master-backlog.md`。

## P0 Board Bring-up

| ID | 待完成项 | 状态 | 验收证据 |
|---|---|---|---|
| P0-01 | 实机烧录与 boot log | Blocked hardware | `flash monitor` 无 panic/reset loop |
| P0-02 | BLE 广播服务可见 | Blocked hardware | 扫描 `0xfff0` / `0xffe0` |
| P0-03 | BLE `ffe2` / `ffe5` / `ffea` 读取 | Blocked hardware | repeated stable reads/notify |
| P0-04 | BLE `ffe8` 配置写入/读回 | Implemented / board blocked | JSON→SD→reboot 一致 |
| P0-05 | SD JSON 实机读写 | Blocked hardware | 有卡/无卡/坏配置 |
| P0-06 | I2S 硬件输出 | Blocked hardware | 波形/录音/听感 |
| P0-07 | encoder 音量调节 | Blocked hardware | volume + persistence |
| P0-08 | throttle pot ADC | Blocked hardware | stable ADC / state impact |
| P0-09 | WS2812 状态 | Blocked hardware | boot/running/muted/fault |
| P0-10 | CAN listen-only 安全证明 | Blocked hardware | analyser zero TX |

## Network / IoT / OTA

| ID | 待完成项 | 状态 | 验收证据 |
|---|---|---|---|
| N-01 | WiFi STA join/reconnect | Implemented / board blocked | network state transitions |
| N-02 | MQTT uplink | Implemented / board blocked | device/vehicle state publish |
| N-03 | MQTT `ota_start` | Implemented / board blocked | accepted/rejected + request |
| N-04 | HTTPS OTA success | Blocked hardware | partition switch/version |
| N-05 | HTTPS OTA failure protection | Blocked hardware | bad URL/image safe recovery |
| N-06 | BLE write does not block app | Implemented / board verify | callback timing / runtime log |
| N-07 | 25 ms App loop under concurrency | Blocked hardware | jitter/health log |

## Memory / Realtime Hardening

| ID | 待完成项 | 状态 | 验收证据 |
|---|---|---|---|
| MEM-01 | fresh `idf.py size` | Pending | current IRAM/DIRAM/Flash |
| MEM-02 | fresh `size-components` | Pending | top consumers |
| MEM-03 | IRAM risk decision | Open | optimization or accepted stress evidence |
| MEM-04 | BLE/WiFi/OTA/I2S/WS2812 stress | Blocked hardware | long-run + OTA concurrency |
| MEM-05 | audio underrun/latency metrics | Pending advanced runtime | counters + measured latency |
| MEM-06 | heap/PSRAM/IRAM runtime metrics | Pending advanced runtime | worst-case report |

## Advanced S12 Sound Integration

旧 backlog 中的 “声浪算法待开始” 已失效。正确状态是：

- S12 Python/PC authoring：`Verified in software through pre-human gate`；
- Human Hellcat：`Blocked by human audition`；
- ESP32 advanced sound runtime：`Not started`。

| ID | 待完成项 | 状态 | 验收证据 |
|---|---|---|---|
| AUD-01 | Human-approved Engineering Profile | Blocked | Jovi + candidate manifest |
| AUD-02 | AudioParameterPackage | Not started | schema/version/SHA |
| AUD-03 | Golden VehicleState/PCM | Not started | deterministic receipts |
| AUD-04 | Portable C++ runtime | Not started | tests/streaming/snapshot |
| AUD-05 | Python↔C++ equivalence | Not started | bounded diffs |
| AUD-06 | Android/desktop realtime proof | Not started | CPU/memory/latency |
| AUD-07 | ESP32 adapter | Not started | compile/I2S output |
| AUD-08 | Embedded quality/resource tuning | Not started | quality tier + resource report |
| AUD-09 | Bench listening against golden | Not started | recording/metric/human check |

## Vehicle / Safety

| ID | 待完成项 | 状态 | 验收证据 |
|---|---|---|---|
| CAR-01 | Tesla CAN signal capture/confirm | Pending | capture + signal mapping |
| CAR-02 | VehicleState freshness/fallback | Pending | disconnect/reconnect |
| CAR-03 | overspeed/fault/missing-state mute | Pending | bench/vehicle tests |
| CAR-04 | DAC/AMP/speaker final chain | Pending | hardware selection + waveform |
| CAR-05 | power/thermal/EMC | Pending | stress/vehicle report |
| CAR-06 | controlled vehicle pilot | Pending | scenario checklist |

## Recommended Order

1. 声学工作流：Stage-AC post-merge truth → Human Hellcat → Engineering Profile。
2. 固件工作流可并行做 board bring-up / network / OTA / IRAM，不需要等 Human。
3. Human PASS 后启动 AudioParameterPackage / C++ runtime。
4. 先用 desktop/Android 证明 realtime/equivalence，再做 ESP32 resource reduction。
5. 高级声浪接入 ESP32 后重新做完整 board stress。
6. 最后进入 Tesla vehicle pilot。
