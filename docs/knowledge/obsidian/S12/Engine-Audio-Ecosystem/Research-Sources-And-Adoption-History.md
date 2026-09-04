---
stage: S12-research-memory
type: source-history
updated: 2026-09-04
status: ACTIVE
---

# S12 参考论文、开源项目与方法吸收历史

> 本文是长期检索入口，回答四个问题：
>
> 1. 我们到底研究过哪些来源？
> 2. 从每个来源学了什么？
> 3. 哪些方法真正进入本地实现？
> 4. 哪些代码、音频、权重、商业资产明确不能复制？
>
> 主证据来自 `S12_Handoff_Package_2026-09-03` 与仓库 `source_registry.json` / `method_adoption_matrix_v3.json`。

---

# 1. 研究原则

Stage Z 之后，来源吸收必须形成：

```text
Source
→ Method
→ Local implementation
→ Runtime call path
→ Test
→ OFF/ON / ablation
→ PCM change
→ Metric / evidence
```

因此“看过某项目”不等于“采用了某项目”。

同时始终区分：

- code license；
- audio/media rights；
- model weights rights；
- commercial runtime rights；
- paper copyright；
- method idea。

公共可下载 != 可进入产品。

---

# 2. 核心开源项目

## 2.1 Engine-Sim

Repository：
`https://github.com/ange-yaghi/engine-sim`

Pinned commit：
`85f7c3b959a908ed5232ede4f1a4ac7eafe6b630`

License：MIT。

项目中的主要方法启发：

- event/cylinder pressure packet；
- crank/cycle state；
- per-cylinder/per-path propagation；
- bank / collector topology；
- forced-induction state / shaft phase；
- persistent processing；
- pressure-to-audio chain；
- engine topology 与声音事件之间的因果关系。

本地 clean-room/equivalent 方向：

- `event_domain/event_scheduler.py`
- `event_domain/chamber_event.py`
- `event_domain/collector_network.py`
- `event_domain/forced_induction.py`
- `stage_w/persistent_engine.py`
- `stage_w/waveguide.py`

重要边界：

- 不复制 C++ 源码；
- 不复制 `.mr`；
- 不复制 IR / recordings / presets / assets；
- Engine-Sim 不是 OEM truth。

历史意义：这是从早期 fixed-harmonic synth 转向 event-domain architecture 的最核心来源。

---

## 2.2 ENSIM4

Repository：
`https://github.com/glouw/ensim4`

Pinned commit：
`35b92a6aa5e038d18769d637dc9bedf0346939e1`

License：MIT。

定位：

`REFERENCE_TEACHER_ONLY`

研究价值：

- 1D CFD / pressure-pipe response；
- combustion/exhaust 压力传播思想；
- 用更重物理模型作为 teacher/诊断参照；
- CPU/runtime feasibility experiment。

明确不做：

- 不直接把 ENSIM4 solver 塞进 Android；
- 不把 CFD teacher 直接提升成 mobile runtime；
- 不因为 solver 更“物理”就允许破坏实时产品约束。

历史结论：**teacher system 与 product runtime 必须分离。**

---

## 2.3 VehicleNoiseSynthesizer

Repository：
`https://github.com/ATG-Simulator/VehicleNoiseSynthesizer`

Pinned commit：
`4241caca5a18be0d47f0b8586df93b1b42d7020d`

License：MIT code；recordings/integrations 权利单独处理。

吸收：

- state scheduling；
- hysteresis；
- equal-power crossfade；
- transition/latch lifecycle；
- RPM/load clip-bank 的状态思想。

本项目不是简单 sample bank 产品；借鉴的是**状态切换与连续性工程**。

禁止：

- 不复制其 recordings / NWH assets；
- 不把 clip-bank 架构直接替换 current S12 source truth。

---

## 2.4 DasEtwas / enginesound

Repository：
`https://github.com/DasEtwas/enginesound`

Pinned commit：
`e5fcca587397c0c8ba9c9d24874b951fed74d260`

License：MIT + separate font/asset notices。

吸收：

- stateful waveguide lifecycle；
- warmup；
- loop continuity；
- chamber/path persistent state。

本地对应：

- `stage_w/waveguide.py`
- `stage_y/audio_chain_dp.py`

Stage AA ablation 结论：有 causal contribution，但部分指标 engineering significance 较弱；所以它是“有贡献的方法”，不是单独的真实性答案。

禁止复制 Rust source / presets / example audio / GUI assets。

---

## 2.5 Ignis

Repository：
`https://github.com/xevrion/ignis`

Pinned commit：
`a618baeede8caed46ada304ed06c4ea01a835aa6`

License：tracked tree 未发现明确 LICENSE，按 all-rights-reserved 边界处理。

只吸收公开方法语义：

