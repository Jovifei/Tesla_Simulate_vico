---
title: Stage Y Hybrid Calibration Tooling
project: Tesla-Speed-Sound
subproject: S12
stage: Stage-Y
document_type: engineering_note
status: tooling_implemented_real_assets_pending
source_url: https://github.com/Jovifei/Tesla_Simulate_vico/tree/agent/s12-stage-y-closed-loop-remediation
created: 2026-08-30
updated: 2026-08-30
tags:
  - S12
  - Stage-Y
  - hybrid-source
  - order-map
  - cycle-residual
  - transfer-identification
---

<!-- S12-STAGE-Y-HYBRID:AUTO:BEGIN -->
# Stage Y Hybrid Calibration Tooling

The event-domain engine remains the timing and physical-structure owner. Realistic residual texture is added only through authorized derived assets:

```text
event timing / torque / per-path exhaust
+ RPM×load×boost×order timbre map
+ rights-cleared cycle residual bank
+ reviewed causal transfer response
→ frozen PTR
```

Implemented files:

- `stage_y/harmonic_timbre_extractor.py`
- `stage_y/cycle_residual_bank.py`
- `stage_y/hybrid_source.py`
- `stage_y/transfer_response_id.py`
- `stage_y/finalist_validation.py`
- `stage_y/calibration_bundle.py`
- `stage_y/drivers/drive_y2_calibration_bundle.py`

The intake bundle is fail-closed and must contain:

```text
audio.wav
state.csv
rights.json
recording.json
```

No source recording is copied into derived output. The hybrid source is disabled by default and cannot change frozen PTR/FVM/Radiation.

Primary external method reference:

- Engine-Sim: https://github.com/ange-yaghi/engine-sim

Professional validation references:

- MoSQITo: https://github.com/Eomys/MoSQITo
- webMUSHRA: https://github.com/audiolabs/webMUSHRA
- ViSQOL: https://github.com/google/visqol
- MATLAB rpmordermap: https://www.mathworks.com/help/signal/ref/rpmordermap.html

Current truth:

`HYBRID_TOOLING_IMPLEMENTED / REAL_DERIVED_ASSETS_PENDING / HUMAN_REVIEW_PENDING / NOT_PROFILE_FREEZE_READY`

Related reports:

- `docs/08-reports/03-s12-stage-y-closed-loop-remediation.md`
- `docs/08-reports/04-s12-stage-y-hybrid-calibration-tooling.md`
- `docs/08-reports/05-s12-stage-y-local-codex-handoff.md`
<!-- S12-STAGE-Y-HYBRID:AUTO:END -->
