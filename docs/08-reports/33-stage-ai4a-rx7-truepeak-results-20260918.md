# Stage AI-4A — RX-7 True-Peak 本地诊断结果（2026-09-18）

## 阶段边界

本阶段只解释 RX-7 的既有数值阻塞，不修复音频，不改变 `1.0` 门禁、`linked_soft_ceiling_v1`、`K=0.90/C=0.94`、IR、Reference、反馈参数或旧包。没有生成修复 WAV，也没有解锁 RX-7 B。

- 源分支：`feature/stage-ai-rx7-truepeak-diagnostics-20260917`
- 实际 HEAD：`aea382bb6b1c7f9d82b3d2186b398dd78af94d87`
- 基点：`52c2d5462993748942c00bf353ea4152bc0ac38e`
- PR：`#28` Draft；main 未修改
- 最终状态：`STAGE_AI4A_TRUEPEAK_DIAGNOSTICS_COMPLETE` / `WAITING_FOR_JOVI_AI4B_REPAIR_DECISION`

## 测试

在独立 worktree `E:\Tesla_speed\worktrees\stage-ai4a-rx7-truepeak-20260917`：

- true-peak focused：`12 passed in 1.53s`
- Stage AI evidence：`15 passed in 1.37s`
- compileall：exit `0`
- `git diff --check`：exit `0`

没有修改源码；诊断工具和测试来自远端交接 HEAD。

## 受控来源与身份

十个 A 原算法 WAV 均来自最新已 seal 的三路包：

`E:\Tesla_speed\review_packages\s12-stage-ai-qualified-three-way-20260916-v2`

- 包 `ARTIFACTS.json` SHA：`179f3ed31ebe93dab316ef9bef6bb238fda31931f29a51eb49009d04a1e6e3f5`
- 车型：`rx7_fd`
- 角色：`A original algorithm baseline`
- 10 个 A WAV 的 SHA 来自该包 `ARTIFACTS.json`，每个 analyzer 调用都传入 `--expected-sha256`。
- 诊断输出目录：`E:\Tesla_speed\review_packages\s12-stage-ai4a-rx7-truepeak-20260917-v2`
- 汇总 JSON：`summary.json`，SHA `a3ad5a8e7f7d83ec6ca6f258cc7a278d1b9fe63d0eda3be5d4bf27e58b252fbd`
- 输入音频和旧包均未改写。

分析方法固定为 `scipy.signal.resample_poly`，up factors `2/4/8/16`，Kaiser beta `5.0`，`line` boundary；结果是工程诊断，不是 ITU/EBU 认证 true-peak meter。

## 十场景结果

所有 WAV 的 sample peak 都为 `0.930419921875`；只有 `09_steady_mid` 被阻塞。

| 场景 | WAV SHA（前 12 位） | 2× peak | 4× peak | 8× peak | 16× peak | 最坏时间 s | 声道 | 4×超限计数 | 分类 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 01_afterfire | `79ecb1d904c0` | 0.930901 | 0.931012 | 0.931039 | 0.931046 | 0.013333 | L | 0 | WITHIN_THRESHOLD |
| 02_full_pull | `50be15c64ce8` | 0.930901 | 0.931012 | 0.931039 | 0.931046 | 2.831188 | L | 0 | WITHIN_THRESHOLD |
| 03_hot_idle | `75bfb6f89fac` | 0.930901 | 0.931012 | 0.931039 | 0.931046 | 0.373042 | L | 0 | WITHIN_THRESHOLD |
| 04_idle_return | `9eca879eea06` | 0.930901 | 0.931012 | 0.931039 | 0.931046 | 1.406063 | L | 0 | WITHIN_THRESHOLD |
| 05_lift | `6a3f21e69e54` | 0.930901 | 0.931012 | 0.931039 | 0.931046 | 1.875479 | L | 0 | WITHIN_THRESHOLD |
| 06_shift | `0f6fd1365b56` | 0.930901 | 0.931012 | 0.931039 | 0.931046 | 2.696458 | L | 0 | WITHIN_THRESHOLD |
| 07_steady_high | `987b7da88a08` | 0.930901 | 0.931012 | 0.931039 | 0.931046 | 5.879625 | L | 0 | WITHIN_THRESHOLD |
| 08_steady_low | `66e3ec62db77` | 0.930901 | 0.931012 | 0.931039 | 0.931046 | 3.735854 | L | 0 | WITHIN_THRESHOLD |
| 09_steady_mid | `c1e13e777f00` | 1.029627 | 1.031070 | 1.041843 | 1.041851 | 0.000424 | L | 2 | INTERSAMPLE_OVERSHOOT_BLOCKED |
| 10_tip_in | `27143685399a` | 0.930901 | 0.931012 | 0.931039 | 0.931046 | 4.215188 | L | 0 | WITHIN_THRESHOLD |

