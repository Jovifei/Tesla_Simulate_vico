# S12 Stage F Human Audition Qualification v3

## 状态

`WAITING_FOR_JOVI_AUDITION`

本报告是 Stage F 的自动化交付证据，不是人耳通过报告。当前分支为 `agent/s12-stage-f-audition-qualification`，基线为 `3c2c891b469adc7a507870c71ee94319e7125226`。本地工作树保留，未 push、未 merge、未 rebase。

## 本轮完成

- 建立 Stage-F 候选契约，按车型使用 exact-key 白名单、C/synthetic provenance、base commit 和 reference SHA 校验。
- 增加 Stage-F candidate renderer；`candidate=None` 继续调用 Stage-C 管线，候选 overlay 位于公共 Pre-PTR EQ 与 Frozen PTR 之前。
- 三个锚点的参数使用诊断已从“JSON 中存在”改为实际渲染消费：Ferrari 10/10、Hellcat 10/10、RX-7 11/11，`unused=[]`。
- RX-7 的 rotary pulse width 与 BOV release 进入真实的源模型时间/幅度计算；默认值保持 Stage-C 回归兼容。
- 生成 `S12_Blind_Audition_Package_v3`：两轮各 15 个匿名 8 秒样本、三组匿名 60 秒 A/B、预填答卷和独立密封答案包。
- 评分器只在收到并校验完整答卷后才解封；目前没有读取 sealed key，也没有生成 confusion matrix。

## 管线

```text
Independent Source with verified overrides
→ Idle Dynamics
→ Deterministic Afterfire
→ Low-Frequency Body
→ Exhaust Rumble
→ Shift Dynamics
→ Named Transient Peak Shaping
→ Common Pre-PTR EQ
→ Frozen PTR
→ Edge Fade
→ Fixed Whole-Cycle Gain
→ PCM24
```

Frozen PTR、FVM、Radiation Boundary、Runtime、Android、MATLAB、Simulink、Stage-C 公共 LF Body/Rumble/Pre-PTR EQ 均未修改。

## 自动化证据

| 范围 | 结果 |
|---|---|
| Stage-F focused | 15 passed |
| Stage-F/Stage-E focused | 26 passed |
| Stage-F package contract after final evidence output | 1 passed |
| Stage-C realism | 9 passed |
| Identity | 58 passed / 78 subtests |
| S12 完整回归 | 455 passed / 232 subtests（410.51 s） |
| Track-P guard | 21/21 |
| `git diff --check` | PASS |

详细记录见 `stage_f_test_evidence.json` 和 `stage_f_parameter_reachability.json`。

## 试听包

目录：`E:\Tesla_speed\review_packages\s12-stage-f-human-audition-v3\`

- Listener ZIP SHA-256：`e96b62e31cf9860a2c28670a12a4ae93aba1386146e8d9e253f2ca23692ddf56`
- Answer Key ZIP SHA-256：`464416ed8da6c749359c6308bcffce6dd2e616d6dca966c882e9b63d39b7c604`
- Listener ZIP 不含车型、seed、source hash、candidate/baseline 标识或 sealed 文件。
- `source_evidence/stage_f_package_evidence.json`、`reference_distance/distance_contract.json` 和根目录 `SHA256SUMS.txt` 已随包生成；source evidence 不含 sealed 答案。
- 8 秒样本为 48 kHz、stereo、PCM24；60 秒 A/B 文件使用同一车型的连续 `build_drive_cycle_trace`，包含 idle、acceleration、换挡、full pull、lift/afterfire、coast 和 idle return；A/B 使用共同 attenuation-only 响度处理。
- 所有声音仍是合成离线审计输出，不是实测录音，也不代表已校准的 OEM 长周期声学。

## Reference distance

当前 `stage_f_reference_distance.json` 为 `PARTIAL / AUTOMATED_GATE_FAIL`。原因是本轮没有把带明确 idle/acceleration/afterfire 窗口的 Stage-C 与 Stage-F 最终 PCM 状态导出为可复核输入；因此没有伪造 distance 或 30% improvement。现有 target 仍是 B/R2 relative features、microphone/AGC dependent、uncalibrated、not OEM。

## 人耳门禁

当前未收到正式：

```text
blind_responses.csv
ab_responses.csv
playback_context.json
```

因此下列项目均为 `NOT_PERFORMED`：recognition、per-vehicle recall、confidence、realism、artifact freedom、confusion matrix、A/B preference 和 Profile Freeze Review。不得把自动测试数量当作真实感证明。

## 下一步

Jovi 只需在试听后返回上述三份文件。Luna 的下一轮必须先校验 30/30 盲听答卷、3/3 A/B 行和播放环境，再解封答案并评分；最多 v3→v4→v5 三轮。通过后的合法状态仍只可能是 `JOVI_SINGLE_LISTENER_BLIND_CANDIDATE_PASS / PROFILE_FREEZE_REVIEW_PENDING`，不能自动升级为 Approved 或 Simulink 集成。

声明：所有声源和候选参数均为 `synthetic / uncalibrated / not OEM reproduction`。
