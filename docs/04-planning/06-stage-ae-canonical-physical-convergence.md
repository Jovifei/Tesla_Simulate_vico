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

## Corrections in this stage

1. `EngineAcoustics` is teacher/diagnostic only; `build_unified_dashboards.py` no longer uses it by default.
2. No comparator-side `MASTER_SCALE=22` or per-scene normalize is used in the new Stage-AE path.
3. One attenuation-only gain is calculated for the entire vehicle audition package, preserving idle/cruise/WOT relative energy.
4. LFA and GT-R receive normal `s12.event_domain_v1` configs and therefore run through the same PersistentEventDomainEngine as Hellcat/Ferrari.
5. Optional exhaust IR is a pre-PTR governed asset with SHA/rights checks. Unknown public IRs are diagnostic only.
6. Randomness is anchored by an explicit seed in the canonical renderer.
7. A deterministic partitioned-convolution Python reference is added for future C++ equivalence.

## Evidence boundary

LFA/GT-R remain `EXPERIMENTAL_R3_AUDITION_PROFILE`. Stage AE is not OEM calibration and cannot promote public-video R3 to R1/R2.

## Exit criteria

- Stage-AE focused tests + full S12 + Track-P green.
- Four vehicles render from the canonical engine.
- package manifests report one gain policy and exact seed.
- no remote web dependency in Stage-AE standalone dashboard.
- Human feedback saved before any Engineering Profile promotion.
- IR asset provenance explicit; no unverified IR distributed as product media.
