# S12 Hellcat Architecture Selection Status

Status: `BAKEOFF_RENDERED / REFERENCE_TARGET_MISSING / NO_ARCHITECTURE_SELECTED`.

The current executable candidates are P1 Legacy, P2 persistent delay/LPF,
P2H persistent waveguide, P3 P2H plus timbre map and P5 P3 plus a clean-room
synthetic one-shot residual. The refreshed smoke evidence is
[`bakeoff_v6`](bakeoff_v6/): all 12 scenario-shaped traces were rendered at a
declared 1.0 s block-aligned duration. Every P1/P2/P2H/P3/P5 case
has equal post-PTR frame counts, raw/post-PTR/monitor PCM, state/phase/event/
path/gain traces, CPU receipt and SHA manifest.

P2/P2H/P3/P5 record one afterfire event for `afterfire_eligible` and zero for
`afterfire_ineligible`; P1 is explicitly `NOT_AVAILABLE_LEGACY` for
persistent-state traces. P5 residuals are generated entirely from current
state/event packets, not recordings. This proves implementation behavior, not
acoustic superiority. P4 remains rights-bound; P6 has nonzero external CFD
ON/OFF teacher audio but is not a Runtime candidate or a fitted S12 response.

No legal, rights-bound and RPM/state-synchronised Reference is available.
The repository's R2/R3 material is diagnostic only, so no median reference
improvement, no 20% target improvement, no non-target regression decision and
no candidate selection can be claimed. P2H/P3 remain candidates, not selected
architectures, and Profile Freeze stays closed.

The current external intake audit is
[`w10_reference_intake_audit.json`](w10_reference_intake_audit.json). It
records the two local public-reference packages as R3/insufficient evidence and
lists the exact original-audio, rights and synchronized telemetry delivery
needed to reopen W10.

The ready-to-fill acquisition package is at
`E:/Claude_allow/Download/s12-stage-w-r1-capture-v1`. Its current failed
preflight is intentional: no raw audio, confirmed rights, SHA manifest or
state traces have been supplied yet.

Scope: synthetic, uncalibrated, vehicle-inspired, not OEM reproduction,
`NOT_R1_QUALIFIED`, `NOT_PROFILE_FREEZE_READY`.

The local review package is
`E:/Tesla_speed/review_packages/s12-stage-w-engine-audio-bakeoff-v4` with ZIP
SHA-256 `3fff4d0e6bc4fdbe93e0d9257d34bba775e3f0e881d3b537033576ecbfe47ab8`.
It is a labelled engineering package, not a scoring result or a selection.
