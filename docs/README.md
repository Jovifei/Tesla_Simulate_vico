# Tesla Simulate Vico Documentation

当前文档主入口服务于 **S12 声音真实性 + 车内 Android App 实时声浪**。

仓库中的 ESP32-S3 固件、CAN/BLE/SD/WiFi/OTA/I2S 等内容属于早期工程资产，目前统一标记为 `Deferred/Future`，不作为当前 blocker 或实施主线。

## Read These First

1. [当前 App-first 产品方向](04-planning/03-current-app-product-direction.md)
2. [当前系统架构](01-architecture/01-project-system-architecture.md)
3. [项目总路线图](04-planning/02-project-master-roadmap.md)
4. [当前项目状态审计 — 2026-09-04](08-reports/10-project-status-20260904.md)
5. [项目总 Backlog](09-backlog/02-project-master-backlog.md)
6. [Stage AA Hellcat 声学收口](08-reports/09-s12-stage-aa-acoustic-quality-closure.md)
7. [Documentation guide](GUIDE.md)

## Current Product Truth

当前产品形态：

```text
车内 Android App
→ speed + acceleration
→ VirtualEngineState
→ vehicle profile selection
→ S12 realtime sound engine
→ App playback
```

当前最小输入合同：`speed + acceleration`。

App 内部负责派生 virtual RPM/load/gear/shift/lift/overrun 等状态。CAN/OBD 可以以后作为 richer input adapter，但不是当前算法/App 的前置条件。

## Current Nearest Gate

```text
Stage-AC AC8 post-merge receipt
→ WAITING_FOR_JOVI_AUDITION
→ Hellcat V3 feedback
→ AA-C3 accept OR ONE source-causal Round2
→ Hellcat Engineering Profile
→ Ferrari / RX-7
→ App runtime productization
```

当前证据边界：

```text
R1 = MISSING
HUMAN_PASS = false
OEM_CALIBRATION = NOT_AUTHORIZED
PROFILE_FREEZE = NOT_AUTHORIZED
ESP32 = DEFERRED_FUTURE_OPTION
```

## App Productization Direction

```text
S12 Python authority
→ AudioParameterPackage
→ Golden speed/acceleration + VirtualEngineState traces
→ Golden PCM
→ portable C++ core
→ Python↔C++ equivalence
→ Android AAudio/Oboe realtime engine
→ speed/acceleration input adapter
→ vehicle profile selector
→ in-car validation
```

Android 是当前目标 runtime，不是临时验证宿主。

## ESP32 Documents

以下文档继续保留，但当前只用于历史/未来参考：

- `04-planning/01-firmware-roadmap.md`
- `09-backlog/01-firmware-backlog.md`

它们不得覆盖 `03-current-app-product-direction.md` 和项目总路线图。

## S12 Key Reports

- [Stage Z open-source absorption](08-reports/08-s12-stage-z-open-source-absorption.md)
- [Stage AA Hellcat acoustic quality closure](08-reports/09-s12-stage-aa-acoustic-quality-closure.md)
- [2026-09-04 integrated status audit](08-reports/10-project-status-20260904.md)
- [S12 engine-audio knowledge mirror](knowledge/obsidian/S12/Engine-Audio-Ecosystem/00-MOC.md)

## Documentation Status Rules

- `Implemented`: code exists.
- `Verified`: fresh software/CI evidence exists.
- `Human accepted`: Jovi listening gate passed.
- `R1 qualified`: legal synchronized real-reference gate passed.
- `Blocked`: external input/human/tool is required.
- `Deferred`: intentionally not part of current implementation.

不要把历史 ESP32 代码存在写成当前产品路线要求。