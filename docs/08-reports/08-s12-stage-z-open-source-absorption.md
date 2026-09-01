# S12 Stage Z 开源方法吸收与 main v2 试听证据

状态：`STAGE_Z_TRACEABILITY_PASS_ACOUSTIC_GAIN_UNPROVEN`

权威起点是当前 main `62b3759c9e8026e62b4aa2cefeb0a3fbc73597aa`。Stage Z 在独立分支 `agent/s12-stage-z-open-source-proof` 上只增加可复现的证据 harness、矩阵和试听包；渲染器使用的 Stage Y/P3/PTR/Radiation/Track-P 代码未被重新调音。Stage Z tested head 为 `6361ce8e3b7b32018e555b5354a95a243b71991f`，包内同时绑定 `base_main_head=62b3759c…`。

## 交付物

- v2 试听包：`E:\Tesla_speed\review_packages\s12-stage-y-hellcat-layers-v2`。
- v2 package manifest SHA-256：`cf70e877b4018389df1fede3963d4cf685244860ae3efacf1476c31d0644a64c`。
- Parent aggregate SHA：`86fb539985c79c6b069d3bd1e5de500c6b1c25e40280582763bf523721d3c109`；Final Raw aggregate SHA：`d3a85676952c46578a4222bc74b725ff8856752bd520530201b1b94d5da918fd`。
- 包含 11 个整体场景、57 个 PCM24 stereo WAV、12 组盲化 A/B、`overall_review.html`、`method_ablation_review.html`、`answers_manifest.html` 和中文说明。
- Repo 机器证据：[`method_adoption_matrix_v2.json`](../research/engine-audio-ecosystem/method_adoption_matrix_v2.json)、[`method_ablation_scorecard.json`](../../tasks/reports/runtime/s12-stage-z/method_ablation_scorecard.json)、[`objective_before_after.json`](../../tasks/reports/runtime/s12-stage-z/objective_before_after.json)、[`teacher_vs_reduced_response.json`](../../tasks/reports/runtime/s12-stage-z/teacher_vs_reduced_response.json)。

## 三层吸收判定

### Level 1 — Research Absorption

25 个 registry source 全部有 method-level row，共 30 个 method rows。许可证、代码状态、音频权利和 Runtime 适用性分开记录：`IMPLEMENTED_CLEAN_ROOM=6`、`IMPLEMENTED_EQUIVALENT=6`、`REFERENCE_TEACHER_ONLY=1`、`REFERENCE_WORKFLOW_ONLY=5`、`BLOCKED_CODE_LICENSE=5`、`BLOCKED_COMMERCIAL_RUNTIME=7`。

### Level 2 — Engineering Absorption

- Engine-Sim clean-room methods：`engine_sim_event_pressure`、`engine_sim_path_waveguide`、`engine_sim_collector_network`、`engine_sim_forced_induction_state`、`engine_sim_persistent_block_state`、`engine_sim_pressure_audio_chain`。
- VehicleNoiseSynthesizer equivalent：`vehicle_noise_state_crossfade`，实际调用 `StateTransientMixer.render_block/equal_power_crossfade`。
- DasEtwas equivalent：`dasetwas_waveguide_lifecycle`，复用本工程 stateful waveguide/warmup/continuity；不复制 Rust、preset 或音频。
- Ignis equivalent：`ignis_pressure_domain_equivalent`，复用本工程 dP/DC/filter chain；Ignis 无 tracked LICENSE，因此不称为移植。
- Markeasting equivalent：`markeasting_state_layer_equivalent`；MIT repository code 与 individual audio rights 分开，音频权利仍 `UNVERIFIED`。
- ENSIM4：`REFERENCE_TEACHER_ONLY`。`teacher_vs_reduced_response.json` 记录 teacher 指标与本地 reduced causal smoothing；reduced model 明确 `runtime_candidate=false`，不把 CFD 或外部音频放入产品 Runtime。

### Level 3 — Acoustic Absorption

12 组 OFF/ON scorecard 全部为 `PROVEN_CONTRIBUTION`：每组都有不同 PCM SHA、目标指标变化、finite/no-clipping/click guard 和 runtime/memory 记录。这里的 `PROVEN_CONTRIBUTION` 只表示方法在实际 PCM 因果链上可独立观测，不表示 ON 一定比 OFF 更符合人耳偏好。

Parent→Final objective 使用已发布 PCM 的 raw_dynamic/timbre diagnostics。aggregate 结果显示 Final 的 spectral centroid、sharpness、roughness 等发生变化，但数字 RMS 与 dynamic range 下降；没有合法同步 R1 reference，因此整体声学质量判定保持 `PARTIAL / UNPROVEN`，不生成 OEM、calibrated 或 Profile Freeze 结论。

## 试听与边界

整体页按 `Parent → Final Raw → Final Monitor` 展示 hot idle 20 s、1200/2000/3000 rpm、tip-in、全油、换挡、收油、回火、idle return 和完整周期。方法页默认只显示 A/B，答案页另行揭盲。旧 `s12-stage-y-hellcat-layers-v1` 未修改；v2 不是 v1 复制，而是从当前 main renderer 重新生成。

本阶段没有复制 Engine-Sim C++/`.mr`/IR、VehicleNoiseSynthesizer recording/NWH、DasEtwas Rust/preset、Ignis/Markeasting source/media 或任何 model weight。HUMAN_AUDITION、LEGAL_SYNCHRONIZED_R1、OEM_CALIBRATION、PROFILE_FREEZE、ANDROID_RUNTIME 和 HARDWARE_ACCEPTANCE 仍关闭。

## Verification

- Stage Z focused TDD：`5 passed`；method scorecard short-window audit：12/12 `PROVEN_CONTRIBUTION`。
- v2 validator：`[]`；独立 WAV reopen/SHA scan：57/57；Parent/Final aggregate SHA 不同。
- Stage Y full S12 的历史当前证据仍为 `1370 passed, 2 skipped`, exit 0；本阶段未修改 Stage Y renderer/runtime，因此不重复执行完整 S12。若后续修改 renderer/source chain，必须在最终 HEAD 单独重跑。
- Track-P mathematical baseline、PTR/Radiation、global gain 未修改。

最终状态：

```text
SOFTWARE: PASS (Stage Z focused + v2 package validation)
OPEN_SOURCE_ENGINEERING_ABSORPTION: PASS
ACOUSTIC_CONTRIBUTION: PARTIAL / UNPROVEN_AS_QUALITY_IMPROVEMENT
HUMAN_AUDITION: WAITING_FOR_JOVI
R1: MISSING
OEM_CALIBRATION: NOT_AUTHORIZED
PROFILE_FREEZE: NOT_AUTHORIZED
```
