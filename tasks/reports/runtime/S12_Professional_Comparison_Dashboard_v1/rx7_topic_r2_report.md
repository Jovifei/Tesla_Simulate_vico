# RX-7 FD 清洁参考 R2 主题对比报告

状态：`RX7_R2_PROFESSIONAL_COMPARISON_COMPLETE / NOT_R1_QUALIFIED`

外部包 manifest SHA-256：`2c92c48e58c371fc92613fd9a4e2747ea9c06866e2b9f7072b741851d26a58df`（source audit） / `candidate_profile.json` profile SHA：`56c631ac3fc4cde747c3e6997ef46f17491a27e434080128d537659addb076ef`。

## 来源边界

- 参考为作者录制的 1993 Mazda RX-7，许可 `CC BY-NC-SA 4.0`，仅非商业 R2 使用；原始/派生音频均在 `E:\Claude_allow\Download`。
- 没有同步 RPM/load/throttle/gear/shift，Order 固定 `ORDER_COMPARISON_NOT_QUALIFIED`。
- 五条参考保持原生时长，不循环、不静音补齐、不对参考做增益/EQ/AGC/重采样。

## 候选参数

- 参数组：`rotary_housing_turbo_distribution`；候选变化数：`1`。
- `rotary_pulse_width_scale=1.08`、`primary_spool_tau_s=0.14`、`secondary_spool_tau_s=0.28`、`boost_attack_s=0.08`、`boost_release_s=0.24`、`blow_off_gain_scale=1.00`、`blow_off_release_s=0.70`。
- 候选使用一次固定包增益 `-10.888 dB` 保持峰值不超过 −1.5 dBFS；这不是参考音频响度匹配。
- 未修改 source、PTR、Radiation 或其它冻结层；不是自动最优调参或 Profile Freeze。

## 试听主题与指标

| 片段 | 主题提示 | 原生时长 | Legacy Proxy 频谱距离 | MATLAB 粗糙度差值 | MoSQITo 粗糙度差值 |
| --- | --- | ---: | ---: | ---: | ---: |
| `rx7_topic_01_idle` | 怠速 | 14.000s | 0.9951 | -0.0661 | -0.0163 |
| `rx7_topic_02_steady_low` | 转速变化 / 音色/机械感 | 7.658s | 0.7468 | 1.4035 | 2.3389 |
| `rx7_topic_03_steady_mid` | 转速变化 / 音色/机械感 | 7.680s | 0.7565 | 1.3825 | 2.2168 |
| `rx7_topic_04_full_pull` | 加速 / 转速变化 | 16.500s | 0.6467 | -0.0839 | 0.2102 |
| `rx7_topic_05_full_pull_interior` | 加速 / 音色/机械感 | 16.500s | 0.4480 | 0.1224 | 1.0469 |

## 听审说明

- 先听每段 reference，再听 candidate；主题提示只说明应该关注的听感，不是自动判定。
- 本包没有真实换挡或回火参考段；页面会显示这些主题不可从当前 RX-7 录音确认，不能凭候选合成声宣称真实。
- MATLAB、MoSQITo、Legacy Proxy 分列，不能合并成总相似度百分比。

## 输出

- 页面：`rx7_topic_r2.html`。
- 指标结果：`rx7_topic_r2_results.json`。
- `parameter_changes=1` 只表示一个外部候选版本已渲染；不代表参数已经通过 Jovi 人耳复核。
