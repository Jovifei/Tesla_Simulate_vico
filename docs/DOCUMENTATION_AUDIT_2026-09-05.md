# docs 全量技术审计账本 — 2026-09-05

审计基线：`s12-stage-ad-closed-loop-calibration@243d92620080a8e13369e0eb7b06f9b1d04ac366`。

目标：逐文件确认“当前 authority / 更新 / 历史保留 / superseded / deferred”。**本次不物理删除历史证据文件**；删除的是它们在 active navigation 中的错误权威地位。

## 内容保留原则

本轮最初的 active 文档重写会显著缩短三份长文。提交后 diff review 发现这不符合“好记性不如烂笔头”的要求，因此将原始详细版本逐字节保留为历史档案：

- `knowledge/.../Project-Historical-Memory-Through-2026-09-04.md` — 原 1150+ 行长期记忆；
- `04-planning/history/05-s12-reference-closed-loop-optimization-20260904.md` — 原详细 Stage AD 计划；
- `05-execution/history/02-stage-ad-local-codex-execution-prompt-20260904.md` — 原详细 Codex runbook。

当前同名 active 文档用于消除过期冲突和突出今天的执行真值；历史细节没有被删除。

## 发现的主要问题

1. `00-reference` / `02-requirements` guide 仍以 firmware 语义描述项目；
2. `04-planning/00-guide.md` 错把 Firmware roadmap 标 active；
3. `09-backlog/00-guide.md` 错把 Firmware backlog 标 active；
4. `03-protocols` 仍只指 BLE/CAN/MQTT/OTA，缺当前 Reference/Human protocol；
5. `06-testing` 仍以 board evidence 为中心，缺 sound/Human/Android 层级；
6. `08-reports/00-guide` current list 停在 Stage Y，缺 AA/AB/AC/AD/current status；
7. canonical memory/MOC 未包含最新 Stage AD；
8. Stage AD plan 与最新公网 R3 extractor 代码边界冲突；
9. Superpowers plans/specs 没有 historical warning；
10. `AA-C3-Gain-Provenance.md` 与 v2 共存，MOC 过去仍指旧版；
11. dashboard template 的展示数值不能被当 execution receipt。

## 本次新增/更新的 ACTIVE 文档

- `docs/README.md` — UPDATED
- `docs/GUIDE.md` — UPDATED
- `docs/00-reference/00-guide.md` — UPDATED
- `docs/00-reference/01-authority-and-evidence-precedence.md` — NEW
- `docs/01-architecture/00-guide.md` — UPDATED
- `docs/01-architecture/01-project-system-architecture.md` — UPDATED
- `docs/02-requirements/00-guide.md` — UPDATED
- `docs/02-requirements/01-current-product-and-audio-requirements.md` — NEW
- `docs/03-protocols/00-guide.md` — UPDATED
- `docs/03-protocols/01-reference-and-human-evidence-protocol.md` — NEW
- `docs/04-planning/00-guide.md` — UPDATED
- `docs/04-planning/02-project-master-roadmap.md` — UPDATED
- `docs/04-planning/03-current-app-product-direction.md` — UPDATED
- `docs/04-planning/05-s12-reference-closed-loop-optimization.md` — UPDATED + detailed old version archived
- `docs/05-execution/00-guide.md` — UPDATED
- `docs/05-execution/02-stage-ad-local-codex-execution-prompt.md` — UPDATED + detailed old version archived
- `docs/06-testing/00-guide.md` — UPDATED
- `docs/06-testing/01-audio-and-runtime-validation-strategy.md` — NEW
- `docs/07-debugging/00-guide.md` — UPDATED
- `docs/07-debugging/01-known-failures-and-do-not-repeat.md` — NEW
- `docs/08-reports/00-guide.md` — UPDATED
- `docs/08-reports/11-project-status-20260905.md` — NEW
- `docs/09-backlog/00-guide.md` — UPDATED
- `docs/09-backlog/02-project-master-backlog.md` — UPDATED
- `docs/10-learning/00-guide.md` — UPDATED
- `docs/10-learning/01-s12-reusable-engineering-playbook.md` — NEW
- `docs/research/engine-audio-ecosystem/README.md` — UPDATED
- `docs/superpowers/README.md` — NEW
- `docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/00-MOC.md` — UPDATED
- `docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md` — UPDATED current synthesis; detailed prior memory archived intact

## 已审计、保留为 Deferred

- `docs/04-planning/01-firmware-roadmap.md` — RETAIN `DEFERRED_FUTURE`
- `docs/09-backlog/01-firmware-backlog.md` — RETAIN `DEFERRED_FUTURE`
- `docs/04-planning/04-android-app-runtime-implementation-plan.md` — RETAIN `ACTIVE_FUTURE_PHASE`; 技术方向仍正确，进入条件由新 roadmap/status 解释。

## 08-reports：保留历史原文

以下全部 `HISTORICAL_SNAPSHOT`，不改写当时事实：

- `01-s12-stage-k-eight-vehicle-round2.md`
- `02-s12-workspace-cleanup-20260830.md`
- `03-s12-stage-y-closed-loop-remediation.md`
- `03-s12-stage-y-wip-checkpoint-20260831.md`
- `04-s12-stage-y-hybrid-calibration-tooling.md`
- `05-s12-stage-y-local-codex-handoff.md`
- `06-s12-stage-y-open-source-integration.md`
- `07-s12-stage-y-final-closure.md`
- `08-s12-stage-z-open-source-absorption.md`
- `09-s12-stage-aa-acoustic-quality-closure.md`
- `10-project-status-20260904.md`

