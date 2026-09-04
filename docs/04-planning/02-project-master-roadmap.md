# Tesla Simulate Vico / S12 项目总路线图

日期：2026-09-04

> 这是全项目主路线。`01-firmware-roadmap.md` 继续作为 ESP32 固件子路线；本文负责把固件、S12 声学、跨语言实时化和实车产品化串成一条交付链。

## 1. 当前总状态

按“真正产品完成度”分层：

```text
A. 软件正确性            已较成熟
B. 声学工程方法          已较成熟
C. Hellcat 声学质量      部分完成
D. Human acceptance      等待 Jovi
E. R1 正式标定           未具备数据条件
F. C++/Android 实时化    未开始
G. ESP32 高级声浪集成    未开始
H. 硬件/实车验收         未完成
```

当前不能用单一百分比描述项目，因为不同子系统成熟度差异很大。

## 2. 已完成主线

### Firmware S0–S7 baseline

已经完成到代码层：

- CAN listen-only parser/source；
- I2S audio baseline；
- BLE GATT；
- SD JSON；
- encoder / throttle pot / WS2812；
- status / network / iot / ota 分层；
- 25 ms App tick；
- build/size/OpenSpec 基线。

仍需硬件证明，不把 Implemented 写成 Verified-on-board。

### S12 Stage V → AC

已完成的工程演进：

```text
Stage V   event-domain prototype
Stage W   persistent streaming architecture
Stage X   comparator / candidate search / reachability
Stage Y   source layers + closed-loop integration
Stage Z   open-source method absorption proof
Stage AA  Hellcat acoustic quality closure / AA-C3 / v3 package
Stage AB  AA-C3 gain provenance + human gate
Stage AB-R validation semantics hardening
Stage AC  CI / hermeticity / measurability closure
```

最新远端快照（2026-09-04 复核）：

```text
main = 82c7cb77d26f446251e63d1a6899b08bf08be65b
PR #5 head = 021fe29480aadabd4d9ba4c20bbc111d1c386795
PR #5 = MERGED at 2026-09-04T13:51:52Z
latest CI run = 33703659821
latest CI = SUCCESS on exact PR head
full S12 = 1423 passed / 10 skipped / 232 subtests passed
Track-P = PASS
artifact = 9875918055
artifact sha256 = 6d9892d60c6f9552aea790f91d9679a1739b77b4aa4fb0a01c5dc729560ea5ae
```

## 3. 当前关卡：Stage AC closeout → Human Gate

### M0 — Stage-AC post-merge truth closure

PR #5 已于 2026-09-04 合并。`021fe294...` 是当前 main `82c7cb77...` 的直接祖先；前者已经被 run `33703659821` exact-head 全量资格化。其后只有一笔 Stage-AC 状态记录提交进入 main，目前未看到 main 分支新的完整 workflow run。

当前完成标准：

- AC6 = PASS：以 `33703659821` exact-head success 为证据；
- AC7 = PASS：以 PR #5 实际 merged + ancestry 为证据；
- 核对 `021fe... → 82c7...` diff 仅为状态/治理元数据，不改变 renderer/PCM/Track-P 数学；
- 执行最小充分的 post-merge smoke + Track-P frozen guard；
- AC8 只有在 post-merge receipt 形成后才能 PASS；
- 然后整体状态进入 `WAITING_FOR_JOVI_AUDITION`。

### M1 — Jovi V3 blind audition

当前 package：

`E:\Tesla_speed\review_packages\s12-stage-aa-hellcat-quality-v3`

manifest：

`b1ea99d36179229ff7d31f30f4790b6b84d8af587c14d44398e8e595f5f0964f`

重点评价：

- vehicle identity；
- realism；
- idle life；
- LF pressure/body；
- mechanical texture；
- blower identity；
- acceleration continuity；
- shift；
- lift/decel；
- afterfire；
- synthetic artifact；
- overall preference。

反馈前禁止调音、禁止揭盲。

### M2 — ONE source-causal Round 2（仅在需要时）

如果 AA-C3 不能直接接受：

- 只允许一轮；
- 最多 3 candidates；
- 每个 candidate 一个明确 hypothesis；
- 禁止 whole-mix / master / broad pre-PTR gain；
- feedback → scene → stem → metric → parameter family → guard；
- objective regression → professional finalist → v4 blind audition。

若一轮 source-causal repair 仍失败：

`MODEL_REDESIGN_REQUIRED`

而不是继续无限调参。

