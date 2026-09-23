# S12 Stage AI-8 接力（2026-09-23）

## 1. 最终目标

沿用 S12 source-local 反馈链路，为 Hellcat、Ferrari 458、LFA、GT-R R35、C63 W204、Supra JZA80 继续扩展声音，并区分软件数值证据、受限 R3 相对诊断和 Jovi 人耳验收。

## 2. 已完成

- 分支 `feature/stage-ai8-six-vehicle-20260922`，AI-7 基线 `53a161d`；代码提交：`531e097`、`db35e1d`、`b9ab654`。`main` 未修改。
- 新增独立资格、六车 readiness、C63/Supra 单参数反馈适配、六车 baseline 预览与 verifier；修复了报告宣称字段泄漏、Supra 源 SHA 未绑定、旧/新事件接口错配和多车索引顺序问题。
- Ferrari 和 GT-R 各完成一次最多 25-trial 的 R3 相对诊断搜索；两者状态为 `RELATIVE_IMPROVEMENT_VALIDATED`，但均保持 `promotable=false`、`human_status=NOT_EVALUATED`。
- 六车预览全部 `DIAGNOSTIC_BASELINE`，每车 30 秒、48 kHz、stereo int16，数值门通过。预览 manifest SHA-256：`d53352b5a96f1ca5c741a7c9ecc1f54893bbf6e7f14fa183c6555ae342ba58d7`。
- 相关回归 `199 passed, 1 skipped`；预览专用回归 `25 passed`；Track-P 冻结 180 个文件、2 个符号未变。

## 3. 仍然阻塞

- Ferrari/GT-R 素材权利与同步 RPM 状态仍未核实；结果限本地 R3 相对诊断，不能升级为 OEM/车型相似度结论，也不能再分发。
- Hellcat/LFA 缺有效评审 split；C63/Supra 缺显式评审计划和权利/可比性结论，因此只生成 baseline 诊断，不进入 optimizer。
- 六车都等待 Jovi 具名人耳试听；当前没有 Human PASS、B-ready、Profile Freeze、OEM 标定或产品化批准。

## 4. 关键文件与产物

- 代码计划：[2026-09-22-six-vehicle-reference-loop.md](plans/2026-09-22-six-vehicle-reference-loop.md)
- Obsidian 记录：[Stage-AI8-Six-Vehicle-Reference-Loop.md](../docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Stage-AI8-Six-Vehicle-Reference-Loop.md)
- readiness：`E:\Tesla_speed\review_packages\s12-ai8-readiness-20260923-v2.json`，SHA-256 `2fe26b7789770f712147e23a98b63ce3a2130e96e0dbe54be2083b4efd626bc4`
- 六车试听：`E:\Tesla_speed\review_packages\s12-ai8-six-vehicle-preview-20260923-v2`
- Ferrari/GT-R 闭环：`E:\Tesla_speed\review_packages\s12-ai8-fourcar-reference-loop-20260923-v1`，ARTIFACTS SHA-256 `8db412ec9a7e5a78138a5f461c166fb2eaf5906d724d9375fadcd167f00a5dbd`
- 唯一搜索计划：`E:\Tesla_speed\review_packages\plans\stage-ai-fourcar-plan-20260916-v3.json`，SHA-256 `d032ffd682c5cf34ebd9cc5a66d4b419151d9f58a6fb3f1b257b73179eb34d90`

## 5. 下一步

1. Jovi 从六车 preview `index.html` 试听并提供具名反馈；如需，可对照 Ferrari/GT-R 闭环目录中的 baseline 与 tuned 十场景 WAV。
2. Hellcat/LFA/C63/Supra 先取得 SHA 绑定的评审窗口、train/validation split 和 rights/use 范围，再启动对应闭环。
3. 本文记录的初始预发布检查（2026-09-23）显示 PR #31 为 open/draft，AI-8 远端分支/PR 尚不存在；本地 `git push` 到 `github.com:443` 经现有 `127.0.0.1` 路径失败。此为带时间戳的状态快照，后续执行前应重新核对 GitHub live 状态；不改网络设置、不 merge main、不 force-push。
4. 本阶段没有使用远端 ChatGPT 网页；没有改动 VPN、代理、DNS 或网络进程。只有 Jovi 指示后才发送远端 ChatGPT 审查请求。

