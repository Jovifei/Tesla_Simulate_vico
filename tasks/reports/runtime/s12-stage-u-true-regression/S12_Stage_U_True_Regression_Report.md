# S12 Stage U 真实比较器驱动声学回归报告

日期：2026-08-23  
当前状态：`WAITING_FOR_JOVI_PARENT_CANDIDATE_REVIEW`、`NOT_R1_QUALIFIED`、`NOT_PROFILE_FREEZE_READY`

## 结论

本轮不再以测试数量宣称声浪改善。已完成真实的“参考音频 → Parent → 候选网格 → 专业三方比较 → 有限候选选择 → 人耳 ABX 页面”链路，并对全部输入、专业回执和试听媒体使用 SHA-256 绑定。

唯一满足 R2/R3 软选择条件的候选是 Hellcat `hellcat_stage_u_04`：3/3 个干净参考场景改善，中位绝对改善为 `0.027958`，最差场景仍为正改善 `0.003434`。它不是 R1，也不能 Profile Freeze。

Ferrari 没有入选：仅有 2 条干净参考，未满足固定的 3 条参考覆盖要求，即使部分指标改善也标记为 `REFERENCE_COVERAGE_NOT_QUALIFIED`。RX-7 的四个候选均为 `NO_MEASURABLE_IMPROVEMENT`，需要模型重构；没有挑选“最不差”候选。

## 证据链

- 基线审计：`S12_Stage_U_Baseline_Audit.md` 记录本轮开始时 Ferrari/Hellcat 未渲染、RX-7 只有手工候选，且 `objective_before_after_claim=NOT_CLAIMED`。
- 参考质量：11 条参考中 10 条通过、1 条 Ferrari 讲话污染被 `REFERENCE_SPEECH_CONTAMINATED` 拒绝；场景、麦克风/AGC 不确定性与匹配渲染 trace 均记录在 `reference_quality_matrix.json`。
- 参数可达性：15 个 Track-S 参数均实际消费并改变目标 stem；未使用参数和跨车型泄漏均为零通过。详细结果见 `parameter_reachability_matrix.json`。
- 候选网格：10 个 Parent、40 个 Candidate 已实际渲染，均有 WAV/PCM/trace/stem/健康度/参数消费 SHA；没有 clipping、wrong-condition 事件或 Parent/Candidate 相同 SHA。见 `candidate_grid_results.json`。
- 专业比较：40 条 Reference↔Parent↔Candidate 记录均绑定 legacy、MATLAB、MoSQITo、MATLAB `audioFeatureExtractor` 的同一三方 SHA；跨采样率 DTW 仅使用固定维度的 MFCC、GTCC 与标量特征，Bark/ERB 完整保留在外置回执中但不跨采样率 DTW。见 `parent_candidate_professional_metrics.json` 与 `audio_feature_dtw.json`。
- 场景绑定：10 个通过质量门禁的场景均按同场景匹配渲染 trace 对齐；这是推断的渲染状态，绝不是 R1 同步 RPM/负载/档位实测。见 `scenario_alignment_matrix.json`。

## 选中候选的有限参数

| 车型 | 候选 | 面板参数 | 实际 source 映射 |
| --- | --- | --- | --- |
| Hellcat | `hellcat_stage_u_04` | `blower_intake_balance=0.25`、`mid_band_pressure_db=3.0`、`pressure_attack_db=3.0` | `blower_intake_balance=0.25`、`intake_gain_scale=1.412538`、`pressure_attack_gain_scale=1.412538` |

这些值仅是有限候选网格点，不是连续置信区间，也不会自动写入 Profile、阶次调参或 Runtime。

## 人耳 ABX 包

V4 外置包路径：`E:\Claude_allow\Download\s12-stage-u-v1\review_package_hellcat_v4`。

- 3 个 Hellcat 场景，每个有 Reference、Parent、Candidate 三路原始副本与独立 48 kHz、−18 LUFS、−1.5 dBFS 峰值上限的试听副本。
- 每个场景的盲听 B/C 映射已随机化并写入 manifest；播放、时长、`canplaythrough`、浏览器 SHA、专业绑定、Parent/Candidate 差异和三题答案均是导出门禁。
- 页面同时显示专业距离前后、参数与不确定性、调整前/后频谱残差 SVG 及其 SHA。AudioCommons `timbral_models` 的 8 个描述符如实显示 `PROJECT_UNMAINTAINED_NOT_AVAILABLE / 非硬门禁`，没有代理填充值。
- 外置最终 ZIP（不含自动化测试反馈）SHA-256：`c3cd26a0f849645a65047cad0274986e3ad8c88fba8ecf94482db2a77cd2b520`；详见仓库外 `review_package_hellcat_v4_final_v2_bundle_receipt.json`。

自动化浏览器导出的 `Jovi_Hellcat_ABX_Submission.json` 只是门禁测试件，**不是** Jovi 的真实人耳反馈，不会导入或用于继续调音。

## 回归与完整性验证

- Stage U 聚焦：79 通过。
- Stage N 专业比较、Stage Q/R/S：45 通过。
- Track-P 冻结守卫：32 通过。
- 完整 S12：534 通过、114 个子测试通过。
- V4 外置包：3 个 trial 的所有 raw/audition WAV、6 张 SVG 残差图、manifest 和 ZIP 内容 SHA 均已复算通过；最终 ZIP 共 25 个受控文件，排除了自动化浏览器测试输出。
- `git diff --check` 通过；没有把 WAV、SVG 或 ZIP 提交到 Git。

## 下一步人工门禁

Jovi 需要通过只读本机回环服务打开页面，完成 3 个场景的 B/C 选择和备注，并把导出的真实 JSON 交回。直接以 `file://` 打开页面会安全地保持导出禁用，因为浏览器 SHA 校验要求同源只读服务。

收到真实反馈后，只允许对 Hellcat 的这一车、这一参数组进行有界下一轮调音与回归；Ferrari 需要第 3 条干净参考，RX-7 需要模型重构后再建网格。没有真实人耳反馈，不修改声源。
