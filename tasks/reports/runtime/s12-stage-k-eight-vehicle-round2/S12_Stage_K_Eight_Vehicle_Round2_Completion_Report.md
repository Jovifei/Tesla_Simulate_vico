# S12 Stage K Eight-Vehicle Round-2 Completion

Date: 2026-08-21

## Result

The Round-2 propagation is implemented for all eight Stage-K vehicles. The
LFA qualification defect was fixed at its source: a continuous `metallic`
carrier is no longer thresholded as an event; ASG re-engagement is measured
from `lfa_shift_exhaust_reengagement` and aligned to trace-detected shifts.
The 60-second LFA evidence contains three aligned events, zero
wrong-condition events, and `eligible=true`.

The three-vehicle package was rebuilt as v4 and the remaining four vehicles
were published as a separate package. Both packages are transport-valid but
remain diagnostic-only: no human audition, OEM reproduction, Approved
Profile, or productization claim is made.

## Code and packages

- Worktree: `E:\Tesla_speed\worktrees\s12-stage-k-four-vehicle-perceptual-repair`
- Round-2 implementation tip: `c6ce1cfbc33ba90cf7d7c22fcf86c070d1bb40e1`.
- Documentation receipts are committed after this implementation tip; use `git rev-parse HEAD` for the current documentation tip.
- LFA fix commit: `e9aa9b6` (`fix(s12): qualify LFA round2 shift events`)
- Remaining-four implementation: `c6ce1cf` (`feat(s12): extend round2 evidence to remaining vehicles`)
- Three-car v4 package: `E:\Tesla_speed\review_packages\s12-stage-k-three-vehicle-round2-v4`
  - ZIP SHA-256: `3f6574633e876d8fd45d2288bf0ee97728a0f0708ce467b1eb65fdd269717a02`
  - manifest SHA-256: `8446e9e1ccdf1a17477967de02e26d33dd5177b3e164fbbd209f3cd22fb3d157`
  - 3 vehicles, 24 WAV, 28 SHA entries, 29 ZIP members
- Remaining-four package: `E:\Tesla_speed\review_packages\s12-stage-k-remaining-four-round2-v1`
  - ZIP SHA-256: `91e86dfbc62052e368b9792b3c076fd67a4902d6309b8d81f380f3b93af36656`
  - manifest SHA-256: `a07f34dc3fd094af0d20539b4f6b8fbbc017e10ca4bb7bdf8b780ba64bca615e`
  - 4 vehicles, 28 WAV, 35 SHA entries, 33 ZIP members

Both manifests keep the fixed state:
`PARTIAL / AUTOMATED_GATE_FAIL / UNQUALIFIED_DIAGNOSTIC_ONLY`.
`human_pass=false` and `csv_content_read=false` remain true.

## Verification evidence

- Combined Round-2 source/package/LFA regression: `22 passed in 240.73s`.
- Track-P pytest: `21 passed in 1.16s`.
- Track-P guard: `180` frozen files and `2` frozen symbols unchanged; `git diff --check` clean.
- Independent package validation: both roots had zero errors; all listed WAVs reopened as 48 kHz, stereo, PCM24 with finite samples and zero clipping; SHA256SUMS and ZIP CRCs matched.
- No CSV content was read. Existing untracked pytest/staging artifacts were preserved.

## Remaining qualification boundary

Automatic transport and source evidence are complete, but acoustic hard gates,
named human audition, reference approval, Profile Freeze, OEM reproduction,
Simulink/Runtime/Android integration, and product release remain unfinished.
The next authorized action is Jovi's explicitly identified listening feedback;
the project does not auto-advance to another calibration stage.

## GitHub publication receipt

- Remote: `https://github.com/Jovifei/Tesla_Simulate_vico.git`
- Branch: `agent/s12-stage-k-four-vehicle-perceptual-repair`
- Published tip: `bdda9c6c53ea58b254c883fb006fec143b85ccf6`
- Pull-request entry point: `https://github.com/Jovifei/Tesla_Simulate_vico/pull/new/agent/s12-stage-k-four-vehicle-perceptual-repair`

The feature branch is published but not merged into `main`. This receipt only
records transport to GitHub; it does not alter the diagnostic-only or
human-feedback boundary.
