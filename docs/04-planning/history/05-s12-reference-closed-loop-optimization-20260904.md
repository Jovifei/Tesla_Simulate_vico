# S12 Stage AD — 真实参考负反馈闭环优化

日期：2026-09-04
状态：`REMOTE_INFRASTRUCTURE_IMPLEMENTED / LOCAL_REFERENCE_AUDIO_EXECUTION_PENDING`

## 1. 目标闭环

这一阶段正式实现用户要求的负反馈优化：

```text
真实参考声音 Reference
        ↓
当前配置 θ_k
        ↓
AA-C3 当前声音处理链
        ↓
Candidate PCM
        ↓
Reference Comparator
        ↓
固定尺度 absolute_reference_distance
        ↓
source-causal 参数搜索
        ↓
recenter 参数中心 + shrink 参数域
        ↓
θ_(k+1)
        └──────────────→ 再渲染
```

最终只产生新的 **Stage-AD diagnostic audition**，交给 Jovi 听；不自动 Human PASS，不自动 Profile Freeze。

## 2. Stage AD 前已经有的零件

仓库此前已经具备：

- `stage_x/reference_caseset.py`：Reference 治理、R1/R2/R3、场景绑定、rights/污染；
- `stage_x/multi_reference_comparator.py`：Reference / Parent / Candidate 对比；
- `stage_x/search_parameters.py`：可达参数、metric/guard；
- `stage_x/parameter_domains.py`：参数物理域；
- `stage_x/candidate_search.py`：Sobol coarse + local refine + PCM materialization；
- `stage_x/human_feedback_objective.py`：Human feedback bounded adjustment。

所以旧系统已经能做“一轮 analysis-by-synthesis search”，但没有完整的跨轮 controller。

## 3. Stage AD 新增的完整控制器

新增 `stage_ad/closed_loop.py`：

```text
iteration 0
  render/search
  → best θ0
  → fixed reference distance d0
  → audition WAV
  ↓
recenter around θ0
shrink search range
  ↓
iteration 1
  → best θ1
  → fixed reference distance d1
  ↓
...
```

每轮保存：

- fixed-scale `absolute_reference_distance`；
- 旧 `improvement_fraction` 仅作诊断；
- parameter centers / deltas；
- best overrides；
- input config SHA；
- best candidate WAV receipt；
- audition manifest。

### 为什么不能直接比较每轮 improvement_fraction

旧 `improvement_fraction` 的 Parent 会随着每轮最佳配置变化，因此不同轮次的 improvement 没有同一个零点。

Stage AD 新增固定标尺：

```text
abs(candidate_metric - reference_metric)
---------------------------------------
max(abs(reference_metric), fixed_metric_floor)
```

对各 metric 做 robust median，得到 `absolute_reference_distance`。这个尺子只由 Reference 与固定 floor 定义，因此跨轮可比较。

停止条件：

- 达到 optional target reference distance；
- reference-distance improvement plateau；
- no eligible candidate；
- parameter not consumed；
- objective unavailable；
- max iterations。

## 4. 当前 baseline：AA-C3-aware，不回退到旧 P3

Stage AD 默认：

```text
--baseline aa-c3
```

这是关键约束。

AA-C3 本身除了 upstream config，还有固定：

- pressure/load scaling；
- event-derived 120–400 Hz body；
- forced-carrier suppression；
- frozen PTR/Radiation。

Stage AD 保留这些处理，只修改其上游 source config。`render_candidate()` 新增 `config_override` 工程入口；不传 override 时仍使用原 `_fitted_config()`。

新增测试要求：

```text
render_candidate(AA-C3, default)
==
render_candidate(AA-C3, config_override=_fitted_config())
```

官方 V3 WAV / manifest 不覆盖、不重写。

## 5. 三个可解释参数家族

不要一次乱搜全部参数，推荐顺序：

```text
BODY / IDLE
→ BLOWER
→ AFTERFIRE
```

### body

- combustion_event_energy；
- combustion_rise_time / decay_time；
- cycle_variation；
- crank_inertia；
- idle_governor；
- primary_length_spread；
- primary_attenuation_spread；
- waveguide_reflection / loss；
- collector_loss。

### blower

- blower_sideband_mix；
- blower_broadband_mix；
- blower_casing_mix；
- intake_mix；
- boost_attack / release；
- bypass_threshold。

### afterfire

- afterfire_reservoir_rate；
- afterfire_ignition_delay；
- afterfire_location_mix；
- afterfire_energy。

默认搜索集明确排除：

- monitor attack/release/max makeup；
- master/global gain；
- broad pre-PTR `attack_mix_120_400`；
- P6 counterfactual residual scaling。

## 6. Family 链式闭环

CLI 支持：

```text
--family body|blower|afterfire|all
--base-config-json <previous/final_config.json>
```

因此本地推荐：

```text
body final_config
→ blower base_config
→ blower final_config
→ afterfire base_config
→ final audition
```

每个 family 单独看 reference error，保持可解释因果关系。

