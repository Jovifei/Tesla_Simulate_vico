# Stage AE 本地 AI 接手文档 — 拉远端后只生成真实试听声音

## 目标

拉取 `s12-stage-ae-canonical-physical-convergence`，在本地运行远端已经准备好的 canonical Stage-AE 管线，生成四车型 A/B 试听包。不要再写第二套 renderer，不做 ESP32，不做 Android。

## 安全接手

```powershell
cd E:\Tesla_speed\prj
git fetch origin --prune
git worktree add E:\Tesla_speed\worktrees\s12-stage-ae-canonical-physical-convergence origin/s12-stage-ae-canonical-physical-convergence
cd E:\Tesla_speed\worktrees\s12-stage-ae-canonical-physical-convergence
```

先确认 HEAD 与远端一致，并运行：

```powershell
python -m pytest -q tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ae_canonical_physics.py
```

## IR 规则

默认**不要**自动使用 engine-sim sound-library WAV。只有本地存在已经写好 SHA/rights 的 IR manifest 时才传 `--ir-manifest`。未知 asset 保持无外部 IR；不要因为 root code MIT 就假定 WAV 可产品分发。

## 生成声音

假设真实参考已按如下组织：

```text
E:\Tesla_speed\review_packages\stage_ae_references\hellcat\ref_hot_idle.wav
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

每台车输出 10 个 candidate WAV、`index_standalone.html` 和 `audition_manifest.json`。页面必须断网可打开。

## 如果需要继续负反馈

只能在 canonical renderer 上做。优先顺序：body/path → induction → transient/afterfire。禁止 master/global/broad-pre-PTR gain；禁止 per-scene normalization；保存每轮 fixed-distance receipt。

## 最终 STOP

生成四车真实声音后立即停止，只回复 Jovi：

- 输出目录；
- HEAD SHA；
- 每车 package gain dB；
- 是否使用外部 IR 及其 asset_id/SHA/rights；
- 四车 A/B 页面路径；
- hard gate / focused tests；
- 等待 Jovi 试听。
