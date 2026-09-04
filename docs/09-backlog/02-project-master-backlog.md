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

| ID | 工作 | 状态 |
|---|---|---|
| H-01 | Source-causal Round2（若需要） | Blocked |
| H-02 | Professional finalist | Blocked |
| H-03 | V4 blind audition（若需要） | Blocked |
| H-04 | Hellcat Engineering Profile | Blocked |

Round2：one round / ≤3 candidates / no broad gain。

## P2 车型迁移

- Ferrari 458 profile migration；
- RX-7 FD profile migration；
- multi-vehicle profile schema；
- App vehicle selector data model。

## P3 App VehicleState / VirtualEngineState

- speed input contract；
- acceleration input/filter；
- virtual RPM；
- virtual load/throttle proxy；
- virtual gear/shift；
- lift/overrun/braking；
- pause/resume state restore；
- offline trace replay。

## P4 Runtime Contract

- AudioParameterPackage schema；
- Golden speed/acceleration traces；
- Golden VirtualEngineState；
- Golden PCM/metrics；
- Portable C++ core；
- Python↔C++ equivalence。

## P5 Android App Runtime

- Native C++ integration；
- AAudio/Oboe 48 kHz；
- realtime-safe callback；
- state ring/double buffer；
- vehicle profile selector UI；
- package/profile persistence；
- latency / underrun；
- CPU/memory/battery/thermal；
- pause/resume/audio focus；
- in-car driving validation。

## P6 Optional richer vehicle inputs

GPS/phone sensor refinement、OBD/CAN richer adapter、real RPM/load/gear override 都是 future enhancement，不是当前 blocker。

核心算法必须在 speed + acceleration 最小输入下可运行。

## P7 R1

合法原始录音、同步真实状态、recording metadata、formal Order-RPM/calibration、higher-level freeze 均是独立后续链。

## Deferred — ESP32

ESP32 advanced sound port、board bring-up、BLE/WiFi/MQTT/OTA、IRAM/PSRAM、CAN analyser、I2S DAC/AMP/speaker、ESP32 vehicle pilot 全部移出当前 active backlog。

统一状态：`DEFERRED_FUTURE_OPTION`。

## 禁止替代完成度

- tests green ≠ human sound pass；
- human pass ≠ R1/OEM calibration；
- desktop PCM ≠ Android realtime；
- Android realtime ≠ 车内动态体验通过；
- 仓库存在 ESP32 代码 ≠ 当前需要做 ESP32。