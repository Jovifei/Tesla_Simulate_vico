---
title: Stage W Bakeoff and Migration V3
project: Tesla-Speed-Sound
subproject: S12
stage: Stage-W
document_type: experiment_note
status: partial_reference_selection_pending
source_url: https://github.com/Jovifei/Tesla_Simulate_vico
source_commit: d5b4dd85fd0aa8db51a243e00d25cd7658f1908f
license: project_internal_synthetic
s12_git_branch: agent/s12-stage-w-ecosystem-bakeoff
s12_git_commit: fcf74f3f31cb113027ac31475a6f8de65cc6efd9

Task 5D current local verification at validation/source-test head `fcf74f3` keeps P1/P2/P2H/P3/P5 frame-aligned and records persistent
phase/event/path/gain traces. The final long-window root `bakeoff_long_v3`
renders `hot_idle_20s` at 20.0 s / 960,000 audio frames and
`complete_cycle_60s` at 60.0 s / 2,880,000 audio frames; the other scenes are
explicit 1.0 s diagnostic windows. Ferrari 458 and RX-7 FD v3 are 8-second,
five-scene P1/P2H/P3 preselection packages. No candidate is selected without
a legal RPM/state-synchronised Reference. The labelled review package is
`E:/Tesla_speed/review_packages/s12-stage-w-engine-audio-bakeoff-v5` with ZIP
SHA `965c0176e106e7bdc5a703d3475ee5e0eebdf560a13ed03ce422f65c893c45c3`.
P5 is executable as a clean-room `synthetic_one_shot_v1` state-triggered
residual before frozen PTR; it is not a recorded asset and remains unselected.
Current local evidence roots are `bakeoff_final_remediation_v24`,
`migration_final_remediation_rx7_v24`, and
`migration_final_remediation_ferrari_v24`, generated from unchanged audio head `5038194`
and validated from source/test head `fcf74f3`; all three validators
return `[]`; JSON finite, WAV reopen/clipping/click/afterfire/parameter and nested SHA gates pass. Selection remains null. The prior Stage-U/R3 packages remain non-R1 because rights, original capture
and synchronized RPM/load/gear evidence are absent; they cannot reopen W10.
The ready-to-fill Hellcat-first intake package is
`E:/Claude_allow/Download/s12-stage-w-r1-capture-v1`; it contains templates
only, never original media. Vault synchronization is
`VAULT_SYNC_PENDING_PARENT_CODEX_MEMORY`; this repository mirror update has
not been written to the Obsidian Vault by this task.

## V27 addendum (2026-08-29)

The v3/v24 roots described above remain the Task5D-era byte record. The
current authoritative synthetic evidence is the v27 external staged set:
`bakeoff_final_remediation_v27`, `migration_final_remediation_rx7_v27`,
`migration_final_remediation_ferrari_v27`, produced by the external stage
renderer → strict verification → atomic final-root publication pipeline and
validated by all eight Task 6Z gates rerun green (see
`.superpowers/sdd/task-6ab-current-verification-rerun-report.md` and
[[05-Stage-W-Logs]]). Selection remains `null`
(`REFERENCE_TARGET_MISSING`); nothing here is a Human PASS, Approved Profile,
OEM reproduction or productization claim.
