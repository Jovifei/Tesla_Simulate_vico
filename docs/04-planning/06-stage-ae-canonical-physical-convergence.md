# Stage AE — Canonical Physical-Acoustic Convergence

## Goal

Turn the successful Stage-AD listening experiment into one maintainable S12 architecture instead of keeping a second renderer.

```text
VehicleState
→ PersistentEventDomainEngine
→ source/path/waveguide
→ optional governed IR transfer
→ frozen PTR/Radiation
→ RAW comparator PCM
→ package-wide MONITOR gain
→ Human A/B
```

## Implemented corrections

1. `EngineAcoustics` is teacher/diagnostic only; the old `build_unified_dashboards.py` default now routes into Stage AE canonical rendering.
2. New Stage-AE comparator path has no `MASTER_SCALE=22`, peak clamp or per-scene normalization.
3. One attenuation-only gain is calculated for the entire vehicle audition package, preserving idle/cruise/WOT relative energy.
4. LFA and GT-R now have normal `s12.event_domain_v1` configs and run through the same `PersistentEventDomainEngine` as Hellcat/Ferrari.
5. Optional exhaust IR is pre-PTR and governed by manifest + SHA + explicit rights status. Unknown public IRs are diagnostic only.
6. Randomness is anchored by an explicit seed.
7. A deterministic partitioned-convolution Python reference was added for future portable C++ equivalence, based on clean-room architectural study of FFTConvolver.
8. The four vehicles share one deterministic 10-scene trace schema and one standalone A/B package format.
9. A generic canonical family fitter now supports `body`, `path`, `induction`, and `afterfire` on the same renderer. Output is deliberately `final_r3_diagnostic_fit.json`, never an OEM-calibrated profile.

## Reusable fitting sequence

```text
governed ReferenceCaseSet
→ body family
→ path family
→ induction family (forced-induction vehicles only)
→ afterfire family
→ fixed absolute reference distance
→ Human A/B
```

Every family consumes the previous diagnostic config as its next base. Monitor/master/broad-pre-PTR gain is outside the search domain.

## Evidence boundary

LFA/GT-R remain `EXPERIMENTAL_R3_AUDITION_PROFILE`. Stage AE is not OEM calibration and cannot promote public-video R3 to R1/R2. External Engine-Sim IR assets remain blocked from product distribution until asset-level provenance is verified.

## Exit criteria

- Stage-AE focused tests + Stage-AD regression + full S12 + Track-P green.
- Four vehicles render from the canonical engine.
- Same-seed render determinism demonstrated.
- package manifests report one gain policy and exact seed.
- Stage-AE standalone dashboard has no remote CSS/JS dependency.
- family-fit output retains input reference evidence level and never promotes it.
- Human feedback saved before any Engineering Profile promotion.
- IR asset provenance explicit; no unverified IR distributed as product media.
