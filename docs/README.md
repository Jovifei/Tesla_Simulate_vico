# Tesla Simulate Vico Documentation

更新：2026-11-15

> 当前主线：**S12 声音真实性 / Stage AD 参考闭环 → Jovi 人耳反馈 → Engineering Profiles → Android App realtime sound**。
>
> 当前产品不是 ESP32。ESP32 = `DEFERRED_FUTURE_OPTION`。
>
> 2026-11-15 增补：声浪统一执行方案 v1.4 已获业主终审通过（2026-11-15 20:16），见 `04-planning/06-sound-unified-plan-v1.4-final.md`；配套业主需求决定记录见 `02-requirements/02-owner-requirements-decisions-20261114.md`。执行未授权（Step 1 主机冒烟测试除外）。本文件 2026-09-09 正文为历史快照，未改写；新旧关系与索引见文末“文档索引（2026-11-15）”。

## 先读这些

1. `00-reference/01-authority-and-evidence-precedence.md` — 谁是当前真值、证据等级怎么判。
2. `08-reports/15-repository-simplification-20260907.md` — 当前仓库简化、路线纠偏、保留/删除边界与验证。
3. `08-reports/14-stage-af-numerical-fixes-and-review-server-20260906.md` — Stage AF 数值修正、试听候选、服务修复与验证边界。
4. `08-reports/16-stage-af-r-evidence-integrity-20260907.md` — Stage AF-R 证据契约、Reference/fit 闭合、H0 oracle、原工作台和发布保护。
5. `08-reports/17-stage-af-r2-pre-fit-qualification-20260907.md` — Stage AF-R2 exact-head CI、identity 分层、fit snapshot、source receipt 与 H0 资格边界。
6. `08-reports/17-stage-ag-vehicle-identity-implementation-20260908.md` — Stage AG v1 车型身份层与 Reference 回退负证据。
7. `08-reports/18-stage-ag-r1-reference-remediation-20260908.md` — R1 修正、双数值门禁、blind resume 边界。
8. `08-reports/19-stage-ag-r1-strict-rich-review-routing-20260909.md` — **当前 Jovi 试听入口**：严格 package/PCM/Reference SHA 与富交互页面路由。
9. `08-reports/34-stage-ai4b-rx7-boundary-repair-20260918.md` — Stage AI4B RX-7 真峰值边界修复、真实参考闭环和 WAV 身份证据。
10. `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md` — 项目长期记忆。
11. `01-architecture/01-project-system-architecture.md` — 当前系统架构。
12. `02-requirements/01-current-product-and-audio-requirements.md` — 当前产品/声音要求。
13. `04-planning/05-s12-reference-closed-loop-optimization.md` — Stage AD 负反馈优化。
14. `04-planning/02-project-master-roadmap.md` — 从现在到 App 的总路线。
15. `06-testing/01-audio-and-runtime-validation-strategy.md` — 软件、声学、人耳、App 的测试层级。
16. `10-learning/01-s12-reusable-engineering-playbook.md` — 可复用工程方法。
17. `DOCUMENTATION_AUDIT_2026-09-05.md` — 本轮逐文件审计结果。
18. `04-planning/06-sound-unified-plan-v1.4-final.md` — 声浪统一执行方案 v1.4 定稿（业主终审通过 2026-11-15 20:16；执行未授权）。
19. `02-requirements/02-owner-requirements-decisions-20261114.md` — 业主 16 条需求决定记录（需求基线配套记录）。

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

2026-09-06 的 Stage AF 接力在保留 `EngineAcoustics` 和原 A/B 工作台的前提下，新增了显式 opt-in 的 cycle-phase、causal delay/convolution/derivative、shift-cut 数值修正，fit/render provenance 与 per-scene guard；Hellcat 已生成 H0/H1/H2 诊断候选。2026-09-07 的 Stage AF-R 进一步把页面、fit/Reference、IR/H0 oracle、逐场景 manifest、原子发布和慢客户端回归改成 fail-closed 证据契约。Stage AF-R2 在此基础上收紧 exact-head CI、audio/fit/UI identity 失效边界、fit 原字节 snapshot、Git source receipt 和单车型导航；只有远端 exact-head CI 全绿才可进入 R3。它们已通过软件验证，但仍等待 Jovi 人耳反馈，不代表 Human PASS、OEM calibration 或 Profile Freeze。

