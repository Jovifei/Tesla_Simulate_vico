# S12 Hellcat Architecture Selection Status

Status: `BAKEOFF_RENDERED / REFERENCE_TARGET_MISSING / NO_ARCHITECTURE_SELECTED`.

The current executable candidates are P1 Legacy, P2 persistent delay/LPF,
P2H persistent waveguide and P3 P2H plus timbre map. The refreshed smoke
evidence is [`bakeoff_v3`](bakeoff_v3/): all 12 scenario-shaped traces were
rendered at a declared 1.0 s block-aligned duration. Every P1/P2/P2H/P3 case
has equal post-PTR frame counts, raw/post-PTR/monitor PCM, state/phase/event/
path/gain traces, CPU receipt and SHA manifest.

P2/P2H/P3 record one afterfire event for `afterfire_eligible` and zero for
`afterfire_ineligible`; P1 is explicitly `NOT_AVAILABLE_LEGACY` for
persistent-state traces. This proves implementation behavior, not acoustic
superiority. P4 and P5 remain rights-bound source pending; P6 remains an
offline teacher blocked by the local C toolchain.

No legal, rights-bound and RPM/state-synchronised Reference is available.
The repository's R2/R3 material is diagnostic only, so no median reference
improvement, no 20% target improvement, no non-target regression decision and
no candidate selection can be claimed. P2H/P3 remain candidates, not selected
architectures, and Profile Freeze stays closed.

Scope: synthetic, uncalibrated, vehicle-inspired, not OEM reproduction,
`NOT_R1_QUALIFIED`, `NOT_PROFILE_FREEZE_READY`.

The local review package is
`E:/Tesla_speed/review_packages/s12-stage-w-engine-audio-bakeoff-v1` with ZIP
SHA-256 `7c0b2b8fe3879db287a3a22f015ecceb032bc36d371bbc6f458a7839bab25e62`.
It is a labelled engineering package, not a scoring result or a selection.
