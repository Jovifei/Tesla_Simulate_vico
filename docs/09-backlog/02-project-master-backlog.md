# 项目总待办 / Master Backlog

> 当前只追踪声音真实性 + Android App 产品化。ESP32 = Deferred Future。
>
> 证据：handoff package ≈90%，旧聊天/总结 ≈10%，动态 GitHub 现场复核。

## P0

1. AC8 post-merge smoke / Track-P / receipt；
2. Jovi Hellcat V3 blind audition；
3. feedback SHA + blind binding；
4. AA-C3 human decision。

## P1 Hellcat

- ONE source-causal Round2 if needed；
- ≤3 candidates；
- professional finalist；
- v4 if needed；
- Hellcat Engineering Profile。

## P2 Vehicles

- Ferrari 458；
- RX-7 FD；
- multi-vehicle profile schema；
- App selector model。

## P3 App state

- speed input；
- acceleration/filter；
- virtual RPM；
- virtual load/throttle；
- virtual gear/shift；
- lift/overrun；
- pause/resume state；
- offline trace replay。

## P4 Runtime contract

- AudioParameterPackage；
- Golden speed/accel / VirtualEngineState traces；
- Golden PCM/metrics；
- portable C++；
- Python↔C++ equivalence。

## P5 Android

- NDK C++；
- AAudio/Oboe；
- realtime-safe callback；
- state buffer；
- vehicle selector；
- persistence；
- latency/underrun；
- CPU/memory/battery/thermal；
- lifecycle；
- in-car validation。

## P6 Future richer inputs

CAN/OBD/real RPM/load/gear override = future enhancement；核心算法必须先在 speed + acceleration 下运行。

## P7 R1

合法原始录音、同步真实状态、recording metadata、formal calibration、higher-level freeze。

## Deferred ESP32

advanced port、board、BLE/WiFi/OTA、IRAM、CAN analyser、hardware audio chain 全部不在 active backlog。
