# S12 真实车辆声音采集、物理声学仿真与负反馈标定方法论

> 版本：v3.0
> 更新时间：2026-09-06
> 当前声音基线：`main=f81d3a3aa1b32fcd35aa8b66a253492c70ed47b4`

## 1. 工程结论

Jovi 已实际试听确认 `f81d3a3` 的 Engine-Sim-inspired 四车型实现明显更接近真车，主观约 70–80% 相似。后续调音必须在该实现基础上增量优化，不能仅因代码架构更整齐就替换 renderer。

声音 authority：

`tools/sound_sim/s12/acoustic_identity_v015/stage_ad/engine_sim_acoustics.py::EngineAcoustics.render_track`

Stage AF 在它外围增加负反馈，不重写其核心发声链。

## 2. 真车 reference 收集与等级

### R1

合法原始 WAV/FLAC + 车型/原厂状态 + mic/recording metadata + synchronized RPM/load/gear。只有 R1 可以支持正式标定/OEM 级结论。

### R2

来源与权利受治理，但同步状态或录音链不完整。可做工程 comparator，不可称 OEM calibration。

### R3

公开视频/POV/私人诊断切片，统一状态 `R3_PRIVATE_DIAGNOSTIC_ONLY`。可做人耳 A/B 和 diagnostic fit；不可升级 R1/R2、不可自动作为产品音频资产。

推荐素材顺序：dyno controlled pull → track/autobahn onboard → stationary idle/rev → public-video diagnostic。

拒绝/降级：背景音乐、人声覆盖、明显 clipping、激进 AGC、未知改装直排、场景无法判断、严重 codec wall。

## 3. 十个统一场景

`afterfire, full_pull, hot_idle, idle_return, lift, shift, steady_high, steady_low, steady_mid, tip_in`。

所有车辆尽量使用同名场景，避免“每辆车挑最有利的片段”。

## 4. 当前有效物理声学链

```text
RPM / throttle trajectory
→ cylinder firing schedule
→ blowdown pressure event
→ bank assignment
→ runner / exhaust delay
→ pressure derivative + airflow/turbulence
→ exhaust transfer / IR convolution
→ mechanical/body resonance
→ supercharger/turbo/BOV identity layer
→ shift / lift / afterfire events
→ A/B audition PCM
```

### 关键经验

- 车型身份先由 firing geometry / combustion event 决定，不先画谐波；
- runner/path delay 提供自然相位与干涉；
- 40–150 Hz body 不要被激进 low-cut 删除；
- IR 对金属管壁/尾段/腔体感有效，但资产权利需单独治理；
- induction 是增强身份，不应盖住 exhaust body；
- transient 必须由车辆状态触发，不做随机贴片。

## 5. Stage AF 负反馈

旧 Stage-AD closed loop 没有驱动当前好听 renderer。Stage AF 改为：

```text
Reference
→ EngineAcoustics baseline
→ frequency-band / spectral / envelope features
→ fixed reference distance
→ bounded physical parameter family
→ re-render
→ shrink / plateau
→ existing A/B workbench
→ Jovi Human judgement
```

搜索范围故意小，只做手工好参数附近 refinement。

禁止优化 master/global/monitor gain。R3 distance 下降只表示 diagnostic feature 更接近，不代表 Human PASS。

## 6. 开源经验吸收

- AngeTheGreat `engine-sim`：事件域、点火几何、排气传播/声学结构，是当前好声音最重要架构来源；
- SSSSM-DDSP：吸收 real/synthetic domain gap 下的 audio/spectral-domain matching 思路；
- DDSP / DiffMoog / CMA-ES sound matching：作为未来 parameter proposal/warm-start 思想，不替换物理 renderer；
- VehicleNoiseSynthesizer：state/hysteresis/crossfade 生命周期；
- FFTConvolver：未来 Android/C++ 实时 IR；
- Oboe：未来 Android 低延迟 audio output。

## 7. 现有 A/B 工作台与 Stage AG-R1 严格路由

不开发新后台。继续使用：

- `review_packages/serve_dashboards.py`
- `stage_ad/audition_dashboard_template.html`
- `stage_ad/build_unified_dashboards.py`

`8080 portal / 8088 Hellcat / 8089 Ferrari / 8090 LFA / 8091 GT-R` 是 Stage AF 历史服务端口，不得作为 Stage AG-R1 的试听入口。Stage AG-R1 复用同一个富交互 HTML template 与 package bytes，但只能由 `stage_ag/serve_r1_review_strict.py` 提供：legacy 为 23380–23383，R1 为 23480–23483。它必须在任何 bind 前验证 exact manifest、自哈希、candidate/Reference WAV SHA、contract mode 和 rich HTML marker；一处 port collision 或 stale Stage-AE marker 即 fail-closed。

音频被 Base64 嵌入生成页面，A/B 可以热切换。当前模板样式仍引用远端 Tailwind runtime，因此“音频零依赖”成立，但严格断网下的完整样式不能假设永久可用；Stage AF 不重写 UI，仅保留这项已知技术债。

## 8. 生成物不进入 Git

四车 WAV、reference/web_audio 和巨型 Base64 HTML 都是可再生成物，统一放：

`E:\Tesla_speed\review_packages`

Git 只保存 generator/server/source/fit receipt/关键文档。这样减少 Cograph、clone、index 的负担。