当前四车型的即时试听路径是 Stage AG-R1：先保留 AG v1 的 3% Reference 回退作为负证据，再以 `vehicle_identity_v1r1` 同时满足 16 个既有 Reference 场景无 >3% 回退及 matched-state separation 不低于 legacy。Jovi 试听必须通过 `stage_ag.serve_r1_review_strict`：它在绑定 23380–23383（legacy）和 23480–23483（R1）前，重验 manifest self-hash、exact manifest SHA、4 车型、dashboard contract、candidate PCM SHA、Reference SHA 和富交互 HTML marker。`8080/8088–8091` 及 `review_packages/serve_dashboards.py` 是历史路由，不能用于此 R1 试听；详见 Report 19。当前状态仍是 `WAITING_FOR_JOVI_ACOUSTIC_REVIEW`，不是 Human PASS、OEM/R1 calibration 或 Profile Freeze。

Jovi 的 2026-09-09 首轮 R1 试听确认四车型身份已经可以区分，整体听感约为 80%；但真车与算法的频率/波形仍不完全一致，因此“可区分”不等于“完美贴合”。后续只有在 Jovi 明确授权新的窄范围声学优化后，才能进入下一轮；不能自动 fit、无限调参或把本轮反馈写成批准结论。

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

---

## 文档索引（2026-11-15）

本次索引随声浪统一执行方案 v1.4 入仓建立。`docs/` 下共 163 个 Markdown 文档（另有 46 个非 Markdown 证据/数据文件，见末尾说明），逐文件列清如下；“最后更新”取各文件最近一次提交日期（新入仓/本次更新的文件记 2026-11-15）。

### 新增与更新（本次提交）

- 新增 `04-planning/06-sound-unified-plan-v1.4-final.md`：声浪统一执行方案 v1.4 定稿，业主终审通过 2026-11-15 20:16；执行未授权（Step 1 主机冒烟测试除外）。技术内容与工作区定稿一致，仅状态头与第八节改为决议记录。
- 新增 `02-requirements/02-owner-requirements-decisions-20261114.md`：业主 16 条需求决定记录，仓内此前无等效需求基线文档，故全文入仓。
- 更新 `02-requirements/00-guide.md`、`04-planning/00-guide.md`：目录索引增列新文档。
- 更新本索引：顶部增补 v1.4 通过提示，“先读这些”增列两项，并新增本文档索引附录。
- 未动：`docs/` 之外的代码/配置/资产/音频；账本生成的 `01-ARC-*` / `02-RPT-*`（勿直接编辑）。
- 注意：仓库 `.gitignore` 对 `docs/` 用白名单式忽略（仅索引/指南等少数文件未忽略），本次两个新文件与既有 161 个已跟踪文档一样以 force-add 入仓；`.gitignore` 本身未动。

### 已删除记录

本次删除 0 个文件。逐文件判定：无任何现有文件的内容被 v1.4 定稿完全取代；`docs/GUIDE.md` §5 亦规定历史报告/计划快照不删除。旧文档全部保留，状态见下表。

### 待业主定事项

1. v1.4 第四节末两处细微口径差异未裁定：① `model_status` 是否一并废止；② `MODEL_INCOMPLETE` 入口是否放宽至从 `SPEC_UNVERIFIED` 转入。定稿保留原表述，待业主定。
2. 本索引上方 2026-09-09 正文（S12 时期主线/状态描述）为历史快照，未改写；是否刷新为 v1.4 双线主线表述，待业主定。
3. S12 时期现行文档（`01-architecture` / `02-requirements/01-*` / `03-protocols` / `04-planning/02–05` / `06-testing/01-*` 等）与 v1.4 定稿的新旧关系，待业主定。
4. 待核验事项（定稿第八节第 3 项）：911 GT3 RS 发动机代码、Ram ISB 精确型号标识及传动配置。

