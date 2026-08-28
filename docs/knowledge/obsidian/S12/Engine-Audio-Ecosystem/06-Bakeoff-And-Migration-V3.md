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
s12_git_commit: da541fde65f8ae399d76ae301e0cc1c2ba5d899a

Task 5 current local verification at source head `d33b3ec` keeps P1/P2/P2H/P3/P5 frame-aligned and records persistent
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
Current local evidence roots are `bakeoff_final_remediation_v23`,
`migration_final_remediation_rx7_v23`, and
`migration_final_remediation_ferrari_v23`, generated from audio head `5038194`
and validated from source/test head `da541fd`; RX-7 and Ferrari validators
return `[]`, while the current bakeoff validator returns 16 content errors
and is retained as a concern. Selection remains null. The prior Stage-U/R3 packages remain non-R1 because rights, original capture
and synchronized RPM/load/gear evidence are absent; they cannot reopen W10.
The ready-to-fill Hellcat-first intake package is
`E:/Claude_allow/Download/s12-stage-w-r1-capture-v1`; it contains templates
only, never original media. Vault synchronization is
`VAULT_SYNC_PENDING_PARENT_CODEX_MEMORY`; this repository mirror update has
not been written to the Obsidian Vault by this task.
