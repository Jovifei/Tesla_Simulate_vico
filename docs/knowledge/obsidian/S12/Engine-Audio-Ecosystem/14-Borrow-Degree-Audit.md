# 14 — Open-Source Borrow Degree Audit (2026-08-30)

Audited against:

- remote Stage W `7d4e49b52b73696af703a1380d83663208c5a897`
- remote/local Stage X `f1714b969ecd033e991e04cfc59df06a05e3685a`
- local research clones under `E:\Tesla_speed\research\engine-audio-ecosystem\`
- Stage X receipts in `tasks/reports/runtime/s12-stage-x/`

Verdict in one sentence: **infrastructure and research notes exist; the methods that make real engines sound like real engines were mostly not transferred into the renderer; that is why Jovi still hears synthesis.**

Scoring rules used below:

- **研究完成度**: checkout / README / license / build evidence in the registry.
- **架构借鉴度**: the method is present as S12 topology (event, path, map, state).
- **运行时落地度**: the method actually changes post-PTR PCM in the current Hellcat path.
- **禁止照搬**: code, weights, recordings, GTA assets, commercial binaries.

None of these percentages is OEM likeness. They measure method transfer, not sound quality.

## A. Tier-1 sources from the ecosystem memo

### A1. Engine-Sim (`ange-yaghi/engine-sim`)

- URL: https://github.com/ange-yaghi/engine-sim
- Pinned: `85f7c3b959a908ed5232ede4f1a4ac7eafe6b630` MIT
- Local clone: `E:\Tesla_speed\research\engine-audio-ecosystem\engine-sim`
- Knowledge: [[Open-Source-Engine-Sim]]
- 研究完成度: 85% (source studied; Docker/Windows build blocked on delta-studio)
- 架构借鉴度: 55%
- 运行时落地度: 35%
- 借鉴成功?: **部分成功（拓扑），未成功（物理保真）**

S12 已落地: continuous crank PLL; cylinder/rotor events; firing-order derived phase; per-path fractional delay; bank/collector; persistent 20 ms state; afterfire location routing. See `stage_w/persistent_engine.py`, `event_domain/event_scheduler.py`, `stage_w/waveguide.py`.

S12 未落地: constraint-solved crank/rod/piston; gas_system mass/momentum; valve flow; IR convolution; pressure-derivative mix; jitter/noise chain; leveling filter. Engine-Sim values are not used as OEM truth.

可参考位置: event → chamber pulse → per-cylinder primary delay → collector. 禁止参考: C++、`.mr` 车型脚本、IR、音频、OEM 声明。

### A2. ENSIM4 (`glouw/ensim4`)

- URL: https://github.com/glouw/ensim4
- Pinned: `35b92a6aa5e038d18769d637dc9bedf0346939e1` MIT
- Knowledge: [[Open-Source-ENSIM4]]
- 研究完成度: 80% (Docker CFD ON/OFF captured)
- 架构借鉴度: 20%
- 运行时落地度: 8%
- 借鉴成功?: **否（仅 teacher 残差，不是 1D CFD）**

S12 已落地: `stage_w/teacher_response.py` `reduced_cfd_teacher_v1` uses an RMS/centroid ratio. Bake-off P6 is `TEACHER_NOT_RUNTIME_CANDIDATE`.

S12 未落地: 128-cell conservation variables; flux; 8 substeps; microphone sample of a real pipe; CFD ON/OFF as a fitted waveguide.

可参考位置: 离线教师模型、CFD ON/OFF 消融方法。禁止: 直接替换 frozen FVM/HLLC/SSP-RK3/PTR。

### A3. PTR Model (`rdoerfler/ptr-model`)

- URL: https://github.com/rdoerfler/ptr-model
- Paper: https://arxiv.org/abs/2603.09391
- Pinned: `af026403458309b3a27dcdc0320ddb485033d4aa` CC BY-NC 4.0
- Knowledge: [[Open-Source-PTR-Model]] [[Papers-PTR-EONE-DDSP]]
- 研究完成度: 70% (source parse; weights absent)
- 架构借鉴度: 25%
- 运行时落地度: 10%
- 借鉴成功?: **否（没有 analysis-by-synthesis 拟合）**

S12 已落地: per-cylinder pulse envelope (rise/decay); bank split; frozen S12 PTR/Radiation adapter (different “PTR”: this is the Tesla radiation package, not the paper model).

S12 未落地: differentiable Karplus-Strong exhaust; learned delay/reflection; DFCO turbulence residual; export of fitted weights to C++.

许可证: 研究可看；商业 Runtime 不得复制代码/权重/数据。

### A4. VehicleNoiseSynthesizer

- URL: https://github.com/ATG-Simulator/VehicleNoiseSynthesizer
- Pinned: `4241caca5a18be0d47f0b8586df93b1b42d7020d` MIT (recordings separate)
- Knowledge: [[Open-Source-VehicleNoiseSynthesizer]]
- 研究完成度: 75%
- 架构借鉴度: 15%
- 运行时落地度: 5%
- 借鉴成功?: **否**

S12 未落地: RPM/load clip banks; constant-power crossfade; cylinder-aware pair hold; OnThrottleTipIn / TipOut / GearShift residual layers; hysteresis.

当前 P5 只是 clean-room synthetic one-shot，不是 VNS 录音分层。

可参考位置: 状态机合同、equal-power crossfade、迟滞。禁止: 其录音/NWH 资产、Unity 工程导入。

### A5. Fubos Engine Sound

- URL: https://brillabsolutions.github.io/Fubos/
- License: commercial Unity EULA
- 研究完成度: 40% (public docs only)
- 架构借鉴度: 30%
- 运行时落地度: 15%
- 借鉴成功?: **形状有了，内容没有**

S12 已落地: `stage_w/timbre_map.py` RPM×Load×Boost×Order table.

S12 未落地: 从一条干净拉转录音自动追踪谐波并压缩为 `.eng` 地图。当前 `TimbreMap4D.default()` 是解析公式 `(0.22+k*rpm)*(0.35+0.65*load)*...`，不是 Ferrari/Hellcat 实车谐波。

这是听感仍像合成器的直接原因之一。

### A6. Crankcase REV

- URL: https://www.crankcaseaudio.com/
- 研究完成度: 30%
- 架构借鉴度: 5%
- 运行时落地度: 0%
- 借鉴成功?: **否。P4 未实现。**

`stage_w/bakeoff.py` 将 P4 固定为 `REFERENCE_RECORDING_RIGHTS_PENDING`。没有 cycle-synchronous 录音重合成 renderer。

可参考位置: 工作流（频域变速、循环级对齐）。禁止: 二进制、模型、评估输出、逆向。

### A7. AudioMotors

- URL: https://lesound.io/product/audiomotors-pro/
- 研究完成度: 30%
- 架构借鉴度: 5%
- 运行时落地度: 0%
- 借鉴成功?: **否**

未实现: 从含噪录音估计 RPM；engine/exhaust/interior 共用同一曲轴时钟；cycle-synchronous 多麦对齐。

### A8. FiveM Engine Sound Simulator

- URL: https://github.com/MushroomFleet/Fivem-EngineSound-Simulator
- Knowledge: [[Open-Source-FiveM-License-Boundary]]
- 研究完成度: 80% (npm build passed)
- 架构借鉴度: 10% (schema 记录)
- 运行时落地度: 0%
- 借鉴成功?: **正确拒绝**

Apache-2.0 文件与 README MIT 冲突。GTA/FiveM 音频禁止进入仓库。可参考的只有层名（Idle / OnLoad / OffLoad / Gear Wobble），且尚未做成 S12 状态层。

## B. Secondary open-source

### DasEtwas/enginesound

- 研究 70% / 架构 25% / 运行时 15%
- 借鉴: waveguide + chamber 想法进入 `waveguide_v1`
- 未借鉴: resonance warm-up before capture。S12 短片段仍可能从全零 delay 状态开始。
- Cargo TLS 阻塞，无 warmup WAV 证据。

### ESP32 RC Engine Sound (`TheDIYGuy999/Rc_Engine_Sound_ESP32`)

- 无 LICENSE → all-rights-reserved
- 研究 50% / 运行时 0%
- 可参考: 嵌入式分层与缓冲。禁止复制源码和采样数组。

### Jonas-Hack Granular Engine Audio

- 无 LICENSE
- 研究 50% / 运行时 0%
- 可参考: grain 调度、低幅切断、crossfade 概念。禁止 C# 和录音。

### yoshiomiyamae/engine-sound-simulator

- **仓库不存在。** 2026-08-30 复查 `https://github.com/yoshiomiyamae`：公开仓库无 engine-sound-simulator。先前备忘把一个未验证名字写进了任务 Prompt。不得再当作可借鉴工程。