### 全部文档清单

| 文档 | 用途 | 状态 | 最后更新 |
|---|---|---|---|
| `00-reference/00-guide.md` | 00-reference 目录索引 | 现行（索引） | 2026-09-05 |
| `00-reference/01-authority-and-evidence-precedence.md` | 权威/证据规则 | 现行 | 2026-09-05 |
| `01-ARC-项目总体路线图.md` | 账本生成文档（勿直接编辑，见文件头） | 生成文档 | 2026-10-02 |
| `01-architecture/00-guide.md` | 01-architecture 目录索引 | 现行（索引） | 2026-09-05 |
| `01-architecture/01-project-system-architecture.md` | 系统架构 | 现行（S12 时期） | 2026-09-05 |
| `02-RPT-项目进度总览.md` | 账本生成文档（勿直接编辑，见文件头） | 生成文档 | 2026-10-02 |
| `02-requirements/00-guide.md` | 02-requirements 目录索引 | 现行（索引） | 2026-11-15 |
| `02-requirements/01-current-product-and-audio-requirements.md` | 产品/声音需求 | 现行（S12 时期） | 2026-09-05 |
| `02-requirements/02-owner-requirements-decisions-20261114.md` | 业主 16 条需求决定记录（需求基线配套记录） | 现行（业主决定记录） | 2026-11-15 |
| `03-protocols/00-guide.md` | 03-protocols 目录索引 | 现行（索引） | 2026-09-05 |
| `03-protocols/01-reference-and-human-evidence-protocol.md` | Reference/证据协议 | 现行（S12 时期） | 2026-09-05 |
| `04-planning/00-guide.md` | 04-planning 目录索引 | 现行（索引） | 2026-11-15 |
| `04-planning/01-firmware-roadmap.md` | 固件路线图 | 已延期（DEFERRED_FUTURE） | 2026-09-04 |
| `04-planning/02-project-master-roadmap.md` | 路线/实施计划 | 现行（S12 时期） | 2026-09-05 |
| `04-planning/03-current-app-product-direction.md` | 路线/实施计划 | 现行（S12 时期） | 2026-09-05 |
| `04-planning/04-android-app-runtime-implementation-plan.md` | 路线/实施计划 | 现行（S12 时期） | 2026-09-04 |
| `04-planning/05-s12-reference-closed-loop-optimization.md` | 路线/实施计划 | 现行（S12 时期） | 2026-09-05 |
| `04-planning/06-sound-unified-plan-v1.4-final.md` | 声浪统一执行方案 v1.4 定稿（命名、状态词汇、M4/RX-7 基线、响度、C2C 范围、第二批变体） | 现行（业主终审通过 2026-11-15 20:16；执行未授权） | 2026-11-15 |
| `04-planning/history/05-s12-reference-closed-loop-optimization-20260904.md` | 规划历史版本 | 历史快照 | 2026-09-05 |
| `05-execution/00-guide.md` | 05-execution 目录索引 | 现行（索引） | 2026-09-05 |
| `05-execution/02-stage-ad-local-codex-execution-prompt.md` | Stage 执行 runbook/交接 | 历史快照 | 2026-09-05 |
| `05-execution/04-stage-af-local-ai-handoff.md` | Stage 执行 runbook/交接 | 历史快照 | 2026-09-09 |
| `05-execution/history/02-stage-ad-local-codex-execution-prompt-20260904.md` | Stage 执行 runbook/交接 | 历史快照 | 2026-09-05 |
| `06-testing/00-guide.md` | 06-testing 目录索引 | 现行（索引） | 2026-09-05 |
| `06-testing/01-audio-and-runtime-validation-strategy.md` | 验收/证据策略 | 现行（S12 时期） | 2026-09-05 |
| `07-debugging/00-guide.md` | 07-debugging 目录索引 | 现行（索引） | 2026-09-06 |
| `07-debugging/01-known-failures-and-do-not-repeat.md` | 已知故障/踩坑记录 | 现行（S12 时期） | 2026-09-05 |
| `07-debugging/02-acoustic-tuning-pitfalls-and-breakthroughs.md` | 已知故障/踩坑记录 | 现行（S12 时期） | 2026-09-06 |
| `07-debugging/02-s12-review-server-refresh.md` | 已知故障/踩坑记录 | 现行（S12 时期） | 2026-09-06 |
| `08-reports/00-guide.md` | 08-reports 目录索引 | 现行（索引） | 2026-09-07 |
| `08-reports/01-s12-stage-k-eight-vehicle-round2.md` | Stage/日期快照报告 | 历史快照 | 2026-08-21 |
| `08-reports/02-s12-workspace-cleanup-20260830.md` | Stage/日期快照报告 | 历史快照 | 2026-08-30 |
| `08-reports/03-s12-stage-y-closed-loop-remediation.md` | Stage/日期快照报告 | 历史快照 | 2026-08-31 |
| `08-reports/03-s12-stage-y-wip-checkpoint-20260831.md` | Stage/日期快照报告 | 历史快照 | 2026-08-31 |
| `08-reports/04-s12-stage-y-hybrid-calibration-tooling.md` | Stage/日期快照报告 | 历史快照 | 2026-08-31 |
| `08-reports/05-s12-stage-y-local-codex-handoff.md` | Stage/日期快照报告 | 历史快照 | 2026-08-30 |
| `08-reports/06-s12-stage-y-open-source-integration.md` | Stage/日期快照报告 | 历史快照 | 2026-09-01 |
| `08-reports/07-s12-stage-y-final-closure.md` | Stage/日期快照报告 | 历史快照 | 2026-09-01 |
| `08-reports/08-s12-stage-z-open-source-absorption.md` | Stage/日期快照报告 | 历史快照 | 2026-09-01 |
| `08-reports/09-s12-stage-aa-acoustic-quality-closure.md` | Stage/日期快照报告 | 历史快照 | 2026-09-02 |
| `08-reports/10-project-status-20260904.md` | Stage/日期快照报告 | 历史快照 | 2026-09-04 |
| `08-reports/11-project-status-20260905.md` | Stage/日期快照报告 | 历史快照 | 2026-09-07 |
| `08-reports/12-stage-af-main-baseline-and-cleanup.md` | Stage/日期快照报告 | 历史快照 | 2026-09-07 |
| `08-reports/13-main-branch-reconciliation-20260906.md` | Stage/日期快照报告 | 历史快照 | 2026-09-07 |
| `08-reports/14-stage-af-numerical-fixes-and-review-server-20260906.md` | Stage/日期快照报告 | 历史快照 | 2026-09-06 |
| `08-reports/15-repository-simplification-20260907.md` | Stage/日期快照报告 | 历史快照 | 2026-09-07 |
| `08-reports/16-stage-af-r-evidence-integrity-20260907.md` | Stage/日期快照报告 | 历史快照 | 2026-09-07 |
| `08-reports/17-stage-af-r2-pre-fit-qualification-20260907.md` | Stage/日期快照报告 | 历史快照 | 2026-09-07 |
| `08-reports/17-stage-ag-vehicle-identity-implementation-20260908.md` | Stage/日期快照报告 | 历史快照 | 2026-09-08 |
| `08-reports/18-stage-ag-r1-reference-remediation-20260908.md` | Stage/日期快照报告 | 历史快照 | 2026-09-08 |
| `08-reports/19-stage-ag-r1-strict-rich-review-routing-20260909.md` | Stage/日期快照报告 | 历史快照 | 2026-09-09 |
| `08-reports/20-stage-ah-source-drone-afterfire-20260909.md` | Stage/日期快照报告 | 历史快照 | 2026-09-09 |
| `08-reports/31-stage-ai-measured-feedback-20260916.md` | Stage/日期快照报告 | 历史快照 | 2026-09-16 |
| `08-reports/32-stage-ai4a-rx7-truepeak-diagnostics-20260917.md` | Stage/日期快照报告 | 历史快照 | 2026-09-17 |
| `08-reports/33-stage-ai4a-rx7-truepeak-results-20260918.md` | Stage/日期快照报告 | 历史快照 | 2026-09-18 |
| `08-reports/34-stage-ai4b-rx7-boundary-repair-20260918.md` | Stage/日期快照报告 | 历史快照 | 2026-09-18 |
| `08-reports/35-stage-ai4b-project-audit-20260919.md` | Stage/日期快照报告 | 历史快照 | 2026-09-19 |
| `08-reports/36-stage-ai5-multirate-peak-gate-20260919.md` | Stage/日期快照报告 | 历史快照 | 2026-09-19 |
| `08-reports/36-stage-ai6-unified-audition-20260920.md` | Stage/日期快照报告 | 历史快照 | 2026-09-21 |
| `09-backlog/00-guide.md` | 09-backlog 目录索引 | 现行（索引） | 2026-09-05 |
| `09-backlog/01-firmware-backlog.md` | 待办/deferred 项 | 现行（S12 时期） | 2026-09-04 |
| `09-backlog/02-project-master-backlog.md` | 待办/deferred 项 | 现行（S12 时期） | 2026-09-05 |
| `10-learning/00-guide.md` | 10-learning 目录索引 | 现行（索引） | 2026-09-05 |
| `10-learning/01-s12-reusable-engineering-playbook.md` | 可复用方法/学习路线 | 现行（S12 时期） | 2026-09-18 |
| `10-learning/02-engine-acoustic-physical-simulation-playbook.md` | 可复用方法/学习路线 | 现行（S12 时期） | 2026-09-06 |
| `DOCUMENTATION_AUDIT_2026-09-05.md` | 逐文件审计账本（2026-09-05） | 历史快照 | 2026-09-05 |
| `GUIDE.md` | 文档指南：权威层级、文档类别、证据规则 | 现行 | 2026-09-09 |
| `README.md` | 文档索引（本文件） | 现行 | 2026-11-15 |
| `README_STAGE_AF.md` | Stage AF 说明 | 历史快照 | 2026-09-07 |
| `architecture/S12_Event_Domain_Source_Architecture_v1.md` | 架构记录 | 历史快照 | 2026-08-25 |
| `architecture/S12_Stage_W_Selected_Architecture.md` | 架构记录 | 历史快照 | 2026-08-28 |
| `knowledge/01-physics-acoustic-engine-methodology.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-09 |
| `knowledge/02-stage-af-current-handoff.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-09 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/00-MOC.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-05 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/01-Stage-V-Independent-Audit.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-26 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/02-Architecture-Comparison.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-26 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/03-License-Matrix.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-26 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/04-Source-To-S12-Traceability.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-27 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/05-Stage-W-Logs.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-29 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/06-Bakeoff-And-Migration-V3.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-07 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/07-Stage-X-Remote-Reconciliation.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-30 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/08-Engineering-Selection-Contract.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-30 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/09-Hellcat-R2-Engineering-Selection.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-30 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/10-Ferrari-RX7-Diagnostic-Migration.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-30 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/11-R1-Formal-Gate-Readiness.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-30 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/12-Stage-X-Final-Status.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-30 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/13-Workspace-Cleanup-20260830.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-30 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/14-Stage-Y-Closed-Loop-Remediation.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-30 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/15-Stage-Y-Hybrid-Calibration-Tooling.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-30 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/15-Stage-Y-Status.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-01 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/16-Stage-Z-Status.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-01 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/17-Stage-AA-Status.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-01 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/AA-C3-Gain-Provenance-v2.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-02 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/AA-C3-Gain-Provenance.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-02 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Blower-Source-vs-Audible-Path.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-02 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Broad-Pre-PTR-vs-Source-Causal-Gain.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-02 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Commercial-Public-Workflow-References.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-26 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Counterfactual-Residual-vs-True-Source-Stem.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-02 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Decision-History-And-Negative-Knowledge.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-06 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Dynamic-Event-Aligned-Metrics.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-02 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Hellcat-Human-V3-Feedback.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-02 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/LF-Persistence-Metric-Failure.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-02 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Open-Source-DasEtwas-Enginesound.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-26 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Open-Source-ENSIM4.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-26 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Open-Source-Engine-Sim.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-26 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Open-Source-FiveM-License-Boundary.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-26 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Open-Source-Granular-ESP32-Boundaries.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-26 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Open-Source-Ignis.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-07 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Open-Source-Markeasting-Engine-Audio.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-07 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Open-Source-PTR-Model.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-26 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Open-Source-VehicleNoiseSynthesizer.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-26 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Papers-PTR-EONE-DDSP.md` | 长期记忆/知识节点 | 历史快照 | 2026-08-26 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Historical-Memory-Through-2026-09-04.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-05 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-20 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Research-Sources-And-Adoption-History.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-04 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Stage-AA-Post-Merge-Truth.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-02 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Stage-AB-Final-Status.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-02 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Stage-AB-Negative-Knowledge.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-02 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Stage-AB-PreHuman-Hardening.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-02 |
| `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Stage-AB-Round2-ADR.md` | 长期记忆/知识节点 | 历史快照 | 2026-09-02 |
| `research/engine-audio-ecosystem/README.md` | 来源/许可证/方法采用证据 | 研究证据 | 2026-09-05 |
| `research/engine-audio-ecosystem/license_matrix.md` | 来源/许可证/方法采用证据 | 研究证据 | 2026-08-26 |
| `research/engine-audio-ecosystem/stage_ad_closed_loop_sources.md` | 来源/许可证/方法采用证据 | 研究证据 | 2026-09-04 |
| `research/engine-audio-ecosystem/stage_af_sources.md` | 来源/许可证/方法采用证据 | 研究证据 | 2026-09-06 |
| `research/engine-audio-ecosystem/stage_ag_vehicle_identity_sources.md` | 来源/许可证/方法采用证据 | 研究证据 | 2026-09-08 |
| `superpowers/README.md` | 历史设计/计划快照 | 历史快照 | 2026-09-05 |
| `superpowers/plans/2026-08-23-s12-professional-comparison-dashboard-r2-diagnostic-tuning.md` | 历史设计/计划快照 | 历史快照 | 2026-08-23 |
| `superpowers/plans/2026-08-23-s12-r1-pilot-acquisition-r2-feedback-closure.md` | 历史设计/计划快照 | 历史快照 | 2026-08-23 |
| `superpowers/plans/2026-08-23-s12-rx7-topic-aware-r2.md` | 历史设计/计划快照 | 历史快照 | 2026-08-23 |
| `superpowers/plans/2026-08-28-s12-stage-w-v26-checkpointed-recovery.md` | 历史设计/计划快照 | 历史快照 | 2026-08-28 |
| `superpowers/plans/2026-08-28-s12-stage-w-v27-external-staging.md` | 历史设计/计划快照 | 历史快照 | 2026-08-28 |
| `superpowers/plans/2026-08-30-s12-stage-y-source-layers.md` | 历史设计/计划快照 | 历史快照 | 2026-08-31 |
| `superpowers/specs/2026-08-23-s12-rx7-topic-aware-r2-design.md` | 历史设计/计划快照 | 历史快照 | 2026-08-23 |
| `superpowers/specs/2026-08-28-s12-stage-w-v26-resume-design.md` | 历史设计/计划快照 | 历史快照 | 2026-08-28 |
| `superpowers/specs/2026-08-28-s12-stage-w-v27-staged-publication-design.md` | 历史设计/计划快照 | 历史快照 | 2026-08-28 |
| `superpowers/specs/2026-08-30-s12-stage-y-source-layers-design.md` | 历史设计/计划快照 | 历史快照 | 2026-08-31 |
| `third_party_acoustic_tools.md` | 第三方声学工具记录 | 历史快照 | 2026-08-21 |
| `vico-cloud-stage-handoff.md` | 交接/验证记录 | 历史快照 | 2026-10-02 |
| `vico-cloud-stage-result.md` | 交接/验证记录 | 历史快照 | 2026-10-02 |
| `vico-device-gate-order-fix.md` | 交接/验证记录 | 历史快照 | 2026-10-02 |
| `vico-device-reception-20261002.md` | 交接/验证记录 | 历史快照 | 2026-10-02 |
| `vico-frozen-hy1-actual-kotlin-result.md` | 交接/验证记录 | 历史快照 | 2026-10-02 |
| `vico-input-timing-repair-validation.md` | 交接/验证记录 | 历史快照 | 2026-10-03 |
| `vico-local-reception-verification.md` | 交接/验证记录 | 历史快照 | 2026-10-02 |
| `vico-main-integration-20261003.md` | 交接/验证记录 | 历史快照 | 2026-10-03 |
| `vico-n2-ci-validation.md` | 交接/验证记录 | 历史快照 | 2026-10-03 |
| `vico-n2-evidence-gate-validation.md` | 交接/验证记录 | 历史快照 | 2026-10-03 |
| `vico-n2-historical-continuity-validation.md` | 交接/验证记录 | 历史快照 | 2026-10-03 |
| `vico-n2-historical-state-validation.md` | 交接/验证记录 | 历史快照 | 2026-10-03 |
| `vico-n2-local-event-atomic-reception.md` | 交接/验证记录 | 历史快照 | 2026-10-02 |
| `vico-n2-local-nested-atomic-reception.md` | 交接/验证记录 | 历史快照 | 2026-10-02 |
| `vico-n2-local-profile-reception.md` | 交接/验证记录 | 历史快照 | 2026-10-02 |
| `vico-n2-render-metrics-validation.md` | 交接/验证记录 | 历史快照 | 2026-10-03 |
| `vico-n2-stem-export-validation.md` | 交接/验证记录 | 历史快照 | 2026-10-03 |
| `vico-p2-n2-binary-artifact-freeze.md` | 交接/验证记录 | 历史快照 | 2026-10-02 |
| `vico-p2-n2-calibration-freeze.md` | 交接/验证记录 | 历史快照 | 2026-10-02 |
| `vico-p2-n2-implementation-preregistration.md` | 交接/验证记录 | 历史快照 | 2026-10-02 |
| `vico-p2-n2-source-design-preregistration.md` | 交接/验证记录 | 历史快照 | 2026-10-02 |
| `vico-p2-n2-stage-result.md` | 交接/验证记录 | 历史快照 | 2026-10-03 |
| `vico-p2-p3-execution-plan.md` | 交接/验证记录 | 历史快照 | 2026-10-02 |
| `vico-p2-p3-remote-audit.md` | 交接/验证记录 | 历史快照 | 2026-10-02 |
| `vico-p3-runtime-hook-result.md` | 交接/验证记录 | 历史快照 | 2026-10-02 |
| `vico-publication-verification.md` | 交接/验证记录 | 历史快照 | 2026-10-02 |

### 非 Markdown 文件（46 个，全部保留）

`docs/.gitattributes`（1）、`docs/project-ledger.json`（1）、`docs/06-testing/n2-cloud-*` 证据包（39：日志/TSV/JSON）、`docs/research/engine-audio-ecosystem/*.json`（5）。均为证据/数据文件，本次未动。
