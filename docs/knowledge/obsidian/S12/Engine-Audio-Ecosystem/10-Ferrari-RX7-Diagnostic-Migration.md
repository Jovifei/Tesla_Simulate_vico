---
title: Ferrari RX7 Diagnostic Migration
project: Tesla-Speed-Sound
subproject: S12
stage: Stage-X
document_type: experiment_note
status: partial_engineering_preselection
source_url: https://github.com/Jovifei/Tesla_Simulate_vico
s12_git_branch: agent/s12-stage-x-r2-engineering-selection
s12_git_commit: 92959f555ab96a42e73c83bbe696868c7b0fdfd2
created: 2026-08-29
updated: 2026-08-29
tags:
  - S12
  - Stage-X
---

<!-- S12-STAGE-X:AUTO:BEGIN -->
Ferrari/RX-7 diagnostic migration (X6): bounded search (64 coarse + 24 refine per architecture) over the reachability-verified parameter box.
- ferrari_458: valid references 3, best architecture `P2H` (full_pull, shift, tip_in)
- rx7_fd: valid references 0, best architecture `P2H` (no bound scenarios)
RX-7 references stay speech-contaminated (Jovi receipt), so its result is diagnostic-only; no reference-supported preselection and no formal migration or OEM likeness claim. Scope: synthetic; uncalibrated; vehicle-inspired; not OEM reproduction.
<!-- S12-STAGE-X:AUTO:END -->
