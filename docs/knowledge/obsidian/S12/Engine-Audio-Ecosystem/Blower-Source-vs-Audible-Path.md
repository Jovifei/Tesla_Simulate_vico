---
tags: [S12, negative-knowledge, blower, ptr]
stage: Stage-AB-R
---

# Blower Source vs Audible Path

**NEGATIVE KNOWLEDGE — a source-layer carrier is not an audible post-PTR carrier.**

v1 defect: `blower_carrier_metrics(forced_layer, post_ptr, ...)` accepted `post_ptr`
but ended with `del post_ptr` — the argument was never analyzed
(`POST_PTR_NOT_ACTUALLY_ANALYZED`), and the search window was biased to >= 1200 Hz
(the AA-C3 suppression filter corner), so a peak ≈1200 Hz could not be
distinguished from a filter/search corner artifact.

## v2 audit (`blower_audible_provenance.json`)

Three separated domains:

- forced_source_metrics (forced-induction source stem)
- audible_output_metrics (post-PTR full output)
- forced_contribution_to_output_metrics (postPTR(full) − postPTR(no_forced) — counterfactual
  attribution, NOT an independent source stem)

Unbiased search 600–4000 Hz + diagnostic cutoff sweep 900→1500 Hz (analysis only,
no sound candidates). Peak pinned at the suppression corner would mean
`FILTER_CORNER_ARTIFACT_SUSPECTED`; peaks stable away from the corner raise
PHYSICAL_CARRIER_CONFIDENCE.

## Results (frozen AA-C3 audio)

| scene | source carrier | audible carrier | contribution RMS share | verdict |
|---|---|---|---|---|
| hot_idle | 741 Hz / 68.0 dB | 741 Hz / 27.3 dB | 78.4% | GENUINE_CARRIER_CANDIDATE |
| full_load | 705 Hz / 48.1 dB | 704 Hz / 36.3 dB | 103.8% | AMBIGUOUS |
| complete_cycle | 705 Hz / 60.4 dB | 705 Hz / 34.3 dB | 103.2% | AMBIGUOUS_NEAR_CORNER |

hot_idle: carrier exists in BOTH source and audible layers, PTR attenuates it by
~40 dB but it survives → genuine whine candidate for Jovi audition discussion.
full_load/complete_cycle: attribution ambiguous (share >100% = residual interacts
with other layers); near-corner verdict kept for honesty.

Tracking: lagged correlation + RPM/order ridge continuity, not just zero-lag
envelope correlation; constant state traces → NOT_MEASURABLE (never tracking_error=0).

Related: [[AA-C3-Gain-Provenance-v2]], [[Stage-AB-Negative-Knowledge]]
