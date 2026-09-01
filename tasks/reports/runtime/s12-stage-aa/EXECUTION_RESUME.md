# S12 Stage AA Resume

## Current state

`AA1_ENERGY_BUDGET_AUDIT`: `IN_PROGRESS` from merged Stage-Z main
`209378bcb9a0c1a352ffd56ca1c765ecce01f81d`. The Stage-Z PR #3 CI run
`33468755129` passed and was merged normally. Stage AA is limited to Hellcat;
the v1 and v2 packages are preserved and must not be overwritten.

## Phase order

`AA0_STAGE_Z_CLOSEOUT → AA1_ENERGY_BUDGET_AUDIT →
AA2_REFERENCE_DIAGNOSTIC_CONTRACT → AA3_HELLCAT_ROOT_CAUSE →
AA4_BOUNDED_CANDIDATES → AA5_PROFESSIONAL_FINALIST_REVIEW →
AA6_V3_AUDITION → AA7_JOVI_FEEDBACK_ROUND2 → AA8_FINAL_QUALIFICATION`

## Recovery rules

- Do not rerun a long task unless renderer/source/test inputs changed or the
  final HEAD is explicitly being qualified.
- Never repair the RMS deficit with a global/master gain.
- Keep raw dynamic evidence separate from monitor loudness processing.
- Keep R1/R2/R3 provenance levels unchanged; no OEM, calibration, Profile
  Freeze, Android Runtime or hardware acceptance claim is implied.
- Do not copy third-party source, recordings, WAVs, assets, presets, weights,
  C++/`.mr`/IR or Rust implementations.
- Stop only at a generated, validated v3 package awaiting Jovi human audition,
  or at a documented external blocker listed in `execution_state.json`.

## Key evidence

- Stage-Z report: `docs/08-reports/08-s12-stage-z-open-source-absorption.md`.
- Stage-Z scorecard v1: `tasks/reports/runtime/s12-stage-z/method_ablation_scorecard.json`.
- Stage-Z objective: `tasks/reports/runtime/s12-stage-z/objective_before_after.json`.
- Canonical reference database: `tasks/reports/runtime/s12-stage-q-real-reference/reference_database_v2/`.
- v1: `E:/Tesla_speed/review_packages/s12-stage-y-hellcat-layers-v1`.
- v2: `E:/Tesla_speed/review_packages/s12-stage-y-hellcat-layers-v2`.

## Completed AA0

AA0 reran all 12 executable Stage-Z ablations at the 4-second evidence
window. `method_ablation_scorecard_v2.json` separates causal detection from
engineering significance and quality direction; 12 effects are causal, 9 are
engineering-significant, and collector/persistent/DasEtwas are below the
metric-specific significance floors. ENSIM4 remains teacher-only. The legacy
Stage-Z scorecard remains unchanged.

## Required next action

Use focused evidence to locate the layer causing the Parent→Final energy loss
before changing any renderer parameter.