## 6. AI-8 预览验包复核与修复（2026-09-23）

- 已在指定的音浪聊天核验 `workspace_info=Tesla_speed` 并取得 PR #32 审查方案。远端连接器只读；本地 Codex 按 Jovi 授权执行，未把远端的方案/报告冒充为代码变更或测试结果。
- 根因：summary 的源码身份与字段未受完整语义校验；`RENDER_FAILED` 报告缺少 schema/车型/字段约束；车型行状态未完整枚举且 `audio_available` 使用隐式布尔转换。独立复核还发现 runtime commit 字段需要与其源码清单绑定。
- 本地修复提交：`a2634a8a22b11ad331922a82c62ae8d4da1a01be`，文件限于 `stage_ai8/diagnostic_preview.py` 与 `test_s12_stage_ai8_diagnostic_preview.py`。Verifier 要求 summary/车型行白名单、真实 JSON 布尔、受限状态集合、失败报告与车型/schema 绑定；源码清单必须匹配其记录的历史 Git 源码归档，不要求等于当前 HEAD。
- TDD：旧实现对 11 个重新封签的 summary/report 反例全部未拒绝；新增源码 commit 替换反例也曾被旧实现接受。修复后这些反例均被拒绝，合法渲染失败包和合法历史身份仍可验证。

### 本次新鲜验证

- 预览 verifier：`38 passed`；四个 AI-8 测试文件：`75 passed`；AI-5/6/7 与 Track-P 定向回归：`87 passed`。
- 完整 `tools/sound_sim/s12/acoustic_identity_v015/tests`：`1409 passed, 3 skipped, 118 subtests`；4 条既有 SciPy `WavFileWarning`（非数据 chunk）为非致命。
- 六车固定 preview：传入原 manifest SHA 后返回 `VERIFIED`，14 个文件；Ferrari/GT-R 固定 run：传入原 `ARTIFACTS.json` SHA 后返回 `verified`。
- Track-P 独立守卫：180 个冻结文件、2 个符号摘要匹配，冻结路径改动 0。未运行 render、reference-loop run、optimizer 或调音；未改写、重封或再分发任何音频/IR/参考材料。
- 本次验证的是软件结构、历史源码绑定和固定产物完整性，不证明来源授权、录音真实性、车型相似度、人耳接受、OEM 标定或产品化。

## 7. 当前下一步

1. 本地源码/测试提交 `a2634a8a22b11ad331922a82c62ae8d4da1a01be` 已发布到现有 PR #32，snapshot `b719b8f99c22ceae1e1e0a4713dd3cf5e0c63a97` 的 Git tree 与本地修复树 `95ae2e07ba5324c37ce5fe38d5df4ef0636fec1c` 一致。PR 保持 open/draft，AI-7 base `53a161d…` 未改变；后续交接/Obsidian 文档也在同一分支同步。
2. 实现后远端审查请求留在指定音浪聊天，但 ChatGPT 两次 `workspace_info` 返回账号连接 400，远端回复 `STATE: BLOCKED / REVIEW_STATUS: NOT_PERFORMED_WORKSPACE_UNVERIFIED`；没有读取 PR diff，不能声称已独立审查。Jovi 随后授权一次同域名恢复：`c2c tunnel login` 返回 `loggedIn=true`，但受控 doctor 启动仍因 `Named tunnel start timed out` 失败，日志记录 `cloudflared` 退出。**任何进一步隧道启动/网络进程重试都需 Jovi 新的明确授权**；不改 VPN、FlClash、Clash Verge、DNS 或系统代理。隧道恢复后，仍在同一聊天先核验 `workspace_info=Tesla_speed`，再续做 PR 审查，不建新聊天/项目、不合并 main。
3. 六车 preview 仍全为 `DIAGNOSTIC_BASELINE`；下一实质产品验收门是 Jovi 的具名人耳试听。Ferrari/GT-R 继续保持 R3 relative-only，四个 reference-blocked 车型不启动优化器。
4. 历史 runtime commit 必须在执行 verifier 的仓库对象库中可解析；若 checkout 缺少该历史 commit，验证会 fail-closed，而不会把身份不明的 source map 当作有效证据。
