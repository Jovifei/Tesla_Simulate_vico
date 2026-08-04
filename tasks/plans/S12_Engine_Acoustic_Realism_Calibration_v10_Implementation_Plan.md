# S12 Engine Acoustic Realism Calibration v1.0 Implementation Plan

> **Status:** `AUTOMATED_REALISM_CANDIDATE / HUMAN_AUDITION_PENDING`  
> **Code boundary:** `E:\Tesla_speed\worktrees\s12-v12\tools\sound_sim\s12\acoustic_identity_v015`  
> **Output boundary:** `E:\Tesla_speed\tasks\reports\runtime\s12-acoustic-realism-v10`  
> **Scope:** synthetic / uncalibrated / not OEM reproduction. No raw reference media is committed.

## Objective

Make the three existing independent sources perceptually more mechanical and stateful: distinct idle behavior, pressure-driven low-frequency body, closed-throttle afterfire, and non-static forced-induction dynamics. Automatic evidence qualifies a listening candidate only; Jovi's audition remains the perceptual acceptance gate.

## Frozen boundaries

- Do not modify FVM, PTR core, Radiation Boundary, runtime latency framework, Android protocol, MATLAB, or Simulink.
- Preserve the existing source interfaces, PCM24 writer, and frozen `RuntimePtrAdapter` consumption.
- Do not use raw sample playback, post-PTR synthesis/EQ, per-clip AGC, random white-noise pops, OEM-measured claims, commit, or push.

## Evidence and calibration contract

| Evidence tier | Allowed use | Prohibited use |
| --- | --- | --- |
| A | official topology/rpm limits | numeric SPL or recorded amplitude target |
| R2/B | third-party video qualitative order, event, and envelope cues | OEM calibration or stock-state assertion |
| C | deterministic source parameters and thresholds | statement of measured vehicle match |

`reference_database` stores source URLs, trim/configuration risk, analysis configuration, segment intent, and derived/qualitative targets. Raw media, when rights permit review, stays only under `E:\Claude_allow\Download`; no candidate becomes an OEM target without auditable configuration, RPM, recording position, and rights evidence.

## RED → GREEN sequence

1. [x] **Research contract:** added a R2 reference manifest with external-media SHA-256/risk/segment audit, relative STFT feature targets, and RED→GREEN extraction tests.
2. [x] **Idle identity:** added deterministic cycle amplitude/phase variation and vehicle-distinct accessory, valvetrain, and crank stems before PTR.
3. [x] **Pressure coupling:** implemented `pressure_pulse → exhaust_coupling → body_resonance → radiation`; full-pull 40–200 Hz fractions are Hellcat `0.8830`, Ferrari `0.4161`, RX-7 `0.3474`.
4. [x] **Deceleration:** added thermal/high-RPM/closed-throttle event clusters; formal deceleration counts are Ferrari `32`, Hellcat `27`, RX-7 `24`.
5. [x] **Forced induction:** implemented Hellcat RPM/load/boost/bypass inertia and RX-7 primary/secondary spool, boost onset, and blow-off state.
6. [x] **Loudness and metrics:** added state/body/transient metrics while retaining one fixed per-vehicle bundle gain; all formal bundles measure `-16.00 LUFS` with RMS/peak/crest metrics.
7. [x] **Publication:** emitted the four requested WAVs per vehicle, plots, JSON, A/B report, SHA manifest, and `S12_Acoustic_Realism_Report.md`.
8. [x] **Verification:** v1.0 `8/8`, v0.15 `58/58`, in-memory syntax `17` modules, `git diff --check`, SHA/PCM24 validation, and frozen adapter SHA passed. Human audition remains pending.

## Human-review rubric

- Ferrari 458: idle is clean but mechanically alive; high RPM becomes metallic/NA scream without excessive low-end weight.
- Hellcat: idle and pull retain 40–200 Hz mass; blower has RPM/load/boost movement rather than a static sine.
- RX-7 FD: rotor-related time structure remains non-piston; turbo spools, transitions, and releases are audible without piston-style firing order.

