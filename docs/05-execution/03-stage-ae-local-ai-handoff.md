# Stage AE 本地 AI 接手文档 — 拉远端后只生成真实试听声音

## 目标

拉取 `s12-stage-ae-canonical-physical-convergence`，只运行 canonical Stage-AE 管线，必要时先做受治理的 family fit，再生成四车型 A/B 试听包。不要再写第二套 renderer，不做 ESP32，不做 Android。

## 安全接手

```powershell
cd E:\Tesla_speed\prj
git fetch origin --prune
git worktree add E:\Tesla_speed\worktrees\s12-stage-ae-canonical-physical-convergence origin/s12-stage-ae-canonical-physical-convergence
cd E:\Tesla_speed\worktrees\s12-stage-ae-canonical-physical-convergence
```

先确认 HEAD 与远端一致并执行 focused tests。

## Reference / IR

- Public-video reference 保持 R3/private diagnostic；不得升 R1/R2。
- 默认不要自动使用 engine-sim sound-library WAV。
- 只有本地存在 SHA/rights 完整的 IR manifest 时才传 `--ir-manifest`。

## 可选：四车统一 family fit

如果某车型已经有受治理 `reference_caseset.json`，可按顺序运行：

```text
body → path → induction（仅增压车型）→ afterfire
```

示例：

```powershell
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_ae.fit_cli `
  --vehicle gtr_r35 `
  --caseset-json E:\...\reference_caseset.json `
  --family body `
  --output-root E:\Tesla_speed\stage_ae_runs\gtr_body `
  --samples 16
```

下一 family 用上一轮 `final_r3_diagnostic_fit.json` 作为 `--base-config-json`。禁止 master/global/pre-PTR broad gain；输出始终叫 diagnostic fit，不叫 OEM calibrated。

## 生成声音

参考目录建议：

```text
E:\Tesla_speed\review_packages\stage_ae_references\hellcat\ref_*.wav
...\ferrari_458\ref_*.wav
...\lfa\ref_*.wav
...\gtr_r35\ref_*.wav
```

执行：

```powershell
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_ae.package_audition `
  --vehicle all `
  --output-root E:\Tesla_speed\review_packages\s12-stage-ae-four-vehicle-v1 `
  --reference-root E:\Tesla_speed\review_packages\stage_ae_references `
  --seed 20260905
```

每台车输出 10 个 candidate WAV、`index_standalone.html` 和 `audition_manifest.json`。页面为纯内嵌 CSS/JS + Base64 audio，断网可打开。

## 最终 STOP

生成四车真实声音后立即停止，只回复 Jovi：输出目录、HEAD SHA、每车 package gain、IR asset/SHA/rights、A/B 页面、focused/full test 状态，然后等待 Jovi 试听。
