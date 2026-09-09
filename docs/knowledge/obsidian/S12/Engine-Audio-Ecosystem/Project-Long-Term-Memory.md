---
type: canonical-project-memory
updated: 2026-09-09
status: ACTIVE
current_product_direction: APP_FIRST
current_acoustic_stage: STAGE_AG_R1_STRICT_RICH_REVIEW
esp32_status: DEFERRED_FUTURE_OPTION
---

# Tesla Simulate Vico / S12 项目长期记忆

## 1. Evidence rule

用户明确指定历史认知：`S12_Handoff_Package_2026-09-03` ≈90%，旧聊天/此前总结 ≈10%。动态 SHA/PR/CI/code 以当前 GitHub 为准，当前用户决策优先。

## 2. 最终目标

先把发动机声音算法做到真实、连续、车型可辨识，再做成车内 Android App：

```text
speed + acceleration
→ VirtualEngineState
→ selected Vehicle Profile
→ S12-derived realtime sound
→ Android playback
```

App 内推导 virtual RPM/load/gear/shift/lift/overrun。CAN/OBD 是 future richer adapter。ESP32 当前不做。

最终用户不是在听“随速度变调的音色”，而是在听一个具有持续 crank/event、负载、机械、进排气/增压、换挡、收油、回火生命史的虚拟发动机。

## 3. 完成度不能混

A 软件正确：persistent/block/snapshot/deterministic/no clipping/click/tests/Track-P。

B 工程方法正确：source/license、clean-room、runtime reachability、ablation/causality。

C 声学有效：指标/reference 支持真实感方向改善。

D Human accepted：Jovi 人耳通过。

E R1 qualified：合法同步真实数据支持正式 calibration。

当前 A/B 较成熟，C 部分完成，D/E 未完成。

## 4. 历史路线

### v0.9/v0.15

fixed harmonics/resonators/procedural whine/post-EQ 能出声音，但 idle、LF、afterfire、车型身份合成感强。结论：不能继续靠谐波/EQ 堆真实感。

### Stage V

event-domain prototype：crank phase、cylinder/rotor event、combustion packet、fractional delay、localized afterfire、forced induction、Raw/Monitor separation。

### Stage W

`PersistentEventDomainEngine`、20 ms continuity、snapshot/restore、per-cylinder path、bank/collector、waveguide、frozen PTR adapter。

### Stage X

ReferenceCaseSet、multi-reference comparator、parameter reachability、candidate search、engineering/formal gate split。

### Stage Y

fitted timbre map、cycle-sync、state transients、dP/DC、source reachability、reference governance、closed-loop building blocks。16/16 fitted-map parameters 曾验证 bidirectional reachability。

### Stage Z

确立：`Source→Method→Local implementation→Runtime path→Test→OFF/ON→PCM→Metric/Evidence`。研究从“看过”升级为“可证明采用”。

### Stage AA

Hellcat 声学收口。AA-C3 相对 Stage-Z 在 RMS/dynamic/centroid/roughness/sharpness/tone 等自动指标明显改善，生成 v3 blind package。但 LF、blower、afterfire 和 broad pre-PTR provenance 仍有风险，未 Human PASS。

官方 V3：`E:\Tesla_speed\review_packages\s12-stage-aa-hellcat-quality-v3`，manifest `b1ea99d36179229ff7d31f30f4790b6b84d8af587c14d44398e8e595f5f0964f`；禁止覆盖。

### Stage AB / AB-R

证明 AA-C3 RMS recovery 主要来自 event-body，但 broad scale 仍占显著部分；P6 被纠正为 counterfactual residual，不是 source stem。修正 LF persistence v1、blower audible-path、dynamic timing/NOT_MEASURABLE 等指标语义。

### Stage AC

解决 cross-platform/CI/Track-P/fixture/measurability；AC6/AC7 已有历史 PASS，AC8 仍需正式 post-merge pre-human receipt。

### Stage AD — 当前新增

用户要求把“生成声音→与真实声比较→反馈参数→再生成”的负反馈系统真正闭合。

Stage AD 增加：

```text
Governed Reference
→ AA-C3-aware render
→ fixed absolute reference distance
→ source-causal parameter family search
→ recenter + shrink
→ repeat
→ audition
```

当前远端已经有 controller、AA-C3 config injection、fixed ruler、body/blower/afterfire family、staged config handoff、audition package/dashboard、Simulink validator/bridge、tests。

但 `tasks/reports/runtime/s12-stage-ad/execution_state.json` 在 2026-09-05 审计时仍是 `LOCAL_REFERENCE_EXECUTION_PENDING`；不要把 dashboard 示例数值当正式 run receipt。

## 5. 当前 Hellcat 风险

