# S12 Stage AG — Vehicle Identity Separation 实现报告（2026-09-08）

状态：`IMPLEMENTED / REMOTE-CI-QUALIFICATION-PENDING / LOCAL-GOVERNED-RENDER-PENDING / DIAGNOSTIC_ONLY`

## 1. 本轮问题

Jovi 的最新 Human 反馈不是“当前声音不像油车”，而是：

> 当前 `EngineAcoustics` 已经有明显机械燃烧、排气轰鸣和油车质感，但 Hellcat / Ferrari 458 / Lexus LFA / GT-R R35 仍继承太多同一套 sonic body，导致车型身份不足。

必须区分：H0/H1/H2 都是同一辆 Hellcat 的数值修正候选，它们相似是预期；Stage AG 解决的是**不同车型之间**的 identity collapse。

## 2. 根因定位

现有四车虽然已经有不同的：

- cylinder count；
- firing angles/order；
- runner / exhaust length；
- IR；
- supercharger / turbo path；
- mechanical resonance；

但主链仍共享大量决定最终“身体感”的结构，包括统一 pulse recipe、bank cross-mix、air-noise处理、mechanical-bass recipe 和最终 saturation。因此可以同时出现：

```text
mechanical realism OK
vehicle identity weak
```

Stage AG 不以 post-EQ/master gain 人为拉开车型，而是在已有 `EngineAcoustics` 上增加显式、source-causal 的 engine-order identity layer。

## 3. Stage AG v1

新增模式：

```text
legacy
vehicle_identity_v1
```

### Hellcat

`identity_mix=0`。它是当前 Human 认可方向的 anchor；`vehicle_identity_v1` 必须与 legacy byte-identical。

### Ferrari 458

以 E4 为 primary firing order，并加入 E8/E12/E16 高阶结构，E2 保持很弱。目标是加强 flat-plane V8 的均匀、高转、尖锐排气结构，而不是 Hellcat-like half-order rumble。

### Lexus LFA

以 E5 为 primary firing order，并加入 E10/E15/E20，高阶更密，低 E2.5 sub-order 很弱。目标是形成 even-firing high-rev V10 identity。

### Nissan GT-R R35

以 E3 为 primary order，并加入 E6/E9 和少量 E1.5，增加受 load/order gate 调制的 broadband source；原 EngineAcoustics turbo/BOV 仍保留为独立来源。

所有 identity layer 都由 RPM/crank phase 和 throttle/load 驱动；使用 bounded convex source blend，禁止 master/global gain 或 broad post-EQ matching。

## 4. 实现文件

```text
tools/sound_sim/s12/acoustic_identity_v015/stage_ag/
  vehicle_identity.py
  render_identity_probe.py
  analyze_vehicle_identity.py
  build_identity_dashboards.py
  build_blind_identity_package.py
  run_local_identity_validation.py
```

测试：

```text
tools/sound_sim/s12/acoustic_identity_v015/tests/
  test_s12_stage_ag_vehicle_identity.py
  test_s12_stage_ag_tools.py
```

研究来源：

```text
docs/research/engine-audio-ecosystem/stage_ag_vehicle_identity_sources.md
```

## 5. 开源/论文吸收边界

Stage AG 只 clean-room 吸收公开方法：

- AngeTheGreat/engine-sim：engine topology / firing / exhaust path identity；
- SenaTaka/engine-simulator：engine-specific harmonic/noise/resonance mode separation；
- EONE (`arXiv:2606.21521`)：per-engine-order + broadband compact timbre representation；
- rdoerfler/ptr-model：firing-aligned pulse remains source anchor；
- VehicleNoiseSynthesizer：layer/state-oriented vehicle identity engineering。

未复制第三方源代码、录音、preset、模型权重或专有数据。

## 6. Identity scorecard

`stage_ag/analyze_vehicle_identity.py` 同时检查两件不同的事情：

### A. Vehicle separation

在 matched-state traces 上比较所有车型 pair：

