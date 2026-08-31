# S12 Professional Comparison Report

状态：`R2_DIAGNOSTIC_CANDIDATE_READY / WAITING_FOR_JOVI_GUIDED_REVIEW / NOT_R1_QUALIFIED / NOT_PROFILE_FREEZE_READY`

## 证据边界

页面 exact A/B：`9` 对、`18` 个片段；参考等级为 R3。manifest SHA：`dc5bb05c24b338485f567b4e4107620aff76f8d210204b6cccae61eb4c4f6052`。
MATLAB Audio Toolbox、MoSQITo 和 Legacy Proxy 分列；数字域结果不是绝对 SPL，不输出总相似度百分比。

统一字段证据表：`professional_evidence_matrix.json`，共 `33` 条记录（Dashboard exact `9` 对 + Stage R3 八车 `24` 条）。每条记录绑定 reference/candidate ID、SHA、采样率/窗口、麦克风不确定性、频带/心理声学残差、瞬态域、Order 状态和人耳状态；R3 记录的 MATLAB/MoSQITo 列明确为 `null`，不把 Proxy 冒充正式工具。

## 专业工具收据

- MATLAB R2026a Audio Toolbox：18 条 exact clip，reference/candidate 各 9 条；外部收据 `E:\Claude_allow\Download\s12-professional-comparison-dashboard-v1\tool_receipts\matlab_exact_clip_metrics_v3\matlab_exact_clip_metrics.json`，SHA-256 `ccf6f1ae3df590f78ac7345730f6fac5dd11750df62fd2c271e875297b0d3dac`。
- MoSQITo 1.2.1：18 条 exact clip，reference/candidate 各 9 条；外部收据 `E:\Claude_allow\Download\s12-professional-comparison-dashboard-v1\tool_receipts\mosqito_exact_clip_metrics_v2.json`，SHA-256 `64506e9594149cb560fc49a204047646bdd3db56cf62a1c95847af66e9c14484`。
- MoSQITo 当前 adapter 不提供 `fluctuation_vacil`；该列显式为 `null / NOT_SUPPORTED_BY_CURRENT_MOSQITO_ADAPTER`，没有用 Proxy 填充。
- MATLAB/MoSQITo 的所有结果均为数字域相对值；没有绝对 SPL 校准，也没有 RPM/state，因此 Order 仍未资格。

## 锚点软件诊断

| 车型 | 软件诊断 | 参数组 | 候选规格 |
| --- | --- | --- | ---: |
| ferrari_458 | 120–400Hz主体不足，主体声压和攻击感偏弱。；1–4kHz相对偏高，候选可能更集中、更像窄带中高频。；4kHz以上真实 metallic 层偏弱，需检查高阶包络和金属质感。；MATLAB 粗糙度差值偏低，机械粗糙度和动态生命感可能偏弱。 | `metallic_high_order_envelope_mid_band` | 64 |
| hellcat | 20–120Hz相对偏多，声音容易闷或低频堆积。；120–400Hz不足，V8压力和加速攻击感可能不够。；400–1000Hz偏多，可能产生箱体感或中频拥挤。；MATLAB 粗糙度差值已列出，需由 Jovi 判断是自然机械纹理还是伪影。 | `pressure_attack_blower_intake_balance` | 64 |
| rx7_fd | 120–250Hz单峰过强，当前更像窄带嗡鸣而不是宽频转子+涡轮。；60–120Hz与400Hz–4kHz不足，宽频转子/涡轮层可能不完整。；MoSQITo 粗糙度差值已列出，需 Jovi 判断机械纹理是否自然。 | `rotary_housing_turbo_distribution` | 64 |

## 使用方式

先阅读软件诊断和图表，再在页面底部确认：诊断是否符合听感、车型身份 0–100、真实感 0–100、最明显问题、偏好和备注。

## 硬门

- 两侧音频必须 `canplaythrough` 且 `duration > 0`；SHA/file-ID/required files 必须通过。
- 没有可信 RPM trace，Order 固定 `ORDER_COMPARISON_NOT_QUALIFIED`。
- 64 个候选只是规格，不是已渲染 source；不修改 reference、FVM、PTR、Radiation、Runtime、Android 或 Track-P。
- Jovi 反馈不自动调音；需要明确指导后才可进入一车一问题一参数组的手工复核。