- hot-idle LF 可能 elevated/boomy；
- blower 存在约 741 Hz carrier，需要判断机械增压身份还是电子蜂鸣；
- afterfire 相对 body 过强曾是 red flag；
- complete-cycle dynamic 仍可能比 Parent 压缩。

因此调参必须 source-causal，并最终由 Jovi 听。

## 6. Stage AD tuning discipline

优先：`body → blower → afterfire`。

禁止 master/global/broad-pre-PTR gain、monitor makeup、P6 residual scaling 充当 source repair。

跨轮使用 fixed `absolute_reference_distance`；changing-parent `improvement_fraction` 只作当轮诊断。

每个真正 source-causal candidate 应能追到：parameter intervention→first changed source/layer→downstream PCM→metric/guard。

## 7. Reference / rights

R1 仍缺失。R2/R3 是工程/诊断材料。

最新分支新增 `extract_reference_audio.py` 和 A/B dashboard。其存在不改变权利规则：经用户明确授权且合法使用时，只产生 `R3_PRIVATE_DIAGNOSTIC_ONLY` 人耳参考；默认不得进入自动 optimizer、不得产品分发、不得升级 R2/R1。

## 8. Simulink

历史 v0.9 binary 已知 structurally invalid/compile fail。Python S12 是 authority。Stage AD 只提供 fixed dimension contract、validator 和 bridge；本地修复必须在复制 candidate 上完成，并经 Update Diagram/simulation/PCM/Python equivalence 才算 verified mirror。

## 9. 已解决且不要重复调查

Windows review-package path、Track-P ancient-base whitespace false positive、generated CRLF、receipt merge-base 规则、旧 failure-count 误读、P6 source-stem 误分类、LF v1、blower v1、fake 0-ms timing、changing-parent closed-loop ruler、跨-ref CI concurrency。

## 10. 当前项目路线

```text
remote/CI/AC8 governance
+ Stage AD local reference loop
→ Jovi listening/Human decision
→ Hellcat Engineering Profile
→ Ferrari/RX-7
→ Vehicle Profile schema
→ AudioParameterPackage
→ Golden speed/acceleration + state + PCM
→ portable C++
→ Python↔C++ equivalence
→ Android NDK + Oboe/AAudio
→ in-car validation
→ R1 formal calibration when available
```

## 11. Android product principles

- App minimum inputs=`speed + acceleration`；
- VirtualEngineState 在 UI/audio callback 之外的 state layer 计算；
- input update rate 与 48 kHz audio rate 解耦；
- realtime callback no heap/file/JSON/UI；
- profile version/SHA/qualification 可追溯；
- Golden trace 防止 Python/C++/Android 漂移；
- lifecycle、xrun、latency、CPU/memory/thermal 都是产品 Gate。

## 12. 可复用工程路线

```text
source/license governance
→ clean-room method adoption
→ persistent source model
→ parameter reachability
→ hard gates
→ reference comparator
→ fixed-ruler negative feedback
→ causal family tuning
→ Human gate
→ Engineering Profile
→ Golden package
→ portable realtime runtime
```

这条路线比“找一个更像的开源声音项目并复制”更重要。

## 13. 主要外部借鉴

Engine-Sim、ENSIM4、DasEtwas enginesound、VehicleNoiseSynthesizer、Ignis、PTR/PSOLA/cylinder-pressure/EONE 等奠定事件/物理/持续状态；DiffMoog、Magenta DDSP、SSSSM-DDSP、Modulation Discovery、InverSynth/synth-setter/TorchSynth 提供 analysis-by-synthesis/parameter inversion 思路；SenaTaka engine-simulator、EV-engine-sound-sonification、ddsp-realtime 提供车辆状态和 realtime separation 参考。

具体 license/adoption boundary 看 `docs/research/engine-audio-ecosystem/`。

## 14. Next Agent 固定启动动作

1. 先读 `docs/README.md` 和 current status；
2. fetch remote current head/PR/CI；
3. 读 Stage AD execution state；
4. 不从旧 report 推断 current blocker；
5. 不恢复 ESP32 主线；
6. 不把公网 R3 当 optimizer/R1；
7. 不覆盖 V3；
8. 声音生成后等待 Jovi 听，不自动无限调参。

## 15. Stage AF 数值修正与服务恢复（2026-09-06）

历史 Stage AF 接力已在 `origin/main=28ee2bd73298959dc4831320e8b080b833c8c3d8` 之上完成，并由隔离分支 `local/main-audio-review-20260906` 在 `df2fb6a3e2b490eb62fc78183a1b7a7bafbc5093` 合并点 fast-forward 进入 main；这段只作为 Historical Stage-AF sound baseline 保留，不能覆盖当前 AG-R1 source authority。原 `stage_ad.engine_sim_acoustics.EngineAcoustics`、`build_unified_dashboards.py`、`audition_dashboard_template.html` 和 `review_packages/serve_dashboards.py` 的历史职责仍可追溯；Stage AE 默认 renderer、第二套试听后台和 Track-P/FVM/PTR/Radiation 修改仍被明确排除。

