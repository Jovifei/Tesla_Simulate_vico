# S12 15/30 秒长窗口专业对比报告

状态：`LONG_WINDOW_R2_R3_DIAGNOSTIC / WAITING_FOR_JOVI_GUIDED_REVIEW / NOT_R1_QUALIFIED`

长窗口 manifest：`ecbe8dc92fa63ed00a76e1554a37a1ff452aaa6af0eff5b3bd3edbadcd64c2a1`；共 `18` 对（15 秒 9 对、30 秒 9 对）。

## 取窗规则

reference 从原始长 WAV 的页面锚点附近取 15/30 秒；candidate 从外部 60 秒本地完整循环取动态场景窗口：怠速→加速→全负荷→收油/减速→巡航→怠速。只做时间切片，无增益/EQ/AGC/重采样。

## 重要边界

- reference 仍是 R3，未核验授权/原厂状态/同步 RPM；长窗口不升级 R1。
- candidate 是本地合成完整循环的外部派生文件，不修改 source；Order 固定 `ORDER_COMPARISON_NOT_QUALIFIED`。
- MATLAB/MoSQITo 36 条信号收据和 Legacy Proxy 分列；MoSQITo fluctuation 仍显式不支持。
- Jovi 只确认动态诊断是否符合听感，反馈前不执行任何调音。

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
