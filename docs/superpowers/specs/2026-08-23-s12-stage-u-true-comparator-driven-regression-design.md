# S12 Stage U 真正 Comparator 驱动声学回归设计

> 本设计逐字承接 Jovi 提供的 Stage U 规格。该规格已明确给出分支、基线、范围、硬门和最终状态，视为已批准设计。

## 目标

把 S12 从“参数规格建议”升级为可证伪的三方回归：`Reference → Parent → Candidate grid → 专业比较 → 选择/拒绝 → Parent/Candidate ABX`。候选只在同场景、干净参考、可达参数和完整硬门都成立时发布；否则输出 `NO_MEASURABLE_IMPROVEMENT` 或明确拒绝原因。

## 基线与冻结边界

- 工作分支：`agent/s12-stage-u-true-comparator-calibration`
- 基线：`b1d500c7c37a71728020c39e6dc115a0cd6743d5`
- 保持冻结：FVM、PTR core、Radiation、Runtime、Android、Simulink Track-P、Stage N 专业工具收据、R1 资格门、SHA/file-ID 反馈合同。
- 所有原始/派生音频、模型权重、第三方环境和候选 WAV 只在 `E:\Claude_allow\Download` 或 `E:\AI_Tools\Other\S12StageU`；Git 只保存代码、SHA、路径别名、许可证、特征和报告。

## 分层架构

### U0–U1：证据、语音污染和场景门

`stage_u_baseline.py` 固化 exact HEAD、冻结摘要和既有“规格未渲染”状态。`stage_u_reference_quality.py` 对每条候选参考运行 Silero VAD、音频完整性、污染人工复核标志、场景/麦克风/AGC 元数据和场景兼容性。连续语音超过阈值标记 `REFERENCE_SPEECH_CONTAMINATED`；没有可验证匹配 trace 的组合标记 `SCENARIO_NOT_COMPARABLE`。这两个状态都从候选网格排除。

### U2：多域特征

`stage_u_features.py` 统一 raw 分析信号的 Legacy band/spectral/transient、MATLAB audioFeatureExtractor、MoSQITo 和可选 timbral/OpenL3 输出。MATLAB 输出 Bark、ERB、MFCC、GTCC、flux、flatness、entropy、pitch、harmonic ratio、short-time energy；AudioCommons/OpenL3 均携带版本和 `OPTIONAL_RESEARCH_METRIC` 标记，不进入硬门。DTW 仅接收同场景且状态窗口重叠的特征轨迹。

### U3：可达性优先于候选网格

每个抽象 Dashboard 参数必须映射到 renderer 实际消费的 Track-S override。单变量 `-delta / baseline / +delta` 探针证明：requested→consumed、目标 stem 改变、目标指标方向正确、非目标 stem 有界。RX-7 将把误名的 `rotary_pulse_width_scale` 改为真实 pulse envelope width，或改为 `rotary_amplitude_scale`；并增加 housing 可审计 override。Ferrari/Hellcat 的抽象参数将转换为明确 stem/source override。任一失败为 `PARAMETER_NOT_REACHABLE`，不能进入 U4。

### U4–U6：渲染、三方比较与选择

每个合格 reference scenario 使用同一个 synthetic trace 渲染 Parent（`candidate=None`/当前正式 profile）和 Candidate。每车最多 64 个候选；每条保存参数、usage、WAV/PCM SHA、trace SHA、stem metrics、health 和非目标车型 SHA。raw 分析信号用于响度和物理指标；固定规则生成的响度匹配 audition copy 仅用于音色/MFCC/听审。三方输出 `reference↔parent`、`reference↔candidate`、`parent↔candidate` 的绝对/相对改善、每参考结果、中位数和最坏回归。

选择只有在所有硬门通过、Ferrari/Hellcat 至少 2/3 干净参考改善、RX-7 至少 3/5 干净 R2 参考改善且无严重回归时成立；否则显式 `NO_MEASURABLE_IMPROVEMENT`。

### U7–U8：人耳和验证

新 ABX 页面为每场景展示 Reference、Parent、Candidate 和 B/C 随机盲听，验证时长、canplaythrough、SHA、专业结果绑定与 Parent/Candidate SHA 不同。报告同时写不确定性、参数、专业 before/after 和 timbral 描述。测试覆盖 identical、增益、shelf/low-pass/AM、VAD、场景、可达性、Parent=Candidate、没有改善和改善候选的拒绝/发布路径。

## 关键数据合同

- `ReferenceQualityRecord`：`reference_id`、audio SHA、speech verdict、scenario、mic/AGC、compatible synthetic trace ID、exclusion reason。
- `ReachabilityRecord`：`parameter_id`、三点扰动、requested/consumed、target/non-target stem deltas、metric direction、status。
- `RenderedCandidateRecord`：`vehicle/scenario/candidate_id`、parent/candidate SHA、PCM SHA、trace SHA、health、usage、stem metrics。
- `TriadComparisonRecord`：reference/parent/candidate SHA、raw metrics、audition copy SHA、professional/timbral domains、DTW、before/after、worst case、qualification。

## 状态和边界

最终只允许：`R2_COMPARATOR_DRIVEN_CANDIDATE_READY`、`WAITING_FOR_JOVI_PARENT_CANDIDATE_REVIEW`、`NOT_R1_QUALIFIED`、`NOT_PROFILE_FREEZE_READY`，或失败态 `NO_MEASURABLE_IMPROVEMENT / REQUIRES_MODEL_REDESIGN`。没有同步合法 R1 RPM/state 时，Order、事件时序自动调参和 Profile Freeze 永远关闭。
