# S12 Ferrari 458 / RX-7 FD Candidate Migration

Status: `UNSELECTED_CANDIDATE_MIGRATION / W11_PRESELECTION_ONLY`.

W11's formal "Selected Architecture" migration remains blocked by W10: no
architecture has been selected without a legal, RPM/state-synchronised
Reference. This report records a preselection readiness exercise only; it does
not bypass that order of operations.

The evidence root is [`migration_v3`](migration_v3/). Ferrari 458 and RX-7 FD
each rendered P1 Legacy, P2H waveguide and P3 waveguide+timbre-map over
`hot_idle`, `steady_mid`, `full_pull`, `lift` and `complete_cycle`. All cases
are 8.0 s / 384,000-frame stereo PCM24 in raw, post-PTR and monitor domains.
Every same-scene Parent/Candidate group has identical frame count and zero
clipping.

P2H/P3 have persistent phase/omega, event, path-state and monitor-gain traces;
P1 is correctly marked `NOT_AVAILABLE_LEGACY` rather than being given synthetic
state. In both vehicles, P2H/P3 `lift` creates one eligible afterfire event.
The trace proves the configured flat-plane or rotary/turbo path executes, but
does not establish Ferrari or RX-7 OEM likeness, a reference improvement or a
selected architecture.

Scope: synthetic, uncalibrated, vehicle-inspired, not OEM reproduction,
`NOT_R1_QUALIFIED`, `NOT_PROFILE_FREEZE_READY`.
