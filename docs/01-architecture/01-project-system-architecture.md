# Tesla Simulate Vico / S12 当前系统架构

日期：2026-09-04

> 当前产品架构以**车内 App 实时声浪**为主线。ESP32 不是当前产品载体，不参与当前 gate；仓库中的 ESP32 固件仅作为历史资产和后期可选 simplified runtime 保留。
>
> 历史和架构依据优先读取：
> `docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md`。

## 1. 当前产品北极星

当前目标：

**App 放在车内，获得车辆速度与加速度，App 自己计算虚拟发动机状态，用户选择车型，App 实时生成并播放该车型声浪。**

```text
            App Input Layer
        speed + acceleration
                │
                ▼
        VehicleState Normalizer
                │
                ▼
       VirtualEngineState Mapper
        ├─ virtual RPM
        ├─ load/throttle proxy
        ├─ virtual gear / shift
        ├─ tip-in / lift / overrun
        └─ transient state
                │
                ▼
        Vehicle Profile Selector
       Hellcat / Ferrari / RX-7 / ...
                │
                ▼
     Persistent Event-Domain Engine
        ├─ combustion events
        ├─ exhaust/path/bank/collector
        ├─ forced induction
        ├─ mechanical texture
        ├─ shift/lift transients
        └─ state-gated afterfire
                │
                ▼
        Pressure Audio Chain
                │
                ▼
     Frozen PTR / Radiation boundary
                │
                ▼
        Realtime PCM Renderer
                │
                ▼
         Android Audio Output
```

## 2. 当前输入合同

### 当前最小必需输入

- `speed`
- `acceleration`

App 必须能在只有这两个连续输入时运行完整声浪模型。

### App 内部派生状态

当前不要把真实 RPM/CAN 当作算法前置条件。App 内部负责从 speed/acceleration 构造合理的：

- virtual RPM；
- virtual engine load；
- throttle proxy；
- gear / shift state；
- lift / braking / coast state；
- idle/launch/overspeed state。

以后如果获得 CAN/OBD/车辆 API，可增加新的输入 adapter 覆盖或修正这些状态，但核心声浪 runtime 不与某个具体 CAN ID 绑定。

## 3. Sound Authority — 当前核心研发

S12 仍是当前声音算法权威：

```text
VehicleState / VirtualEngineState
  ↓
PersistentEventDomainEngine
  ├─ continuous crank / rotor phase
  ├─ combustion event
  ├─ per-cylinder / path propagation
  ├─ bank / collector
  ├─ forced induction
  ├─ mechanical / cycle-sync
  ├─ tip-in / shift / lift / BOV
  └─ afterfire lifecycle
  ↓
PressureAudioChain
  ↓
Frozen Track-P PTR / Radiation
  ↓
Raw / Realtime PCM
```

工程边界：

- Track-P / PTR / Radiation 冻结；
- Track-S 负责车型身份、状态和听感；
- Human audition 与自动指标分开；
- no clipping/click；
- block/stream/snapshot 连续；
- afterfire 必须状态因果；
- 没有 R1 不声称 OEM calibration。

## 4. App Productization Bridge

Hellcat Human PASS 后进入：

```text
Engineering Profile
→ AudioParameterPackage
→ Golden speed/acceleration traces
→ Golden VirtualEngineState
→ Golden PCM
→ portable C++ realtime core
→ Python ↔ C++ equivalence
→ Android integration
```

Android App 不是“中间证明宿主”，而是**当前目标产品 runtime**。

### App Runtime 模块建议

```text
app/
  vehicle-input/
    speed-source
    acceleration-source
    filters
  engine-state/
    virtual-rpm
    virtual-load
    virtual-gear
    transient-state
  profiles/
    selector
    package-loader
  audio/
    native-cpp-core
    realtime-output
    metrics
  ui/
    vehicle-selector
    status
    tuning-debug
```

## 5. 三锚点车型

当前深度验证顺序：

1. Hellcat；
2. Ferrari 458；
3. RX-7 FD。

Hellcat 先完成 human loop，然后把**方法**迁移到 Ferrari/RX-7；不能只复制 pitch/EQ。

## 6. 当前完成度

| 架构块 | 状态 |
|---|---|
| S12 persistent sound architecture | Verified in software |
| Hellcat AA-C3 | Engineering candidate |
| V3 audition package | Verified package |
| Stage-AC AC8 | Pending |
| Human acceptance | Waiting after AC8 |
| Ferrari/RX-7 final profiles | Frozen pending Hellcat |
| AudioParameterPackage | Not started |
| speed/acceleration → VirtualEngineState | Product implementation not started |
| portable C++ realtime | Not started |
| Android App realtime audio | Not started |
| vehicle profile selector | Not started |
| in-car App validation | Not started |
| R1 formal calibration | Blocked external data |
| ESP32 simplified runtime | Deferred future option |

## 7. ESP32 的正确定位

仓库已有 ESP32-S3/CAN/BLE/SD/WiFi/OTA/I2S 代码，但**当前不继续推进它，也不要求当前声浪算法接入 ESP32**。

它只保留为：

- 既有历史工程资产；
- 未来如果 App 路线稳定后，可能评估的低成本/独立硬件 simplified runtime；
- 不进入当前产品完成度；
- 不进入当前 P0/P1 blocker。

状态统一标记：

`ESP32 = DEFERRED_FUTURE_OPTION`

## 8. 硬规则

- 当前 App 不要求先接 Tesla CAN 才能工作；
- speed + acceleration 是当前最小输入合同；
- 不用 CI green 替代 Human PASS；
- 不用 Human PASS 替代 R1；
- 不用 whole-mix/master gain 做 source-causal 修复；
- 不在反馈前揭盲；
- 不把完整 CFD/teacher 系统塞入手机 realtime callback；
- Android/C++ 实现必须能由 Golden trace 与 Python 权威模型做等价回归；
- ESP32 不得重新被提升为当前 blocker。