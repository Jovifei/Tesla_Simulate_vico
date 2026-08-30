---
title: R1 Formal Gate Readiness
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
R1 formal gate readiness (X8): the formal pipeline is complete and exercised
on a synthetic fixture — multi-scenario binding, SHA receipts, rights fields,
synchronized RPM/load/gear traces, time coverage, microphone/AGC declaration,
MATLAB order-input export, multi-reference median, formal selection and the
profile-candidate gate. Fixture result: all pipeline checks
PASS, formal selection
`FORMAL_SELECTION_READY_NOT_RUN`, selected architecture
`None`, profile candidate gate
closed (fail-closed).
The fixture carries FIXTURE_ONLY / NOT_REAL_R1 / NOT_TUNING_AUTHORITY markers
and can never produce a real formal selection; real status remains
`FORMAL_R1_REFERENCE_MISSING`. When real R1 data arrives it is imported into
this same pipeline with no new selection algorithm. Scope: synthetic; uncalibrated; vehicle-inspired; not OEM reproduction.
<!-- S12-STAGE-X:AUTO:END -->