- simulation-coupled cylinder pressure；
- pressure-domain source context；
- DC / dP / filter lifecycle；
- per-sample exhaust synthesis 的概念。

禁止：

- 不复制 C++；
- 不复制 demo media/assets；
- 不做 OEM claim。

---

## 2.6 Markeasting / engine-audio

Repository：
`https://github.com/markeasting/engine-audio`

Pinned commit：
`b8cf9887c914f17c2f006d68427080e39d02d0b0`

Repository code license：MIT。

风险：individual audio rights 未验证。

吸收：

- browser engine-audio demo 的高层 state/layer authoring 思路；
- authoring 与运行时层次组织。

禁止：

- 不复制 TypeScript/source；
- 不复制 public WAV；
- 不复制 recordings/presets/assets。

历史意义：再次确认“代码 License 与音频素材 rights 是两件事”。

---

## 2.7 Granular Synthesis for Engine Audio

Repository：
`https://github.com/Jonas-Hack/Granular-Synthesis-for-Engine-Audio`

Pinned commit：
`d27967bea639feea1fb8429a7dbfb42cb9bd508f`

License：未找到，按 all-rights-reserved。

只学习：

- grain scheduling；
- low-amplitude cut；
- crossfade。

禁止复制 C# 和 recordings。

---

## 2.8 FiveM EngineSound Simulator

Repository：
`https://github.com/MushroomFleet/Fivem-EngineSound-Simulator`

Pinned commit：
`f0c12aa5a09d56344f9d96ce989299e900d76b70`

许可证问题：Apache-2.0 文件与 README MIT claim 冲突。

只学习：

- layer/state schema。

禁止：

- license 未澄清前不复制代码；
- GTA/FiveM assets 不进入产品。

---

## 2.9 Rc_Engine_Sound_ESP32

Repository：
`https://github.com/TheDIYGuy999/Rc_Engine_Sound_ESP32`

Pinned commit：
`5520d721ef41b50f39dfe9a7081ac4620138702a`

License：未找到。

研究过：

- embedded state；
- buffer；
- voice layering。

禁止：

- source；
- audio arrays；
- hardware assets。

当前更重要的结论：ESP32 项目仅作为方法边界/历史参考，当前产品路线已经是 Android App，不因为研究过该项目就回到 ESP32。

---

## 2.10 ptr-model

Repository：
`https://github.com/rdoerfler/ptr-model`

Pinned commit：
`af026403458309b3a27dcdc0320ddb485033d4aa`

License：CC BY-NC 4.0。

研究：

- pressure pulse；
- resonator；
- engine-order loss；
- PTR 相关响应思想。

边界：非商业许可证，不允许其 code/data/weights 进入商业 product runtime。

---

# 3. 关键论文 / 技术文章

## 3.1 Physically informed car engine sound synthesis for virtual and augmented environments

Authors：Stefano Baldan, Hélène Lachambre, Stefano Delle Monache, Patrick Boussard。

Year：2015。

DOI：
`10.1109/SIVE.2015.7361287`

研究意义：

- procedural + physically informed engine sound；
- intake/exhaust/source 分离；
- 说明实时发动机声音不一定必须完全依赖 sample bank；
- 支撑本项目“物理启发但 runtime 可控”的架构方向。

项目内 mapping：

`digital waveguide source/intake/exhaust split`

边界：论文思想可研究，录音/代码/参数必须单独确认 rights。

---

## 3.2 Sample-based engine noise synthesis using an enhanced pitch-synchronous overlap-and-add method

Authors：Jan Jagla, Julien Maillard, Nadine Martin。

Journal：Journal of the Acoustical Society of America。

Year：2012。

DOI：
`10.1121/1.4754663`

研究意义：

- engine-cycle aligned sample extraction；
- pitch-synchronous overlap-and-add；
- cycle continuity；
- arbitrary RPM evolution 下的实时重合成；
- 低计算负担。

项目内 mapping：

`cycle-aligned grains and phase continuity`

本项目没有转成纯 PSOLA 产品，但该论文影响了 cycle-sync / grain / continuity 的思考。

---

## 3.3 Toward a cylinder pressure signals-based active synthesis algorithm for engine sound

Authors：Liping Xie, Zhien Liu, Chihua Lu, Yawei Zhu, Weizhi Song。

First online：2022；期刊卷期 2023。

DOI：
`10.1177/09544070221078399`

研究方法：

- cylinder-pressure periodicity；
- grain index matrix；
- RPM-traced frame length/shift；
- Hamming-window extraction；
- overlap-and-add；
- real-time driving-status feedback；
- continuity evaluation。

项目内 mapping：

`pressure grain indexing / OLA`

本地研究边界：workflow/reference only，不对未完整复现的方法做“已实现”宣称。

---

## 3.4 Gradient-Based Learning of Parametric Engine Sound Representations for Real-Time Resynthesis and Tuning on Embedded Systems

