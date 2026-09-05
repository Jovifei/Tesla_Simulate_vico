# Stage AD 本地 Codex 执行 Prompt — 只生成声音供 Jovi 试听

更新：2026-09-05
状态：`ACTIVE_EXECUTION_RUNBOOK`

把本文整体交给本地 Codex。

## 目标

拉取最新 `s12-stage-ad-closed-loop-calibration`，在不覆盖用户工作树、不覆盖官方 V3 的前提下：

```text
现有 governed Hellcat Reference
→ AA-C3-aware Stage AD
→ body
→ blower
→ afterfire
→ final monitor-WAV package
→ Jovi listen
→ STOP
```

本轮不做 Android、不做 ESP32、不做 Profile Freeze。

## 1. Git

```powershell
cd E:\Tesla_speed\prj
git fetch origin --prune
git status --short
git ls-remote origin refs/heads/s12-stage-ad-closed-loop-calibration
```

工作树非空则创建独立 worktree；禁止 force-reset 用户改动。

## 2. 必读

```text
docs/00-reference/01-authority-and-evidence-precedence.md
docs/08-reports/11-project-status-20260905.md
docs/04-planning/05-s12-reference-closed-loop-optimization.md
docs/07-debugging/01-known-failures-and-do-not-repeat.md
tasks/reports/runtime/s12-stage-ad/execution_state.json
```

## 3. Tests

至少运行：

```powershell
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ad_closed_loop.py -q
```

再运行 Stage AA/X/Y 相关 focused tests 和 `git diff --check`。任何 regression 先修；不得改官方 V3 WAV/manifest。

## 4. Reference 选择

### 优先：已有 governed local Reference

搜索 canonical registry/caseset 和本地 WAV，核对 SHA、rights/evidence、scene、contamination。只有 BOUND case 进入 Stage AD optimizer。

### 公网 extractor 的新规则

仓库存在 `stage_ad/extract_reference_audio.py`。**不要默认运行。** 只有 Jovi 明确要求/授权，且使用符合来源平台条款和版权要求时，才可生成 R3 私人试听片段。

这些片段只能：

```text
R3_PRIVATE_DIAGNOSTIC_ONLY
→ make_audition_dashboard human A/B
```

不得：

```text
feed --reference-registry closed-loop optimizer by default
promote to R2/R1
commit media into repo
redistribute as product asset
claim OEM calibration
```

如果本地没有可用 governed Reference：生成 AA-C3/Stage-AD smoke + 可选经授权的 R3 human dashboard，然后报告 `GOVERNED_REFERENCE_MISSING`；不要伪造自动优化结果。

## 5. Closed-loop 顺序

默认每 family 2 outer iterations、coarse 24、refine 12。只在 fixed reference distance 仍稳定改善时增加第 3 轮。

### Body

```powershell
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_ad.cli `
  --reference-registry <REGISTRY> `
  --vehicle-id hellcat_v1 `
  --baseline aa-c3 `
  --family body `
  --iterations 2 `
  --coarse-count 24 `
  --refine-count 12 `
  --output-root E:\Tesla_speed\stage_ad_runs\hellcat_v1\01_body
```

### Blower

使用 body `final_config.json` 作为 `--base-config-json`，`--family blower`。

### Afterfire

使用 blower `final_config.json`，只有存在可用 afterfire reference 时运行 `--family afterfire`。

每一阶段检查：finite、no clipping、click gate、wrong-condition afterfire、parameter consumed、absolute reference distance、source-causal family。

## 6. Simulink

可选。Python S12 是 authority。历史 v0.9 `.slx` 不能直接当有效模型；必须复制 candidate，在用户已有 MATLAB session 中用 Stage AD validator/bridge 修复。禁止覆盖原始 SLX。

只有 Update Diagram + simulation + finite Nx2 PCM + 960 frame multiple + Python equivalence 才记录 `SIMULINK_MIRROR_PASS`。

## 7. 最终试听

从最后成功的 config 生成 Stage AD monitor WAV，并用 `package_audition` 整理：

```text
E:\Tesla_speed\review_packages\s12-stage-ad-hellcat-closed-loop-v1
```

如用户明确授权并已有 R3 extracted clips，可再用 `make_audition_dashboard.py` 生成私人 A/B 页面；页面必须保留 R3/非正式校准标识。

## 8. 最终只报告

- exact branch/head；
- tests；
- governed Reference level/count；
- body/blower/afterfire 各轮数；
- final absolute reference distance；
- hard gates；
- Simulink mirror PASS/NOT_READY；
- audition path；
- 是否存在 R3 human-only dashboard。

然后：`STOP: WAITING_FOR_JOVI_STAGE_AD_AUDITION`。
