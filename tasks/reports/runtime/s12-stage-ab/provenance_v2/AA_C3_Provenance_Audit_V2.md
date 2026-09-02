# AA-C3 Provenance Audit v2 (Stage-AB-R Pre-Human Validation Hardening)

STATUS: DIAGNOSTIC_ONLY. No audition package, AA-C0..C3 behavior, frozen PTR/Radiation/Track-P,
or the legacy default renderer is changed by this evidence set.

## P5/AA-C3 PCM SHA parity with v1 evidence

P5 raw PCM byte-identical to provenance/variant_metrics.json for all 11 scenes: YES

## P6 semantic reclassification (AB-R)

P6 rescales pre_ptr(full) - pre_ptr(event_energy=0) by 2+2*load. That residual is the
interventional COUNTERFACTUAL TOTAL EFFECT of combustion energy on the whole pre-PTR mix;
it is NOT a captured source stem. Route kind is now COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE
with source_causal_eligible=False. The old STEM_LOCAL_GAIN label was a semantic overclaim.
See source_causal_eligibility.json for the OFF/ON event_energy probe evidence and the
SOURCE_LOCAL_PARAMETER_NOT_AVAILABLE verdict for the AA-C3/P6 gain paths.

## Source-local OFF/ON probe (event_energy)

- first_changed_layer = combustion_event (causal order)
- per-layer: [('combustion_event', 'CHANGED'), ('per_cylinder_path', 'CHANGED'), ('forced_induction', 'UNCHANGED_PRACTICALLY'), ('pre_transients', 'CHANGED'), ('transients', 'CHANGED'), ('dp_dc', 'CHANGED'), ('pre_ptr', 'CHANGED')]
- Coupling note: non-source stems are NOT bit-identical across OFF/ON because the engine
  shares state (phase/inertia/filter memory); categories CHANGED/UNCHANGED_PRACTICALLY/
  UNCHANGED_BIT_IDENTICAL are defined in the probe method.
- Conclusion: the engine DOES expose genuine source-local parameters (event_energy); the probe
  machinery can place first_changed_layer at the source. AA-C3/P6 do not use such a placement.

## Factorial attribution (exact Shapley over 2^3 corners, mean across 11 scenes)

- RMS: total effect +15.539 dB; broad-scale share 33.5%; event-body 10.247 dB; carrier 0.090 dB

## LF body guard v2 (v1 superseded)

v1 `persistent_energy_ratio = mean(env > percentile(env,50))` is ~0.5 BY CONSTRUCTION for any
continuous envelope, so v1 thresholds 0.6/0.75 were unreachable and v1 boom-risk conclusions
are NOT usable evidence. v2 uses envelope-shape statistics (steady_run_ratio, crest, CV,
fluctuation depth, pulse density) validated against synthetic sine/burst/AM/noise/silence in
the test suite; silent bands report NOT_MEASURABLE.

- parent_legacy: hot_idle boom_risk=OK (contiguity 0.45); full_load boom_risk=OK
- P0: hot_idle boom_risk=NOT_MEASURABLE (contiguity 0.00); full_load boom_risk=NOT_MEASURABLE
- P2: hot_idle boom_risk=NOT_MEASURABLE (contiguity 0.00); full_load boom_risk=OK
- P5: hot_idle boom_risk=ELEVATED (contiguity 0.95); full_load boom_risk=OK
- P6: hot_idle boom_risk=NOT_MEASURABLE (contiguity 0.00); full_load boom_risk=NOT_MEASURABLE

## Blower audit v2

- hot_idle: source carrier 741Hz/68.0dB; audible 741Hz/27.3dB; contribution RMS share 78.4%; verdict=GENUINE_CARRIER_CANDIDATE
- full_load: source carrier 705Hz/48.1dB; audible 704Hz/36.3dB; contribution RMS share 103.8%; verdict=AMBIGUOUS
- complete_cycle: source carrier 705Hz/60.4dB; audible 705Hz/34.3dB; contribution RMS share 103.2%; verdict=AMBIGUOUS_NEAR_CORNER

v1 searched only >=1200 Hz, never split source vs audible, and contained the `del post_ptr`
defect (argument unused). v2 scans the unbiased 600-4000 Hz window and sweeps the low cutoff
900->1500 Hz to test whether a ~1200 Hz singleton peak is a suppression-filter corner artifact.

## Dynamic preservation v2 (event-aligned windows)

v1 measured attack from a whole-clip envelope without an isolated-event contract (0 ms possible).
v2 requires >=250 ms pre and >=500 ms post event context per scene; scenes without a compliant
isolated event report NOT_MEASURABLE instead of a fabricated number.

| variant | idle->WOT RMS dB | cycle env p95-p10 dB | afterfire peak-vs-body dB | events |
|---|---|---|---|---|
| parent_legacy | 9.37 | 19.59 | 2.99 | tip_in:MEAS; gear_shift:MEAS; lift:N/M; idle_return:N/M; afterfire:N/M |
| P0 | 6.17 | 6.64 | 3.70 | tip_in:MEAS; gear_shift:MEAS; lift:N/M; idle_return:MEAS; afterfire:N/M |
| P1 | 9.60 | 10.36 | 4.65 | tip_in:MEAS; gear_shift:MEAS; lift:N/M; idle_return:N/M; afterfire:N/M |
| P4 | 14.57 | 10.65 | 20.63 | tip_in:MEAS; gear_shift:MEAS; lift:N/M; idle_return:N/M; afterfire:N/M |
| P5 | 12.77 | 10.50 | 20.06 | tip_in:MEAS; gear_shift:MEAS; lift:N/M; idle_return:N/M; afterfire:N/M |
| P6 | 10.64 | 9.64 | 3.16 | tip_in:MEAS; gear_shift:MEAS; lift:N/M; idle_return:MEAS; afterfire:N/M |

Afterfire ~20 dB peak-vs-body under AA-C3 (P5) is retained as a RED FLAG (firecracker check)
for the Jovi audition. See metric_definition_registry.json: dynamic_range_db (Stage-AA per-clip
frame-percentile) is NOT equivalent to complete_cycle_envelope_range_db (Stage-AB scene env).

Evidence files (provenance_v2/): energy_gain_taxonomy.json, variant_metrics.json,
aa_c3_metric_attribution.json, source_causal_eligibility.json, lf_body_guard_v2.json,
dynamic_preservation_audit_v2.json, blower_audible_provenance.json, metric_definition_registry.json.
