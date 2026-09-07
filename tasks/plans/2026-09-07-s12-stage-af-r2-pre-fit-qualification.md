# S12 Stage AF-R2 PRE-FIT QUALIFICATION Plan

## Goal

从现场 `origin/local/stage-af-r-evidence-20260907` 的 exact PR head 开始，把 Stage AF-R 的证据范围收紧到可远端资格验证、fit identity 可判失效、package source 可独立恢复，并为 Hellcat H0/H1/H2 重新打包准备条件。只推送隔离分支，不合并 `main`。

## Baseline and evidence boundary

- PR #15 exact head at handoff: `49bb97756c1f78baa9a25ae1e78168ebb72d258d`；base `main@ba13ced7f9eafdf0e4e4287c9c23eefc838c53f8`。
- Worktree: `E:\Tesla_speed\worktrees\stage-af-r2-qualification-20260907`.
- Current Actions matching exact head were observed `in_progress`: `34110365821` and `34110365538`; re-read after push.
- Preserve `EngineAcoustics`, original dashboard/template/service, existing H0/H1/H2 and old packages. No Stage AE, new renderer/backend, Track-P/PTR/Radiation, global gain, four-car fit, Android, ESP32, automatic tuning or human/OEM/R1 claim.

## Tasks

### 1. RED fixtures and remote qualification inventory

- Read current AF-R report/handoff, source/tests and PR exact-head diff.
- Add tests for three fingerprint scopes, HTML-only vs audio/fit invalidation, fit JSON snapshot/recovery, source receipt/dirty gate, single-vehicle navigation, status split, H0 steady/shift/afterfire fixed oracle, style dependency label, and full manifest identity.
- Run new tests before production changes and record the intended RED failures.

### 2. Identity and recovery contracts

- Split `dependency_fingerprint()` into `audio_runtime_fingerprint`, `fit_algorithm_fingerprint`, and `package_ui_fingerprint` with explicit file sets.
- Give fit v5 (only if contract semantics require it) a self-hash and the fit-algorithm fingerprint; preserve v4 compatibility only where semantics are unchanged.
- Snapshot exact fit JSON bytes under `<vehicle>/evidence/fit/final_fit.json`, record source/snapshot SHA, schema and fit self SHA, and list the snapshot in manifest artifacts.
- Add Git source receipt fields `repository`, `git_head`, `base_main`, `dependency_dirty`, `source_policy`; default fitted package requires tracked source clean; `--allow-dirty-dev` marks `DEV_DIRTY_SOURCE` and `NOT_PROMOTABLE`.

### 3. Existing workbench/package hardening

- Keep original renderer and service; make package build include the split identities, fit/source receipt, fit snapshot, per-scene records, and explicit status fields `fit_status`, `fit_metric_status`, `human_status`.
- For `--vehicle hellcat`, generate navigation only for package-present vehicles; never link to historical 8088–8091.
- Mark current HTML honestly as `AUDIO_SELF_CONTAINED / STYLE_NETWORK_DEPENDENCY` unless local/inline CSS is proven; do not rewrite the UI.

### 4. H0 oracle and regression

- Extend fixed Git oracle to steady/body, shift and afterfire windows with events truly inside output windows.
- Use same fixed pre-fix implementation, IR bytes, seed and inputs, with `numerical_fixes=[]`; require PCM byte equality and never change production sound to satisfy the test.

### 5. Verification and remote CI

- Run required focused pytest command, compileall, Track-P guard, full S12 and `git diff --check` on final code.
- Build a fresh non-overwriting smoke package to verify fit snapshot, source receipt, manifest SHA and single-vehicle navigation; do not generate H0/H1/H2 until R2 is green.
- Commit/push only this isolated branch, then query GitHub Actions by exact pushed SHA and record run IDs/conclusions. Stop with `STAGE_AF_R2_REMOTE_QUALIFIED` only if exact-head CI is green; otherwise report blocker and do not proceed to R3.

## Rollback and stop conditions

- Never reset or clean user worktrees; never overwrite existing package IDs or old H0/H1/H2.
- Missing/invalid fit, IR, Reference, source receipt, dirty tracked source (without explicit dev flag), fingerprint mismatch, oracle drift, or non-green exact-head CI stops the phase.
- R3 package generation is conditional on R2 remote qualification and must use new IDs, shared vehicle/seed/IR/input/Reference identities, and stop immediately after the three packages.
