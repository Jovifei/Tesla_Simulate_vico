# S12 Stage AD — 真实参考负反馈闭环优化

更新：2026-09-05
状态：`REMOTE_INFRASTRUCTURE_IMPLEMENTED / LOCAL_GOVERNED_REFERENCE_EXECUTION_PENDING`

## 1. 闭环目标

```text
Governed Reference
→ current config θk
→ AA-C3-aware S12 render
→ Candidate PCM
→ comparator
→ fixed absolute_reference_distance
→ source-causal parameter search
→ recenter + shrink
→ θ(k+1)
→ repeat
→ monitor WAV
→ Jovi listen
```

Stage AD 把 Stage X/Y 已有的一轮 search 组织成真正跨轮 controller；不会自动 Human PASS/Profile Freeze。

## 2. 当前实现

已有：ReferenceCaseSet adapter、多轮 controller、fixed reference ruler、AA-C3 `config_override`、source-causal search、`body/blower/afterfire` family、staged `final_config.json` handoff、audition packager、Simulink contract/validator/bridge、focused tests。

AA-C3 固定 pressure/event-body/carrier processing 与 Frozen PTR 保留；不回退旧 P3；官方 V3 不改。

## 3. 参数家族

- `body`：combustion event/rise/decay、cycle variation、crank inertia、idle governor、primary spread、waveguide/collector。
- `blower`：sideband/broadband/casing/intake、boost attack/release、bypass。
- `afterfire`：reservoir、delay、location、energy。

默认排除 monitor/master/global/broad-pre-PTR controls。

## 4. 为什么使用 fixed reference distance

每轮 `improvement_fraction` 的 Parent 会变化，不能跨轮直接比较。Stage AD 以 Reference 值和固定 metric floor 定义统一距离；plateau/target 都用同一把尺。

## 5. Reference policy

### 闭环 optimizer

优先使用已有 canonical/rights-governed BOUND ReferenceCaseSet。R2/R3 保持原等级；污染 case fail-closed。

### 公网试听提取工具

最新分支提供 `extract_reference_audio.py` 和 dashboard。它可以在**用户明确授权且使用符合平台条款/版权条件**时生成 YouTube/Bilibili 片段，但其产物统一定位：

```text
R3_PRIVATE_DIAGNOSTIC_ONLY
human A/B dashboard only
NOT default closed-loop optimizer target
NOT R1/R2
NOT product/redistribution asset
```

工具内 `reference_audio_manifest` 的 note 已明确它不是 R1/R2 optimization target；文档与代码以此边界统一。

## 6. Simulink

历史 v0.9 SLX 已知 invalid。Stage AD 不远端假装修好 binary；Python 是 authority。Simulink candidate 必须在本地 MATLAB 中复制后修，满足 48 kHz、20 ms、960 frame、19x1 config、960x1 excitation/pressure、960x2 PCM，并通过 Update Diagram/simulation/Python equivalence。

## 7. 输出与停止

每 family 建独立 immutable output；后一 family 可用前一 `final_config.json`。最终 `package_audition` 只整理 monitor WAV 给 Jovi。生成试听包后停止等待反馈，不无限自动调参。

## 8. 开源方法启发

Stage AD 借鉴 DiffMoog、Magenta DDSP、SSSSM-DDSP、Modulation Discovery、InverSynth/synth-setter/TorchSynth、SenaTaka engine-simulator、EV-engine-sound-sonification、ddsp-realtime 的 analysis-by-synthesis、parameter inversion、domain-gap、continuous state/realtime separation 思想；不复制第三方音频/权重/专有资产。

详见 `docs/research/engine-audio-ecosystem/stage_ad_closed_loop_sources.md`。