本轮新增的是可审计、默认关闭的数值修正：`cycle_phase` 将 720° crank radians 单次换算到 cycle domain；`causal_delays` 用零状态分数延迟消除 `np.roll` 未来样本回卷；`causal_convolution` 用已有分块卷积消除 centered `same` IR 的提前响应；`causal_derivative` 用后向差分移除 look-ahead；`shift_cut` 用 unity→cut→unity 约束换挡包络。H0 空旗标必须与旧 EngineAcoustics 在相同输入、seed、IR 下逐 PCM 相等；H1 仅开相位旗标；H2 再开四项时间修正。它们是听感诊断候选，不能自动转成 Human PASS 或 Profile。

Stage AF fit v4 是历史状态；Stage AF-R2 将 identity 合同升级为 fit v5，并把车型、seed、numerical_fixes、renderer source SHA、IR 原始/有效 SHA、Reference source SHA 及 audio/fit fingerprint 放入同一 receipt，并在 build 时 fail-closed 校验。多分辨率 STFT distance 负责捕捉同一宽频带内的八度错误，per-scene guard 负责阻止单个参考场景被总体均值掩盖。缺 fit、缺 IR、IR provenance 漂移、旧 schema 或模式不一致，都必须停止；`R3_PRIVATE_DIAGNOSTIC_ONLY` 不能升级为 R1/R2 或产品素材。

Hellcat H0/H1/H2 三套本地试听均为原工作台 10 个 candidate WAV + 真车 Reference 字节副本 + `stage_af_binding.json`，共用已有 IR SHA `44ce5af25a55efdf996c7e5026271f80949625b95fbdc1c4b83863b6e991b152`，rights=`UNVERIFIED_LOCAL_ASSET`。页面刷新故障的根因是约 34.5 MB 自包含 HTML 被单线程 `TCPServer` 的慢客户端写入占住；服务改为 `ThreadingMixIn + TCPServer` 并以慢 socket + 第二请求验证。页面服务恢复不代表声音真实感或人耳通过。

可复用证据：focused AF/AD/numerical=`29 passed`；full S12=`1459 passed, 2 skipped, 1 warning, 232 subtests passed`；Track-P 冻结路径改动 0；Stage-Z/AA 真实 rows 各 `12/12 executable`。后续 Agent 必须先读 `docs/08-reports/14-stage-af-numerical-fixes-and-review-server-20260906.md` 与 `docs/05-execution/04-stage-af-local-ai-handoff.md`，完成编号候选后停止等待 Jovi。

## 16. Stage AF-R 证据完整性（2026-09-07）

Stage AF-R 的核心经验是：页面和试听包本身也是证据边界，不能靠静态文案或旧包路径“看起来完成”。保留 `EngineAcoustics` 与原 A/B 工作台后，新增的 `package_integrity.py` 将 dashboard contract、fit/reference/IR identity、逐场景 PCM/Reference SHA、binding、依赖源码 fingerprint 和 manifest 自哈希串成一条可重算链；所有新包先进入新 staging 目录，artifact 校验通过后才原子发布，已存在目标绝不覆盖。

fit v4 必须包含 `hot_idle / steady_mid / full_pull / afterfire` 四个 Reference source filename/SHA。构建时只接受调用者显式提供的 `--reference-root`；不传 root 时不搜索 output/旧包，目标目录已有而 source 缺失时也拒绝 stale destination。Reference provenance 要保留 source path、SHA、rights/evidence 状态；`UNVERIFIED_LOCAL_ASSET` 和 R3 只能支持受控诊断试听，不能升级为 R1、OEM 或产品素材。

H0 回归必须以固定 pre-fix Git commit 加载旧 renderer，并在同一 IR、输入、随机 seed 下逐 PCM 比较当前空 flags 输出；当前 IR 名称搜索顺序为 `new → archive → smooth → root`。不要把 H0 写成 current-vs-current，也不要把 H1/H2 的实际 flags 描述错。页面应从 contract 渲染 `NOT_FITTED`/`NOT_MEASURED`、真实 Reference label、实际 scene counts、B 轨 availability 和 sample-rate FFT 轴；feedback JSON 必须带 package/candidate/vehicle/contract SHA，状态停在 `WAITING_FOR_JOVI_FEEDBACK`。

验证顺序固定为：AF-R/受影响 AF/AD focused → compileall/diff-check → Track-P guard → full S12 → 原服务真实慢客户端+第二请求及 single-thread negative control → manifest/contract SHA 重算。软件测试、自动距离下降、浏览器 HTTP 200 都不能替代 Jovi 人耳试听或宣称 Human PASS/OEM calibration/Profile Freeze；生成编号候选后停止等待反馈。

