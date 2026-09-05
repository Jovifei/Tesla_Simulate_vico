# Stage AE 本地 AI 接手文档 — 拉远端后只生成真实试听声音

## 目标

拉取 `s12-stage-ae-canonical-physical-convergence`，只运行 canonical Stage-AE 管线，必要时先做受治理的 family fit，再**用最终 fit config**生成四车型 A/B 试听包。不要再写第二套 renderer，不做 ESP32，不做 Android。

## 安全接手

```powershell
cd E:\Tesla_speed\prj
git fetch origin --prune
git worktree add E:\Tesla_speed\worktrees\s12-stage-ae-canonical-physical-convergence origin/s12-stage-ae-canonical-physical-convergence
cd E:\Tesla_speed\worktrees\s12-stage-ae-canonical-physical-convergence
```

确认本地 HEAD 等于远端分支 HEAD，然后执行：

```powershell
python -m pytest -q tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ae_canonical_physics.py
```

## Reference / IR

- Public-video reference 保持 `R3_PRIVATE_DIAGNOSTIC_ONLY`；不得升 R1/R2。
- 默认不要自动使用 engine-sim sound-library WAV。
- 只有本地存在 SHA/rights 完整的 IR manifest 时才传 `--ir-manifest`。
- 未确认 asset provenance 的 IR 可以研究/私人诊断，但不得作为产品媒体分发。

## 四车统一 family fit

如果车型已经有受治理 `reference_caseset.json`，建议目录固定为：

```text
E:\Tesla_speed\stage_ae_runs\hellcat\body\
E:\Tesla_speed\stage_ae_runs\hellcat\path\
E:\Tesla_speed\stage_ae_runs\hellcat\induction\
E:\Tesla_speed\stage_ae_runs\hellcat\afterfire\
...
E:\Tesla_speed\stage_ae_runs\gtr_r35\afterfire\
```

顺序：

```text
body → path → induction（仅增压车型）→ afterfire
```

第一轮：

```powershell
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_ae.fit_cli `
  --vehicle gtr_r35 `
  --caseset-json E:\Tesla_speed\review_packages\stage_ae_references\gtr_r35\reference_caseset.json `
  --family body `
  --output-root E:\Tesla_speed\stage_ae_runs\gtr_r35\body `
  --samples 16 `
  --seed 20260905
```

下一轮必须消费上一轮：

```powershell
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_ae.fit_cli `
  --vehicle gtr_r35 `
  --caseset-json E:\Tesla_speed\review_packages\stage_ae_references\gtr_r35\reference_caseset.json `
  --family path `
  --base-config-json E:\Tesla_speed\stage_ae_runs\gtr_r35\body\final_r3_diagnostic_fit.json `
  --output-root E:\Tesla_speed\stage_ae_runs\gtr_r35\path `
  --samples 16 `
  --seed 20260905
```

依次把 `path` 的 final config 交给 `induction`，再交给 `afterfire`。自然吸气车型没有 induction 参数时跳过该 family。

硬规则：

- 禁止 master/global/broad-pre-PTR gain；
- 禁止 per-scene normalization；
- comparator 只看 RAW/canonical PCM；
- 每轮输出始终叫 `final_r3_diagnostic_fit.json`；
- 不得改名成 OEM calibrated / Profile Freeze；
- 保存 `family_fit_receipt.json`。

## 生成最终试听声音

参考目录：

```text
E:\Tesla_speed\review_packages\stage_ae_references\hellcat\ref_*.wav
...\ferrari_458\ref_*.wav
...\lfa\ref_*.wav
...\gtr_r35\ref_*.wav
```

如果已经跑了 family fit，**一定传 `--config-root`**，否则试听会退回仓库默认 profile：

```powershell
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_ae.package_audition `
  --vehicle all `
  --output-root E:\Tesla_speed\review_packages\s12-stage-ae-four-vehicle-v1 `
  --reference-root E:\Tesla_speed\review_packages\stage_ae_references `
  --config-root E:\Tesla_speed\stage_ae_runs `
  --seed 20260905
```

打包器会按优先级查找每台车的：

```text
<vehicle>\afterfire\final_r3_diagnostic_fit.json
<vehicle>\induction\final_r3_diagnostic_fit.json
<vehicle>\path\final_r3_diagnostic_fit.json
<vehicle>\body\final_r3_diagnostic_fit.json
```

并把实际采用的 `config_source` / `config_sha256` 写进 `audition_manifest.json`，防止“调参完成但试听仍是默认参数”。

每台车输出：

- 10 个 candidate WAV；
- `index_standalone.html`；
- `audition_manifest.json`。

页面为纯内嵌 CSS/JS + Base64 audio，断网可打开；一台车所有场景只使用一个 attenuation-only package gain，保持 idle/cruise/WOT 相对能量。

## 最终 STOP

生成四车真实声音后立即停止，不继续 Android、不继续 ESP32、不自动调下一轮。

只回复 Jovi：

- 输出目录；
- HEAD SHA；
- 每车实际 `config_source` / `config_sha256`；
- 每车 package gain dB；
- IR asset/SHA/rights（若有）；
- 四车 A/B 页面路径；
- focused/full test 状态；
- 然后等待 Jovi 试听。
