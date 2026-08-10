# S12 Stage H — Hellcat Perceptual Calibration

## Baseline

- Base: `60bca7cccac91c520a12c0b058f3f70d56dcf4b8`
- Branch: `agent/s12-stage-h-hellcat-perceptual-calibration`
- Worktree: `E:\Tesla_speed\worktrees\s12-stage-h-hellcat-perceptual-calibration`
- Stage G v4 remains historical/unscored; its sealed key is never read during the first pass.
- Stage H is offline Track-S only. FVM, PTR, Radiation, Runtime, Android, MATLAB, Simulink, Track-P guard, and Stage C shared layers stay frozen.

## Execution checklist

- [ ] H0: freeze baseline hashes, record anonymous feedback as unbound, and run focused regression.
- [ ] H1: document Hellcat public architecture facts and synthetic acoustic targets.
- [ ] H2: write RED tests, implement deterministic load/boost-coupled whine and candidate v5 contract.
- [ ] H3: add Hellcat-specific metrics, bounded candidate selection, and non-regression gates.
- [ ] H4: publish the named Hellcat/Ferrari/RX-7 calibration package and stop for Jovi.
- [ ] H5: after named feedback, perform at most three vehicle-isolated candidate iterations.
- [ ] H6: only after named calibration, publish the anonymous Stage H blind/A-B package.
- [ ] H7: run full verification, update reports/Obsidian, and keep commits local.

## Required stop states

The first implementation pass stops at `WAITING_FOR_JOVI_NAMED_CALIBRATION`. It must not read sealed keys, invent answers, or create a Profile Freeze Candidate. All output remains `synthetic / uncalibrated / Hellcat-inspired / not OEM reproduction`.
