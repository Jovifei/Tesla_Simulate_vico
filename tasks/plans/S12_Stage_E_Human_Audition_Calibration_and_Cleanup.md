# S12 Stage E Human Audition Calibration and Cleanup

> Execution state: implementation in a dedicated local worktree. No push, merge, rebase, main, Simulink, Runtime, or Android work is allowed.

**Goal:** make the three anchor Candidate parameters reach the pre-PTR rendering path, rebuild a valid anonymous audition package, and wait for Jovi's real responses before any sound calibration is promoted.

**Baseline:** Stage D local `4e363c66b92e51848a35700650ee1464925c479a`; Stage C baseline `a5d048145c29b20d687376c0b73226bc4a2435c7`; Stage D upstream remains `a5d0481` and is intentionally eight commits behind local.

**Architecture:** Stage E keeps Stage C's public pipeline and frozen boundary unchanged. Candidate source/idle overrides are injected before the shared Pre-PTR EQ; transient shaping touches only named transient stems. Stage D v1 files and its external package remain immutable historical evidence.

**Status:** `WAITING_FOR_JOVI_AUDITION` until complete 30-trial responses, playback context, and three A/B preference records are received.

## Global constraints

- Synthetic, uncalibrated, not OEM reproduction.
- FVM, PTR core, Radiation Boundary, Runtime, Android, MATLAB, Simulink, Track-P guard, Stage C public profiles, and fixed loudness policy remain frozen.
- Candidate v1 and the Stage D v1 audition package are never overwritten.
- No generated WAV, cache, build output, or `.workbuddy` file is copied into the repository.
- No push, merge, rebase, or main checkout mutation.

## Execution phases

1. Freeze the local baseline and create `agent/s12-stage-e-human-calibration` from local Stage D HEAD.
2. Write RED tests for parameter reachability, pre-EQ ordering, scorer denominators, and playback-context validation.
3. Add minimal Stage E candidate schema, override plumbing, and corrected rendering path.
4. Generate Candidate v2 profiles and a new sealed two-round package.
5. Run all focused and regression gates; publish evidence and cleanup inventory.
6. Stop and wait for Jovi. Only after complete responses may the scorer reveal the sealed key and start up to three narrow iterations.

## Cleanup rule

Generate a Git-external inventory with exact paths, sizes, tracked state, tree hashes, and `approved=false`. Never use `git clean -X`; the repository ignore rules include required agent files and documentation templates. Deletion is a separate user-approved action.