```text
Hellcat / Ferrari / LFA / GT-R
quarter-redline
mid-redline
high-redline
normalized full-pull
```

输出 legacy 与 identity_v1 的 pairwise multi-resolution spectral distance。

### B. Real-Reference direction

当调用者显式提供已有 governed `--reference-root` 时，逐场景计算：

```text
legacy -> Reference
identity_v1 -> Reference
```

并记录 3% regression guard。

核心边界：

```text
larger inter-vehicle distance != more correct vehicle identity
```

如果 identity 更不同但 Reference 明显更差，应标为诊断失败，不能自动推广。

## 7. 不可变 Stage AG package

`stage_ag/build_identity_dashboards.py` 复用：

- 原 `stage_ad/build_unified_dashboards.py`；
- 原 HTML A/B workbench；
- Stage AF-R Reference binding / artifact SHA / source receipt / atomic publish helpers。

它不建立新 backend。

Stage AG package 强制：

```text
fit_status=NOT_FITTED
human_status=WAITING_FOR_JOVI_FEEDBACK
package_gain_db=0.0
reference_evidence_level=AUDITION_ONLY
```

并新增：

```text
identity_mode
vehicle_identity_signature
identity_runtime_fingerprint
```

旧 Stage-AF fit 不能无声复用给 identity_v1。

## 8. Blind identity gate

`stage_ag/build_blind_identity_package.py` 从一个四车型 Stage AG package 中**直接复制 candidate bytes**，不重新 render、不 normalize。

公开包只出现：

```text
Car A
Car B
Car C
Car D
```

真实 mapping 写到调用者指定的独立路径，且不能位于公开 blind package 内；public manifest 只保存 mapping SHA：

```text
SEALED_UNTIL_JOVI_FEEDBACK
```

Jovi 提交盲听判断前不能揭示 mapping。

## 9. 一键本地执行

在拥有真实 IR 和已有 Reference 的 Jovi 本机，可直接运行：

```powershell
$env:S12_ENGINE_SIM_IR_ROOT="E:\project\engine-sim\runtime\v0.1.11a\engine-sim-build_0_1_11a\es\sound-library"

python -m tools.sound_sim.s12.acoustic_identity_v015.stage_ag.run_local_identity_validation `
  --output-root E:\Tesla_speed\review_packages `
  --mapping-root E:\Tesla_speed\review_packages_private `
  --run-id s12-stage-ag-identity-20260908-v1 `
  --reference-root <EXISTING_GOVERNED_REFERENCE_ROOT> `
  --seed 20260908
```

执行器顺序固定：

```text
legacy-vs-identity probe
→ identity separation scorecard
→ Reference 3% guard
→ immutable legacy 4-car package
→ immutable identity-v1 4-car package
→ Hellcat byte-identical guard
→ non-Hellcat actual-change guard
→ shared Reference-byte guard
→ sealed blind identity package
→ summary receipt
```

只要显式 Reference 存在且任一场景 identity-v1 相对 legacy 退化 >3%，执行器会在 immutable package promotion 前停止。

## 10. 当前停止边界

远端能完成的是源码、测试、证据合同和 CI。真实四车 WAV 必须访问 Jovi 本机未入库的 IR / Reference bytes，因此本报告不声称已经完成真实本机听感验证。

下一位本地 Agent 只负责：

1. fetch 最新 Stage AG branch；
2. 跑 exact local tests；
3. 提供真实 IR / governed Reference root；
4. 运行一键 Stage AG validation；
5. 启动生成出的页面；
6. 返回 manifest/SHA/scorecard/ports；
7. 停止等待 Jovi blind feedback。

禁止自动 fit、修改 Hellcat、自动 profile freeze、Android、ESP32 或 OEM/R1 claim。

最终目标状态：

```text
STAGE_AG_IDENTITY_CANDIDATES_READY
WAITING_FOR_JOVI_BLIND_IDENTITY_FEEDBACK
```
