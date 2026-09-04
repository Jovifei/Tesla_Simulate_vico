# Tesla Simulate Vico / S12 统一系统架构

日期：2026-09-04

> 本文是当前项目的高层架构真值。它把“已经存在的 ESP32-S3 固件产品壳”和“S12 声学研发主线”放到同一张架构图中，避免继续把两者当成互不相关的项目。

## 1. 产品北极星

最终目标是一套**车辆状态驱动、CAN 只监听、低延迟、车型可辨识、经人工验证的实时发动机声浪系统**。

最终车端产品形态仍以现有 ESP32-S3 固件为嵌入式目标；在高级 S12 声音模型冻结后，优先通过跨语言参数包与 C++/Android 实时运行验证完成模型降风险，再把满足资源约束的实时子集移植回 ESP32-S3。

```text
Tesla / Vehicle CAN-OBD
        │
        │ listen-only
        ▼
VehicleState abstraction
(speed / acceleration / throttle / load / gear / shift / lift / online)
        │
        ├──────────────────────────────┐
        │                              │
        ▼                              ▼
Existing ESP32 product shell       S12 sound-authoring authority
CAN/BLE/SD/WiFi/OTA/I2S            Persistent Event-Domain Engine
safety / mute / status             source layers / transients / comparator
        │                              │
        │                              ▼
        │                         Human / Reference gate
        │                              │
        └──────────────┬───────────────┘
                       ▼
               AudioParameterPackage
                       │
                       ▼
             Portable C++ realtime core
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
        Android/PC proof     ESP32-S3 adapter
        realtime/equivalence resource-reduced runtime
             │                   │
             └─────────┬─────────┘
                       ▼
                I2S → DAC/AMP/Speaker
                       ▼
                 controlled vehicle pilot
```

## 2. 三个架构层

### A. Product Shell — 已有 ESP32-S3 固件基线

当前仓库已经有真实代码的产品壳：

- `components/can/`：TWAI listen-only + Tesla frame baseline；
- `components/domain/`：车辆状态/虚拟 RPM 基线；
- `components/audio/`：I2S PCM + 当前基础合成；
- `components/ble/`：NimBLE GATT；
- `components/storage/`：SD JSON 持久化；
- `components/network/`：WiFi；
- `components/iot/`：MQTT；
- `components/ota/`：HTTPS OTA；
- `components/status/`：运行状态；
- `components/input/` / `components/ui/`：旋钮、油门电位器、WS2812；
- `components/app/`：25 ms 主循环协调。

这个层已经证明“产品骨架存在并能编译”，但 BLE/WiFi/MQTT/OTA/SD/I2S/CAN 无发送等多数行为仍需要板级验收。

### B. Sound Authority — S12 声学研发主线

S12 已经不是“待开始的 MATLAB 声浪任务”，而是经过多个 Stage 的独立工程体系。

当前主数据流：

```text
VehicleState
  ↓
PersistentEventDomainEngine
  ├─ continuous crank / rotor phase
  ├─ combustion events
  ├─ per-cylinder / per-path propagation
  ├─ bank / collector
  ├─ forced induction
  ├─ mechanical / cycle-sync layers
  ├─ tip-in / shift / lift / BOV / afterfire
  ↓
PressureAudioChain
  ├─ DC handling
  ├─ dP / pressure-to-audio transformation
  ├─ persistent filter / delay state
  ↓
Frozen Track-P PTR / Radiation boundary
  ↓
Raw analysis PCM
  +
Monitor / audition PCM
```

S12 的工程约束：

- Track-P / FVM / PTR / Radiation 数学边界冻结；
- Track-S 负责车型身份和声音创作；
- Raw analysis 与 Monitor audition 分离；
- no clipping/click；
- block / one-shot / snapshot-restore 连续性；
- afterfire 必须由状态门控和路径传播产生；
- 自动指标不能替代 human audition；
- 没有同步合法 R1 时不得宣称 OEM calibration / Profile Freeze。

### C. Productization Bridge — 尚未正式开始

S12 Human PASS 后才进入这一层：

