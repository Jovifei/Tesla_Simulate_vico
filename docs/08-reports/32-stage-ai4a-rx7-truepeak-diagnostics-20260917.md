# Stage AI-4A — RX-7 4× 重建峰值阻塞诊断

## 当前目标

只回答一个问题：RX-7 `09_steady_mid` 为什么出现“样本峰值约 0.93046，但既有 4× 重建峰值约 1.031113”的数值阻塞。

本阶段**不改声音**、不改 `linked_soft_ceiling_v1`、不改 `K=0.90/C=0.94`、不改 Reference、IR、反馈参数、阈值或旧包。它不是 RX-7 修复本身，而是决定下一阶段该修输出重建峰值、源带宽还是局部瞬态的证据阶段。

开发基点：`feature/stage-ai-measured-feedback-20260916@52c2d5462993748942c00bf353ea4152bc0ac38e`。
新分支：`feature/stage-ai-rx7-truepeak-diagnostics-20260917`。

## 为什么不能直接把阈值放宽

当前阻塞的特征是 sample peak 低于满幅，而 `resample_poly(up=4)` 后超过 1.0。这属于典型的“离散样本安全但带限重建峰值更高”的候选情况。此时：

- `hard clip count = 0` 不能证明重建峰值安全；
- 把 1.0 改到 1.04 会抹掉门禁而不解释根因；
- 全轨降增益虽然能压过门禁，但会改变所有场景，不能作为第一诊断；
- 只看 4× 单一数字也不足以判断结果是否收敛、是否是边界/插值滤波伪影。

## 新诊断

`stage_ah/true_peak_diagnostics.py`：

1. 读取受控 WAV，可选要求文件 SHA-256 完全匹配；
2. 保留现有 4× `scipy.signal.resample_poly(..., kaiser beta=5, padtype=line)` 结果；
3. 同时计算 2×/8×/16×，记录峰值、时间、声道、超限样本数和最长连续超限区间；
4. 输出 sample peak 和重建峰值的 dB 差；
5. 在最坏峰值附近取 40 ms 原采样窗口，输出频谱质心与前 8 个能量峰；
6. 输出分类：`WITHIN_THRESHOLD`、`INTERSAMPLE_OVERSHOOT_BLOCKED` 或 `SAMPLE_AND_INTERSAMPLE_BLOCKED`；
7. 不修改输入，不输出修复 WAV。

这些结果都是工程诊断，不宣称 ITU/EBU 认证 true-peak meter。

## 本地 Codex 必做

从已有 RX-7 v5/最新三路资产中找到 `09_steady_mid.wav` 的真实算法基线，先从对应 manifest/summary 独立读取并核对 WAV SHA，不允许手工猜路径后跳过身份校验。

执行：

```powershell
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_ah.true_peak_diagnostics `
  --wav <RX7_09_STEADY_MID_WAV> `
  --expected-sha256 <MANIFEST_SHA_FOR_THIS_WAV> `
  --out E:\Tesla_speed\review_packages\s12-stage-ai4a-rx7-truepeak-20260917-v1\rx7_09_steady_mid_truepeak.json
```

同时对 RX-7 其余 9 场景运行相同诊断，生成一张 10 场景表，避免只修一个场景后引入另一个峰值问题。

至少返回：

- 原 WAV 路径与 SHA；
- sample peak；2×/4×/8×/16× peak；
- 最坏时间点、声道和最长超限区间；
- 4× 与原门禁数值是否复现；
- 8×/16× 是否继续明显增长或已基本收敛；
- 局部频谱 top bins/centroid；
- 同一时间附近是否对应 shift/afterfire/BOV/高频 rotary/turbo 瞬态；
- 10 场景中还有没有其它 >1.0 的场景。

## 下一步决策门

只有拿到真实本地结果后才进入 AI-4B：

- 若 4×→8×→16×基本收敛，且峰值集中于少量瞬时高频区域：优先做局部、左右联动、可测量的 true-peak 输出保护候选；
- 若 8×/16×持续增长明显或频带异常接近 Nyquist：优先检查源带宽/离散源实现，不先上 limiter；
- 若 10 场景多处发生且与同一命名 stem 强相关：优先修该 stem 的带宽/瞬态，不用全局 gain；
- 若只在插值边界附近出现：先查 pad/filter 边界，不把边界伪影当真实音频问题。

任何修复都必须生成新候选，与旧 RX-7 A/C 字节隔离；不得原地覆盖 v5 或三路包。

## 证据边界

Stage AI-4A 完成只表示“远端诊断工具已具备工程资格 + 本地真实 WAV 结果可复现”。不等于 RX-7 已修复、B 已解锁、Human PASS、OEM、Profile Freeze。
