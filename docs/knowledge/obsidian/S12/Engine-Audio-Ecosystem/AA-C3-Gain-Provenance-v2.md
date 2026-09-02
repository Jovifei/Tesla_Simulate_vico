---
tags: [S12, stage-ab, provenance, hardening]
stage: Stage-AB-R
status: AA_C3_PROVENANCE_AUDITED_V2 (DIAGNOSTIC_ONLY)
---

# AA-C3 Gain Provenance v2

SUPERSEDES: [[AA-C3-Gain-Provenance]] validation semantics only — the v1 exact 2^3 Shapley
factorial and bit-exact P5===AA-C3 results remain valid. What failed in v1 was part of the
*validation interpretation*, not the factorial math.

## What v2 adds

- P6 reclassified: `COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE`, `source_causal_eligible=false`.
  See [[Counterfactual-Residual-vs-True-Source-Stem]].
- Source-causal eligibility contract (`source_causal_eligibility.json`): 7 conditions (A-G)
  including first_changed_layer must be in combustion/event/source, never pre_ptr/post_dp/post_ptr/PCM.
- True source-local OFF/ON probe on `combustion_event.event_energy`: first_changed_layer =
  combustion_event. The engine DOES expose source-local parameters; AA-C3/P6 gain paths do not use them
  → `SOURCE_LOCAL_PARAMETER_NOT_AVAILABLE` for those paths is the honest verdict.
- LF guard v2, blower source-vs-audible split, event-aligned dynamic metrics — see
  [[LF-Persistence-Metric-Failure]], [[Blower-Source-vs-Audible-Path]], [[Dynamic-Event-Aligned-Metrics]].
- `metric_definition_registry.json`: every metric registered with equation/domain/window/aggregation;
  Stage-AA `dynamic_range_db` (Parent ≈9.368 / Stage-Z ≈3.582 / AA-C3 ≈5.747) is NOT the same metric as
  Stage-AB `complete_cycle_envelope_range_db` (Parent ≈19.6 / P5 ≈10.5).

## Receipts

- `tasks/reports/runtime/s12-stage-ab/provenance_v2/` (v2 evidence set)
- `tasks/reports/runtime/s12-stage-ab/pre_human_hardening/` (remote truth + f7ba scope audit)

## Status

DIAGNOSTIC_ONLY. No sound tuning. WAITING_FOR_JOVI_AUDITION. R1_MISSING.
PROFILE_FREEZE_NOT_AUTHORIZED.
