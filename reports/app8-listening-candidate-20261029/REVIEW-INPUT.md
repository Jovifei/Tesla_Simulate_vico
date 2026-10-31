# APP8 controlled listening execution: review input

Jovi explicitly approved C2C-OPTIMIZATION-PLAN.md on 2026-10-29. Task c2c_a1d7, iteration 1. Source worktree: worktrees/hellcat-state-contract-20261027 (7acf3b5 plus approved uncommitted changes). This is a bounded listening experiment, not full vehicle physics or OEM/human acceptance.

## Evidence entry points

- This lab: reports/app8-listening-candidate-20261029/ under the source worktree.
- Contract: LISTENING_CONTRACT.json (frozen SHA f55a423f711f986171a8d043907bd723f35a46246e0843ae658f41ec6b2ba23c).
- Accepted run: runs/full-20261029-013256/run-summary.json and analysis.json. Every case receipt binds actual control CSV, telemetry, PCM/WAV and 34 pre/post runtime dependencies. All 16 directories are unique and all 12 stationary controls match their declared anchors.
- Before-render build-receipt.json binds stock/candidate model hashes; actual cold-load, update, compile and model_check passed. New isolated SLX SHA 30d0c9b024dc9cd70d39f45544e1518c61fed511b6ba112c278562fac6891db3.
- delivery-manifest.json: 604 protected original/model/asset/profile/Android/Frozen files unchanged, all 34 runtime dependencies still match. Global renderer gain remains 0.1.
- regression-bound.log: MATLAB 131/131, failed/incomplete 0. Earlier regression.log is a retained failed test-environment invocation missing common path; corrected explicit path rerun passed without source edits. Source-interface Python core log: 8/8. Parent analysis pytest: 59/59.
- full-bound.log: actual A90+B90+C90+C_repeat90 and 12 stationary6s renders, same fixed parameters.
- Source defaults/disabled options: three vehicles, nine golden frames exactly match previous source output/state/diagnostics.
- Two existing sources modified only: normalized identity component output, default-off Hellcat research source options. Additive gearbox effect disabled only for research. New research helpers/tests isolated here and tests/test_s12_v12_listening_*.

## Results

A remains bit-identical to prior default90 PCM SHA 2e809bf2f17e1ea07f9a3e9c1b54027da12d9d09f8cd85f974ce39f66ce2f74d. B/C have identical new controls. Three upshifts 11/20/30s, one downshift58s, duration0.24/0.30s. Locked RPM follows declared virtual ratios and speed; shift slip explicit. Main combustion/orders/identity-exhaust gain smoothly falls to0.35 and recovers. Mechanical/whine not cut. Source phase continuous, max alignment error1.975e-7rad.

C post-normalization whine scale0.501187 (-6dB), induction0.707946 (-3dB), smooth RPM2000-3500 activation. No pressure-recording or engineering pure-tone injection, new bass oscillator, EQ compensation, limiter/AGC or gain change.

Six stationary LF gates pass (maximum20-250Hz absolute-power change0.000326dB); four eligible high-RPM/load anchors show HF/LF ratio reductions5.918-5.999dB. Every eligible drive window passes:15.08-17.94,23.66-28.42,68.12-72.36s, worst reduction5.999277dB, aggregate5.999658dB. Both channels checked independently, then power averaged; angular orders include0.5/1/1.5/2/4/8/22/44, anti-aliased angle resampling. No gates changed or parameter sweep.

C/C_repeat raw PCM SHA b77d372ddc23336e9d94437854f53548ae4b626a4ea553a5b47297072c4be610, PCM24 WAV SHA f3d3ae39cf511b4413958ad70a4a6ae557ada80dfe7c1129219c87035cb5d279; each4500frames/4,320,000samples/ch/48kHz/90s, peak0.0295912. PCM and WAV exact repeats, final real/finite/peak/continuity and independent PCM24 readback passed.

Matched audition: runs/full-20261029-013256/audition/,18 files. One fixed scalar per full A/B/C, target-23LUFS, verified-23.0 each; same case gain used for excerpts and5ms endpoint fade. No per-window AGC. Formal raw outputs unchanged. Human evaluation remains pending.

## Integrity correction retained

Old runs/full-20261029-011621/INVALIDATED.json is excluded: nested-function workspace variable capture reused stationary output directories. Runner was changed to a file-level local function with explicit context, fail-if-existing directory and dependency checks; fresh complete run above passed. Do not reuse old run or weaken gates. Terra max independent reviewer recomputed all6anchor and3drive metrics and verified controls/dependencies; no new blocker.

Review the current two-source diff, new lab and accepted run through the Tesla_speed connector. Scope: this approved controlled-listening package. Return DONE if no concrete blocker; keep full physics, hardware, OEM calibration and Jovi hearing acceptance explicitly open.

Final persisted evidence: analysis-tests.log records59/59 after a fresh exact-suite run; native-frame-verification.json/.log reads every4500 native frame of all4full runs against sequential Float64LE stereo bytes, with no trailing data (all pass). final-source.diff contains only the two approved existing-source edits. These checks do not re-render, retune or change runtime source.

Final PCM event inspection is persisted separately in accepted-run final-pcm-shift-envelopes.{json,csv,png}: raw B/C20ms per-channel RMS, pre/post100ms and all4event curves, downstream state retained. This complements the source-cut plot; descriptive only, not a cut-only counterfactual or human audibility threshold.
