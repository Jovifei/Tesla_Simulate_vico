# S12 Stage AB Interim Report — AB0/AB1/AB2

状态：**WAITING_FOR_JOVI_AUDITION**（2026-09-02）。本报告第一部分先回答合同第 33 节的 15 个问题，之后才是 tests/CI/commit/receipts。

## Part 1 — 合同 15 问

**1. AA-C3 到底是否比 Stage-Z 更好听？**
**未知，未经人耳确认。** 客观指标上 AA-C3 相比 Stage-Z 的 RMS / centroid / dynamic range / roughness / sharpness 更接近 Parent 诊断区间，但指标接近不等于更真实（TEST PASS != SOUND PASS）。本阶段保持 DIAGNOSTIC_ONLY，无任何人耳结论。

**2. Jovi 是否确认？**
否。`jovi_v3_feedback.json` 不存在，AB2 门禁确认 WAITING_FOR_JOVI_AUDITION，一切声学参数修改已停止。

**3. AA-C3 改善有多少来自 broad pre-PTR scale？**
11 场景均值、2³ 全因子精确 Shapley 归因：**RMS +15.54 dB 总修复中 broad scale 仅占 33.5%（+5.20 dB）；event-body 120–400 Hz 注入占 66%（+10.25 dB）；carrier suppression ≈0.6%**。centroid 修正中 broad scale 为反向作用（+573 Hz，抵消 event-body 的 −2881 Hz 过度变暗）。注意：这与合同预设的“改善主要来自 broad scale”假设相反。

**4. 去掉 broad scale 后，event-body / blower correction 自己是否成立？**
**部分成立。** P4（event+carrier、无 broad scale）RMS 达 −47.2 dB（P5 为 −46.3，Stage-Z 为 −61.8），RMS 修复成立；但 centroid 塌到 591 Hz、sharpness 0.022 —— **频谱（亮度/车身平衡）修正不成立**，两因子强交互。blower suppression 单独效应微弱（carrier Shapley ≈0.09 dB RMS / −51 Hz centroid）。

**5. 当前主要真实性缺陷是什么？**
(a) complete-cycle envelope range 仅 10.5 dB（Parent 19.6 dB）——整体包络层次仍不足；(b) afterfire 相对 body 峰值 ~20 dB（Parent ~3 dB）——爆竹化风险；(c) blower 身份未证实（见 8）；(d) 全部未经人耳验证。

**6. Dynamic 是否仍过平？**
idle→WOT 分层**不过平**：P5 = +12.77 dB（Parent +9.37，Stage-Z +6.17），broad scale 也没有压平它（P1 = +9.60）。真正过平的是**整周期包络范围**（10.5 vs 19.6 dB）。tip-in attack 23.5 dB 高于 Parent 14.35 dB（过冲而非不足）。

**7. LF body 是否 boom/overshoot？**
20–90 Hz band ratio：P5 = 0.129（Parent 0.216、Stage-Z 0.111），所有变体 boom_risk = OK，persistent ratio 未超阈值。**当前 1 s 窗口诊断未发现 boom 过冲**；Stage-AA 报告的 LF body share overshoot 在 band-ratio 意义下未复现，但需 Jovi low_frequency_pressure 打分最终裁定。

**8. blower 是否仍像电子固定哨声？**
**无法判定，标记 OPEN。** 载波峰恰在 1200–1234 Hz（即抑制滤波器拐角），prominence 20–24 dB，sideband/carrier ~0.49，broadband 主导（>500×），RPM tracking 误差怠速 0.97 / 全负荷 0.02。sharpness 下降不作为 blower 更真实的证据；等 Jovi blower_identity 打分。

**9. afterfire 是否自然？**
未验证。数值红旗：event-body 注入使 afterfire 峰值相对 body 达 ~20 dB（Parent ~3 dB）。若 Jovi 报“爆竹/太规律/太响”，按合同映射到 event amplitude distribution / inter-event interval / path damping / cluster size，禁单旋钮粗调。

**10. Round2 是否真正 source-causal？**
Round 2 尚未开始（被人耳门禁阻塞）。已预置 source-causal 基础设施：P6 = combustion 差分局部 scaling（精确因果差分法 `pre_ptr(full) − pre_ptr(event_energy=0)`，无叠加性假设），其动态指标最接近 Parent（idle→WOT +10.64 dB、afterfire 3.16 dB）。`route_is_stem_local` + `assert_no_broad_mix_gain_in_round2_raw_candidate` 硬门禁已测试。

**11. 有没有 whole-mix/master gain cheat？**
**AA-C3 本身存在 broad mix scaling**（`base_pre_ptr * (2+2*load)`，candidates.py:94-96，整个 pre_ptr 全混合），已如实分类为 STATE_DEPENDENT_BROAD_PRE_PTR_SCALING——它通过了旧的 `global_gain_changed` gate，说明旧 gate 不足。没有常量 master/monitor/PCM gain。Round 2 raw candidate 的 whole-mix gain 已被新测试禁止。

**12. Track-P / PTR / Radiation 是否 untouched？**
是。`git diff --name-only d156f3d7 -- <frozen paths>` 为空（测试 `test_frozen_paths_untouched_since_stage_aa_merge`）；candidate gates 的 ptr_radiation_track_p_unchanged = true；本阶段零改动。