Authors：Robin Doerfler, Matthieu Kuntz, Clemens Zimmer。

arXiv：
`2606.21521`

Submitted：2026-06-19。

项目 registry id：`eone`。

研究意义：

- per-order + broadband timbral variation；
- RPM/torque operating range；
- compact parameter representation；
- gradient-based analysis-by-synthesis；
- 参数可手工调节；
- 参数可以转到传统 DSP / embedded target。

项目内 mapping：

`RPM/torque lookup timbre maps`

重要启发：**authoring/training 可以重，runtime 参数可以轻**。

边界：paper 为 CC BY-NC-ND 4.0；产品数据/权重/EVx 生态属于额外 proprietary boundary，不直接使用私有数据/weights。

---

## 3.5 DDSP-Based Neural Vehicle Sound Synthesis from Driving Signals

Authors：Minsuk Choi, Dabin Kim, Daehun Song, Juhan Nam。

Venue：AES International Conference on Automotive Audio 2026。

Project page：
`https://dabinkim0.github.io/publications/ddsp-carsound/index.html`

研究意义：

- driving-signal conditioned sound synthesis；
- 比较 RPM；
- RPM + gear + pedal；
- RPM + gear + pedal + speed + acceleration；
- direct/encoded conditioning；
- F0 crank-based vs firing-based。

项目内 mapping：

`RPM/gear/pedal/speed/acceleration ablation`

与当前 App 路线的关系尤其重要：它证明 speed / acceleration 等车辆运动信号是合理的声音条件变量，但本项目当前不直接复制 neural model/data/weights，而是用 speed + acceleration 驱动自己的 VirtualEngineState + S12 source engine。

数据/weights rights 未建立，不进入 runtime。

---

## 3.6 An On-Line, Order-Based Roughness Algorithm

SAE Technical Paper：2007-01-2397。

DOI：
`10.4271/2007-01-2397`

研究意义：

- engine-order based roughness；
- 由 order amplitude / phase / frequency 重建 critical-band envelope；
- 实时 roughness diagnostics；
- 将 perceptual roughness 与具体 engine order 联系起来。

项目内 mapping：

`order roughness diagnostic`

边界：SAE publication copyright；公式/数据再分发遵守出版许可。

---

# 4. 商业/专有系统：只学习公开 workflow

## 4.1 Fubos

`https://brillabsolutions.github.io/Fubos/`

研究：

- harmonic map authoring；
- zero-allocation DSP concept。

禁止：code / `.eng` / presets / UI / assets。

---

## 4.2 Crankcase REV

`https://www.crankcaseaudio.com/`

研究：

- cycle-synchronous recorded resynthesis concept。

禁止：binary/model/audio/evaluation outputs。

---

## 4.3 AudioMotors Pro

`https://lesound.io/product/audiomotors-pro/`

研究：

- recording-driven RPM/granular workflow。

禁止：binary/sample banks/reverse engineering。

---

## 4.4 Krotos Igniter

`https://www.krotosaudio.com/igniter/`

研究：

- hybrid granular / synth / one-shot authoring workflow。

禁止：plugin / presets / WKEP / recordings。

---

## 4.5 Nemisindo

`https://nemisindo.com/documentation/unity-engine`

研究：

- low-parameter procedural runtime API；
- 游戏/实时运行时如何暴露少量控制参数。

禁止：native binaries / presets / UI。

---

## 4.6 QNX ESE

`https://www.qnx.com/content/qnx/cn/products/acoustic/ese.html`

研究：

- authoring / runtime separation；
- additive + granular layers。

禁止：runtime/profiles/recordings。

---

## 4.7 EVx Suite

`https://evx-suite.com/`

研究：

- desktop authoring → embedded module boundary；
- authoring representation 与 deployment DSP 分离。

禁止：embedded libraries / templates / undocumented algorithms。

---

## 4.8 Ansys Sound / PyAnsys Sound

Ansys：
`https://www.ansys.com/en-gb/products/acoustics-analysis/ansys-sound`

PyAnsys：
`https://sound.docs.pyansys.com/`

研究：

- measurement / simulation / psychoacoustic workflow；
- Python analysis orchestration。

边界：Ansys core proprietary；PyAnsys wrapper MIT 不代表 licensed core/data 可自由使用。

---

# 5. 25 个 registry source 总览

当前 source registry 记录的长期来源包括：

1. engine-sim
2. ensim4
3. dasetwas-enginesound
4. granular-engine-audio
5. fivem-enginesound
6. esp32-rc-engine-sound
7. ptr-model
8. sive-2015
9. psola-2012
10. cylinder-pressure-ola
11. eone
12. ddsp-vehicle
13. sae-roughness
14. vehicle-noise-synthesizer
15. fubos
16. crankcase-rev
17. audiomotors-pro
18. krotos-igniter
19. nemisindo
20. qnx-ese
21. evx-suite
22. ansys-sound
23. pyansys-sound
24. ignis
25. markeasting-engine-audio

