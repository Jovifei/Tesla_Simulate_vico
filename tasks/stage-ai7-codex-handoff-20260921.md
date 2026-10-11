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

本地 AI-7 证据合同整改、最终全量回归、v3 verifier/browser 复核、PR 创建和 iteration 4 证据收口已完成；当前仍是工程证据状态，不是产品放行状态：

- 远端 iteration 3 已确认没有新的声音实现缺陷，要求 iteration 4 补齐 PR 身份、完整差异、可读测试输出、v3 只读复核和最终交接。
- PR #31 已通过 GitHub API 独立核对：`open`、`draft=true`、base `main@29b50961`、head `feature/stage-ai7-continuous-event-evidence-20260921@3956c08`、`mergeable=true`、`mergeable_state=unstable`。
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

1. iteration 4 已重新发布可读证据：C2C output ID `7–16`，并保存完整差异、PR API、refs、v3 只读验证和路由检查。
2. 文档收口后在同一分支正常提交并 push，更新同一个 Draft PR #31；不修改主工作树、不 merge、不 force-push。
3. 最终 pushed HEAD 以 iteration 4 `EXECUTED` 和 PR head 最后查询为准；文档不追逐自身 SHA。
4. 远端确认 AI-7 工程阶段闭合后，把同一 v3 包交给 Jovi 做 RX-7/Aventador 命名人耳试听；反馈前不做主线合并、参数推广或 Android 产品化。

## Iteration 3 最终收口附录

- 最终分支 HEAD：`f9c5681b567248bbaee78140a4b0dabdcad3b7f9`；源码/verifier：`cd61c58`；包源：`adaf72d`；main：`29b50961`。
- 最终 full S12：`1334 passed, 3 skipped, 118 subtests passed`；real-material `1 passed`；slow `2 passed`；core focused `39 passed`；真实包级 re-seal `qualified.verify()` 负测 `1 passed`。
- AI-6 inventory 215/215 无漂移；v3 preflight、浏览器和 8 路由检查通过；分支已 push。
- iteration 3 远端复核结论为 `EVIDENCE_CLOSURE_REQUIRED`，`SOURCE_TEST_CHANGES_REQUESTED=NONE`；没有要求重新调音、重开模型或修改源码。
- iteration 4 收据：`E:\Tesla_speed\review_packages\s12-stage-ai7-pr31-review-receipt-20260922-v1`；其中包含 PR API 200 响应、完整 patch、分段差异、C2C 可读输出和 v3/路由/PCM 只读验证。

## Iteration 4 最终证据收口

- 验证起点：分支 `feature/stage-ai7-continuous-event-evidence-20260921`，HEAD `3956c08be496f7d950ec3cf33fd16ab9fce9dc9f`，main `29b50961d9628f835e7172b797380ccb36a7f38d`。
- C2C output：`7` full S12；`8` 包级负测；`9` focused；`10` real-material；`11` slow；`12` compile；`13` Track-P；`14` diff-check；`15` v3 preflight；`16` HTTP/embedded 路由。
- 验证结果：full S12 `1334 passed, 3 skipped, 118 subtests passed`（tested head `cd61c58`）；负测 `1 passed`；focused `39 passed`；real-material `1 passed`；slow `2 passed`；v3 `qualified ABC preflight PASS`；9 路由 HTTP 200。
- 固定 v3 manifest/summary SHA：`44d9449c056768f454533041fd27a880b01a6f83df16057fe40f0526fab53833` / `ecb8154c84c3a63cb81c71914fdc39afc23e2b026d9d64cc4b1f7623dd963740`；旧 AI-6 包未改，四项 A/B decoded PCM 对照一致。
- 当前阻塞只剩产品门：`HUMAN_STATUS=NOT_EVALUATED`、`promotable=false`；六车型 B 和连续 C 的不可用边界保持不变。

### NEXT_CODEX_PROMPT

接收 `c2c_7d21 / iteration 4` 的 AI-7 证据收口。先核对最终交接中的 PR #31、最终 pushed HEAD、C2C output `7–16`、收据目录和 v3 SHA；不要 checkout/merge main，不重新搜参，不修改源码、测试、音频或 v3。确认 AI-7 工程阶段闭合后，停止工程扩展，等待 Jovi 对同一 v3 的 RX-7/Aventador 连续 A/B 具名试听；若试听反馈明确不接受，再另行授权新的窄范围技术阶段。
