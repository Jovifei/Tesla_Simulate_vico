# Documentation Guide

更新：2026-09-05

## 1. Authority hierarchy

发生冲突时按以下优先级处理：

1. 用户当前明确决策；
2. 当前 GitHub remote truth（代码、PR、CI、machine state）；
3. `docs/00-reference/01-authority-and-evidence-precedence.md`；
4. 当前 status / architecture / requirements / roadmap；
5. canonical long-term memory；
6. 历史 report/spec/plan；
7. 旧聊天摘要；
8. 外部项目/文章。

历史信息证据权重继续遵循用户指定规则：`S12_Handoff_Package_2026-09-03` ≈90%，旧聊天/此前助手总结 ≈10%；但动态状态永远现场复核。

## 2. Document classes

- `ACTIVE_AUTHORITY`：当前应该遵循的技术/产品规则。
- `CURRENT_STATUS`：某个明确时间点的远端状态。
- `EXECUTION_RUNBOOK`：可直接执行的步骤。
- `RESEARCH_EVIDENCE`：外部来源、license、method adoption。
- `HISTORICAL_SNAPSHOT`：保留历史事实，不能覆盖 current authority。
- `SUPERSEDED`：已被更高版本替代，仅用于追溯。
- `DEFERRED_FUTURE`：明确不在当前路线。

## 3. Current direction

```text
Stage AD acoustic loop
→ Jovi Human feedback
→ Hellcat Engineering Profile
→ Ferrari / RX-7
→ AudioParameterPackage + Golden Evidence
→ portable C++
→ Android App
```

App minimum input = `speed + acceleration`；ESP32 = `DEFERRED_FUTURE_OPTION`。

## 4. Evidence classes

- `Implemented`：代码存在。
- `Verified`：fresh test/CI evidence。
- `Acoustically improved`：reference metric 支持改善，但还不是人耳通过。
- `Human accepted`：Jovi 明确通过。
- `R1 qualified`：合法、同步、可追溯真实参考通过。
- `Blocked`：需要外部输入、人耳或环境。
- `Deferred`：有意不做。

禁止证据升级：

```text
CI green != Human PASS
R3 public clip != R1
Human PASS != OEM calibration
Simulink file exists != model verified
```

## 5. Historical files

旧 Stage report、Superpowers plan/spec、旧 firmware roadmap 不删除，因为它们包含决策/故障/验收历史。它们必须通过目录 guide/MOC 被明确标为 historical/deferred，不能成为 Agent 默认执行入口。

## 6. Update rule

任何改变产品方向、Reference policy、声音 authority、profile promotion、App runtime contract 的提交，都必须同时检查：

- `docs/README.md`
- current status report
- architecture
- requirements
- master roadmap/backlog
- long-term memory/MOC
- relevant execution runbook

逐文件审计账本见 `DOCUMENTATION_AUDIT_2026-09-05.md`。
