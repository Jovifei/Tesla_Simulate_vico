# S12 Stage K 四车声学修复与状态响度校准报告

## 结论

本轮完成四车 Track-S 候选声源修复、负载状态响度平衡、最终 PCM 参考距离测量和具名试听包生成。结果不是自动或人耳通过：

```text
PARTIAL / AUTOMATED_GATE_FAIL
WAITING_FOR_JOVI_STAGE_K_NAMED_REVIEW
```

尚未收到新的正式评分 CSV；未读取任何 sealed key，未生成 confusion matrix，未进入 Profile Freeze、Approved Profile、Simulink、Runtime 或 Android。

所有输出均为：`synthetic / uncalibrated / vehicle-inspired / not OEM reproduction`。

## 起点、分支与边界

- Stage J 基线：`b78b6c3031269eae1a0b917ce7bbaaed2af81c76`。
- Stage K 当前提交：`4261bbfe34b11980fcb15a0a9b01bd6d5f75c9e6`。
- 分支：`agent/s12-stage-k-four-vehicle-perceptual-repair`。
- 工作树：`E:\Tesla_speed\worktrees\s12-stage-k-four-vehicle-perceptual-repair`。
- Stage J 工作树起点核验：clean，`origin/main...HEAD = 0 42`。
- 未 push、未 merge、未 rebase、未修改 `main`。

冻结的 FVM、PTR core、Radiation Boundary、Runtime、Android、MATLAB、Simulink、Track-P guard、Stage C 公共 LF Body/Rumble/Pre-PTR EQ、`manage_bundle_loudness` 均未修改。

## 最终管线

```text
Independent Source
→ Source Operating Trim(load/throttle)
→ Idle Dynamics
→ Deterministic Afterfire
→ Low-Frequency Body
→ Exhaust Rumble
→ Vehicle Shift/Transient
→ Common Pre-PTR EQ
→ Frozen PTR
→ Edge Fade
→ One Fixed Whole-Cycle Gain
→ PCM24
```

Operating trim 只读取 `load`/`throttle`：低负载约 `+1.5 dB`、高负载约 `-1.5 dB`，使用平滑状态包络；它不读取 RPM、speed、PCM、RMS、LUFS 或 peak，也不使用 AGC、compressor、limiter 或 per-section normalization。试听包的 `1.25x (+1.9382 dB)` 只是共同的、受 peak ceiling 限制的 review copy 增益，不改变正式产品响度策略。

## 四车候选与反馈映射

### Hellcat

Jovi 明确反馈 A/B/C 都“不像地狱猫”，但偏好 C 的柔和机械方向；本轮以 `Hellcat_candidate_v6_C_SofterMechanical` 作为未合格诊断 parent，生成 `hellcat_candidate_v7`。重建了 2.36:1 轴相位、11.8/23.6 合成阶次、直接 sideband/main 比、真实 10–90/90–10 attack/release、进气/壳体传递和 boost-history bypass。HEMI 低频主体保持独立，未使用固定 tone、白噪声或全局 gain。

### Mercedes C63 W204

保留 Jovi 认可的加速低频轰鸣；把旧 `bark_resonance_scale` 从“改变阶次位置却被当成响度”改为显式 primary order、upper partial、decay、mechanical upper tilt 和 high-RPM compression，降低事件驱动高频 roughness，未重写低频事件时序。

### Nissan GT-R R35

保留原有音色方向，修复顺序涡轮误建模和 `turbo_whistle_mix` 绝对值/比例混用。v3 使用两个并行 shaft state、轻微失谐 beating、shaft-phase BPF、V6 三事件/转和 boost-history BOV；未把转子/叶片未知数写成 OEM 实测。

### Lexus LFA

保留 V10 5/10/15 阶、intake、metallic 和主体声源，仅替换通用换挡深切与固定 70 Hz recovery boom，加入 ASG torque cut、排气 re-engagement、intake reopen、连续 lift decay 和 overrun。加速响度平衡由 load/throttle operating trim 处理，不以 RPM 直接放大整体声音。

## Jovi 输入与视频证据

Jovi 输入已固化到 `stage_k_jovi_input_feedback.json`：Hellcat 目标为可识别的 twin-screw whine + HEMI body；C63 保留低频、降低错误高频；GT-R 保留音色方向、补真实涡轮时序；LFA 保留身份、修复换挡/减速/响度跨度。

两个 Douyin 页面已登记，但本轮没有合法、可审计的原始音轨：

- `https://www.douyin.com/video/7442878447719943460`
- `https://www.douyin.com/video/7512312931426585890`

因此音频状态为 `NOT_AVAILABLE`；页面只属于 `R2/social-media-compressed`、`microphone/AGC dependent` 的定性边界，不能用于绝对 LUFS/RMS 或 OEM 测量。未下载新参考音频。