## 4. Hellcat Human PASS 后

### M3 — Engineering Profile

冻结：

`Hellcat Engineering Profile`

它代表“当前工程模型 + 人耳接受”的 profile，不等于 R1/OEM 标定。

### M4 — 三锚点迁移

顺序：

```text
Hellcat Human PASS
→ Ferrari 458 diagnostic migration
→ RX-7 FD diagnostic migration
→ 其余车型
```

每个车型必须有自己的 source identity，不允许仅复制 EQ/pitch。

## 5. 跨语言实时化

### M5 — AudioParameterPackage v1

定义统一可版本化合同：

- vehicle/profile id；
- source topology；
- event/cycle parameters；
- RPM/load domain；
- transient rules；
- filter/resonance/path parameters；
- monitor config；
- provenance / qualification level；
- schema version / commit / SHA。

### M6 — Golden Evidence

生成：

- deterministic VehicleState traces；
- Golden PCM；
- metrics；
- block sizes；
- snapshot/restore cases；
- exact package/render hashes。

### M7 — Portable C++17 reference runtime

只实现移动/嵌入式真正需要的最小集合：

- persistent phase/event；
- source layers；
- reduced path/waveguide；
- transients；
- dP/DC；
- PTR adapter equivalent boundary；
- monitor；
- snapshot/restore。

### M8 — Python ↔ C++ equivalence

完成标准：

- same state + same profile；
- block output bounded；
- long streaming continuity；
- snapshot/restore deterministic；
- no allocation/state reset artifacts。

### M9 — Android / desktop realtime proof

目标不是改变产品方向，而是验证 portable runtime：

- 48 kHz；
- realtime-safe audio callback；
- AAudio/Oboe 或桌面 host；
- CPU / memory / underrun / latency metrics；
- VehicleState ring/double buffer；
- 不在 callback heap allocate。

## 6. ESP32-S3 高级声浪落地

### M10 — Embedded profile reduction

依据 C++ profile/性能数据决定：

- 哪些 source/stem 保留；
- filters/order simplification；
- fixed-point / lookup table；
- PSRAM / IRAM / DMA budget；
- sampling/block strategy；
- quality tier。

### M11 — 接入现有 firmware shell

重点连接点：

```text
components/domain/VehicleState
        ↓
portable sound core / ESP32 adapter
        ↓
components/audio/I2S
```

BLE/SD/WiFi/OTA 只负责配置/管理，不侵入实时音频 callback。

### M12 — Board acceptance

必须覆盖：

- boot；
- BLE；
- SD；
- I2S；
- encoder/pot/LED；
- WiFi/MQTT/OTA；
- IRAM/heap/PSRAM；
- audio underrun；
- startup pop/mute；
- long-running thermal；
- CAN analyser no-transmit proof。

## 7. 实车路线

### M13 — VehicleState truth

- Tesla CAN IDs / signals 重新现场确认；
- decode confidence；
- timing/freshness；
- offline/test fallback；
- disconnect/reconnect state。

### M14 — Controlled vehicle pilot

覆盖：

- idle/low speed；
- cruise；
- tip-in；
- acceleration；
- virtual shift；
- lift/coast；
- afterfire；
- idle return；
- CAN loss；
- BLE loss；
- overspeed mute；
- thermal duration。

## 8. R1 并行工作流

R1 不必阻塞所有工程研发，但必须独立维护：

```text
legal raw WAV/FLAC
+ exact vehicle/config
+ mic/AGC/processing record
+ synced RPM/load/throttle/gear/shift
→ R1 reference
→ formal Order-RPM / calibration
→ higher-level Profile Freeze
```

没有 R1 时只能称：

- synthetic / vehicle-inspired；
- engineering candidate/profile；
- R2/R3 diagnostic；
- human accepted engineering profile。

## 9. 当前实施顺序（next agent）

```text
1. Re-verify remote truth
2. Close Stage-AC post-merge truth (AC6/AC7 factual PASS; AC8 smoke/receipt)
3. Reach WAITING_FOR_JOVI_AUDITION
4. Collect Jovi v3 feedback
5. Accept AA-C3 OR run one source-causal Round2
6. Professional finalist + v4 if needed
7. Hellcat Engineering Profile
8. Ferrari/RX-7 migration
9. AudioParameterPackage + Golden Evidence
10. C++ realtime + Android/desktop proof
11. ESP32 advanced sound integration
12. board + CAN + vehicle pilot
13. R1 calibration when data becomes available
```
