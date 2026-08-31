# S12 Stage W Architecture Bake-Off (W9/W10)

Status: `BAKEOFF_RENDERED / REFERENCE_TARGET_MISSING / NO_ARCHITECTURE_SELECTED`

## Compared architectures

| ID | Path | Current result |
|---|---|---|
| P1 | Legacy Parent + frozen RuntimePtrAdapter | Rendered baseline |
| P2 | Persistent event-domain + `delay_lpf_v1` + frozen PTR | Rendered |
| P2H | P2 + `waveguide_v1` + localized afterfire + frozen PTR | Rendered |
| P3 | P2H + `timbre_map_v1` | Rendered |
| P4 | Cycle-synchronous recorded resynthesis | Rejected: rights-bound recording pending |
| P5 | Hybrid P2H + clean-room synthetic one-shot residual | Rendered; no third-party transient source |
| P6 | ENSIM4 CFD teacher | Built teacher executable; not a Runtime candidate |

The refreshed `bakeoff_long_v3` rendered all five executable architectures
across the unified Hellcat scene set: idle, 1200/2000/3000 RPM, tip-in, full
load, shift, high-RPM lift, eligible/ineligible afterfire, idle return and
complete-cycle. It renders `hot_idle_20s` at 20.0 s / 960,000 audio frames and
`complete_cycle_60s` at 60.0 s / 2,880,000 audio frames; the other ten scenes
remain declared 1.0 s diagnostic windows. Each executable case has
raw source, post-PTR raw PCM, monitor PCM, state/phase/event/path/gain traces,
metrics, CPU wall time and SHA manifest.
The state trace uses the exact 50 Hz timeline (`0.00` through `19.98`/`59.98` s)
while the rendered audio spans the declared full 20/60 s windows.

## Selection boundary

The current external reference inventory is R3/rights-unverified and lacks
synchronized RPM/state. Therefore the bake-off records Parent/Candidate deltas
but does not compute an OEM identity score, does not select the lowest-distance
candidate and does not create a Profile Candidate. `selected_architecture.json`
is intentionally null with status `REFERENCE_TARGET_MISSING`.

## Evidence

- Current Git-tracked evidence: the five JSON summaries in
  `tasks/reports/runtime/s12-stage-w/`, bound by `artifact_manifest.json`.
- The long-window WAV render root is a local, Git-ignored runtime artifact and is not
  part of this repository delivery.
- Manifest validation: `0 errors`
- P1/P2/P2H/P3/P5 post-PTR outputs are present, SHA-bound and frame-aligned.
- P2/P2H/P3/P5 record an event for `afterfire_eligible` and zero events for
  `afterfire_ineligible`; P1 correctly has no persistent event trace.
- P5 has a deterministic `synthetic_one_shot_v1` residual on valid throttle
  closure or gear-RPM-drop states; P4/P6 reasons are explicit in
  `bakeoff_results.json`.

All output remains synthetic, uncalibrated, vehicle-inspired, not OEM
reproduction, NOT_R1_QUALIFIED and NOT_PROFILE_FREEZE_READY.

Formal qualification outcome: `NO_ARCHITECTURE_CANDIDATE_PASSED`. This records
that no candidate can pass the declared Reference/Parent/Candidate gate while
the legal synchronized R1 Reference is absent; it is not an acoustic rejection,
OEM similarity result or evidence that model redesign has been diagnosed.
