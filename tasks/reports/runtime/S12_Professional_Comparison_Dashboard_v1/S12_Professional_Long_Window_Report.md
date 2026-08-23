# S12 15/30 秒长窗口专业对比报告

状态：`JOVI_FEEDBACK_VALIDATED / R2_DIAGNOSTIC_REVIEW_READY / NOT_R1_QUALIFIED`

长窗口 manifest：`ecbe8dc92fa63ed00a76e1554a37a1ff452aaa6af0eff5b3bd3edbadcd64c2a1`；共 `18` 对（15 秒 9 对、30 秒 9 对）。

## 取窗规则

reference 从原始长 WAV 的页面锚点附近取 15/30 秒；candidate 从外部 60 秒本地完整循环取动态场景窗口：怠速→加速→全负荷→收油/减速→巡航→怠速。只做时间切片，无增益/EQ/AGC/重采样。

## 重要边界

- reference 仍是 R3，未核验授权/原厂状态/同步 RPM；长窗口不升级 R1。
- candidate 是本地合成完整循环的外部派生文件，不修改 source；Order 固定 `ORDER_COMPARISON_NOT_QUALIFIED`。
- MATLAB/MoSQITo 36 条信号收据和 Legacy Proxy 分列；MoSQITo fluctuation 仍显式不支持。
- Jovi 只确认动态诊断是否符合听感；反馈已导入，但仍不执行自动调音。

## 场景覆盖

| 试次示例 | 场景 | 窗口 |
| --- | --- | --- |
| `ferrari_01_15s` | `start_idle_rev_acceleration` | `15s` |
| `ferrari_01_30s` | `start_idle_rev_acceleration` | `30s` |
| `ferrari_02_15s` | `onboard_full_load_shift` | `15s` |
| `ferrari_02_30s` | `onboard_full_load_shift` | `30s` |
| `ferrari_03_15s` | `launch_acceleration_shift` | `15s` |
| `ferrari_03_30s` | `launch_acceleration_shift` | `30s` |
| `hellcat_01_15s` | `idle_rev_acceleration` | `15s` |
| `hellcat_01_30s` | `idle_rev_acceleration` | `30s` |
| `hellcat_02_15s` | `onboard_acceleration_shift` | `15s` |

请在同一播放器音量下先听 15 秒，再听 30 秒；重点判断加速/减速连续性、怠速生命感、换挡与回火是否自然。

## Jovi 长窗口反馈导入（2026-08-23）

反馈文件已通过车型聚合入口校验：3 个车型、每车 6 个 pair/file/SHA、音频提交门 `PASS`。外部输入文件名为 `Jovi_Guided_Feedback.json`，SHA-256 为 `acfbcbab2022612621aba2cec8a73a5dbc193e0a142f247989f81b00356b673d`；校验收据为 `Jovi_Guided_Feedback_Long_Window_Validation.json`。

| 车型 | 软件诊断 | 身份 / 真实感 | 偏好 | 问题分类 | 处理结论 |
| --- | --- | ---: | --- | --- | --- |
| Ferrari 458 | 不符合 | 30 / 10 | 候选 | 太薄、太刺、机械感不足、回火不自然 | 只允许中频/金属纹理有界诊断；回火时序暂不处理 |
| Hellcat | 部分符合 | 60 / 50 | 参考 | 机械感不足、低频无冲击、固定电子哨声、回火不自然 | 只允许压力攻击/进气增压平衡有界诊断；回火时序暂不处理 |
| RX-7 FD | 无法判断 | 10 / 10 | 候选 | 无 | 反馈指出含人声，数据质量阻塞，不进入调音 |

具体建议见 `long_window_parameter_recommendations.json`。本轮只生成两个车型各一组、每组 64 个候选规格的人工复核范围，没有渲染候选音频、没有修改声源、`parameter_changes=0`，也没有生成 Profile Candidate。由于反馈为车型聚合行，不能把问题可靠地绑定到某一个 15 秒或 30 秒窗口。

## 当前闭环边界

- R3 参考来源仍不是合法原始 R1 录音；R1、同步 RPM/load/throttle/gear/shift 和 Order 资格仍为 `0 / NOT_QUALIFIED`。
- 回火、换挡、转速变化属于事件/状态问题，缺少同步状态时保持 fail-closed，不猜测、不自动调时序。
- 这是 `R2_DIAGNOSTIC_REVIEW_READY`，不是 `R2` 自动调参、Order hard gate、声源修改或 Profile Freeze。下一步如需继续，需人工选择一个锚点和一个参数组进行候选试听与第二轮 A/B。
