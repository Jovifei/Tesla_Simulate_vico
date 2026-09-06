# S12 物理发动机声学生成与负反馈调音 Playbook

更新：2026-09-06

> 本文只总结经 Jovi 实际 A/B 试听确认“明显更像真车（约 70–80% 主观相似）”的 `main=f81d3a3...` 路线，以及 Stage AF 在该路线上的增量改进。不要用后来听感失败的 Stage AE 取代这条基线。

## 1. 当前成功基线

权威 renderer：

`tools/sound_sim/s12/acoustic_identity_v015/stage_ad/engine_sim_acoustics.py::EngineAcoustics`

它不是简单的 pitch-shift，也不是纯 harmonic synth。当前有效声音来自多个物理/物理启发层共同作用：

```text
RPM / throttle trajectory
→ 720° four-stroke cycle phase
→ per-cylinder firing phase
→ asymmetric blowdown pressure pulse
→ cylinder-to-bank assignment
→ runner + exhaust propagation delay
→ pressure/flow derivative component
→ turbulence / airflow modulation
→ exhaust IR convolution
→ mechanical/body resonance
→ supercharger or turbo/BOV layer
→ shift ignition cut / lift / afterfire
→ audition output
```

## 2. 为什么这一版比早期合成路线真实

### 2.1 Blowdown pulse 而不是“画谐波”

排气门打开后的压力释放先生成非正弦脉冲。非正弦事件天然包含丰富阶次，因此低频 body、中频脉动和高频边缘来自同一因果事件，而不是分别加几个 sine。

### 2.2 点火几何决定车型节奏

V8 cross-plane、V8 flat-plane、V10 even-firing、V6 even-firing 的差异首先来自 firing schedule / bank timing。车型身份应优先由事件时序形成，再由 induction/path 修饰。

### 2.3 Runner / exhaust delay 提供自然干涉

每缸传播时间不同，左右 bank 混合后产生微小时序差与梳状干涉。Stage AF 允许只在当前手工调好值附近小范围缩放 `primary_length_scale` / `exhaust_length_scale`，不从零乱搜。

### 2.4 IR 是排气路径的一部分，不是万能美容器

当前好声音使用 Engine-Sim sound-library 中的 IR 做 diagnostic/audition transfer。它对金属管壁、尾段与腔体感贡献明显；但 root code 的 MIT 不自动等于每个 WAV 的产品权利已核实。正式产品必须重新治理 IR provenance。

### 2.5 Induction 是车型身份层

Hellcat 的 supercharger、GT-R 的 turbo/BOV 是身份强化层。它们不能盖过 combustion/exhaust body，也不能用固定高频纯音替代整个发动机声音。

## 3. Stage AF 负反馈：只调“已经好听”的 renderer

旧 `stage_ad/closed_loop.py` 虽然有迭代控制器，但实际驱动旧 Stage-X renderer，和本次好声音不是同一条链。

Stage AF 改为：

```text
真实 R2/R3 reference
→ EngineAcoustics 当前手工参数
→ render
→ scale-invariant spectral/envelope distance
→ bounded physical family search
→ re-render
→ fixed ruler compare
→ shrink / plateau
→ existing A/B dashboard
→ Jovi Human judgement
```

### 参数族

**body**：`exhaust_gain_scale`、`mechanical_resonance_scale`、`df_mix_scale`

**path**：`primary_length_scale`、`exhaust_length_scale`、`ir_volume_scale`

**induction**：`air_noise_scale`（增压车型才运行）

**afterfire**：`afterfire_scale`

所有范围围绕 `f81d3a3` 手工调好的 baseline 小范围搜索。Stage AF 不是重新发明声音。

### 永久禁止作为优化旋钮

- master/global gain；
- monitor gain；
- whole-mix EQ 当作 source repair；
- 用单场景 peak normalization 的差异宣称物理改善；
- 把 R3 public-video distance 下降写成 OEM calibration。

## 4. 参考音频如何收集

优先级：

1. 受控 dyno / 原始录音 + 同步 RPM/load/gear（未来 R1）；
2. 有明确来源、车辆与录音上下文的工程 reference（R2）；
3. 用户明确授权的公开视频切片，仅 `R3_PRIVATE_DIAGNOSTIC_ONLY`。

R3 必须记录 URL、时间段、SHA256、车型/改装信息已知程度、speech/music、AGC/clipping 风险。R3 可以做人耳 A/B 和 diagnostic fit，但不能升 R1/R2。

## 5. 为什么 Stage AF 不做 waveform MSE

真实视频与合成 PCM 存在：麦克风、位置、AGC、codec、道路/风噪、空间声学差异。逐 sample MSE 会优化错误目标。

Stage AF 使用 scale-invariant 特征：

- 20–80 / 80–160 / 160–400 Hz 等多频带能量比例；
- spectral centroid；
- envelope CV / peak；
- positive envelope flux。

这是对 SSSSM-DDSP 等 sound-matching 项目“real-domain 与 synthetic-domain 要在音频/频谱域匹配，而不是只看参数误差”经验的 clean-room 方法吸收。

## 6. 四车型复用路线

```text
先手工建立一个可辨识 physical baseline
→ 10 scene A/B
→ 找差异最大的 source/path family
→ Stage AF bounded fit
→ existing dashboard 再试听
→ 保存 Human feedback
→ 只保留确实听感改善的参数
```

不要同时搜索几十个无解释参数。一次只收一个可解释 family。

## 7. 工作台

不再开发新 UI。统一继续使用：

- `review_packages/serve_dashboards.py`
- `stage_ad/audition_dashboard_template.html`
- `stage_ad/build_unified_dashboards.py`

Stage AF 只把 tuned `EngineAcoustics` 注入原生成器。端口保持 8080 / 8088 / 8089 / 8090 / 8091。

## 8. 仓库体积规则

A/B WAV 和 Base64 HTML 是**可再生成产物**，不再提交 Git。Hellcat 旧单文件 HTML 单个约 34.5 MB，同时还有独立 candidate/ref WAV，产生大量重复。以后本地生成到：

`E:\Tesla_speed\review_packages`

Git 只保存 renderer、generator、server、参数/receipt、文档。
