---
tags: [S12, stage-ab, hardening, ci]
stage: Stage-AB-R
status: AB_PREHUMAN_VALIDATION_HARDENED (DIAGNOSTIC_ONLY)
---

# Stage-AB PreHuman Hardening

AB-R = Pre-Human Validation Hardening & Remote CI Closure. No sound tuning, no default
renderer change, no frozen-path change. FORWARD_ONLY remediation.

## Remote truth (AB-R0)

- origin/main = `f7ba35b` (Stage-AB head), parent `d156f3d7` (PR #4 merge)
- **MAIN_ADVANCED_TO_STAGE_AB_WITHOUT_PR** — no PR for f7ba, GitHub Actions head_sha=f7ba → 0 runs
- `MAIN_ADVANCED...` is provable (ls-remote + API); what it does NOT prove: who/how pushed it,
  and it does not authorize resetting or rewriting main → `FORWARD_ONLY_REMEDIATION`
- f7ba diff audit: 25 files, 0 production-renderer / frozen-boundary changes → `F7BA_ANALYSIS_ONLY_CONFIRMED`
- Hardening branch: `s12-stage-ab-prehuman-validation-hardening` (flat name, no slash), explicit
  refspec pushes only, main-before == main-after asserted around every push

## What was fixed (all analysis/test/receipt layer)

1. P6 reclassified counterfactual (see [[Counterfactual-Residual-vs-True-Source-Stem]])
2. Source-causal eligibility contract A–G + true source-local OFF/ON probe
   (event_energy probe works; AA-C3/P6 gain paths: SOURCE_LOCAL_PARAMETER_NOT_AVAILABLE)
3. LF persistence v1 invalidated, guard v2 (see [[LF-Persistence-Metric-Failure]])
4. Blower post-PTR actually analyzed, source vs audible split (see [[Blower-Source-vs-Audible-Path]])
5. Event-aligned dynamic timing with honest 0 ms semantics (see [[Dynamic-Event-Aligned-Metrics]])
6. `metric_definition_registry.json` — Stage-AA DR vs complete-cycle envelope DR never conflated
7. Afterfire ~20 dB red flag preserved (window validated)

## Status

AA_C3_PROVENANCE_AUDITED_V2 · DIAGNOSTIC_ONLY · REMOTE_CI run on the hardening PR HEAD ·
WAITING_FOR_JOVI_AUDITION · R1_MISSING · PROFILE_FREEZE_NOT_AUTHORIZED.
V3 audition package byte-immutable: manifest SHA `b1ea99d36179…f0964f` recomputed on site.

Receipts: `tasks/reports/runtime/s12-stage-ab/pre_human_hardening/` and `…/provenance_v2/`.