## C. Recursive search finds that were missing from Stage W registry

These were found by following Engine-Sim / VNS README alternatives / GitHub related projects. They must be studied in Stage Y; they are not yet borrowed.

| Source | Why it matters | License | S12 action |
|---|---|---|---|
| `markeasting/engine-audio` | MIT WebAudio **soundbank** engine; RPM/throttle loops. Was listed in Stage U prompt but never registered. | MIT (check sample rights separately) | Study schema only; do not import third-party samples |
| `xevrion/ignis` | Engine-Sim inspired **clean-room** C++: constraint solver + lumped gas + delay-line pipes + DC / dP chain | check LICENSE on checkout | Highest-value next physical-audio read after Engine-Sim |
| `MeFisto94/engine-sound-sim` | Rust pressure-wave procedural library, realtime-oriented | check LICENSE | Secondary waveguide read |
| `Engine-Simulator/engine-sim-community-edition` | Binary distribution of Engine-Sim; no extra source | not a code source | Listen/compare only, no import |
| GameSynth Engines (Tsugi) | Commercial procedural engine model | proprietary | Public workflow only |
| VNS README also lists Realistic Engine Sounds, RevHeadz, FMOD | product category proof that hybrid sample+granular is industry default | various | Do not copy assets |

## D. Commercial workflow references (docs only)

