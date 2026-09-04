# S12 Stage AD — 真实参考负反馈闭环优化

日期：2026-09-04
状态：`INFRASTRUCTURE_IMPLEMENTED / LOCAL_AUDIO_EXECUTION_PENDING`

## 1. 用户要求的闭环

目标不是一次性调参，而是：

```text
真实参考声音 Reference
        ↓
当前参数 θ_k
        ↓
S12 / Simulink / Python render
        ↓
Candidate PCM
        ↓
Reference Comparator
        ↓
误差 / objective / human feedback
        ↓
参数搜索与域收缩
        ↓
θ_(k+1)
        └──────────────→ 再 render
```

直到满足停止条件，再把最终候选交给 Jovi 人耳试听。

## 2. 之前做到哪里

已有零件：

- `stage_x/reference_caseset.py`：真实参考治理、R1/R2/R3、场景绑定、污染检测；
- `stage_x/multi_reference_comparator.py`：Reference / Parent / Candidate 对比；
- `stage_x/search_parameters.py`：可达参数及 metric/guard；
- `stage_x/parameter_domains.py`：参数物理域；
- `stage_x/candidate_search.py`：Sobol coarse search + local refine + PCM materialization；
- `stage_x/human_feedback_objective.py`：Human feedback 的有界 objective adjustment。

因此旧系统已经是“一轮 analysis-by-synthesis search”，但缺少显式的跨轮 controller：没有统一 iteration receipt、参数中心更新、搜索域收缩、plateau/target stop、final audition manifest。

## 3. Stage AD 新增

`stage_ad/closed_loop.py` 把已有零件组合成真正的多轮 controller：

```text
iteration 0
  coarse + refine
  → best θ0
  → objective0
  → audition WAV
  ↓
recenter parameter domains around θ0
shrink search deltas
  ↓
iteration 1
  → best θ1
  → objective1
  ↓
...
```

每轮保存：

- objective / reference objective；
- gain from previous iteration；
- parameter center/delta；
- best overrides；
- input config SHA；
- best-candidate WAV receipt；
- audition manifest。

停止条件：

- target objective reached；
- objective plateau；
- no eligible candidate；
- parameter not consumed；
- objective unavailable；
- max iterations。

Stage AD 永远：

```text
automatic_profile_promotion = false
human_audition_required = true
r1_promotion_forbidden = true
```

## 4. Reference 输入

优先使用 canonical reference registry：

```bash
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_ad.cli \
  --reference-registry <local_reference_registry.json> \
  --vehicle-id hellcat_v1 \
  --output-root <output_dir>
```

也可以直接使用已经生成的 ReferenceCaseSet：

```bash
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_ad.cli \
  --caseset-json <reference_caseset.json> \
  --vehicle-id hellcat_v1 \
  --output-root <output_dir>
```

ReferenceCaseSet 会 fail-closed：REJECTED/speech-contaminated reference 不进入闭环；R2/R3 不会被提升为 R1。

## 5. Human feedback 如何进入闭环

可传：

```bash
--human-feedback-json <jovi_feedback.json>
```

但仍遵循现有协议：V3 feedback 必须先保存 SHA，再揭 blind identity。

Human feedback 只作为有界 engineering guidance，不能覆盖 hard gate，也不能自动 Profile Freeze。

## 6. 当前建议 parameter family

第一轮不要全参数无脑搜索。按 Jovi feedback / reference error 选择 source-causal family：

### idle/LF

- combustion event energy/rise/decay；
- cycle variation；
- crank inertia / idle governor；
- primary path spread；
- collector/path loss。

### blower

- sideband mix；
- broadband mix；
- casing mix；
- intake mix；
- boost attack/release；
- bypass threshold。

### afterfire

- reservoir rate；
- ignition delay；
- event location；
- afterfire energy。

Round2 仍禁止 whole-mix/master/broad pre-PTR gain。

## 7. Simulink 当前真实状态

旧 v0.9 offline audit 已证明当前 `.slx`：

- default `In1→Out1` bypass；
- 设计端口未正确连接；
- packed configuration 未固定为 19x1；
- excitation/pressure/PCM dimensions inherited；
- Audio Device Writer/To Workspace 接错 bypass；
- compile evidence FAIL；
- simulation/audio 未证明。

因此 Stage AD **不把 Simulink 当权威 renderer**。

新增：

- `stage_ad/simulink/closed_loop_contract.json`；
- `s12_stage_ad_validate_model.m`；
- `s12_stage_ad_closed_loop_bridge.m`；
- `stage_ad/simulink_exchange.py`。

这些工具要求：

```text
48 kHz
20 ms fixed step
960 samples/frame
configuration = 19x1
excitation = 960x1
pressure = 960x1
PCM = 960x2
PCM To Workspace = S12ClosedLoopPCM
```

并禁止 silent fallback 到历史 bypass。

Simulink 只有在：

```text
Update Diagram PASS
→ simulation PASS
→ finite 960x2 PCM
→ Python equivalence receipt
```

后才可作为 diagnostic mirror。

## 8. 为什么现在不直接使用 differentiable gradient 优化全部 S12

当前 S12 包含离散 routing、afterfire event state、persistent path、snapshot、Human gate 等非平滑/离散结构；直接把整套重写成 differentiable graph 风险很高。

Stage AD 采用两层路线：

1. **现在**：保留现有 renderer，使用 governed reference + Sobol/local search + iterative domain shrink；
2. **后续可选**：对连续、局部、可微的 source submodule 引入 DDSP/differentiable surrogate，作为 warm-start/parameter proposal，不替换权威 renderer。

## 9. 与开源 sound matching 项目的关系

Stage AD 新研究重点不是复制其它 synth，而是吸收 analysis-by-synthesis / synth inversion 的控制结构：

- DiffMoog：differentiable modular synth + sound matching；
- Magenta DDSP：可微 DSP processors/loss；
- SSSSM-DDSP：synthetic→real domain sound matching；
- InverSynth/synth-setter：reference audio→parameter prediction→re-synthesis confidence；
- Modulation Discovery：有约束的 time-varying modulation 参数化；
- SenaTaka engine-simulator：GPS/accelerometer real-vehicle state → continuous engine state；
- EV-engine-sound-sonification：低频 telemetry 与高频 DSP 之间的连续状态重建。

详细来源见 `docs/research/engine-audio-ecosystem/stage_ad_closed_loop_sources.md`。

## 10. 本地执行后给 Jovi 的输出

Codex 本地只需要交付试听结果，不自动宣布 winner：

```text
<output>/iteration_00/best_candidate/*/monitor.wav
<output>/iteration_00/audition_manifest.json
...
<output>/closed_loop_summary.json
<output>/final_config.json
```

最后整理出一个 audition folder，Jovi 只听 monitor WAV；Raw/post-PTR 保留作工程证据。
