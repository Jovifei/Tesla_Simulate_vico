# Stage AI-7 Codex 接力文档

更新时间：2026-09-22

工作区：`E:\Tesla_speed`

实际 Git 仓库：`E:\Tesla_speed\prj`

隔离 worktree：`E:\Tesla_speed\worktrees\stage-ai7-continuous-event-evidence-20260921`

分支：`feature/stage-ai7-continuous-event-evidence-20260921`

## 1. 当前最终目标

完成 S12 Stage AI-7 的连续驾驶事件证据闭合：把固定调度时间与源 stem 实际观测 onset 分开记录，验证观测域、观测帧、能量、事件计数和 A/B/off-switch 身份，并在不改变音频 PCM 和既有受保护范围的前提下交付可审查的包、报告和分支。

## 2. 已完成

- 远端 ChatGPT 已在既有“音浪”项目的既有 C2C 聊天中完成 AI-7 规划；本地执行使用同一工作区连接器和同一聊天，没有创建新的远端项目。
- 根因已修复：连续流水线不再把 requested `18.0s` 冒充 observed onset；观测域固定为 `SOURCE_STEM_PRE_IR`。
- 连续收据升级为 `s12.stage_ai6.continuous_drive_pair.v2`，A、B、off-switch 共用并校验事件观测证据。
- `qualified_three_way` 增加旧连续文件 role hash 校验、canonical 十场景加载和 RX-7 历史 A provenance 校验。
- `render_continuous_pair`、`write_continuous_pair`、`qualified_three_way` 统一复用事件合同；合法 30 秒 PCM 缺失 onset/count/energy/源层绑定时，写包入口会在创建文件前拒绝。
- 新增 AI-7 红绿测试并更新 AI-6 continuous/three-way 测试。
- 工作流已加入 AI-7 观测事件回归门禁。
- 整改提交：`adaf72db254f28cc64616452d629c9a750db6616`。
- 新包 v3 已生成并验证，未覆盖旧 v1/v2：
  `E:\Tesla_speed\review_packages\s12-stage-ai7-continuous-event-evidence-20260921-v3`
- 包 manifest SHA：`44d9449c056768f454533041fd27a880b01a6f83df16057fe40f0526fab53833`
- 包 summary SHA：`ecb8154c84c3a63cb81c71914fdc39afc23e2b026d9d64cc4b1f7623dd963740`
- v3 的 `old_threeway_manifest_sha256`：`28ef0738097f7e28bb4d49136a47a17dac5b3f80bff229dfbbe2161f1bb8cb13`；该值与现场 AI-6 `ARTIFACTS.json` 实测一致。旧报告/交接中的 `...97e7e28...` 是历史笔误，旧包未改。
- RX-7 observed onset：`18.043s / frame 866064`；Aventador：`18.010s / frame 864480`。
- 验证：iteration 2 contract RED/GREEN `19 passed`，当前 focused `92 passed`；strict compile、Track-P、`git diff --check` 和 v3 `qualified.verify` 已通过。

## 3. 现在卡在哪里

本地 AI-7 证据合同整改、最终全量回归、v3 verifier/browser 复核和分支 push 已完成；PR/CI 元数据与远端最终复核仍待收口。当前仍是工程证据状态，不是产品放行状态：

- 远端独立审查正在等待 iteration 3 的完整执行记录；必须核对 `cd61c58`、v3 和包级负测。
- 分支已 push；`gh auth status` 未登录，因此 Draft PR/CI metadata 为 `NOT_VERIFIED/PENDING`，没有创建 PR。
- 最终 exact HEAD `cd61c58` 的完整 S12：`1334 passed, 3 skipped, 118 subtests passed`，退出码 `0`；定向 real-material `1 passed`、slow `2 passed`，full-suite skip 原因保持如实记录。
- Jovi 的命名人耳试听尚未完成；因此 `HUMAN_STATUS=NOT_EVALUATED`、`promotable=false` 保持不变。
- 六个其他车型仍没有合格 B 源，必须保持 `B_UNAVAILABLE`，不能为了凑齐车型而降级证据标准。

## 4. 关键文件和证据

代码与测试：

- `tools/sound_sim/s12/acoustic_identity_v015/stage_ah/remaining_vehicle_pipeline.py`
- `tools/sound_sim/s12/acoustic_identity_v015/stage_ah/continuous_drive.py`
- `tools/sound_sim/s12/acoustic_identity_v015/stage_ah/qualified_three_way.py`
- `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ai7_event_evidence.py`
- `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ai6_continuous_drive.py`
- `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ai_threeway.py`
- `.github/workflows/s12-stage-ai-measured-feedback.yml`

文档与包：

- `docs/08-reports/37-stage-ai7-continuous-event-evidence-20260921.md`
- `tasks/stage-ai7-codex-handoff-20260921.md`
- `tasks/todo.md`
- `E:\Tesla_speed\review_packages\s12-stage-ai7-continuous-event-evidence-20260921-v3`
- 固定对照包：`E:\Tesla_speed\review_packages\s12-stage-ai6-unified-audition-20260920-v2`

## 5. 下一步

1. 最终 v3 preflight 和真实浏览器检查已通过；完整 S12 已在 exact HEAD `cd61c58` 通过，slow/material 定向验收也已通过。
2. 提交本 worktree 的报告、交接文档、todo 和 workflow 改动；不修改主工作树。
3. 把 iteration 3 执行记录发送给既有远端聊天，请远端通过 MCP 独立复核；若返回下一轮 `PLAN`，只按该计划继续；若返回 `DONE`，保持产品试听门禁不变。
4. 分支已正常 push；若 GitHub 认证恢复，再创建唯一 Draft PR 并核对 exact-head CI，否则保持外部元数据阻塞。
5. 远端审查结束后，把 v3 包交给 Jovi 做 RX-7/Aventador 命名人耳试听；反馈前不做主线合并、参数推广或 Android 产品化。

## Iteration 3 最终收口附录

- 最终分支 HEAD：`f9c5681b567248bbaee78140a4b0dabdcad3b7f9`；源码/verifier：`cd61c58`；包源：`adaf72d`；main：`29b50961`。
- 最终 full S12：`1334 passed, 3 skipped, 118 subtests passed`；real-material `1 passed`；slow `2 passed`；core focused `39 passed`；真实包级 re-seal `qualified.verify()` 负测 `1 passed`。
- AI-6 inventory 215/215 无漂移；v3 preflight、浏览器和 8 路由检查通过；分支已 push。
- GitHub CLI 未认证，Draft PR/CI 为 `NOT_VERIFIED/PENDING`；远端 iteration 3 复核在一次重试后仍返回服务错误，未收到 `DONE/PLAN/BLOCKED`。
- 本地执行已停在 `HUMAN_STATUS=NOT_EVALUATED`、`promotable=false`，下一步需要远端复核恢复后再确认接手，不开启新的工程阶段。