**13. 是否有 R1？**
**MISSING**（R1=0，合法同步参考不存在）。OEM_MATCH / OEM_CALIBRATED 均未声明。

**14. 是否允许 Profile Freeze？**
**NOT_AUTHORIZED**。即使人耳通过，也只能到 HUMAN_ACCEPTED / R2_DIAGNOSTIC_ACCEPTED / ENGINEERING_CANDIDATE，不得越级。

**15. 下一步到底是迁移车型还是 MODEL_REDESIGN_REQUIRED？**
**当前都不触发**——先等 Jovi V3 反馈：认可 AA-C3 → HUMAN_ACCEPTED_R2_DIAGNOSTIC_CANDIDATE 后停止；否定 → 唯一一轮 source-causal Round 2（≤3 候选）；Round 2 再失败 → MODEL_REDESIGN_REQUIRED + PARAMETER_TUNING_STOPPED。Ferrari/RX-7/八车传播继续冻结。

## Part 2 — 工程证据

### AB0 — Post-merge truth
- `git ls-remote origin main` = `d156f3d7`（= PR #4 merge，**未前进**）；PR #4 state=merged (GitHub API)；CI run 33510767391 = success (head 8bb9df7)；merge commit 无独立 run（如实记录）。
- Receipt：`tasks/reports/runtime/s12-stage-ab/post_merge_truth/stage_aa_post_merge_receipt.json`
- `execution_state.json`：保留历史 `base_main_head`/`main_head`=209378b，新增 `post_merge_truth` 块（post_merge_main_head / merge_commit / merge_status / final_ci_status）；报告 stale truth（"final branch CI pending"）已更新；历史 receipt 未改写。
- Stage-AB 分支/worktree：`s12-stage-ab-hellcat-human-source-causal-closure` @ d156f3d7（扁平分支名：沙箱对带斜杠分支 ref 不稳定，已记录）。

### AB1 — Provenance audit（全部 DIAGNOSTIC_ONLY）
- 分类：`STATE_DEPENDENT_BROAD_PRE_PTR_SCALING`（file:line 证据入档）。
- Taxonomy：`provenance/energy_gain_taxonomy.json`（11 类 + hard gate 扩展字段 gain_scope / affected_stems / location_in_chain / state_dependency / is_broad_mix_scaling / physical_interpretability）。
- Provenance set：P0–P8 × 11 场景（共享源实现 + 各因子独立开关）；P5 与 AA-C3 raw PCM **bit-exact**。
- 归因：`provenance/aa_c3_metric_attribution.json`（精确 Shapley，封闭性 = 总效应，测试强制）。
- Dynamic preservation：`provenance/dynamic_preservation_audit.json`（raw PCM，零归一化；Parent 用 `render_parent_scene` 原始渲染）。
- LF body guard：`provenance/lf_body_guard.json`（6 个 LF band + boom_risk）。
- Blower provenance：`provenance/blower_provenance.json`（carrier prominence / sideband ratio / broadband ratio / rpm·load·boost tracking error）。
- 审计报告：`provenance/AA_C3_Provenance_Audit.md`。
- P6 source-causal prototype：combustion 差分 stem 隔离（非目标 stem bit 级不动），DC/finite/click/clipping 验证，标记为 engineering diagnostic，非试听 winner。

### AB2 — Human feedback gate
- 无 `jovi_v3_feedback.json` → 生成 `human_feedback/jovi_v3_feedback.schema.json`（合同 15.1 全部字段 + free-text 标签 + 绑定协议）。
- `human_feedback/waiting_status.json`：WAITING_FOR_JOVI_AUDITION，`acoustic_parameter_changes_since_v3 = 0`。
- 揭盲纪律就位：answers_manifest 未被打开用于候选选择；无 binding receipt；`test_blind_map_not_revealed_and_feedback_not_yet_submitted` 强制。
- v1/v2/v3 包零改动（manifest SHA 校验测试）。

### Tests / 卫生
- 新增 `tests/test_s12_stage_ab_provenance.py`：**15 passed**（确定性、SHA 区分、P5==AA-C3 bit-exact、P6 stem 隔离、broad-gain 禁令、Shapley 封闭性、JSON finite、frozen paths、v1/v2/v3 不可变、blind 未揭盲等）。
- 既有 Stage-AA focused 回归（candidates / candidate_audit / package_v3）：**5 passed**。
- `compileall` OK；`git diff --check` OK。
- 生产 renderer / 默认声音 / 冻结边界：零改动 → 按 §30 只跑 focused suite。

### Obsidian（定向镜像）
新增 7 篇：Stage-AA-Post-Merge-Truth、AA-C3-Gain-Provenance、Broad-Pre-PTR-vs-Source-Causal-Gain、Hellcat-Human-V3-Feedback、Stage-AB-Round2-ADR、Stage-AB-Negative-Knowledge、Stage-AB-Final-Status。未触碰无关 Arduino 笔记。

### 状态枚举
`STAGE_AA_POST_MERGE_TRUTH_PASS` + `AA_C3_PROVENANCE_AUDITED` + `WAITING_FOR_JOVI_AUDITION`
（R1_MISSING / PROFILE_FREEZE_NOT_AUTHORIZED / OEM_MATCH_NOT_CLAIMED）
