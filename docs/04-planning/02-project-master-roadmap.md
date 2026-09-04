# Tesla Simulate Vico / S12 项目总路线图

日期：2026-09-04

> 当前全项目主线：**声音真实性 → Human Gate → Android App 实时运行**。ESP32 simplified runtime 明确后移，不属于当前实施计划。
>
> 详细历史、参考来源、负面知识和 Agent 接管规则见：
> `docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md`。

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

重点听 vehicle identity / realism / hot-idle LF / blower / acceleration / shift/lift / afterfire / synthetic artifact。

反馈前不调音、不揭盲。

## 5. M2 — ONE source-causal Round2（仅需要时）

如果 AA-C3 不直接接受：仅一轮、最多 3 candidates、每个 candidate 对应不同 hypothesis，禁止 whole-mix/master/broad pre-PTR gain；失败则 `MODEL_REDESIGN_REQUIRED`。

## 6. M3 — Engineering Profiles

```text
Hellcat Human PASS
→ Hellcat Engineering Profile
→ Ferrari 458 migration
→ RX-7 FD migration
→ multi-vehicle profile schema
```

Engineering Profile 不等于 R1/OEM Freeze。

## 7. M4 — App 输入与虚拟发动机状态合同

当前 App 最小输入：

```text
speed
acceleration
```

定义：

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

未来 CAN/OBD 是 richer input adapter，不阻塞当前实现。

## 8. M5 — AudioParameterPackage

统一可版本化合同：vehicle/profile id、source topology、event/cycle、speed/acceleration axes、virtual RPM/load/gear mapping、transient、path/filter/monitor、schema/version/SHA/provenance。

## 9. M6 — Golden Evidence

生成 deterministic speed/acceleration traces、VirtualEngineState traces、Golden PCM、metrics、block/snapshot cases 和 exact hashes。

## 10. M7 — Portable C++ reference runtime

只移植 App realtime 所需 subset：persistent phase/event、source layers、reduced path/waveguide、transients、dP/DC、frozen boundary adapter、monitor/output、snapshot/restore。

## 11. M8 — Python ↔ C++ equivalence

同一 state trace/profile 下验证 block output、long-stream continuity、snapshot/restore 和 event timing。

## 12. M9 — Android App 产品化

必须完成：speed source、acceleration/filter、VirtualEngineState、profile selector、package loader、native C++、AAudio/Oboe 48 kHz、realtime-safe callback、state buffer、underrun、CPU/memory/battery/thermal、pause/resume/audio focus、long-drive continuity 和车内试听。

## 13. M10 — App 车内验收

覆盖 stationary idle、low speed、cruise、gentle/hard acceleration、virtual shift、deceleration/lift、afterfire、idle return、input异常、background/foreground、audio interruption/recovery。

重点：input→audio latency、continuity、underrun、CPU/memory、车型切换、听感。

## 14. R1 并行工作流

R1 不阻塞 App Engineering Profile，但 formal OEM calibration 仍需要 legal raw audio + exact vehicle/config + recording metadata + synchronized real state。

## 15. Deferred — ESP32

`ESP32_SIMPLIFIED_RUNTIME = DEFERRED`

当前不做 advanced sound port、board bring-up、IRAM、BLE/WiFi/MQTT/OTA 验收、CAN analyser 或外置硬件产品链。

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