## 7. Reference 输入

优先使用本地已有、rights-governed canonical registry：

```powershell
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_ad.cli `
  --reference-registry <reference_registry.json> `
  --vehicle-id hellcat_v1 `
  --baseline aa-c3 `
  --family body `
  --output-root <output_dir>
```

或者：

```powershell
--caseset-json <reference_caseset.json>
```

规则：

- REJECTED / speech-contaminated 不进入闭环；
- R2/R3 保持 R2/R3；
- 不从公网临时下载未授权音频充当 Reference；
- 无本地可用 reference 时，只允许 baseline smoke，不做参数优化。

## 8. Human feedback

可追加：

```text
--human-feedback-json <feedback.json>
```

但 Human adjustment 只是 bounded guidance；fixed reference distance 单独保存。

V3 feedback 协议仍是：

```text
save verbatim
→ SHA256
→ reveal
→ bind
```

## 9. Simulink 的当前真实状态

历史 `S12_Simulink_Playground_v09_Offline_Audit.md` 已证明旧 `.slx`：

- default `In1→Out1` bypass；
- packed configuration 不是固定 19x1；
- excitation / pressure / PCM 尺寸未锁定；
- Audio Device Writer / To Workspace 接错 bypass；
- Update Diagram / compile 失败；
- simulation/audio 没有有效证据。

所以 **Python S12 继续是权威 renderer**。

Stage AD 新增：

- `stage_ad/simulink/closed_loop_contract.json`；
- `s12_stage_ad_validate_model.m`；
- `s12_stage_ad_closed_loop_bridge.m`；
- `stage_ad/simulink_exchange.py`。

固定合同：

```text
48 kHz
20 ms fixed step
960 samples/frame
config = 19x1
excitation = 960x1
pressure = 960x1
PCM = 960x2
workspace variable = S12ClosedLoopPCM
```

只有：

```text
Update Diagram PASS
→ Simulation PASS
→ finite Nx2 PCM
→ sample count multiple of 960
→ Python equivalence receipt
```

后，Simulink 才可以保留为 diagnostic mirror。

旧 SLX 不远端强改；本地 Codex 在用户已有 MATLAB session 中复制候选 SLX 后修复，禁止覆盖原始文件。

## 10. 本轮开源方法研究结论

这次不再搜索“哪个项目声音更像”，而是研究**闭环反演 / analysis-by-synthesis**：

- DiffMoog：differentiable synth + sound matching；
- Magenta DDSP：differentiable DSP/audio loss；
- SSSSM-DDSP：synthetic↔real domain gap；
- Modulation Discovery：受约束、可解释 modulation；
- InverSynth / synth-setter / TorchSynth：audio→parameter proposal + re-synthesis；
- SenaTaka engine-simulator：GPS/accelerometer → continuous vehicle state；
- EV-engine-sound-sonification：低频 telemetry 与高频 DSP 的连续状态重建；
- ddsp-realtime：后续 C++/mobile realtime 参考。

本阶段没有复制任何外部 source/audio/weights；只 clean-room 吸收架构思想。

详见：

`docs/research/engine-audio-ecosystem/stage_ad_closed_loop_sources.md`

## 11. 为什么现在不把整套 S12 改成 differentiable graph

当前 S12 有：

- discrete event routing；
- afterfire eligibility/state；
- persistent path/filter；
- snapshot；
- Human gate；
- frozen Track-P boundary。

直接全量 differentiable rewrite 风险大。

当前路线：

1. 保留现有权威 renderer；
2. 用 governed real reference + bounded search + fixed-distance closed loop；
3. 未来只对连续局部 submodule 做 differentiable surrogate/warm-start；
4. surrogate 永不自动替换权威 renderer。

## 12. 试听输出

每轮已有：

```text
<loop>/iteration_XX/best_candidate/<scene>/monitor.wav
<loop>/iteration_XX/audition_manifest.json
<loop>/closed_loop_summary.json
<loop>/final_config.json
```

最终用：

```powershell
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_ad.package_audition `
  --loop-root <last_successful_loop> `
  --output-root E:\Tesla_speed\review_packages\s12-stage-ad-hellcat-closed-loop-v1
```

生成简洁试听目录：

```text
01_hot_idle.wav
02_steady_low.wav
03_steady_mid.wav
04_steady_high.wav
05_tip_in.wav
06_full_pull.wav
07_shift.wav
08_lift.wav
09_afterfire.wav
10_idle_return.wav
audition_manifest.json
```

这是**非盲 Stage-AD diagnostic audition**，与官方 V3 分离。

## 13. 本地 Codex 接手

完整执行 Prompt：

`docs/05-execution/02-stage-ad-local-codex-execution-prompt.md`

本地 Codex 的终点不是继续自动调参，而是：

```text
生成 Stage-AD monitor WAV 试听目录
→ 回复 Jovi 目录位置
→ STOP: WAITING_FOR_JOVI_STAGE_AD_AUDITION
```
