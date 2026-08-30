---
title: Stage Y Closed-Loop Remediation
project: Tesla-Speed-Sound
subproject: S12
stage: Stage-Y
document_type: engineering_note
status: software_loop_remediated_external_calibration_pending
source_url: https://github.com/Jovifei/Tesla_Simulate_vico/tree/agent/s12-stage-y-closed-loop-remediation
created: 2026-08-30
updated: 2026-08-30
tags:
  - S12
  - Stage-Y
  - engine-audio
  - comparator
  - closed-loop
---

<!-- S12-STAGE-Y:AUTO:BEGIN -->
# Stage Y Closed-Loop Remediation

Stage Y starts from Stage X commit `f1714b969ecd033e991e04cfc59df06a05e3685a` and repairs the parts of the sound-design feedback loop that can be closed from repository code.

## Completed

- Video-derived audio is no longer automatically treated as R2.
- Reference support counts independent source/session evidence rather than duplicate windows from the same file.
- Canonical bands, spectral flux and time-axis modulation/roughness proxies were repaired.
- Engineering hard gates fail closed when evidence is absent.
- Search covers idle, steady-state, tip-in, full pull, shift, lift, afterfire and idle return.
- Categorical search controls use explicit domains.
- Jovi’s named issues are converted into bounded objective weights; contaminated feedback is withheld.
- Selected candidates are written as PCM24, reopened, checked and SHA-bound.
- CI includes focused Stage X/Y contracts, historical receipt-bound log integrity and the full S12 Python regression.

## Main external reference

- Engine-Sim: https://github.com/ange-yaghi/engine-sim

The S12 implementation keeps the clean-room architectural lessons—persistent engine state, event scheduling, per-path exhaust timing and bank/collector aggregation—but does not copy Engine-Sim code or vehicle scripts.

Additional tooling references:

- MoSQITo: https://github.com/Eomys/MoSQITo
- webMUSHRA: https://github.com/audiolabs/webMUSHRA
- ViSQOL: https://github.com/google/visqol
- MATLAB rpmordermap: https://www.mathworks.com/help/signal/ref/rpmordermap.html

## Still external / not complete

- legal R1 WAV/FLAC and synchronized RPM/load/throttle/gear;
- authorized cycle-synchronous clip/residual bank;
- real RPM×load×order timbre maps;
- ENSIM4/CFD sweep-derived transfer identification;
- MATLAB/MoSQITo runs on private reference media;
- Jovi blinded human feedback;
- eight-vehicle real calibration and profile freeze.

Current truth:

`STAGE_Y_SOFTWARE_LOOP_REMEDIATED / REAL_REFERENCE_CALIBRATION_PENDING / HUMAN_REVIEW_PENDING / NOT_PROFILE_FREEZE_READY`

Full report: [[../../../../08-reports/03-s12-stage-y-closed-loop-remediation|S12 Stage Y Closed-Loop Remediation]]
<!-- S12-STAGE-Y:AUTO:END -->