Registry 之外如果后续新增来源，必须先：

- 写 source_registry；
- 固定 URL/version/commit；
- 明确 license；
- 明确 adoption boundary；
- 明确 copied_source/audio/weights = false/true；
- 才进入方法吸收。

---

# 6. 哪些方法真正影响了本地实现

高影响：

### Engine event / pressure

主要来自 Engine-Sim + physically-informed literature。

本地：event scheduler / chamber packet / persistent engine。

### Persistent phase/state

来自 Engine-Sim / DasEtwas / 自己的 continuous engine state 需求。

本地：persistent engine + snapshot/restore。

### Path / bank / collector / waveguide

来自 Engine-Sim / DasEtwas / physically-informed paper。

本地：collector network / waveguide / persistent path state。

### Forced induction

受 Engine-Sim state concept 影响，结合自己的 Hellcat identity 需求。

### State transitions

VehicleNoiseSynthesizer 对 hysteresis/crossfade/lifecycle 的工程思想有价值。

### Cycle synchronous / grains

PSOLA、cylinder pressure OLA、commercial resynthesis workflow 提供概念参考。

### dP / DC / pressure audio

Ignis / physics-informed pressure workflow / 本地 Track-P 约束共同形成当前 dP/DC chain。

### Timbre maps

EONE / Fubos / commercial authoring workflow 提醒我们：高维重模型可以压缩成 runtime 参数合同；当前 fitted timbre map 是本地实现，不复制其专有模型。

### Driving-signal conditioning

DDSP vehicle paper 对 RPM/gear/pedal/speed/acceleration 的条件变量分析，为当前 App speed+acceleration→VirtualEngineState 路线提供研究背景；本项目采用自己的 deterministic state model，而不是其 neural weights。

---

# 7. 已证明“有因果改变”不等于“值得保留”

Stage AA/Z 已明确区分：

```text
causal effect
engineering significance
quality direction
```

一个方法可能：

- OFF/ON 确实改变 PCM；
- 但变化非常小；
- 或没有合法 Reference 判断方向；
- 因此不能只因为“有 effect”就进入最终 profile。

例如部分 collector/waveguide 方法有 causal effect，但在某些 metric 上低于 engineering significance floor。

这个结论必须长期保留，避免未来 Agent 把 method count 当质量。

---

# 8. 许可证/权利长期规则

## MIT / permissive

也要 clean-room 或明确 import policy；尤其 audio assets 单独审查。

## No LICENSE

默认不能复制代码/音频；只能学习公开思想。

## License conflict

在冲突解决前不复制。

## CC BY-NC

不能直接进入商业产品 runtime。

## Commercial / proprietary

只读公开 docs/workflow；不复制 binary / preset / internal implementation。

## Audio Rights

最重要：

```text
repository code license != recording rights
```

公共 WAV 不因“能下载”自动成为产品资产或 R1。

---

# 9. 现在不要继续扩大研究数量

交付包已明确：

> 当前 open-source research 已够。

下一阶段主要瓶颈：

```text
声音实际是否更真实
→ Jovi Human Gate
→ App Runtime
```

因此新 Agent 默认不应再做“第 26/27/28 个 engine sound repo 调研”。

只有出现明确能力缺口，例如：

- 当前 source model 无法解决某个 human feedback；
- Android realtime 出现特定 DSP 问题；
- R1 calibration 需要新的专业方法；

才允许有目标地新增来源。

---

# 10. 证据文件索引

```text
docs/research/engine-audio-ecosystem/source_registry.json
docs/research/engine-audio-ecosystem/source_evidence_receipts.json
docs/research/engine-audio-ecosystem/source_coverage_matrix.json
docs/research/engine-audio-ecosystem/method_adoption_matrix_v2.json
docs/research/engine-audio-ecosystem/method_adoption_matrix_v3.json
docs/research/engine-audio-ecosystem/license_matrix.md
THIRD_PARTY_NOTICES.md
```

声学方法是否真正有效，还要结合：

```text
tasks/reports/runtime/s12-stage-z/method_ablation_scorecard.json
tasks/reports/runtime/s12-stage-aa/method_ablation_scorecard_v2.json
```

---

# 11. 长期结论

目前最值得继承的不是某个开源项目代码，而是这套工程纪律：

```text
明确来源
→ 明确 license
→ 明确借鉴 method
→ clean-room implementation
→ runtime reachability
→ OFF/ON causal proof
→ engineering significance
→ reference/human quality direction
→ versioned product profile
```

这套链比“复制一个看起来像发动机声音的项目”更重要，也是 S12 从实验走向 App 产品化的核心资产。