Igniter / Igniter Live / Nemisindo / QNX ESE / EVx / Ansys Sound / neosonic: **研究 25–40%，运行时 0%。**

共同可参考、且 S12 仍缺的结构:

1. engine + exhaust + intake 分层，而不是一条 PCM 包打天下
2. granular / one-shot / synth 混合，而不是坚持纯物理
3. 桌面调音定义与 Runtime 共用同一 profile
4. 真实录音残差层

S12 目前更接近“纯事件物理 + 合成 timbre 公式 + 合成 one-shot”。这正好是工业界已经放弃的单一路线。

## E. Why the local sound still does not match real vehicles

Measured, not opinion:

1. Hellcat X5 round-1 objective vs Parent: P2H **−13.1%**, P3/P5 **−4.2%** (worse or not 15% better).
2. Hellcat X5 round-2 after structural redesign: P3 **+3.4%**, still below 15% gate. Status `NO_MEASURABLE_IMPROVEMENT_AFTER_REDESIGN`.
3. Ferrari diagnostic search: P2H **−1289%** relative error scale on the gate metric (candidate much worse than Parent on bound scenes).
4. RX-7: 0 valid references (speech). Fail-closed. Correct.
5. Reachability: **11/27** parameters actually move target metrics. Unreachable includes crank inertia, idle governor, blower mixes, boost attack/release, afterfire family, monitor family.
6. Hellcat bound references are only `hot_idle, steady_low, steady_mid, steady_high`. Tip-in, full pull, shift, lift, afterfire have **NaN** on those dimensions — the search cannot hear the problems Jovi named.
7. Timbre map is a synthetic formula, not a recording-derived harmonic map.
8. P4 (real cycle-sync resynthesis) is a placeholder.
9. P5 equals P3 metrics in round 1 — synthetic residual did not change the objective.
10. `roughness` movement is 0.0 in the reachability probe for several event parameters: the roughness proxy is not a useful search signal yet.

Jovi 听感对照（历史反馈，仍有效）:

- Ferrari 身份 30 / 真实感 10
- Hellcat 身份 60 / 真实感 50；缺低频冲击、机械感、固定电子哨、回火不自然
- RX-7 参考含人声，原评审无效

这些问题无法靠再搜 64 个 gain 解决。缺的是录音残差、谐波地图拟合、状态颗粒层，以及让 afterfire/blower 参数真正可达。

## F. Local completion vs the Stage X contract

| Stage X item | Status | Honest label |
|---|---|---|
| X0 remote/local reconcile | PASS | Local 8637e62 is unpushed Stage W; Stage X branched from it. Remote Stage W remains 7d4e49b |
| X1 split engineering vs formal gates | PASS | `selection_eligible` is data-driven, no longer hardcoded false |
| X2 ReferenceCaseSet | PASS with gap | Hellcat only bound 4 steady/idle scenes |
| X3 multi-reference comparator | PASS | Exists; several dimensions NaN without matching refs |
| X4 reachability | PASS as measurement | 11/27 reachable — gate passed as a probe, not as a capable search space |
| X5 Hellcat preselection | PASS as process | **No architecture selected** |
| X6 Ferrari/RX-7 | PARTIAL | Diagnostic search only; Ferrari worse; RX-7 no ref |
| X7 review package | PASS | `E:\Tesla_speed\review_packages\s12-stage-x-r2-engineering-selection-v1` |
| X8 R1 fixture | PASS | Fixture-only; formal selection still null |
| X9 Obsidian | PASS | This note is the missing borrow-degree page |
| Sound realism proven | NOT_PROVEN | Do not claim improvement |
| Profile freeze | NOT READY | Correct fail-closed |

Remote test number that may be cited: Stage X HEAD must re-run pytest to quote a number. Do not reuse 1015 or 1205 in new claims without a new receipt on the exact HEAD.

## G. What to borrow next (priority, not a new implementation in this audit)

1. **Fubos/PSOLA/REV method, clean-room**: extract HarmonicTimbreMap from rights-cleared R2 pull recordings. Replace `TimbreMap4D.default()` formula.
2. **VNS/Igniter method**: idle / on-load / off-load / exhaust / intake stems + equal-power crossfade + tip-in/out/shift one-shots. Still synthetic-or-R2, never GTA.
3. **Engine-Sim / ignis method**: pressure derivative + IR/jitter-equivalent clean-room, and delay-line pipe resonances that stay warm across blocks (DasEtwas warmup).
4. **PTR-paper method, clean-room**: analysis-by-synthesis pulse width / bank resonator fit on R2. Do not import CC BY-NC weights.
5. **ENSIM4**: keep teacher-only; fit waveguide loss/length to CFD ON/OFF, do not run CFD on device.
6. **Fix reachability** before another 64-candidate search: blower, afterfire, inertia, governor, monitor must move the metric they claim.

Until (1)+(2) exist, further gain search on P2H/P3/P5 will keep producing “tests pass, ears say synth”.