当前状态转到 `11-project-status-20260905.md`。

## knowledge：逐文件定位

### Canonical/current

- `00-MOC.md` — UPDATED current index
- `Project-Long-Term-Memory.md` — UPDATED current synthesis
- `Project-Historical-Memory-Through-2026-09-04.md` — NEW archival copy of original detailed memory
- `Research-Sources-And-Adoption-History.md` — RETAIN canonical research history；Stage AD 由 dedicated research doc 补充
- `Decision-History-And-Negative-Knowledge.md` — RETAIN active negative knowledge；新增 debug doc 提供快捷入口
- `AA-C3-Gain-Provenance-v2.md` — CURRENT topic reference
- `Broad-Pre-PTR-vs-Source-Causal-Gain.md` — CURRENT topic reference
- `Counterfactual-Residual-vs-True-Source-Stem.md` — CURRENT topic reference
- `Blower-Source-vs-Audible-Path.md` — CURRENT topic reference
- `Dynamic-Event-Aligned-Metrics.md` — CURRENT topic reference
- `LF-Persistence-Metric-Failure.md` — CURRENT negative-knowledge reference
- `Hellcat-Human-V3-Feedback.md` — CURRENT human-protocol context

### Superseded but retained

- `AA-C3-Gain-Provenance.md` — SUPERSEDED by `AA-C3-Gain-Provenance-v2.md`; keep for provenance, removed from current MOC.

### Historical stage snapshots

- `01-Stage-V-Independent-Audit.md`
- `02-Architecture-Comparison.md`
- `03-License-Matrix.md`
- `04-Source-To-S12-Traceability.md`
- `05-Stage-W-Logs.md`
- `06-Bakeoff-And-Migration-V3.md`
- `07-Stage-X-Remote-Reconciliation.md`
- `08-Engineering-Selection-Contract.md`
- `09-Hellcat-R2-Engineering-Selection.md`
- `10-Ferrari-RX7-Diagnostic-Migration.md`
- `11-R1-Formal-Gate-Readiness.md`
- `12-Stage-X-Final-Status.md`
- `13-Workspace-Cleanup-20260830.md`
- `14-Stage-Y-Closed-Loop-Remediation.md`
- `15-Stage-Y-Hybrid-Calibration-Tooling.md`
- `15-Stage-Y-Status.md`
- `16-Stage-Z-Status.md`
- `17-Stage-AA-Status.md`
- `Stage-AA-Post-Merge-Truth.md`
- `Stage-AB-Final-Status.md`
- `Stage-AB-Negative-Knowledge.md`
- `Stage-AB-PreHuman-Hardening.md`
- `Stage-AB-Round2-ADR.md`

### External-source topic notes

`Open-Source-Engine-Sim.md`, `Open-Source-ENSIM4.md`, `Open-Source-DasEtwas-Enginesound.md`, `Open-Source-PTR-Model.md`, `Open-Source-VehicleNoiseSynthesizer.md`, `Open-Source-FiveM-License-Boundary.md`, `Open-Source-Granular-ESP32-Boundaries.md`, `Open-Source-Ignis.md`, `Open-Source-Markeasting-Engine-Audio.md`, `Papers-PTR-EONE-DDSP.md`, `Commercial-Public-Workflow-References.md` — RETAIN source/topic notes；current aggregate truth in research history/registry。

## research：机器证据优先保留

- `README.md` — UPDATED
- `source_registry.json` — RETAIN machine evidence
- `source_evidence_receipts.json` — RETAIN
- `source_coverage_matrix.json` — RETAIN
- `method_adoption_matrix_v2.json` — RETAIN historical machine version
- `method_adoption_matrix_v3.json` — RETAIN current Stage-Z matrix
- `license_matrix.md` — RETAIN
- `stage_ad_closed_loop_sources.md` — RETAIN current Stage-AD research

机器 evidence 不因 docs 重构被手工重写。

## superpowers：逐文件定位

全部 `HISTORICAL_SNAPSHOT`：

### plans
- `2026-08-23-s12-professional-comparison-dashboard-r2-diagnostic-tuning.md`
- `2026-08-23-s12-r1-pilot-acquisition-r2-feedback-closure.md`
- `2026-08-23-s12-rx7-topic-aware-r2.md`
- `2026-08-28-s12-stage-w-v26-checkpointed-recovery.md`
- `2026-08-28-s12-stage-w-v27-external-staging.md`
- `2026-08-30-s12-stage-y-source-layers.md`

### specs
- `2026-08-23-s12-rx7-topic-aware-r2-design.md`
- `2026-08-28-s12-stage-w-v26-resume-design.md`
- `2026-08-28-s12-stage-w-v27-staged-publication-design.md`
- `2026-08-30-s12-stage-y-source-layers-design.md`

新增 `docs/superpowers/README.md` 统一阻止它们覆盖 current authority。

## 删除决定

物理删除：`0`。

原因：当前“旧文件”大多是里程碑/设计/失败证据，删除会损害追溯。采用 navigation demotion + status classification，既纠正当前技术方向又保留历史。

## 后续维护规则

每次进入新 Stage 或产品方向改变：更新 current status、roadmap/backlog、long-term memory/MOC；历史 report 新增而不改写旧 snapshot；外部 source 先 registry/license 再 adoption。
