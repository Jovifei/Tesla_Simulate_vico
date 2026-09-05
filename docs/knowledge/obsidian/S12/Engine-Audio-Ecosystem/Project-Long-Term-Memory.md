---
type: canonical-project-memory
updated: 2026-09-05
status: ACTIVE
current_product_direction: APP_FIRST
current_acoustic_stage: STAGE_AD
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
