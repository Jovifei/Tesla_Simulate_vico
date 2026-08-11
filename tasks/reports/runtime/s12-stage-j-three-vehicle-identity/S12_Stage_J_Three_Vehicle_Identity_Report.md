# S12 Stage J 三车型独立声学身份与试听响度报告

## 状态

`PARTIAL / AUTOMATED_GATE_FAIL` 语义上同时等待 Jovi 的具名试听：`WAITING_FOR_JOVI_STAGE_J_NAMED_REVIEW`。

本阶段没有生成虚构答卷、confusion matrix 或 Human PASS。输出是 C/synthetic、uncalibrated、not OEM reproduction。

## 起点与边界

- Worktree：`E:\Tesla_speed\worktrees\s12-stage-j-three-vehicle-identity`
- Branch：`agent/s12-stage-j-three-vehicle-identity`
- Base：`d8b8c24530eafc354d420c95e1ff071034e51707`
- 保护：FVM、PTR core、Radiation Boundary、Runtime、Android/ESP32、MATLAB/Simulink、Stage C 公共 EQ/LF/Rumble、Track-P guard、正式 `manage_bundle_loudness` 均未修改。
- 渲染顺序：独立声源 → idle → deterministic afterfire → LF body → rumble → shift → Pre-PTR EQ → frozen PTR → fixed whole-cycle gain → PCM24。

## 三套独立声源

### C63 W204

`mercedes_na_v8_source_v2.py` 使用 cross-plane bank event pulses、移动阶次 bark、机械相位纹理和收油尾部。逐参数扰动均改变目标 stem；没有固定中心音或涡轮声。

### GT-R R35

`nissan_twin_turbo_v6_source_v2.py` 使用 even-fire V6 event train、primary/secondary spool、boost attack/release、turbo whistle、wastegate/BOV。所有涡轮声源来自状态历史，不是固定 tone。

### Lexus LFA

`lexus_high_rev_v10_source_v2.py` 使用 72° V10 事件列和 5/10/15 RPM-tracked order family、事件激励进气与 metallic texture；明确禁止固定中心 tone、随机白噪声和普通活塞 firing order。

## 参考数据

Stage J 以现有三份 `reference_database/*_reference_targets.json` 的 `stock_median` 为数值真值。官方架构事实与 B/R2 相对特征分开记录在 `reference_database/stage_j_three_vehicle_target_matrix.md` 和 `targets/stage_j_vehicle_acoustic_target.json`。不使用参考录音的绝对 LUFS/RMS，不下载新音频。

## 自动证据

- Stage J 专项：`39 passed / 27.99 s`。
- Stage I 兼容回归：`108 passed / 55.98 s`。
- Realism/identity：`67 passed, 78 subtests / 137.64 s`。
- 完整 `tools/sound_sim/s12/tests`：`321 passed, 114 subtests / 138.82 s`。
- 完整 `acoustic_identity_v015/tests`：`313 passed, 118 subtests / 615.22 s`。
- Track-P pytest：`21 passed`；guard：`180 frozen files / 2 symbols`。
- `git diff --check`：通过。
- 三车 60 秒最终 PCM：48 kHz、stereo、PCM24、2,880,001 frames、finite、clipping 0。

## 参考距离（最终 PCM）

| 车辆 | eligible 状态平均改善 | 状态 |
|---|---:|---|
| C63 W204 | 19.68% | `PARTIAL / AUTOMATED_GATE_FAIL` |
| GT-R R35 | -210.88% | `PARTIAL / AUTOMATED_GATE_FAIL` |
| LFA | 14.05% | `PARTIAL / AUTOMATED_GATE_FAIL` |

30% 公式和门限没有被降低；因此本阶段不能进入 Profile Freeze。

## 审核副本响度

正式候选仍使用固定 `-16 LUFS / -1.5 dBFS` 策略。具名审核副本请求统一 `1.25x = +1.9382002601611283 dB`，之后按 baseline/candidate pair 的共同峰值做 attenuation-only headroom cap，不使用 compressor、limiter、EQ 或 per-section AGC。

- C63：实际约 `1.00000002x`，因为 pair peak 已到 `-1.5 dBFS`。
- GT-R：实际约 `1.00000002x`，同样受峰值限制。
- LFA：实际约 `1.24752694x`，仍记录为 headroom-limited。

这解释了“请求增加四分之一”和“不能削波”之间的约束；不能用全局增益越过峰值门限。

## 试听包

外部包：`E:\Tesla_speed\review_packages\s12-stage-j-three-vehicle-identity-v1\`。

每车包含：Stage C baseline 60 s、Stage J candidate v1 60 s、12 s identity、12 s shift/lift、spectrogram、order map、metrics、reference distance。试听后请填写 `Jovi_Stage_J_Named_Feedback.csv`。

## 下一步

当前停止点是 `WAITING_FOR_JOVI_STAGE_J_NAMED_REVIEW`。收到具名反馈后最多做 v2/v3，每次只修改一辆失败车辆，其他车辆 PCM SHA 必须保持不变。未收到反馈前不生成 Human PASS、Approved Profile 或 Simulink/Runtime/Android 集成。
