---
tags: [S12, negative-knowledge, metrics, lf]
stage: Stage-AB-R
---

# LF Persistence Metric Failure

**NEGATIVE KNOWLEDGE — the v1 metric was invalid by construction.**

v1 definition:

    persistent_ratio = mean( env > percentile(env, 50) )

For any continuous envelope distribution, the fraction of samples strictly above
the distribution's own median is ≈ 0.5 BY CONSTRUCTION. Therefore:

- `persistent > 0.6` and `> 0.75` thresholds were essentially unreachable
- every `boom_risk = OK` derived from it was NOT evidence
- all v1 boom conclusions are marked `OLD_LF_GUARD_INVALIDATED`

A metric that returns 0.5 by construction is not a persistence metric.
A test that only proves its own metadata is not a causal test.

## LF guard v2

Envelope-shape statistics per band (20-60 / 60-90 / 90-120 / 120-180 / 180-250 / 250-400 Hz):

- envelope_crest_db (p95-p50), envelope_cv_linear, fluctuation_depth_db (p90-p10)
- envelope_contiguity_ratio (fraction of frames within ±1.5 dB of median — this is the
  reference-independent "steadiness" measure; threshold never equals the median itself)
- pulse_density_per_s (peaks above p75)
- band_ratio (energy share), presence NOT_MEASURABLE below -70 dB floor

Boom verdict: HIGH when the 20-90 Hz envelope is STEADY (crest < 4 dB AND contiguity > 0.85 AND
pulse density < 5/s) AND band ratio elevated (> 0.35). Validated on synthetic sine (steady → flagged
class), bursts (not flagged), AM pulse, broadband noise, silence (NOT_MEASURABLE — never auto-PASS).

## v2 results on the frozen P5/AA-C3 audio

- P5 hot_idle: **ELEVATED** (contiguity 0.95) — the earlier "P5 OK" does not survive
- P5 full_load: OK
- Still not a human LF pass; LF evidence is diagnostic only.

Related: [[AA-C3-Gain-Provenance-v2]], [[Stage-AB-Negative-Knowledge]]
