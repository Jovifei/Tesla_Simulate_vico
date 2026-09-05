# Tesla Simulate Vico / S12 当前系统架构

更新：2026-09-05
状态：`ACTIVE_AUTHORITY`

## 1. Product North Star

最终产品是车内 Android App：

```text
speed + acceleration
→ Input Conditioning
→ VirtualEngineState
→ selected Vehicle Profile
→ realtime S12-derived sound core
→ Android low-latency audio output
```

用户可选择 Hellcat / Ferrari 458 / RX-7 FD 等车型。声音必须随车辆运动连续变化，而不是简单 speed→pitch。

## 2. Authoring / calibration architecture

```text
ReferenceCaseSet / Human feedback
            │
            ▼
Python S12 Authoritative Renderer
  ├─ persistent crank / event
  ├─ combustion source
  ├─ cylinder / bank / collector / path
  ├─ forced induction / mechanical
  ├─ tip-in / shift / lift / afterfire
  ├─ dP/DC pressure chain
  └─ Frozen PTR / Radiation
            │
            ▼
Candidate PCM + layer diagnostics
            │
            ▼
Comparator / Stage AD fixed reference distance
            │
            ▼
source-causal parameter family search
            │
            └── recenter + shrink → next render
```

Stage AD 当前围绕 **AA-C3-aware** 链工作，不回退到旧 plain P3；官方 V3 不覆盖。

## 3. Model roles

### Python S12

当前声音建模、离线渲染、reference comparison、闭环参数搜索、evidence receipt 的权威实现。

### Simulink

历史 v0.9 已知 invalid。当前只允许作为 diagnostic/teaching mirror：

```text
48 kHz / 20 ms / 960 samples
config 19x1
excitation 960x1
pressure 960x1
PCM 960x2
```

必须 Update Diagram + simulation + finite PCM + Python equivalence 才能被称为 verified mirror。

### Portable C++

Human accepted Engineering Profile 后的产品参考实现。它消费版本化 `AudioParameterPackage` 和 Golden traces，不携带 offline optimizer/报告系统。

### Android

当前目标产品 runtime。Kotlin/Java 负责应用层，NDK C++ + Oboe/AAudio 负责 realtime audio；audio callback 中禁止 heap/file I/O/JSON/UI。

## 4. Vehicle-state architecture

最小输入：

```text
speed_mps
acceleration_mps2
```

App 内部生成：

```text
virtual RPM
virtual load/throttle proxy
virtual gear + shift phase
tip-in
lift/coast/overrun
afterfire eligibility
idle/overspeed state
```

CAN/OBD/真实 RPM 以后只是 richer adapters，不能让核心声音算法绑定特定 CAN ID。

## 5. Profile architecture

一个 Vehicle Profile 需要承载：engine identity、event topology、state mapping、source/path/forced-induction/transient 参数、qualification metadata、schema/version/SHA/provenance。

顺序：Hellcat 先闭环，再迁移 Ferrari 458 和 RX-7 FD；迁移的是方法/架构，不是简单 pitch/EQ。

## 6. Evidence boundaries

```text
Track-P/PTR/Radiation = frozen during listening-preference tuning
Stage AD = diagnostic engineering loop
Human = final perceptual gate
R1 = formal calibration gate
ESP32 = deferred future option
```

公网提取音频可以在授权条件下作为 R3 私人 A/B 试听，不能自动进入 optimizer 或成为产品资产。