1. 冻结 `Engineering Profile`（注意：不是 R1 OEM Profile Freeze）；
2. 定义 `AudioParameterPackage`；
3. 固化 deterministic VehicleState traces；
4. 生成 Golden PCM / metrics；
5. 实现最小 portable C++17 realtime core；
6. Python ↔ C++ block / snapshot / streaming equivalence；
7. Android/PC 实时证明（AAudio/Oboe 或桌面实时 host）；
8. 根据 CPU / memory / latency 结果抽取 ESP32-S3 可运行子集；
9. 接入现有 `components/audio/` 与 `components/domain/`；
10. 完成真实 CAN、安全 mute、I2S、功放、扬声器和实车验收。

Android 在这里是**实时等价验证与产品化中间宿主**，不是替代 ESP32 最终产品目标。

## 3. Track P / Track S 边界

### Track P — Physics / Numerical Authority

负责：

- FVM / Simulink / PTR / Radiation；
- 数值和传播边界；
- 已冻结的物理核心；
- 作为 Track-S 输出的受控后级。

默认不允许因“听起来不够像”而修改。

### Track S — Acoustic Identity / Authoring Authority

负责：

- persistent event-domain source；
- combustion / exhaust / mechanical / forced-induction；
- Ferrari / Hellcat / RX-7 等车型身份；
- transient lifecycle；
- reference comparator；
- bounded calibration；
- human audition package；
- Engineering Profile。

## 4. 三锚点车型策略

深度真实感优先锚点：

1. Hellcat：cross-plane V8、低频 body、机械增压器、换挡/收油/afterfire；
2. Ferrari 458：flat-plane V8、高转 order sweep、高频机械纹理；
3. RX-7 FD：rotary event timing、housing buzz、sequential turbo/BOV。

当前只允许先关闭 Hellcat human loop。Ferrari/RX-7 在 Hellcat Human PASS 前保持冻结，避免把尚未验证的方法扩散到更多车型。

## 5. 当前证据等级

### R3
公共/不同步参考，可用于方向诊断。

### R2
来源/权利较清楚但缺同步状态，可用于相对频谱/心理声学比较。

### R1
必须具备合法原始音频 + 同步 RPM/load/throttle/gear/shift 等状态，才能支撑正式真实标定和高等级 Profile Freeze。

当前仓库状态仍是：

```text
R1 = MISSING
OEM_CALIBRATION = NOT_AUTHORIZED
PROFILE_FREEZE = NOT_AUTHORIZED
```

## 6. 当前架构完成度

| 架构块 | 状态 | 说明 |
|---|---|---|
| ESP32 产品壳 | Implemented | 编译基线存在，S7 分层已进入代码 |
| ESP32 硬件验收 | Blocked | 需要真实板卡 / CAN analyser / audio hardware |
| S12 persistent source | Verified in software | Stage V/W/Y/Z/AA/AB/AC tests + CI |
| Track-P frozen guard | Verified | 最新 PR #5 CI 已通过 frozen-boundary guard |
| Hellcat AA-C3 | Engineering candidate | 自动指标改善，未 human accepted |
| V3 blind audition package | Verified package | manifest 已固定，等待 Jovi |
| Human feedback loop | Blocked | 需要 Jovi 试听 |
| R1 qualification | Blocked | 缺合法同步参考 |
| AudioParameterPackage | Not started as product contract | Human PASS 后启动 |
| Portable C++ realtime | Not started | Human PASS / profile 后启动 |
| Android realtime proof | Not started | C++ reference 后启动 |
| ESP32 advanced sound port | Not started | C++/resource characterization 后启动 |
| Vehicle pilot | Not started | 需要硬件、CAN、安全、热/EMC/延迟验收 |

## 7. 架构上的硬规则

- CAN 产品路径永远 listen-only；
- 不用 CI 通过替代声音真实感通过；
- 不用 human preference 替代 R1 qualification；
- 不把 whole-mix / master gain 当 source-causal 修复；
- 不在反馈前打开 blind answer；
- 不在 Hellcat 通过前扩散车型；
- 不把完整 ENSIM4 CFD 搬进 Android/ESP32 runtime；
- 平台差异只能在 adapter / scheduling / I/O 层，不允许各端形成不同的声音算法真值。
