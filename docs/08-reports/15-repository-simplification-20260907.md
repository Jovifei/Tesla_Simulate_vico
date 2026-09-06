# S12 仓库简化与路线纠偏报告（2026-09-07）

状态：`CURRENT_STATUS / REPOSITORY_SIMPLIFICATION / DIAGNOSTIC_ONLY`

## 1. 目标与结论

本轮以最新 `origin/main` 为基线，只清理没有当前代码/测试调用、且其结论已经由 `docs/08-reports` 或 `docs/knowledge` 承接的根目录历史报告和过程审计产物。当前 Python S12/Stage-AF 声音实现、原 A/B 工作台、Reference/IR receipt、静态测试、Track-P 守卫和长期知识全部保留。删除通过 Git 提交完成，历史提交仍可恢复，不使用 reset 或 force-push。

当前技术 authority 明确为：

```text
Python S12 / EngineAcoustics / Stage AF
→ 原 build_unified_dashboards.py + HTML template
→ 并发版 review_packages/serve_dashboards.py
→ Jovi 人耳试听
```

Simulink 是 diagnostic/teaching mirror；ESP32 是 deferred future；旧 v0.9/v0.8 过程报告不再作为 Agent 默认入口。

## 2. 已删除的无关历史/过程文件

### 根目录重复报告

删除 9 份 2026-07 的根目录报告：

- `S12_Engine_Sound_Review_v03.md`
- `S12_engine_sound_review.md`
- `S12_Sound_Product_Overnight_Review.md`
- `S12_Simulink_Playground_v09_Offline_Audit.md`
- `S12_Simulink_Sound_Playground_v09.md`
- `S12_Simulink_Sound_Playground_v09_Offline_Repair_Report.md`
- `S12_Simulink_Sound_Playground_v09_Offline_Repair_v3_Report.md`
- `S12_Simulink_Sound_Playground_v09_Offline_Repair_v4_Report.md`
- `S12_Simulink_Sound_Playground_v09_v4_Untracked_Scope_Audit.md`

这些文件是根目录重复的历史审计/修复叙述，内容并非当前 S12 authority；可追溯结论保留在 `docs/08-reports/`、`docs/knowledge/` 和 Git 历史中。

### `.superpowers/sdd` 过程产物

删除 `.superpowers/sdd/` 下 26 个旧任务脚本、临时 receipt、验证日志和阶段报告。它们无当前源码/测试调用，且 `.superpowers` 本身是被 `.gitignore` 标记的 AI/过程目录；可复用的 Stage-W/Stage-AF 结论已转存到正式 docs/knowledge。

### playground 审计快照

删除 `tools/sound_sim/s12/playground/` 下无当前调用的历史 `git_status.txt`、`git_diff_check.txt`、`git_diff_stat.txt`、`untracked_scope_audit.md`、`fourth_audit_report_availability.md`、旧 external audit reference、旧 static verification 和未使用 manifest。首次候选清单的 57 个文件中，有 12 个 manifest 被仓库静态合同读取，已恢复并保留；实际删除 45 个。保留仍被测试读取的全部 17 个 manifest，以及所有 playground 源码和测试。

## 3. 路线纠偏

- `docs/README_STAGE_AF.md` 和 `docs/05-execution/04-stage-af-local-ai-handoff.md` 不再把旧分支名当作当前入口；新的 Agent 必须从最新 `origin/main` 建立独立 worktree。
- `tools/sound_sim/s12/README.md` 明确 Simulink models 是验证参考，不是当前最终声音 renderer；Python S12/Stage AF 是 authoring/listening authority。
- `tools/sound_sim/README.md` 标记为 legacy v0 prototype，避免后续 Agent 把早期单振荡器路线当作当前声学实现。
- `Open-Source-Markeasting-Engine-Audio.md`、`Open-Source-Ignis.md` 和 Stage-W 知识不再链接不存在的 `.superpowers/sdd` intake 文件，统一指向 tracked research registry/知识记录。
- 2026-09-05/09-06 旧 status/reconciliation report 标注为 historical/superseded；当前入口是本报告和 Stage-AF 数值/刷新报告。

## 4. 保留边界

以下不删除：当前 `tools/sound_sim/s12/acoustic_identity_v015/` 源码和 tests、Stage-AF/AD/Track-P 守卫、原 review server、Reference/IR provenance、`android_vehicle_sound_demo`（未来 Android 目标的最小源）、所有 `docs/knowledge/obsidian` durable notes、`tasks` 作为历史审计索引，以及被静态测试实际读取的 playground manifests。用户工具目录、忽略目录和生成试听包也不在本次 Git 删除范围。

## 5. 验证要求与恢复

清理后必须执行：

```powershell
rg -n "S12_Engine_Sound_Review_v03|S12_Sound_Product_Overnight_Review|\.superpowers/sdd/task-|stage-y-research-intake\.json" docs README.md tools scripts .github --glob '!docs/08-reports/15-repository-simplification-20260907.md'
python -m pytest -q tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ad_closed_loop.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_af_physical_closed_loop.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_af_numerical_fixes.py
python -m compileall -q tools/sound_sim/s12/acoustic_identity_v015
python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py
git diff --check
```

如果未来需要恢复某一历史报告，只能从清理提交的父提交或 Git 对象中按文件恢复，不能把整套旧路线重新设为 current authority。清理本身不改变声音 PCM，不升级任何 Human/R1/OEM 状态。

## 6. 清理后实测结果

- 受影响的 Stage-AD/AF、package self-contained 与 playground 静态合同：`122 passed, 1 warning`；
- 清理后的完整 S12 Python 回归：`1460 passed, 2 skipped, 2 warnings, 232 subtests passed`；
- 失败过的两项 manifest 合同已恢复后重新通过，证明“无业务调用”不等于“可删除”；
- warning 为原始 IR WAV 的既有非 data chunk 提示；
- Track-P、compileall、全仓 stale-reference scan 和 `git diff --check` 均已通过。
