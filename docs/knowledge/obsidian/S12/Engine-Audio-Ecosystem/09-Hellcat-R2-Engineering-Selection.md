---
title: Hellcat R2 Engineering Selection
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
Hellcat engineering search (X5): deterministic Sobol two-stage search
(64 coarse + 32 refine per architecture, seed-bound), every candidate
rendered, reopened, hashed and compared against the scenario-bound R2
references (bound scenarios: hot_idle, steady_high, steady_low, steady_mid).
Reachability probe: 11/27 parameters reachable under the per-parameter targeted protocol (architecture + scenes + stem).

- P2H: status `NO_R2_ENGINEERING_CANDIDATE_IMPROVED`, objective -0.13111101381214735
- P3: status `NO_R2_ENGINEERING_CANDIDATE_IMPROVED`, objective -0.04238151764798337
- P5: status `NO_R2_ENGINEERING_CANDIDATE_IMPROVED`, objective -0.04238151764798337

Selected engineering architecture: **none (NO_R2_ENGINEERING_CANDIDATE_IMPROVED)**. Scope: synthetic; uncalibrated; vehicle-inspired; not OEM reproduction.
<!-- S12-STAGE-X:AUTO:END -->
