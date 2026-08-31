---
title: Engineering Selection Contract
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
Stage X splits the single selection gate into two layers
(`tools/sound_sim/s12/acoustic_identity_v015/stage_x/selection_contract.py`):

1. **engineering_preselection** — inputs: R2 audio, clean R3, Jovi feedback,
   Parent/Candidate metrics, ablation, runtime hard gates. May emit
   `R2_ENGINEERING_PRESELECTION`; never APPROVED_PROFILE / PROFILE_FREEZE /
   OEM_MATCH.
2. **formal_selection** — R1 only (rights + synchronized RPM/load/gear +
   scenario binding + human confirmation). Stays
   `FORMAL_R1_REFERENCE_MISSING` with `architecture=null` until real R1.

`selection_eligible` is now computed from data (hard gates, valid reference
count ≥2, median improvement ≥15%, evidence level) — the unconditional
`false` is gone. Scenario-bound `ReferenceCaseSet`
(`stage_x/reference_caseset.py`) binds each bake-off scenario to an
independent SHA-verified R2 segment with a deterministic speech-band detector;
speech-contaminated windows are rejected fail-closed (RX-7 is rejected by
Jovi receipt + detector). Multi-reference comparator
(`stage_x/multi_reference_comparator.py`) separates raw-dynamic metrics from
loudness-matched timbre metrics and outputs the 12 contract dimensions plus a
multi-reference median objective; order metrics stay NOT_QUALIFIED without
RPM traces. Scope: synthetic; uncalibrated; vehicle-inspired; not OEM reproduction.
<!-- S12-STAGE-X:AUTO:END -->
