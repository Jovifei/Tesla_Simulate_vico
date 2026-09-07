# Tesla Simulate Vico Documentation

更新：2026-09-07

> 当前主线：**S12 声音真实性 / Stage AD 参考闭环 → Jovi 人耳反馈 → Engineering Profiles → Android App realtime sound**。
>
> 当前产品不是 ESP32。ESP32 = `DEFERRED_FUTURE_OPTION`。

## 先读这些

1. `00-reference/01-authority-and-evidence-precedence.md` — 谁是当前真值、证据等级怎么判。
2. `08-reports/15-repository-simplification-20260907.md` — 当前仓库简化、路线纠偏、保留/删除边界与验证。
3. `08-reports/14-stage-af-numerical-fixes-and-review-server-20260906.md` — Stage AF 数值修正、试听候选、服务修复与验证边界。
4. `08-reports/16-stage-af-r-evidence-integrity-20260907.md` — Stage AF-R 证据契约、Reference/fit 闭合、H0 oracle、原工作台和发布保护。
5. `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md` — 项目长期记忆。
6. `01-architecture/01-project-system-architecture.md` — 当前系统架构。
7. `02-requirements/01-current-product-and-audio-requirements.md` — 当前产品/声音要求。
8. `04-planning/05-s12-reference-closed-loop-optimization.md` — Stage AD 负反馈优化。
9. `04-planning/02-project-master-roadmap.md` — 从现在到 App 的总路线。
10. `06-testing/01-audio-and-runtime-validation-strategy.md` — 软件、声学、人耳、App 的测试层级。
11. `10-learning/01-s12-reusable-engineering-playbook.md` — 可复用工程方法。
12. `DOCUMENTATION_AUDIT_2026-09-05.md` — 本轮逐文件审计结果。

## 当前产品最终效果

```text
车内 Android App
  ↓
speed + acceleration
  ↓
VirtualEngineState
  ├─ virtual RPM
  ├─ load / throttle proxy
  ├─ gear / shift
  ├─ tip-in / lift / overrun
  └─ transient lifecycle
  ↓
Vehicle Profile Selector
  ├─ Hellcat
  ├─ Ferrari 458
  ├─ RX-7 FD
  └─ future profiles
  ↓
S12-derived realtime sound core
  ↓
低延迟、连续、车型可辨识的车内声浪
```

CAN/OBD/真实 RPM 可以以后作为 richer input adapter，但不是当前 MVP 前置条件。

## 当前声音研发状态

已经完成/具备的软件基础包括：persistent event-domain engine、source/path/bank/collector、forced induction、transients、dP/DC、frozen PTR/Radiation、ReferenceCaseSet、comparator、parameter reachability、Stage Z 方法追踪、AA-C3、AB/AB-R 因果/指标 hardening、AC remote qualification，以及 Stage AD 的显式多轮 reference-driven controller。

2026-09-06 的 Stage AF 接力在保留 `EngineAcoustics` 和原 A/B 工作台的前提下，新增了显式 opt-in 的 cycle-phase、causal delay/convolution/derivative、shift-cut 数值修正，fit/render provenance 与 per-scene guard；Hellcat 已生成 H0/H1/H2 诊断候选。2026-09-07 的 Stage AF-R 进一步把页面、fit/Reference、IR/H0 oracle、逐场景 manifest、原子发布和慢客户端回归改成 fail-closed 证据契约。它们已通过软件验证，但仍等待 Jovi 人耳反馈，不代表 Human PASS、OEM calibration 或 Profile Freeze。

Stage AD 当前是：

```text
ReferenceCaseSet
→ AA-C3-aware render
→ fixed-scale absolute_reference_distance
→ source-causal search
→ recenter + shrink
→ repeat
→ monitor-WAV audition
→ Jovi feedback
```

远端基础设施已实现；本地真实 Reference 闭环和最终人耳结论仍是待办。

## Reference 边界

- R1：rights-cleared + 同步车辆状态，可用于正式标定；当前仍 `MISSING`。
- R2/R3：只做工程/诊断用途，不能冒充 R1。
- `extract_reference_audio.py` 产生的公网片段只允许在**用户明确授权且满足平台/版权条件**时用于 `R3_PRIVATE_DIAGNOSTIC_ONLY` 人耳 A/B；默认不得送入自动参数优化、不得产品分发、不得提升为 R2/R1。

## Simulink 的定位

历史 v0.9 `.slx` 已知存在 bypass/尺寸/compile 问题。当前：

```text
Python S12 = authoritative authoring / calibration renderer
Simulink = diagnostic / teaching mirror only
portable C++ = future product reference runtime
Android = target product runtime
```

Simulink 只有通过 Update Diagram、simulation、960x2 finite PCM 和 Python equivalence 后才可作为有效 mirror。

## docs 目录职责

- `00-reference`：权威/证据规则和外部参考边界。
- `01-architecture`：当前架构。
- `02-requirements`：当前产品/声音/性能要求。
- `03-protocols`：Reference、Human、数据合同及未来 wire protocol。
- `04-planning`：当前路线和实施计划。
- `05-execution`：可直接执行的 runbook / Codex prompt。
- `06-testing`：验收和证据策略。
- `07-debugging`：已知故障、根因、禁止重复踩坑。
- `08-reports`：按日期/Stage 保存的快照；旧 report 不代表当前方向。
- `09-backlog`：当前待办和 deferred 项。
- `10-learning`：可复用方法和学习路线。
- `knowledge`：长期记忆与历史知识节点。
- `research`：source registry、license、method adoption evidence。
- `superpowers`：历史设计/计划快照，不是当前 authority。

## 永久证据规则

```text
CI green != Human PASS
Human PASS != R1/OEM calibration
public media != rights-cleared reference
historical plan != current product direction
repository has ESP32 code != ESP32 is current product
```
