# S12 Numerical Benchmark Report

- Schema: `benchmark.schema.v1`
- Profile: `full`
- Selector: `all`
- Git commit: `4afe65a67ed21822422f1eb6dbf43fdd627072d3`
- MATLAB: `R2026a`
- Overall acceptance: **PASSED**

| Case | Category | Status | Finest order | Conservation | Runtime (s) |
|---|---|---:|---:|---:|---:|
| uniform_state | conservation | passed | NaN | 2.77555756156e-17 | 0.624742 |
| long_time_sod | shock_tube | passed | NaN | 7.80103254721e-15 | 0.3898887 |
| smooth_periodic_entropy_wave | temporal_accuracy | passed | 3.00619517259 | 1.9931972739e-15 | 11.233569 |
| smooth_periodic_entropy_wave_spatial | spatial_accuracy | passed | 1.93606788833 | NaN | 28.8124258 |
| lax_shock_tube | standard_shock_tube | passed | NaN | 7.32023036745e-14 | 1.2249678 |
| shu_osher_shock_entropy | standard_shock_entropy | passed | NaN | 3.68517969333e-13 | 3.9695953 |
| woodward_colella_blast_wave | standard_blast_wave | passed | NaN | 1.63780100593e-12 | 9.0135704 |
| double_rarefaction | positivity_stress | passed | NaN | 2.49800180541e-15 | 0.5012783 |
| fanno_pipe_g_cross_validation | cross_validation | passed | NaN | NaN | 11.1178678 |
| fanno_fvm_three_way_cross_validation | cross_validation | passed | 1.99045018947 | 0.00409980326549 | 96.0362221 |
| transient_pipe_wave_cross_validation | transient_wave | passed | 0.887656671168 | 2391.50914453 | 47.1305764 |
| unflanged_open_end_radiation_impedance | radiation_impedance | passed | NaN | NaN | 0.1098431 |
| radiation_single_tone | radiation_boundary_time_domain | passed | NaN | NaN | 7.8710047 |
| radiation_multisine | radiation_boundary_time_domain | passed | NaN | NaN | 1.7091279 |
| radiation_chirp | radiation_boundary_time_domain | passed | NaN | NaN | 1.5605106 |
| radiation_pulse | radiation_boundary_time_domain | passed | NaN | NaN | 1.6494011 |
| radiation_limit_open | transient_open_end_impedance | passed | NaN | NaN | 1.6368538 |
| radiation_limit_matched | radiation_boundary_time_domain | passed | NaN | NaN | 1.6604124 |
| radiation_limit_rigid | radiation_boundary_time_domain | passed | NaN | NaN | 1.7416896 |
| radiation_amplitude_linearity | radiation_boundary_time_domain | passed | NaN | NaN | 4.5288377 |
| radiation_grid_convergence | radiation_boundary_time_domain | passed | 1.00221423269 | NaN | 43.4830026 |
| radiation_time_convergence | radiation_boundary_time_domain | passed | NaN | NaN | 70.0566462 |
| radiation_zero_input_decay | radiation_boundary_time_domain | passed | NaN | NaN | 7.3445356 |
| radiation_retry_rollback | radiation_boundary_time_domain | passed | NaN | NaN | 0 |

## Artifacts

Machine acceptance is stored in `benchmark-result.json`; this report does not recompute it.

## Positivity diagnostics

| Case | Recon PP activations | Flux PP activations | Min recon theta | Min flux theta | Retries |
|---|---:|---:|---:|---:|---:|
| uniform_state | 0 | 0 | 1 | 1 | 0 |
| long_time_sod | 0 | 0 | 1 | 1 | 0 |
| smooth_periodic_entropy_wave | 0 | 0 | 1 | 1 | 0 |
| smooth_periodic_entropy_wave_spatial | 0 | 0 | 1 | 1 | 0 |
| lax_shock_tube | 0 | 0 | 1 | 1 | 0 |
| shu_osher_shock_entropy | 0 | 0 | 1 | 1 | 0 |
| woodward_colella_blast_wave | 0 | 0 | 1 | 1 | 0 |
| double_rarefaction | 0 | 28 | 1 | 0.932342353373 | 0 |

## Fanno / Pipe (G) cross-validation

- Reference: `analytical_fanno_exact_relation`
- Single-pipe maximum relative error: 0.0111416637098
- Five-segment maximum relative error: 0.00105167676678

## Fanno three-way cross-validation

- Balance law: `fanno_constant_darcy`
- Boundary: `subsonic_fanno_validation.v1`
- Moderate-pipe finest grid order: 1.99841328839
- Maximum profile L1 relative error: 0.000739906441009
- Maximum outlet relative error: 0.0164152906696
- Minimum sonic margin: 0.614655637692
- Source-balanced momentum residual: 0.00409980326549
- Uniform friction-decay maximum relative error: 2.84298688176e-16
- Cold-start steady: 1 (linear_endpoint_primitive.v1)
- Maximum FVM / five-segment station difference: 0.00129990763318

## Transient pipe-wave cross-validation

- Reference wave speed: 530.385708706 m/s
- Maximum arrival-time error: 7.16890579078e-06 s
- Closed pressure reflection coefficient: 0.995097971984
- Open pressure reflection coefficient: -0.994250478727
- Pipe(G) open end is an ambient-pressure reservoir approximation, not analytical truth.

## Unflanged open-end radiation impedance

- Geometry: `circular_unflanged`; reference plane: `bore_end`.
- Reference: `levine_schwinger_direct_quadrature.v1`; candidate: `silva_2009_causal_pade_1_2.v1`.
- Maximum complex reflection error: 0.0486927355841
- Maximum phase error: 0.12853374385 rad
- Minimum passivity margin: 0.00011009404248
- Fit stability margin: 19845.6992636
- Frequency arrays are retained in `radiation-impedance-frequency.csv`; this report does not recompute acceptance.