## Review

- Formal output has 24 signed non-manifest artifacts and 12 48 kHz/stereo/PCM24 WAVs under `E:\Tesla_speed\tasks\reports\runtime\s12-acoustic-realism-v10`.
- Same-state final PCM A/B passed: correlations Ferrari/Hellcat `0.0098`, Ferrari/RX-7 `0.0482`, Hellcat/RX-7 `0.6468`; order distances `0.5267`, `0.7371`, `0.4082`.
- Frozen adapter SHA-256 remained `fdb594838ada4e2867f0ee1d2ea64a53788c1feb6593f7f37c5caf7bae494cb5`; no FVM/PTR core/Radiation/Runtime/Android/MATLAB/Simulink diff.
- This is an automated realism candidate only, not an OEM or human-audition PASS.

## 2026-08-04 30-second audition reissue

- [x] Preserved the verified 3-second package and published a separate complete 30-second package at `E:\Tesla_speed\tasks\reports\runtime\s12-acoustic-realism-v10-30s`.
- [x] Re-ran v1.0 tests (`8/8 PASS`), recomputed the 24-artifact manifest, re-read all 12 WAVs as 48 kHz/stereo/PCM24, verified fixed `-16 LUFS` bundles and same-state A/B PASS.
- [x] Recorded the inclusive trace endpoint duration precisely: each WAV is `30.000020833 s` (30 s plus one 48 kHz endpoint sample), not looped or time-stretched.

## 2026-08-04 complete drive-cycle audition correction plan

**Problem:** The review link was `full_pull.wav`; it is intentionally a continuous-open-throttle scenario, so it cannot exercise the closed-throttle afterfire model.

**Single hypothesis:** A single continuous vehicle-state trace with sustained hot WOT followed by an abrupt high-RPM throttle close will preserve thermal/state history and produce an audible, deterministic afterfire window without altering the source architecture.

**Acceptance contract:** Per car, publish one 30-second PCM24 WAV: `0–4 s idle`, acceleration, loaded pull, `18 s` lift/afterfire, coast, then return to idle. Regression metrics must prove `afterfire_event_count > 0`, nonzero afterfire energy, and event onset at/after the lift; all existing protected boundaries remain byte-identical.

**RED → GREEN:** Add a test for the public drive-cycle trace/source contract and run it missing; implement only the trace/publisher required to pass; then regenerate artifacts and re-run focused plus v0.15 tests and all final-domain/frozen-path checks.

### Completion review

- RED evidence: `CompleteDriveCycleTests` first failed with `ModuleNotFoundError` because no drive-cycle publisher existed. Green evidence: v1.0 `9/9 PASS`, including the continuous source test that requires nonzero afterfire events/energy after the lift for all three vehicles.
- Formal output: `E:\Tesla_speed\tasks\reports\runtime\s12-acoustic-realism-v10-complete-drive-cycle-30s`; each WAV is 48 kHz/stereo/PCM24, `1,440,001` frames / `30.000020833 s`, and the 13-entry manifest recomputes exactly.
- Actual lift result: Ferrari `43` events / `121.925709` energy; Hellcat `38` / `93.795542`; RX-7 `30` / `44.788674`. All formal files target `-16.00 LUFS` and have zero clipping.
- Regression/boundaries: v0.15 `58/58 PASS`, `compileall` and `git diff --check` pass, frozen adapter SHA remains `fdb594838ada4e2867f0ee1d2ea64a53788c1feb6593f7f37c5caf7bae494cb5`, and protected FVM/PTR core/Radiation/Runtime/Android/MATLAB/Simulink paths have no diff.
- Status remains `synthetic / uncalibrated / not OEM reproduction / HUMAN_AUDITION_PENDING`.
