# S12 Hellcat Architecture Selection Status

Status: `BAKEOFF_RENDERED / REFERENCE_TARGET_MISSING / NO_ARCHITECTURE_SELECTED`.

The current executable candidates are P1 Legacy, P2 persistent delay/LPF,
P2H persistent waveguide, P3 P2H plus timbre map and P5 P3 plus a clean-room
synthetic one-shot residual. The current Git-tracked evidence is the five
top-level JSON summaries bound by `artifact_manifest.json`; their local
long-window WAV source remains Git-ignored. All 12 scenario-shaped traces were
rendered, with `hot_idle_20s` at 20.0 s and `complete_cycle_60s` at 60.0 s;
the remaining diagnostic windows are declared at 1.0 s. Every P1/P2/P2H/P3/P5 case
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
`E:/Tesla_speed/review_packages/s12-stage-w-engine-audio-bakeoff-v5` with ZIP
SHA-256 `965c0176e106e7bdc5a703d3475ee5e0eebdf560a13ed03ce422f65c893c45c3`.
It is a labelled engineering package, not a scoring result or a selection.

The W9 closure status is `NO_ARCHITECTURE_CANDIDATE_PASSED` for the formal gate
only. No candidate is selected, and the missing R1 Reference prevents an
acoustic improvement or redesign conclusion.
