# Android App 实时声浪详细实施计划

日期：2026-09-04
状态：`PLANNED / NOT_STARTED`

> 当前 App 是产品载体。本文不是立即跳过 Human Gate 的许可；它定义的是 **Hellcat Engineering Profile 形成后** 的 App 产品化执行顺序、模块边界、接口和验收门。

---

# 1. 产品目标

App 放在车内运行，实时获得车辆速度与加速度，内部生成连续的虚拟发动机状态，再用用户选择的车型 Profile 合成声音。

```text
speed + acceleration
→ Input Conditioning
→ VirtualEngineState
→ Vehicle Profile
→ Native Realtime Sound Core
→ Android Audio Output
```

当前最小输入：

- speed
- acceleration

真实 CAN/RPM/load/gear 以后可以作为 richer adapters，但不能成为 MVP 前置条件。

---

# 2. 进入 App 开发前的 Gate

必须先满足：

1. Stage-AC AC8 已闭合；
2. Jovi 完成 Hellcat V3 Human Gate；
3. AA-C3 被接受，或 ONE source-causal Round2 已完成；
4. Hellcat `Engineering Profile` 已版本化；
5. 任何用于 App 的 profile 都有 immutable manifest/SHA；
6. Python authoritative renderer 的输入/输出合同已冻结到可回归程度。

可以并行做 App skeleton/UI prototype，但**不能在 Human Gate 前把未接受声音写成产品 profile**。

---

# 3. Phase A — Product Contracts

## A1. AppInput schema

建议结构：

```text
AppInputFrame
- timestamp_ns
- speed_mps
- acceleration_mps2
- source_quality
- freshness_ms
- valid
```

要求：

- 单位固定 SI；
- timestamp monotonic；
- missing/invalid 明确；
- 输入 source 与声音算法解耦；
- 支持 offline trace replay。

## A2. VirtualEngineState schema

建议：

```text
VirtualEngineState
- timestamp
- speed_mps
- acceleration_mps2
- rpm
- load_0_1
- throttle_proxy_0_1
- gear_index
- shift_phase
- tip_in
- lift
- overrun
- afterfire_eligibility
- idle_state
- overspeed_state
```

## A3. Vehicle Profile schema

至少：

```text
ProfileManifest
- schema_version
- vehicle_id
- display_name
- engine_family
- profile_version
- source_topology
- operating_domain
- state_mapping_params
- acoustic_params
- transient_params
- path/filter params
- output/monitor params
- qualification_level
- generator_commit
- sha256
```

---

# 4. Phase B — speed/acceleration → VirtualEngineState

这是 App 产品体验的核心桥梁，不应该塞进 UI 或 audio callback。

## B1. Speed conditioning

需要：

- sampling rate normalization；
- low-pass / smoothing；
- outlier rejection；
- stale-data handling；
- stop detection；
- monotonic timestamp handling。

验收：

- steady cruise 不导致 virtual RPM 抖动；
- GPS/传感器一个异常点不触发 gear shift / afterfire；
- stop→move 不产生巨大瞬时 acceleration artifact。

## B2. Acceleration conditioning

可能来源：

- speed derivative；
- phone IMU longitudinal estimate；
- future vehicle API。

第一版必须有 deterministic fallback：由 filtered speed derivative 产生 acceleration。

验收：

- gentle vs hard acceleration 可区分；
- braking/deceleration 可稳定判定；
- acceleration 在低速噪声区不反复正负翻转。

## B3. Virtual RPM mapping

不能简单 `rpm = speed * constant`。

需要：

- profile-specific gear ratios / virtual ratios；
- idle floor；
- launch behavior；
- shift hysteresis；
- downshift behavior；
- redline / overspeed strategy；
- transient RPM smoothing。

目标：车辆加速时听起来像一个有档位和惯性的发动机，而不是 tone generator。

## B4. Virtual load

从 speed + acceleration + state 推导：

```text
load = f(acceleration, speed, gear, transient history)
```

需要区分：

- cruise；
- tip-in；
- medium pull；
- full virtual load；
- lift/coast；
- braking。

## B5. Virtual gear / shift

必须 hysteretic/stateful：

```text
GEAR_STABLE
→ SHIFT_REQUEST
→ TORQUE_CUT / RPM_TRANSITION
→ GEAR_ENGAGE
→ RECOVERY
```

禁止 speed 在阈值附近时 gear chatter。

---

# 5. Phase C — Golden Evidence

在 C++/Android 前生成 deterministic traces。

至少：

1. stationary idle；
2. 0→30 km/h gentle；
3. 0→80 medium；
4. hard acceleration；
5. steady cruise；
6. lift/coast；
7. stop/idle return；
8. repeated shift thresholds；
9. noisy speed input；
10. missing/stale input；
11. profile switch；
12. pause/resume snapshot。

每条 trace 保存：

- raw speed/acceleration；
- conditioned input；
- VirtualEngineState；
- Python PCM；
- metrics；
- SHA/version。

---

# 6. Phase D — Portable C++ Realtime Core

## D1. 移植原则

只移植 realtime 必需 subset：