完整 WAV SHA、诊断 JSON SHA、每个倍频的超限区间和频谱字段都在外部 `summary.json` 与十个 JSON 文件中。

## 既有阻塞复现

旧 RX-7 failure receipt：

`E:\Tesla_speed\review_packages\s12-stage-ah-reference-loop-20260914-v1\diagnostics\rx7_fd-baseline-numeric-failure.json`

其 SHA 为 `ac6c1b5d445a106ac11d64b69be91ff9ac94a0186c9c27d355a684c9b655a06e`，旧记录的 pre-quantized `peak_estimate_4x` 为 `1.0311131137519787`。当前 package WAV 域重新计算得到：

- 当前 WAV sample peak：`0.930419921875`
- 当前 WAV 4×：`1.0310696444758585`
- 使用旧 helper 的 `/32767` 量化口径：约 `1.0311011112`
- 当前 WAV 8×：`1.041843101897096`
- 当前 WAV 16×：`1.0418505942977803`

因此“4×超过 1.0”的既有阻塞可以复现；旧记录的最后几位来自旧运行的 pre-quantized float 域，不是当前 WAV 字节域的精确同值。不能把这个差异当作门禁容差，也不能用它放宽阈值。

`09_steady_mid` 的 2×/4×/8×/16×超限最长连续段分别为：

- 2×：1 sample，约 `10.4167 µs`
- 4×：2 samples，约 `10.4167 µs`
- 8×：3 samples，约 `7.8125 µs`
- 16×：7 samples，约 `9.1146 µs`

16×相对 8×只增加约 `7.49e-06`，已经基本收敛；不是持续随倍频增长的 Nyquist 高频失控。

## 最坏峰值与事件关联

最坏峰值发生在 `09_steady_mid` 左声道，16×时间 `0.000424479 s`，超限区间约 `0.000420573–0.000429688 s`。该场景在 `build_unified_dashboards.py` 中是 6 秒恒定约 45% redline、35% throttle 的 steady cruise，没有 shift、afterfire 或 BOV event；因此不能归因于回火、换挡或泄压瞬态。

最坏点附近 40 ms 原采样局部频谱：

- centroid：`126.0223 Hz`
- top bins：`97.9592 Hz`、`146.9388 Hz`、`48.9796 Hz`、`195.9184 Hz`、`489.7959 Hz`、`244.8979 Hz`、`440.8163 Hz`、`734.6939 Hz`
- 前两峰占局部功率约 `51.41%` 与 `42.95%`

这更像信号起始边界/插值滤波响应叠加低频 rotary/order 内容；目前没有证据证明是高频 turbo 或某个命名瞬态 stem 的实际事件峰。

## AI-4B 决策建议

建议先选 **C：interpolation/boundary investigation**。理由是：

1. 十个场景只有一个阻塞；
2. 阻塞点在恒定 steady scene 的开头约 0.42 ms；
3. 4×到 8×增加明显，但 8×到 16×已经收敛；
4. 局部频谱以低频 order/rotary 内容为主；
5. shift、afterfire、BOV 场景都没有超过 1.0。

当前不进入 AI-4B 修复，不改输出保护、不改 rotary/turbo 参数、不降全轨增益、不改门禁、不覆盖旧包。
