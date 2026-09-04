# S12 Engine-Audio Ecosystem — MOC

## 当前首先阅读

- [[Project-Long-Term-Memory]] — **当前项目长期记忆真值**：最终目标、历史阶段、当前 blocker、App-first 产品路线、负面知识、执行顺序。
- [[Research-Sources-And-Adoption-History]] — 参考论文、开源项目、商业工作流、许可证和方法吸收历史。
- [[Decision-History-And-Negative-Knowledge]] — 关键决策、已证伪路线、指标陷阱、CI/治理踩坑和禁止重复事项。
- Android App 详细实施计划：`docs/04-planning/04-android-app-runtime-implementation-plan.md`。

证据权重：`S12_Handoff_Package_2026-09-03` 约 90%，旧聊天/此前总结约 10%；会变化的远端状态以现场 GitHub 为准。

当前产品方向：

```text
S12 声音真实性
→ Jovi Human Gate
→ Hellcat/Ferrari/RX-7 Engineering Profiles
→ speed + acceleration → VirtualEngineState
→ portable C++
→ Android App realtime sound
→ in-car validation
```

ESP32 当前状态：`DEFERRED_FUTURE_OPTION`，不是当前 blocker。

## 历史知识节点

- [[01-Stage-V-Independent-Audit]]
- [[02-Architecture-Comparison]]
- [[03-License-Matrix]]
- [[04-Source-To-S12-Traceability]]
- [[05-Stage-W-Logs]]
- [[Open-Source-Engine-Sim]]
- [[Open-Source-ENSIM4]]
- [[Open-Source-DasEtwas-Enginesound]]
- [[Papers-PTR-EONE-DDSP]]
- [[Commercial-Public-Workflow-References]]
- [[06-Bakeoff-And-Migration-V3]]
- [[Open-Source-PTR-Model]]
- [[Open-Source-VehicleNoiseSynthesizer]]
- [[Open-Source-FiveM-License-Boundary]]
- [[Open-Source-Granular-ESP32-Boundaries]]
- [[Open-Source-Ignis]]
- [[Open-Source-Markeasting-Engine-Audio]]
- [[07-Stage-X-Remote-Reconciliation]]
- [[08-Engineering-Selection-Contract]]
- [[09-Hellcat-R2-Engineering-Selection]]
- [[10-Ferrari-RX7-Diagnostic-Migration]]
- [[11-R1-Formal-Gate-Readiness]]
- [[12-Stage-X-Final-Status]]
- [[13-Workspace-Cleanup-20260830]]
- [[15-Stage-Y-Status]]
- [[16-Stage-Z-Status]]
- [[17-Stage-AA-Status]]
- [[AA-C3-Gain-Provenance]]
- [[Broad-Pre-PTR-vs-Source-Causal-Gain]]
- [[Hellcat-Human-V3-Feedback]]

Repository research registry：

`docs/research/engine-audio-ecosystem/`

关键 runtime evidence：

```text
tasks/reports/runtime/s12-stage-aa/
tasks/reports/runtime/s12-stage-ab/
tasks/reports/runtime/s12-stage-ac/
```

当前长期边界：

```text
R1 = MISSING
HUMAN_PASS = false
OEM_CALIBRATION = NOT_AUTHORIZED
PROFILE_FREEZE = NOT_AUTHORIZED
ESP32 = DEFERRED_FUTURE_OPTION
```

如果历史节点与 `Project-Long-Term-Memory.md` 的当前产品方向冲突，以长期记忆文档 + 当前用户明确决策为准。