# S12 Stage AA Hellcat 声学质量收口

第一结论：AA-C3 的数字指标明显比 Stage-Z 更接近 Parent，但在 Jovi 人耳试听前不能称为“真实感已验收”。当前状态是 `ACOUSTIC_QUALITY_NOT_YET_HUMAN_ACCEPTED`。

## 基线与根因

- `STAGE_AA_BASE_MAIN=209378bcb9a0c1a352ffd56ca1c765ecce01f81d`（Stage-Z PR #3 merge）。
- AA1 的 10 场景 layer ledger 定位主要损失为 `transients → dp_dc` 的 `-22…-25 dB`，以及 frozen PTR 的 `-21…-23 dB` 固定衰减。
- `full_load` 的 pre-transients DC mean=`0.187067`、AC RMS=`0.094866`，dP/DC 后 RMS=`0.009289`；因此不是可以用 master gain 掩盖的播放音量问题。
- PTR/Radiation/Track-P 保持 frozen，未被修改。

## AA0–AA6 证据

- 机器证据集中在 `tasks/reports/runtime/s12-stage-aa/`：`metric_significance_contract.json`、`method_ablation_scorecard_v2.json`、`energy_budget_trace.json`、`reference_diagnostic_contract.json`、`hellcat_root_cause.json`、`candidate_audit.json`、`finalist_review.json`、`raw_dynamic_contract.json` 及逐阶段 receipts/logs。
- AA0：12 个可执行 Stage-Z ablation 重新计算；12/12 有 causal PCM effect，9/12 达到逐指标 engineering significance，3/12 明确低于阈值。ENSIM4 继续 teacher-only。
- AA2：canonical Q reference 为 R1=0、R2=8、R3=15；order gate=`NOT_QUALIFIED`。Timbre Review 可共享 RMS 匹配，Dynamic Review 保持相对响度。
- AA4：只生成 AA-C0…AA-C3，4/4 候选在 11 个场景通过 finite/clipping/click/afterfire/边界 hard gates；AA-C3 仅是诊断偏好。
- AA5：AA-C1/C2/C3 的 Python finalist 指标已生成；MATLAB=`MATLAB_FINALIST_RECEIPT_PENDING`，未启动新 session。
- AA6：v3 已通过 validator，包含 11 场景、110 个 PCM24 stereo WAV、Timbre Review、盲化 Dynamic B/C、答案页和 objective receipt。

## Objective（平均值，诊断）

| 指标 | Parent | Stage-Z | AA-C3 |
| --- | ---: | ---: | ---: |
| RMS dBFS | -45.588 | -62.039 | -47.801 |
| Dynamic range dB | 9.368 | 3.582 | 5.747 |
| Spectral centroid Hz | 1683.1 | 4247.3 | 1830.4 |
| Roughness proxy | 0.546 | 0.580 | 0.517 |
| Sharpness proxy | 0.146 | 0.297 | 0.115 |
| Persistent-tone ratio | 0.453 | 0.488 | 0.444 |

AA-C3 相比 Stage-Z 的 RMS、动态范围、centroid、roughness、sharpness 和 persistent-tone 均改善，但低频 body share 有过冲，且没有同步合法 R1，故不生成 OEM、Profile Freeze 或自动调音结论。

## v3 与下一步

试听包：`E:\Tesla_speed\review_packages\s12-stage-aa-hellcat-quality-v3`。manifest SHA-256：`b1ea99d36179229ff7d31f30f4790b6b84d8af587c14d44398e8e595f5f0964f`。旧 v1/v2 保持不动。

下一步唯一允许动作是 Jovi 试听并填写每个关键场景的身份、真实感、怠速生命感、低频压力、机械纹理、blower、加速连续性、换挡、回火、synthetic artifact 和整体偏好。收到反馈后最多做一轮 metric-hypothesis→scene→parameter-family 的 Round 2；反馈前不把 AA-C3 合并到 main，也不扩散 Ferrari/RX-7。

最终门禁：

```text
SOFTWARE: PASS (focused/package/validator; final branch CI run 33510767391 = success on 8bb9df7)
ENERGY_BUDGET_ROOT_CAUSE: IDENTIFIED
HELLCAT_BOUNDED_CANDIDATES: COMPLETE
PROFESSIONAL_FINALIST_REVIEW: COMPLETE_WITH_MATLAB_PENDING
V3_AUDITION_PACKAGE: VALID
HUMAN_AUDITION: WAITING_FOR_JOVI
R1: MISSING
OEM_CALIBRATION: NOT_AUTHORIZED
PROFILE_FREEZE: NOT_AUTHORIZED
```
