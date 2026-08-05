# S12 真实录音参考数据库索引 v1

> Phase 1 产物。从外部 R2 真实录音提取的相对特征，用于驱动 Phase 2-5 声学真实度优化。
> 边界：synthetic; uncalibrated; not OEM reproduction。原始音轨不入库，仅保存派生数值。
> 所有指标随录音设备/AGC/距离/改装而变，仅作相对方向参考。

## 提取指标（对齐 Hellcat v6 reference_targets schema）

| 指标 | 含义 |
| --- | --- |
| band_shares | 4 段能量占比 [20-250, 250-1000, 1k-4k, 4k-12k] Hz |
| spectral_flux | 相邻 STFT 帧正谱差均值（瞬态变化强度）|
| modulation_depth | 包络 AC_rms/DC（燃烧脉冲周期性强度，0-1）|
| modulation_peak_hz | 5-500Hz 包络主调制频率（燃烧脉冲基频）|
| pulse_amplitude_cv | 检测脉冲幅度变异系数 |
| pulse_interval_cv | 检测脉冲间隔变异系数 |
| crest_factor | 峰值/RMS |
| dropout_ratio | 低于静默阈值的帧占比 |

## 三车型 stock_median 聚合目标

### Ferrari 458 Italia (ferrari_458) — 1 条录音

声学身份：clean naturally aspirated flat-plane V8 attack that becomes increasingly metallic and high-order at high RPM

| 工况 | 20-250Hz | 250-1kHz | 1-4kHz | 4-12kHz | flux | mod_depth | mod_peak | crest | pulse_amp_cv |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| idle | 0.009 | 0.521 | 0.467 | 0.002 | 0.2213 | 0.996 | 5Hz | 10.41 | 0.207 |
| acceleration | 0.356 | 0.569 | 0.068 | 0.004 | 0.2029 | 0.791 | 71Hz | 6.10 | 0.231 |
| afterfire | 0.122 | 0.686 | 0.183 | 0.007 | 0.2192 | 1.000 | 5Hz | 8.89 | 0.283 |

录音来源：
- `X0yiRilcKME` [AutoTopNL stock-bias acceleration](https://www.youtube.com/watch?v=X0yiRilcKME)

### Mazda RX-7 FD (13B-REW) (rx7_fd) — 1 条录音

声学身份：non-piston rotary event texture with turbo inertia, boost onset, and release

| 工况 | 20-250Hz | 250-1kHz | 1-4kHz | 4-12kHz | flux | mod_depth | mod_peak | crest | pulse_amp_cv |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| idle | 0.968 | 0.032 | 0.000 | 0.000 | 0.1299 | 0.664 | 60Hz | 2.78 | 0.260 |
| acceleration | 0.936 | 0.062 | 0.002 | 0.000 | 0.1641 | 0.643 | 59Hz | 3.87 | 0.266 |
| afterfire | 0.953 | 0.044 | 0.003 | 0.000 | 0.1743 | 0.598 | 45Hz | 3.88 | 0.215 |

录音来源：
- `Thh69Wc5uco` [RX-7 FD 13B-REW rotary acceleration](https://www.youtube.com/watch?v=Thh69Wc5uco)

### Dodge Challenger SRT Hellcat (hellcat) — 3 条录音

声学身份：large-displacement low-frequency exhaust pressure plus boost/load-dependent mechanical whine

| 工况 | 20-250Hz | 250-1kHz | 1-4kHz | 4-12kHz | flux | mod_depth | mod_peak | crest | pulse_amp_cv |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| idle | 0.698 | 0.217 | 0.040 | 0.003 | 0.2265 | 0.716 | 16Hz | 7.63 | 0.315 |
| acceleration | 0.484 | 0.488 | 0.003 | 0.000 | 0.1834 | 0.520 | 29Hz | 3.52 | 0.273 |
| afterfire | 0.414 | 0.483 | 0.005 | 0.000 | 0.1792 | 0.488 | 80Hz | 3.31 | 0.265 |

录音来源：
- `eyzGRhXp0do` [AutoTopNL stock road acceleration](https://www.youtube.com/watch?v=eyzGRhXp0do)
- `FvORN7EH2cc` [Hellcat Redeye brutal downshifts](https://www.youtube.com/watch?v=FvORN7EH2cc)
- `nnEaamqsieM` [Hellcat Redeye near-field leave](https://www.youtube.com/watch?v=nnEaamqsieM)

## 三车型声学身份差异（数值证据）

| 维度 | Ferrari 458 | Hellcat | RX-7 FD |
| --- | --- | --- | --- |
| 加速低频(20-250Hz)占比 | 中（0.356）| 中高（0.484）| 极高（0.936）|
| 加速高频(1-4kHz)占比 | 低（0.068）| 极低（0.003）| 极低（0.002）|
| 加速调制深度 | 高（0.791）| 中（0.484）| 中（0.643）|
| 加速调制峰频 | 71Hz（V8 燃烧）| 81Hz（V8 燃烧）| 59Hz（转子）|
| 回火高频占比 | 高（0.183）| 极低（0.005）| 极低（0.003）|
| 怠速谱重心 | 980Hz（高频金属）| 290Hz（低频机械）| 156Hz（低频转子）|

**身份方向结论**：
- Ferrari：中频为主 + 加速高频增长 + 回火中高频瞬态 → 高转 NA V8 金属尖叫方向
- Hellcat：低频+中频双峰 + 中等调制 + 低 crest → 大排量 V8 低频重量 + 机械增压方向
- RX-7：极低频主导 + 转子调制 59Hz + 低 crest → 转子时间结构 + 涡轮方向

## 文件清单

| 文件 | 内容 |
| --- | --- |
| `ferrari_458_reference_targets.json` | Ferrari 458 完整参考目标 + stock_median |
| `rx7_fd_reference_targets.json` | RX-7 FD 完整参考目标 + stock_median |
| `hellcat_reference_targets.json` | Hellcat 三录音完整参考目标 + stock_median |
| `reference_database_build_summary.json` | 构建摘要 |
| `vehicle_records.json` | 三车型拓扑 + 公开视频定性观察（原有）|
| `vehicle_sound_character_matrix.md` | 声学特征矩阵（原有）|