- persistent phase/event；
- source layers；
- reduced path/waveguide；
- forced induction / mechanical；
- transient state machines；
- dP/DC；
- frozen boundary equivalent；
- output/monitor；
- snapshot/restore。

不移植：

- research/report generation；
- large search/optimizer；
- CFD teacher；
- offline professional metrics；
- Python-only diagnostics。

## D2. Memory rules

audio callback 内：

- no heap allocation；
- no file I/O；
- no JSON parse；
- no locks that can block indefinitely；
- no logging hot path；
- no UI calls。

所有 profile 参数提前 load/validate。

## D3. Determinism

同一：

- profile；
- seed；
- input state trace；
- sample rate；
- block size；

应该产生稳定/有界差异的 PCM。

---

# 7. Phase E — Python ↔ C++ Equivalence

## E1. Unit-level

- phase/event count；
- event timestamps；
- gear/transient states；
- filter state；
- afterfire eligibility；
- snapshot roundtrip。

## E2. PCM-level

比较：

- RMS；
- band energies；
- centroid；
- envelope；
- dynamic range；
- event timing；
- click/pop；
- long-stream continuity。

允许 floating-point implementation 的小数值差异，但不允许感知结构差异。

## E3. Scene-level

所有 Golden traces 都要一键跑 Python/C++ pair regression。

---

# 8. Phase F — Android Native Integration

推荐技术：

- Kotlin/Java UI/application layer；
- Android NDK C++ sound core；
- Oboe（优先）或 AAudio；
- 48 kHz；
- low-latency performance mode（设备支持时）。

模块：

```text
app/
  input/
  engine-state/
  profiles/
  native-audio/
  ui/
  diagnostics/
```

JNI 边界不要每 audio frame 高频跨越。VehicleState 通过 shared/native state buffer 更新。

---

# 9. Phase G — Realtime Threading

建议：

```text
Input Thread / Sensor Callback
→ State Estimator
→ double/ring buffer
→ Audio Realtime Thread
→ PCM output
```

UI 读取 snapshot，不直接参与 audio render。

关键：

- input update rate 与 audio callback rate 解耦；
- interpolation/state smoothing 在 audio/core 合适层完成；
- profile change 在安全边界 atomic/scheduled apply。

---

# 10. Phase H — App UI MVP

第一版只做必要功能：

- vehicle profile selector；
- start/stop；
- master listening volume（注意这不是 source tuning）；
- current speed；
- current acceleration；
- virtual RPM；
- virtual gear；
- virtual load；
- runtime status；
- underrun counter；
- debug trace record/export。

高级 EQ/tuning UI 后置，避免 UI 参数变成绕过 profile qualification 的后门。

---

# 11. Phase I — Lifecycle

必须处理：

- app start；
- pause/resume；
- background/foreground；
- screen off；
- audio focus loss/gain；
- Bluetooth route change；
- output device change；
- interruption/call；
- process recreation；
- profile reload。

Persistent sound state 需要明确：暂停是 freeze、fade、reset 还是 snapshot restore。

---

# 12. Phase J — Performance Gates

建议记录而不是先写死绝对阈值；第一轮基于目标手机实测建立 baseline。

必须测：

- average callback time；
- p95/p99 callback time；
- callback budget utilization；
- underrun/xrun count；
- end-to-end input→audio latency；
- CPU%；
- native heap；
- Java/Kotlin heap；
- battery drain；
- device temperature；
- 30/60/120 min long run。

性能优化后必须重跑 Golden equivalence，不能用降质 hack 静默改变车型声音。

---

# 13. Phase K — In-car Validation

场景：

1. stationary / idle；
2. parking-lot low speed；
3. 30–50 km/h cruise；
4. gentle accel；
5. medium accel；
6. hard accel；
7. repeated virtual shifts；
8. lift/coast；
9. stop/idle return；
10. sensor noise/gap；
11. profile switch；
12. long urban drive；
13. long constant-speed drive。

记录：

- App trace；
- screen recording optional；
- audio capture optional；
- Jovi notes；
- latency impression；
- profile identity；
- unnatural events。

---

# 14. App Acceptance Definition

App v1 可以进入下一里程碑，当：

- Hellcat/Ferrari/RX-7 profile 可选择；
- speed/acceleration drive 不抖；
- virtual RPM/gear/load 连续；
- audio 无 click/pop/频繁 underrun；
- profile identity 可听辨；
- input→sound latency 主观可接受；
- lifecycle 恢复可靠；
- long-run 不明显过热/崩溃；
- Golden regression 保持；
- Jovi 车内体验通过。

这仍不等于 R1/OEM calibration。

---

# 15. 当前明确后移

不在当前 App 里程碑：

- ESP32 port；
- BLE/WiFi/OTA firmware；
- external DAC/AMP hardware；
- CAN-only dependence；
- advanced public tuning marketplace；
- cloud account/system；
- OEM certification claims。

---

# 16. Next-Agent 执行前提

后续 Agent 开 App 工作前必须先确认：

```text
AC8 = PASS
Human Hellcat = accepted or Round2 complete
Engineering Profile = immutable/versioned
```

否则只允许做不绑定具体 winner 的 App infrastructure/skeleton，不允许把未通过 candidate 当正式产品声音。