## 17. Stage AF-R2 预拟合资格（2026-09-07）

当 package UI 继续演进而声音 renderer 不变时，必须把 dependency identity 拆成 `audio_runtime_fingerprint`、`fit_algorithm_fingerprint`、`package_ui_fingerprint`。fit 只比较前两段、车型/采样率/IR/flags 等 fit identity；HTML、dashboard 或服务修改不能无故使 fit 失效。若 fit objective、guard、CLI search 或 runtime/IR 改变，则必须失效；合同语义实质变化时升 schema，不能静默复用旧 v4。

正式 fitted package 要把 fit JSON 原始字节快照到 `<vehicle>/evidence/fit/final_fit.json`，并记录 source/snapshot SHA、schema、fit self SHA，使 source 删除后仍可独立验证。包还要保存 repository、git_head、base_main、dependency_dirty、source_policy；正式默认只接受 tracked source clean，开发 smoke 必须明确 `DEV_DIRTY_SOURCE` + `NOT_PROMOTABLE`。单车型 package 的导航只能指向实际存在的车型，外网 CSS 依赖必须标明 `AUDIO_SELF_CONTAINED / STYLE_NETWORK_DEPENDENCY`。

R2 的资格来源是最终 pushed SHA 的 GitHub Actions，而不是本机历史计数。H0 fixed oracle 至少覆盖 steady/body、shift、afterfire，事件必须落在输出窗口，并在同一 pre-fix implementation、IR、seed、输入和 `numerical_fixes=[]` 下逐 PCM 相等。只有 exact-head CI、source receipt、snapshot、manifest 和 oracle 全部闭合，才可进入 R3 重新生成 H0/H1/H2；否则停止等待外部证据。

## 18. Stage AG-R1 严格富交互试听路由（2026-09-09）

Stage AG 解决的是 Hellcat、Ferrari 458、LFA、GT-R R35 之间的车型身份，不是 H0/H1/H2 这一辆 Hellcat 的数值修正差异。v1 提高 pairwise separation 但在 Ferrari hot-idle、LFA hot-idle、GT-R full-pull 出现 >3% governed Reference 回退；这些失败必须保留为负证据，不能通过放宽阈值或 global/master gain 掩盖。R1 `vehicle_identity_v1r1` 以 redline-relative RPM、取消 identity layer per-track peak recovery、GT-R 仅对新增 identity source 的 WOT attenuation 修复，保持 Hellcat legacy/R1 byte-identical；16 个 Reference row 回退数为 0，separation 不低于 legacy，但这仍不是 Human PASS/OEM/R1 calibration。

当前 source authority 是 `origin/local/stage-ag-vehicle-identity-20260908@717a5226eef39491938f7e796cb87de521c2c477`，它从 AF-R2 `4ee1f833...` 向前发展。固定 local package 的 legacy/R1 manifest SHA 分别是 `0f9338...d7a541` 与 `3fecb566...f599519`；package source receipt 仍指向 R1 package 构建时的 `0e9207a...`，而 717a 负责严格 review serving，不重渲染声音。

文档/路由提交 `71bb91804e0b89b5af40aaf1130999b058d906fa` 及后续状态修正已正常 fast-forward 合并到 `origin/main@374c7b50db51fee935601954c9ee28de5ad15797`；这不改变 source branch 的身份，也不把 R1 package 或 Jovi 的人耳结论升级为产品资格。`local/stage-ag-r1-rich-audition-workbench-20260909` 与 `local/stage-ag-r1-rich-audition-workbench-r2-20260909` 仅是实验分支，必须保持 `DO NOT USE`。

试听路由本身是证据边界：`stage_ag.serve_r1_review_strict` 先验证 manifest 自哈希与 exact SHA、4 车型目录、R1 mode、dashboard contract、candidate/Reference WAV SHA、rich HTML required marker，再原子性地绑定全部 8 个 loopback ports。它要求 23380–23383 是 legacy、23480–23483 是 R1；`8080/8088–8091` 与 `review_packages/serve_dashboards.py` 是历史路由，禁止用于 AG-R1，因为 collision 后可能继续暴露旧 package/旧 WAV。正确页面必须显示 A/B 瞬时比对、FFT/Waveform、分类、10 场景和反馈输入；若出现 `canonical S12 renderer` 或 `package-wide gain`，停止且不听音。

本轮已通过 strict preflight、8 端口 HTTP 200、Ferrari R1 rich UI 浏览器截图与 HTML marker 检查。状态固定为 `STAGE_AG_R1_STRICT_RICH_REVIEW_READY / WAITING_FOR_JOVI_ACOUSTIC_REVIEW`；下一动作仅是 Jovi 在 R1 页面实际试听，记录人耳反馈，不自动 fit/R2/profile freeze/Android/ESP32。
