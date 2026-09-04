# 项目整体状态审计与交接（2026-09-04）

## 1. 本次审计来源

本状态报告综合：

- 当前 GitHub `main` / PR #5 / CI 实测真值；
- 仓库现有 S12 Stage V→AB/AA 报告与执行状态；
- `S12_Handoff_Package_2026-09-03` 下一 Agent 交接包；
- 项目固件 `README.md` / `PLAN.md` / S7 roadmap/backlog；
- 当前统一的产品架构判断。

原则：远端当前事实优先于历史聊天和旧 SHA。

## 2. 一句话状态

**产品壳已经存在，S12 声音工程已经走到 Hellcat pre-human gate，PR #5 已完成合并；高级声音尚未进入最终 ESP32 runtime。当前最近关卡是 Stage-AC post-merge truth/AC8 收口和 Jovi V3 盲听，而不是继续扩算法或车型。**

## 3. 当前远端事实

审计时间：2026-09-04。

```text
main:
82c7cb77d26f446251e63d1a6899b08bf08be65b

PR #5:
S12 Stage AB pre-human validation hardening
state = MERGED
merged_at = 2026-09-04T13:51:52Z
head = 021fe29480aadabd4d9ba4c20bbc111d1c386795
current main direct parent chain includes PR head; `82c7...` is a later Stage-AC state-record commit

latest successful CI:
run = 33703659821
head_sha = 021fe29480aadabd4d9ba4c20bbc111d1c386795
result = SUCCESS

full S12:
1423 passed
10 skipped
232 subtests passed
1 warning

Track-P frozen guard:
PASS

CI artifact:
9875918055
sha256:6d9892d60c6f9552aea790f91d9679a1739b77b4aa4fb0a01c5dc729560ea5ae
```

所以：**PR exact-head CI 已不是 blocker。当前只剩 post-merge governance/smoke 需要闭合，不能把旧 `execution_state.json` 的 IN_PROGRESS 当作真实 CI 失败。**

## 4. 已经完成到哪里

### 4.1 ESP32 固件产品壳

Implemented：

- ESP-IDF baseline；
- CAN listen-only receive/parser；
- I2S baseline audio；
- BLE GATT；
- SD JSON；
- encoder / throttle pot / WS2812；
- Network / IoT / OTA / RuntimeStatus；
- 25 ms App loop；
- build/OpenSpec/size 工程门。

未完成：真实板级验收和高级 S12 runtime 接入。

### 4.2 S12 声音架构

Software-verified：

- persistent event-domain engine；
- per-cylinder/path/bank/collector；
- forced induction / mechanical / transient lifecycle；
- waveguide/path state；
- dP/DC pressure-to-audio；
- frozen PTR/Radiation adapter；
- comparator/reference governance；
- open-source method traceability；
- candidate ablation / reachability / receipts；
- block/stream/snapshot regression；
- Track-P frozen boundary guard。

### 4.3 Hellcat 声学收口

完成：

- Stage AA energy budget/root cause；
- AA-C0…C3 bounded candidates；
- AA-C3 finalist candidate；
- v3 audition package；
- Stage AB gain provenance / Shapley；
- source-causal eligibility hardening；
- LF metric v2；
- blower post-PTR audit；
- isolated-event dynamic timing；
- Stage AC hermetic CI closure。

仍未完成：human acceptance。

## 5. 当前最重要的声音事实

AA-C3 相对 Stage-Z 的主要诊断均值：

| Metric | Parent | Stage-Z | AA-C3 |
|---|---:|---:|---:|
| RMS dBFS | -45.588 | -62.039 | -47.801 |
| Dynamic range dB | 9.368 | 3.582 | 5.747 |
| Spectral centroid Hz | 1683.1 | 4247.3 | 1830.4 |
| Roughness proxy | 0.546 | 0.580 | 0.517 |
| Sharpness proxy | 0.146 | 0.297 | 0.115 |
| Persistent-tone ratio | 0.453 | 0.488 | 0.444 |

这些数字说明 AA-C3 比 Stage-Z 更合理，但**不等于真实感已通过**。

### Provenance

AA-C3 RMS recovery 约 +15.5 dB，Shapley 归因主要来自：

- event-body：约 66%；
- broad pre-PTR scale：约 33%；
- carrier：很小。

因此 Round 2 明确禁止 whole-mix / broad-mix gain。

### 三个 Human 风险

1. Afterfire：约 20 dB above body 的 red flag，可能像“鞭炮”；
2. Hot idle LF：v2 guard 结果 `ELEVATED`，可能从重量感变成 boom；
3. Blower：hot idle 约 741 Hz persistent carrier，需要判断是真机械增压身份还是电子蜂鸣。

## 6. 当前真正 blocker

### P0 — Stage-AC post-merge truth 尚未闭合

PR #5 已合并，AC7 在事实层已经完成；run `33703659821` 证明 AC6 对 PR head 已 green。当前 main 又多一笔状态记录提交，且没有新的 main workflow，因此需要：

- 记录 AC6=PASS；
- 记录 AC7=PASS；
- 核对 post-merge delta 仅为治理元数据；
- 做 AC8 最小充分 smoke/Track-P guard；
- 生成 post-merge receipt。

### P1 — Jovi V3 blind audition

这是当前声学产品门。

试听包：

`E:\Tesla_speed\review_packages\s12-stage-aa-hellcat-quality-v3`

manifest：

`b1ea99d36179229ff7d31f30f4790b6b84d8af587c14d44398e8e595f5f0964f`

反馈前：

- 不改 AA-C3；
- 不揭盲；
- 不做 Round 2；
- 不宣称 HUMAN_PASS。

### P2 — R1 missing

当前：

```text
R1 = MISSING
OEM_CALIBRATION = NOT_AUTHORIZED
PROFILE_FREEZE = NOT_AUTHORIZED
```

这和 Human Gate 是不同维度。

### P3 — Product runtime bridge 未开始

仍缺：

- AudioParameterPackage；
- Golden state/PCM；
- portable C++ runtime；
- Android/desktop realtime proof；
- ESP32 advanced runtime port；
- CPU/heap/latency/underrun；
- board/vehicle validation。

## 7. 已经关闭、不要重复调查的问题

- Ubuntu CI 访问 Windows review-package path；
- Track-P guard ancient-base whitespace false positive；
- generated evidence CRLF；
- stage receipt base 必须等于 current merge-base 的错误规则；
- “97 errors”旧误判；
- P6 被错误当成 source stem；
- LF persistence v1 数学无效；
- blower v1 未真正分析 audible post-PTR；
- dynamic 0 ms 在缺 isolated event 时的错误解释。

## 8. 当前应该做什么

最近动作只有：

```text
Stage-AC exact-head/merge truth reconciliation
→ AC8 post-merge smoke + receipt
→ WAITING_FOR_JOVI_AUDITION
→ Jovi V3 feedback
→ feedback hash/binding
→ accept AA-C3 OR one source-causal Round2
```

不应该做：

- 扩更多开源项目；
- 重写 Track-P；
- 提前做 Ferrari/RX-7；
- 用 master gain 修 Hellcat；
- 把 Python candidate 直接塞入 ESP32；
- 因为 CI green 宣称声音完成。

## 9. 后续产品路线

```text
Hellcat Human PASS
→ Hellcat Engineering Profile
→ Ferrari/RX-7
→ AudioParameterPackage
→ Golden evidence
→ portable C++
→ Android/desktop realtime proof
→ ESP32 reduced realtime runtime
→ board validation
→ Tesla CAN listen-only pilot
→ R1 formal calibration when available
```
