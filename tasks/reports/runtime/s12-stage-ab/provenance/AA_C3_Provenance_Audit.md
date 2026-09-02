# AA-C3 Provenance Audit (Stage-AB AB1)

STATUS: DIAGNOSTIC_ONLY. This audit does not change AA-C0..C3, the v3 audition package, or any default renderer.

## Classification of the AA-C3 pressure scale

`_candidate_pre_ptr` (candidates.py:90-108) computes `base = layers["pre_ptr"]` and then
`result = base * (pressure_idle_scale + pressure_load_scale * load)`.
`layers["pre_ptr"]` is the FULL mix (combustion + forced induction + mechanical + cycle-sync +
transients + dp_dc/transfer-IR chain output; persistent_engine.py:694-708). For AA-C1/C2/C3 the
scales are (2,2), so the entire pre-PTR mix is multiplied by `2 + 2*load`.

**Classification: STATE_DEPENDENT_BROAD_PRE_PTR_SCALING** - not a source-pressure-AC repair,
despite the AA-C1 parameter-family name `pressure_ac_load_scale`.
The `event_body_mix` and `forced_carrier_reduction` terms ARE stem-derived (combustion_event /
forced_induction layers) and classify as FILTER_REBALANCE.

## Factorial attribution (exact Shapley over 2^3 corners, mean across 11 scenes)

- RMS: total effect +15.539 dB; broad-scale share 33.5%; event-body +10.247 dB; carrier +0.090 dB
- Dynamic range: total +1.805 dB; broad-scale share 18.1%
- Centroid: total -2358.8 Hz; broad-scale share -24.3%
- Sharpness: total -0.1780; broad-scale share -23.9%

## P4 test: does the correction hold WITHOUT the broad scale?

| metric | P0 (Stage-Z) | P4 (event+carrier, no broad) | P5 (= AA-C3) |
|---|---|---|---|
| rms_dbfs | -61.8113 | -47.2204 | -46.2722 |
| dynamic_range_db | 3.8336 | 6.4987 | 5.6381 |
| spectral_centroid_hz | 4180.3378 | 591.4850 | 1821.5820 |
| sharpness_proxy | 0.2920 | 0.0218 | 0.1140 |

## Dynamic preservation (raw PCM, no normalization)

| variant | idle->WOT RMS delta dB | cycle envelope range dB | tip-in attack dB | afterfire peak vs body dB |
|---|---|---|---|---|
| Parent (legacy) | 9.37 | 19.59 | 14.35 | 2.99 |
| Stage-Z | 6.17 | 6.64 | 6.99 | 3.70 |
| P1 | 9.60 | 10.36 | 10.11 | 4.65 |
| P4 | 14.57 | 10.65 | 25.96 | 20.63 |
| P5 | 12.77 | 10.50 | 23.50 | 20.06 |
| P6 | 10.64 | 9.64 | 10.34 | 3.16 |

Findings:

- AA-C3/P5 idle->WOT layering (+12.77 dB) EXCEEDS Parent (+9.37 dB); the broad pre-PTR scaling
  is not flattening idle->WOT dynamics. The remaining gap is complete-cycle envelope range
  (Parent 19.59 dB vs P5 10.50 dB vs Stage-Z 6.64 dB).
- NEGATIVE KNOWLEDGE: the event-body injection lifts afterfire peak-vs-body to ~20 dB
(Parent ~3 dB, Stage-Z ~3.7 dB). If Jovi reports firecracker-like afterfire, the mapping is
event-body 120-400 Hz injection in the afterfire scene, NOT a single afterfire gain knob.
- P6 (combustion-local scaling) keeps afterfire at Parent-like levels (3.16 dB) while restoring
idle->WOT to +10.64 dB: closest to Parent dynamics among repair variants.

## LF body guard (boom risk)

- parent_legacy: hot_idle 20-90Hz band ratio 0.216, boom_risk hot_idle=OK, full_load=OK
- P0: hot_idle 20-90Hz band ratio 0.111, boom_risk hot_idle=OK, full_load=OK
- P2: hot_idle 20-90Hz band ratio 0.118, boom_risk hot_idle=OK, full_load=OK
- P5: hot_idle 20-90Hz band ratio 0.129, boom_risk hot_idle=OK, full_load=OK
- P6: hot_idle 20-90Hz band ratio 0.064, boom_risk hot_idle=OK, full_load=OK

## Blower provenance

Carrier peak sits at ~1200-1234 Hz, i.e. at/near the 1200 Hz suppression filter corner, with
prominence 20-24 dB, sideband/carrier ~0.49 and a strongly broadband-dominated spectrum
(broadband/tonal > 500). RPM envelope tracking is poor at idle (~0.97 error) and good at full
load (~0.02). Sharpness reduction ALONE is not accepted as blower-realism evidence; whether the
suppressed content is true Hellcat blower identity or an electronic carrier artifact remains
OPEN until Jovi feedback.

## Consequences for Round 2 (one round only, source-causal)

DATA-DRIVEN CONCLUSION (11-scene mean, exact Shapley): the AA-C3 RMS recovery is dominated by
the STEM-DERIVED event-body 120-400 Hz injection (~66% of the +15.5 dB), with the broad
pre-PTR state scaling contributing ~33%. The broad scale is NOT the primary RMS fix; instead
it provides spectral rebalancing (+573 Hz centroid, +0.043 sharpness) that counteracts the
event-body darkening. Without it (P4), the centroid collapses to ~591 Hz and sharpness to
~0.022 - the correction does NOT hold spectrally without the broad scale interaction.

- Round 2 must still move residual broad-scale effect upstream (combustion-event amplitude vs
  load, event pulse energy, pressure-AC extraction, collector/path transmission,
  forced-induction balance) and MUST NOT continue `base_pre_ptr * 2~4`.
- The event-body injection is stem-derived but its +4.0 mix is a large additive overlay: Round 2
  should re-derive body energy from source events (state-dependent event energy) rather than a
  fixed 4.0x bandpassed overlay, and check the afterfire scene overshoot it causes.
- P6 (combustion-difference local state scaling) is the in-repo preview of the upstream
  direction: the SAME load-dependent scale applied only to the combustion difference signal
  `pre_ptr(full) - pre_ptr(event_energy=0)`, leaving every other stem untouched.
- P6 is an engineering diagnostic; it is NOT an audition winner before Jovi feedback.

## Method note

The combustion difference decomposition is an exact causal difference method (no linearity
assumption): the two engine renders differ ONLY in `combustion_event.event_energy` (0.6 -> 0).

Evidence files: `energy_gain_taxonomy.json`, `variant_metrics.json`,
`aa_c3_metric_attribution.json`, `dynamic_preservation_audit.json`, `lf_body_guard.json`,
`blower_provenance.json`. P5 == AA-C3 raw PCM bit-exact (verified in tests).
