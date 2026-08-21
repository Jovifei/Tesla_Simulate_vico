# S12 Stage K Eight-Vehicle Round-2 Delivery

Date: 2026-08-21
Evidence class: synthetic / uncalibrated / Hellcat-inspired diagnostic evidence

## Current status

The Stage K Round-2 source and package contracts now cover all eight vehicles.
The LFA event-eligibility defect was fixed by replacing the continuous
`metallic` carrier with the trace-aligned
`lfa_shift_exhaust_reengagement` event. The verified 60-second evidence has
three aligned shift events, zero wrong-condition events, and
`eligible=true`.

The release boundary remains:

`PARTIAL / AUTOMATED_GATE_FAIL / UNQUALIFIED_DIAGNOSTIC_ONLY`

`human_pass=false` and `csv_content_read=false`. No OEM reproduction, human
approval, Approved Profile, Profile Freeze, Simulink/Runtime/Android
productization, or production-release claim is made.

## Published diagnostic packages

| Package | Scope | ZIP SHA-256 | Manifest SHA-256 |
|---|---|---|---|
| `s12-stage-k-three-vehicle-round2-v4` | C63 W204, GT-R R35, LFA; 24 WAV | `3f6574633e876d8fd45d2288bf0ee97728a0f0708ce467b1eb65fdd269717a02` | `8446e9e1ccdf1a17477967de02e26d33dd5177b3e164fbbd209f3cd22fb3d157` |
| `s12-stage-k-remaining-four-round2-v1` | Ferrari 458, RX-7 FD, Supra JZA80, Aventador LP700; 28 WAV | `91e86dfbc62052e368b9792b3c076fd67a4902d6309b8d81f380f3b93af36656` | `a07f34dc3fd094af0d20539b4f6b8fbbc017e10ca4bb7bdf8b780ba64bca615e` |

Both packages were independently reopened and checked for 48 kHz, stereo,
PCM24, finite samples, zero clipping, SHA256SUMS coverage, and ZIP CRC
integrity. The package roots are external review artifacts under
`E:\Tesla_speed\review_packages\` and are intentionally not copied into the
source repository.

## Verification snapshot

- Round-2 source/package/LFA regression: `22 passed`.
- Stage K full regression: `131 passed`.
- Track-P pytest: `21 passed`.
- Track-P guard: `180` frozen files and `2` frozen symbols unchanged.
- No CSV content was read; existing untracked validation artifacts were
  preserved.

## GitHub publication

- Remote: `https://github.com/Jovifei/Tesla_Simulate_vico.git`
- Branch: `agent/s12-stage-k-four-vehicle-perceptual-repair`
- Published implementation/documentation tip: `bdda9c6c53ea58b254c883fb006fec143b85ccf6`
- Implementation anchor: `c6ce1cfbc33ba90cf7d7c22fcf86c070d1bb40e1`
- Pull-request entry point: `https://github.com/Jovifei/Tesla_Simulate_vico/pull/new/agent/s12-stage-k-four-vehicle-perceptual-repair`

The branch is pushed for review; it is not merged into `main` and the
diagnostic-only status is unchanged.

## Next authorized step

The next evidence-bearing action is Jovi's explicitly identified listening
feedback. The project must not infer a human pass or advance automatically to
another calibration stage.