## 最终 PCM reference-distance

比较域是最终 PCM，窗口为 idle `0–8 s`、acceleration `8–26 s`、afterfire/lift `36–46 s`，四频带固定为 `20–250 Hz / 250–1000 Hz / 1–4 kHz / 4–12 kHz`。公式保持：

```text
D = sqrt(0.25 × Σ(actual_share - target_share)^2)
improvement = (D_parent - D_candidate) / max(D_parent, 1e-12)
```

| 车型 | idle | acceleration | afterfire/lift | 平均改善 | 自动门 |
|---|---:|---:|---:|---:|---|
| Hellcat | +19.2024% | −6.2002% | −0.3964% | +4.2019% | FAIL |
| C63 W204 | −0.5360% | −167.1418% | −459.8779% | −209.1852% | FAIL |
| GT-R R35 | +4.4783% | −199.2142% | +0.7722% | −64.6546% | FAIL |
| LFA | +0.0313% | +54.3453% | +1.3086% | +18.5617% | FAIL |

四车均未达到平均改善 `>=30%`；未降低阈值、未修改公式。参考音频不比较 RMS/LUFS。该结果只允许诊断，不允许 Profile Freeze。

## 具名试听交付

包目录：

`E:\Tesla_speed\review_packages\s12-stage-k-four-vehicle-perceptual-repair-v1`

包 ID：`S12_Stage_K_Named_Review_v1`。

- 四车各有 Baseline/Stage-K Candidate 60 s、Low Load、High Load、Shift、Lift/Deceleration 和三个工程诊断 stem。
- 60 s 时间线：idle → acceleration + 3 shifts → full pull → lift/afterfire/bypass → coast → idle return。
- WAV：48 kHz、stereo、PCM24、finite、无 clipping；formal 文件 2,880,001 帧（端点含 1 帧）。
- `SHA256SUMS.txt`：51 项，0 mismatch。
- Listener ZIP SHA-256：`d81bc9e77276bf6066c73bf3444239800067f1a1545f43460061c37bd88fdeef`。
- `sealed_key_read=false`；具名反馈模板已预填 file_id/vehicle_id，但没有虚构评分。
- 旧中断目录已可恢复移动到 `E:\Tesla_speed\review_packages\_incomplete_stage_k_four_vehicle_perceptual_repair_v1_previous`，未删除。

逐文件 raw/final LUFS、peak、requested/actual gain、headroom 和 PCM health 已写入包 manifest。近乎静音的诊断 stem 的 LUFS 可为 `null`，这是测量不可用，不是填零或伪造。

## 验证证据

- Stage K focused：`84 passed / 18.10 s`。
- Stage J C63/GTR/LFA：`8 / 11 / 9 passed`。
- Stage C realism：测试执行无失败断言；一次性 shell 输出在末端被截断，因此未把截断输出单独宣称为完整 PASS。
- Identity：按类/测试隔离执行 `58 passed / 78 subtests`；一次性全文件 Windows 进程在末端中止，报告保留该事实，不把它冒充单次 PASS。
- Track-P pytest：`21 passed`。
- Track-P guard：`180 frozen files / 2 symbols unchanged`。
- `git diff --check`：PASS。

详细 JSON 见同目录的 `stage_k_test_evidence.json`、`stage_k_parameter_reachability.json`、`stage_k_perceptual_metrics.json`、`stage_k_reference_distance.json`、`stage_k_loudness_state_balance.json` 和 `stage_k_artifact_manifest.json`。

## Obsidian handoff

已更新项目概览、总体计划、当前进度、工作流、技术事实、Stage I/Stage J 历史页、Hellcat/C63/GT-R/LFA 卡片、`tesla/index.md`，并新增 `21-S12-Stage-K-四车声学修复与状态响度校准.md`。YAML frontmatter `13/13` 通过，检查到 `41` 个内部链接、`0` 个断链。更新后的 SHA 记录在 `stage_k_obsidian_sha_receipt.json`；由于 Stage K 写入前未建立字节级 pre-image，receipt 将 `pre_sha256_status` 明确记录为 `NOT_CAPTURED_BEFORE_STAGE_K_WRITE`，没有伪造旧 SHA。

## 下一步与停止条件

下一步只接受 Jovi 的具名 `Jovi_Stage_K_Named_Feedback.csv`。收到后最多三轮，只修改明确失败车型对应的 source/transient/operating-trim 层，其他三车最终 PCM SHA 必须保持不变。反馈前不得生成匿名盲听、解封评分或冻结 Profile。

当前停止状态严格为：

```text
PARTIAL / AUTOMATED_GATE_FAIL
WAITING_FOR_JOVI_STAGE_K_NAMED_REVIEW
```
