# S12 Stage R 真实声浪差异基线报告

状态：`R2_LIMITED_COMPARISON_COMPLETE / R1_BLOCKED`

当前仍没有 R1 资格参考，但 Jovi 已授权下载并审计三条明确 CC/CC0 许可的公开声浪，已完成 Ferrari 458、Hellcat 与 Supra 的 R2 有限比较。本文件不把 R2 结果升级为真实阶次资格，不输出单个真实性百分比，不把 synthetic parent 当作真实车辆，也不生成车型参数建议。

## 原始 24 条 YouTube URL 的 R3 补充基线

随后对原始 24 条 URL 使用直接无代理音频重试，并将 24 条完整可解码音频重新接入现有 Comparator。该补充结果仍全部为 `R3_DIAGNOSTIC_ONLY`，仅用于相对频谱、响度、心理声学代理和瞬态听审排序；没有同步 RPM/Load/Throttle/Gear、合法授权或原厂排气证据，因此不改变本报告的 R1/R2 状态。

- 中文差异报告：`E:\Claude_allow\Download\s12-real-vehicle-source-library-v1-20260822\retry_direct_20260822_v1\analysis_r3_direct_v1\S12_Stage_R_Direct_YouTube_R3_Difference_Report_20260822.md`，SHA-256 `5428C2085A8BD0CA0AC60C6338CABDC8B6000CC6F6BF255B46503ACA33A98D93`。
- 机器收据：`direct_analysis_receipt_v1.json`，SHA-256 `A007C99EAC91D3A875EF3EDEF4E2A6433EBF6AC18BF1F724D9DD89D46F778876`。
- 逐车输出：8 车各 3 条，`24/24` 特征与 `24/24` Comparator；`order.status=not_evaluated_without_rpm_trace`，`automatic_tuning_eligible=false`，人耳反馈仍为空。

## 本轮 R2 结果

| 车型 | 参考/场景 | R2 结果 | 频谱残差 | 响度残差 | 阶次/自动调参 |
| --- | --- | --- | ---: | ---: | --- |
| Ferrari 458 | [Goodwood 起步录音](https://commons.wikimedia.org/wiki/File:Ferrari_458_Italia.ogg) / acceleration | `R2_LIMITED_COMPARISON_COMPLETE` | `0.574775` | `+2.7001 dB` | `NOT_QUALIFIED` / withheld |
| Dodge Hellcat | [启动/起步录音](https://commons.wikimedia.org/wiki/File:Launching_sound_Challenger.ogg) / launch | `R2_LIMITED_COMPARISON_COMPLETE` | `0.503287` | `+0.4530 dB` | `NOT_QUALIFIED` / withheld |
| Toyota Supra | [CC0 底盘测功机全油门录音](https://freesound.org/people/editboy23/sounds/496171/) / full_pull | `R2_LIMITED_COMPARISON_COMPLETE` | `0.854657` | `-6.4747 dB` | `NOT_QUALIFIED` / withheld |

完整机器结果和中文单案报告位于：

- `web-authorized-20260822/ferrari_458/`
- `web-authorized-20260822/hellcat/`
- `web-authorized-20260822/supra_jza80/`
- `web_authorized_r2_index_20260822.json`

这些数值是未增益分析信号上的相对数字域残差；没有同步 RPM、Load/Throttle、Gear/shift，所以不能作为 order hard gate、OEM 绝对门限或自动调音目标。Hellcat 的本地文件是合成 launch proxy，场景状态也没有与公开录音同步；Supra 参考是 CC0 的有损 HQ MP3 预览，且页面未核实 JZA80 代际。

待真实资料满足 Q 门后，逐车逐工况计算：阶次、20–60/60–120/120–250/250–400/400–1000/1–4k/4–5.5k/5.5–12kHz 频带、怠速调制、换挡/收油瞬态、响度/尖锐度/粗糙度/波动度/音调，以及参考不确定性。

试听副本必须与未经增益/EQ/AGC 的原始分析信号分离。本轮没有创建或导入 Jovi 听审结果；所有参数建议保持 `WITHHELD`。

原始音频不会复制进 Git；本报告只绑定 Stage Q manifest、外部路径和 SHA-256。
