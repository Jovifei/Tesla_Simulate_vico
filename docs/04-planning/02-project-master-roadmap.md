# Tesla Simulate Vico / S12 项目总路线图

日期：2026-09-04

> 当前全项目主线：**声音真实性 → Human Gate → Android App 实时运行**。ESP32 simplified runtime 明确后移，不属于当前实施计划。

## 1. 当前总状态

```text
A. S12 软件正确性            已较成熟
B. 声学工程方法              已较成熟
C. Hellcat 声学质量          部分完成
D. Human acceptance          等待 Jovi
E. Ferrari/RX-7 车型闭环      待 Hellcat 后迁移
F. App runtime contract       未开始
G. C++/Android 实时化         未开始
H. speed/acceleration 驱动    未开始产品实现
I. 车内 App 验收              未开始
J. R1 正式标定               外部数据条件未具备
K. ESP32 simplified runtime   Deferred future option
```

## 2. 已完成：S12 Stage V → AC

```text
Stage V   event-domain prototype
Stage W   persistent streaming architecture
Stage X   comparator / candidate search / reachability
Stage Y   source layers + closed-loop integration
Stage Z   open-source method absorption proof
Stage AA  Hellcat acoustic quality closure / AA-C3 / v3
Stage AB  gain provenance + human gate
Stage AB-R validation semantics hardening
Stage AC  CI / hermeticity / measurability closure
```

远端快照：

```text
main = 82c7cb77d26f446251e63d1a6899b08bf08be65b
PR #5 = MERGED
qualified head = 021fe29480aadabd4d9ba4c20bbc111d1c386795
CI 33703659821 = SUCCESS
full S12 = 1423 passed / 10 skipped / 232 subtests passed
Track-P = PASS
R1 = MISSING
AC8 = PENDING
```

## 3. M0 — Stage-AC post-merge closeout

- 核对 qualified head 到 current main 仅是状态/治理变化；
- 完成最小充分 post-merge smoke / Track-P guard；
- 写 AC8 exact receipt；
- 进入 `WAITING_FOR_JOVI_AUDITION`；
- 不改声音。

## 4. M1 — Hellcat V3 Human Gate

Package：

`E:\Tesla_speed\review_packages\s12-stage-aa-hellcat-quality-v3`

manifest：

`b1ea99d36179229ff7d31f30f4790b6b84d8af587c14d44398e8e595f5f0964f`

重点听：

- vehicle identity / realism；
- hot-idle life / LF body；
- blower identity；
- acceleration continuity；
- shift/lift；
- afterfire；
- synthetic artifact。

反馈前不调音、不揭盲。

## 5. M2 — ONE source-causal Round2（仅需要时）

如果 AA-C3 不直接接受：

- 仅一轮；
- 最多 3 candidates；
- 每个 candidate 对应不同 hypothesis；
- feedback → scene → source/stem → metric → parameter family → guard；
- 禁止 whole-mix/master/broad pre-PTR gain；
- objective regression → professional finalist → v4 blind audition。

失败则 `MODEL_REDESIGN_REQUIRED`，不无限搜参数。

## 6. M3 — Engineering Profiles

Hellcat Human PASS 后：

```text
Hellcat Engineering Profile
→ Ferrari 458 diagnostic/human migration
→ RX-7 FD diagnostic/human migration
→ multi-vehicle profile schema
```

Engineering Profile 代表“工程模型 + 人耳接受”，不等于 R1/OEM Freeze。

## 7. M4 — App 输入与虚拟发动机状态合同

当前 App 最小输入：

```text
speed
acceleration
```

定义稳定接口：

```text
AppInput
→ filtering / freshness
→ VehicleState
→ VirtualEngineState
   ├─ virtual RPM
   ├─ load/throttle proxy
   ├─ gear / shift
   ├─ tip-in / lift / overrun
   └─ transient lifecycle
```

完成标准：

- speed 抖动不会导致声浪抖动；
- acceleration 正负变化能自然驱动 load/lift；
- virtual RPM 连续；
- virtual gear/shift 不频繁误触发；
- pause/resume 后状态可恢复；
- offline/test trace 可重放。

未来 CAN/OBD 只是可插拔的 richer input adapter，不阻塞当前实现。

## 8. M5 — AudioParameterPackage

统一可版本化合同：

- vehicle/profile id；
- source topology；
- event/cycle parameters；
- speed/acceleration operating axes；
- virtual RPM/load/gear mapping；
- transient rules；
- path/filter/monitor parameters；
- schema version；
- generator commit / SHA；
- qualification metadata。

## 9. M6 — Golden Evidence

生成：

- deterministic speed/acceleration traces；
- derived VirtualEngineState traces；
- Golden PCM；
- metrics；
- block/snapshot cases；
- exact profile/package SHA。

## 10. M7 — Portable C++ reference runtime

只移植 App realtime 所需的最小集合：

- persistent phase/event；
- source layers；
- reduced path/waveguide；
- transient state machines；
- dP/DC；
- frozen boundary equivalent adapter；
- monitor/output；
- snapshot/restore。

完整 CFD/teacher systems 不进入手机 callback。

## 11. M8 — Python ↔ C++ equivalence

同一 speed/acceleration trace + 同一 profile：

- block output bounded；
- long-stream continuity；
- snapshot/restore deterministic；
- event timing一致；
- 无平台特供声音逻辑。

## 12. M9 — Android App 产品化

当前产品载体：Android App。

必须完成：

- speed source；
- acceleration source / filtering；
- VirtualEngineState mapper；
- vehicle profile selection；
- package loader；
- native C++ engine；
- AAudio/Oboe 48 kHz；
- realtime-safe callback；
- state double-buffer/ring-buffer；
- underrun / callback time metrics；
- CPU / memory / battery / thermal；
- pause/resume/audio focus；
- long-drive continuity；
- 车内试听。

## 13. M10 — App 车内验收

场景至少覆盖：

- 静止/idle；
- 低速；
- 匀速；
- gentle acceleration；
- hard acceleration；
- virtual shift；
- deceleration/lift；
- afterfire；
- stop/idle return；
- GPS/传感器短时异常；
- App background/foreground；
- audio interruption/recovery。

重点指标：

- input→audio latency；
- continuity；
- underrun；
- CPU/memory；
- 车型切换；
- 人耳自然度。

## 14. R1 并行工作流

R1 不阻塞 App Engineering Profile，但仍独立存在：

```text
legal raw audio
+ exact vehicle/config
+ recording metadata
+ synced real state
→ R1 reference
→ formal calibration
→ higher-level freeze
```

## 15. Deferred — ESP32

仓库已有 ESP32 资产保留，但统一状态：

`ESP32_SIMPLIFIED_RUNTIME = DEFERRED`

当前不做：

- advanced sound port；
- board bring-up；
- IRAM 优化；
- BLE/WiFi/MQTT/OTA 验收；
- CAN analyser；
- 外置功放/扬声器产品链。

App 版本稳定后，才重新评估是否有必要做独立嵌入式简化版。

## 16. 当前 Next Agent 顺序

```text
1. AC8 post-merge receipt
2. Jovi Hellcat V3 audition
3. AA-C3 accept OR ONE source-causal Round2
4. Hellcat Engineering Profile
5. Ferrari / RX-7 migration
6. AudioParameterPackage
7. speed/acceleration → VirtualEngineState contract
8. Golden traces / PCM
9. portable C++
10. Python↔C++ equivalence
11. Android App realtime
12. vehicle selector + realtime playback
13. in-car App validation
14. R1 calibration when data becomes available
15. ESP32 only if later explicitly reopened
```
