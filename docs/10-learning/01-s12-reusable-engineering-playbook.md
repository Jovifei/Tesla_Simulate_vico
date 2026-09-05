# S12 可复用发动机声浪工程 Playbook

更新：2026-09-05

这套路线可复用于新的车型，而不是每辆车从“听起来不像”重新乱调。

## 1. Source governance first

先建立 source registry、license/rights、paper/project version。代码许可和录音权利分开。

## 2. Clean-room method adoption

```text
Source
→ Method
→ local equivalent implementation
→ runtime call path
→ OFF/ON / ablation
→ PCM SHA
→ metric/evidence
```

不要复制不必要的第三方代码/音频/权重。

## 3. Persistent event-domain model

优先建立 crank/event/state、combustion、cylinder/path/bank/collector、forced induction、mechanical、transients，而不是 fixed harmonics + EQ。

## 4. ReferenceCaseSet / hard gates

reference 治理与 renderer correctness 分开。先保证 finite/no-clipping/no-click/state continuity/afterfire condition/Track-P，再比较真实感。

## 5. Reachability before optimization

参数必须真的被 runtime 消费并改变目标 layer/PCM/metric，才进入 search。不可达参数不放进优化器。

## 6. Analysis-by-synthesis

Stage X/Y 一轮 search → Stage AD 多轮 negative feedback：

```text
render
→ compare with Reference
→ fixed reference distance
→ source-causal parameter proposal
→ recenter/shrink
→ repeat
```

跨轮必须固定 ruler；不拿 changing-parent improvement 假装收敛。

## 7. Tune by causal family

推荐：body/idle → blower/induction → afterfire/transients。每个 family 有明确 target/guard；后一级继承前一级 final config。

## 8. Human is a separate sensor

算法指标不能替代人耳。听感问题转换为 scene→source→metric→hypothesis，再决定是否做 bounded final round。

## 9. Profile freeze is not OEM freeze

Human accepted 可以形成 Engineering Profile；只有 R1 才能进入更正式 calibration/OEM-level claims。

## 10. Product bridge

```text
Engineering Profile
→ AudioParameterPackage
→ Golden state/PCM
→ portable C++
→ Python↔C++ equivalence
→ Android realtime
```

离线 optimizer/CFD/report 不进入 realtime callback。

## 11. 借鉴的主要项目/论文路线

### 发动机事件/物理启发
- Engine-Sim：event/cylinder/path/bank/collector/forced-induction/persistent thinking。
- ENSIM4：重物理/1D CFD teacher，明确 teacher≠mobile runtime。
- DasEtwas enginesound：stateful waveguide/continuity。
- VehicleNoiseSynthesizer：state scheduling/hysteresis/crossfade。
- Ignis/pressure-domain literature：pressure/dP/DC lifecycle。
- PSOLA/cylinder-pressure OLA：cycle alignment/continuity。
- EONE/parametric engine representation：heavy authoring→compact runtime parameters。

### 负反馈/参数反演
- DiffMoog：differentiable modular synth / sound matching。
- Magenta DDSP：differentiable DSP/audio-domain losses。
- SSSSM-DDSP：synthetic↔real domain gap。
- Modulation Discovery：可解释 time-varying modulation。
- InverSynth / synth-setter / TorchSynth：audio→parameter proposal + re-synthesis。

### 车辆状态与实时产品
- SenaTaka engine-simulator：GPS/accelerometer→vehicle/engine state。
- EV-engine-sound-sonification：低频 telemetry→高频 DSP 的 interpolation/state reconstruction。
- ddsp-realtime：authoring 与 realtime runtime 分离的工程参考。

具体版本/license/adoption boundary 以 `docs/research/engine-audio-ecosystem/` 为准。

## 12. 最重要的复用经验

**不要以“找一个更像的项目”为路线；以“可解释 source model + governed reference + causal reachability + negative feedback + Human gate + versioned product runtime”为路线。**
