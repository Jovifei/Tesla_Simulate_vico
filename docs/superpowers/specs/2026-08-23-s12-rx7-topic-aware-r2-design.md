# S12 主题化听审与 RX-7 清洁参考 R2 设计

## 目标

在不覆盖既有 R3 5 秒/15 秒/30 秒页面、不修改冻结声学核心的前提下，补齐中文听审主题入口，并用已审计、无讲话污染的 RX-7 作者录音建立独立 R2 对比包。RX-7 只生成一个可试听的有界候选版本，不宣称 R1、OEM 复刻或 Profile Freeze。

## 现状与问题

- 上一轮 `long_window_parameter_recommendations.json` 只有规格，`parameter_changes=0`，没有写回或渲染候选。
- Dashboard 当前有“回火不自然/换挡不自然/转速变化不自然”问题标签，但没有独立的听审主题字段，反馈无法区分用户正在听怠速、加速、减速还是换挡窗口。
- 旧 RX-7 长窗口参考含讲话声，不能用于调音。
- 外部 `s12-rx7sim-source-audit-20260823` 已绑定作者页面、Git commit、CC BY-NC-SA 4.0、5 条 RX-7 录音 SHA；缺少同步 RPM/load/throttle/gear/shift，因此仍为 R2。

## 设计

### 1. 中文主题字段

保留每车型一次提交的简化流程，在每车型反馈卡增加 `focus_topics` 多选按钮：

`怠速`、`加速`、`减速/收油`、`换挡`、`回火/爆音`、`转速变化`、`音色/机械感`。

新导出的 v3 反馈仍为车型聚合行；`focus_topics` 至少一个时才允许导出。v1/v2 历史反馈继续可导入，缺失主题时标记 `legacy_feedback_without_topics`，不回写旧反馈。

每个 pair 顶部显示由场景元数据推导的“当前窗口主题”，例如 `onboard_full_load_shift → 加速 / 换挡`；推导只用于提示，不替代人工选择。

### 2. RX-7 R2 外部包

新建 `tools/sound_sim/s12/real_reference/rx7_topic_r2.py`，输入固定为外部授权审计目录与现有 Stage-G RX-7 candidate profile，输出固定在 `E:\Claude_allow\Download\s12-rx7-topic-r2-v1`。使用 5 个原生长度参考：idle、revShort01、revMedium01、revLong01、interior/revLong01；不循环、不静音补齐、不增益/EQ/AGC/重采样。

候选使用 Stage-G renderer 的独立副本，参数组只改 `rotary_housing_turbo_distribution`：

- `rotary_pulse_width_scale=1.08`
- `primary_spool_tau_s=0.14`
- `secondary_spool_tau_s=0.28`
- `boost_attack_s=0.08`
- `boost_release_s=0.24`
- `blow_off_gain_scale=1.00`
- `blow_off_release_s=0.70`

这些是手工诊断候选，不是从 R2 指标自动搜索得到的最优解；`rotary_phase_offset_deg`、afterfire、shift 和公共层保持不变。

### 3. 指标与页面

对 5 对 reference/candidate 运行 Legacy Proxy、MATLAB Audio Toolbox 和 MoSQITo；保留 `ORDER_COMPARISON_NOT_QUALIFIED`。输出独立 `rx7_topic_r2.html`，显示中文主题、来源/许可、原生时长、SHA、MATLAB/MoSQITo/Proxy 指标和候选参数变更。

## 边界与失败策略

- 原始/派生音频只在 `E:\Claude_allow\Download`，Git 只保存 manifest、SHA、来源、许可证、参数和报告。
- 任何 source SHA、音频解码、许可证字段或主题字段缺失都 fail-closed。
- 缺同步 RPM/state 时，页面只能显示转速/换挡/回火的主题提示，不能生成 Order 图、自动时序调参或真实性百分比。
- RX-7 新包不替换旧 R3 包；若新源仍含讲话或其它污染，整包标记 `HUMAN_DATA_QUALITY_BLOCKED`。

## 验收标准

1. Dashboard 主题按钮可直接点击，反馈导出包含 `focus_topics`，旧 v1/v2 导入回归保持通过。
2. RX-7 外部包有 5 对可解码、非零、SHA 匹配的原生时长音频；无循环/静音补齐。
3. RX-7 candidate profile 的变更只属于一个参数组，公共冻结层和 source 核心未改。
4. 新页面可在 Chromium 中播放并导出中文主题反馈。
5. 聚焦测试、全量 S12、Track-P guard、`git diff --check` 和远端 SHA 校验通过。
