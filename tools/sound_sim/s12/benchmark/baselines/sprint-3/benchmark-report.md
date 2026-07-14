# S12 Sprint 3 Positivity Final Qualification

- Schema: `benchmark.schema.v1` minor `2`
- Profile: `full`
- Git commit: `d3986cf9aaad8e193e0f11574816f84466f410cf`
- MATLAB: `R2026a`
- Acceptance: **PASSED**

| Case | MUSCL rho L1 | PP rho L1 | PP/MUSCL | Recon PP | Flux PP | Retries |
|---|---:|---:|---:|---:|---:|---:|
| uniform_state | 0 | 0 | NaN | 0 | 0 | 0 |
| long_time_sod | 0.00420537883454 | 0.00420407165193 | 0.999689164126 | 0 | 0 | 0 |
| smooth_periodic_entropy_wave | NaN | NaN | NaN | 0 | 0 | 0 |
| smooth_periodic_entropy_wave_spatial | 1.23357809273e-06 | 1.23357809273e-06 | 1 | 0 | 0 | 0 |
| lax_shock_tube | 0.00936506958234 | 0.00936559184735 | 1.00005576734 | 0 | 0 | 0 |
| shu_osher_shock_entropy | NaN | NaN | NaN | 0 | 0 | 0 |
| woodward_colella_blast_wave | NaN | NaN | NaN | 0 | 0 | 0 |
| double_rarefaction | NaN | NaN | NaN | 0 | 28 | 0 |

## Acceptance

Machine acceptance is stored in `benchmark-result.json`; this report does not recompute it.
- `historical_baselines_unchanged`: true
- `pp_full_suite`: true
- `smooth_pp_second_order`: true
- `smooth_pp_no_time_clip`: true
- `smooth_pp_error_no_regression`: true
- `analytic_cases_no_regression`: true
- `all_pp_evidence_healthy`: true
- `nominal_retries_zero`: true
- `stress_pp_activated`: true
- `stress_conservative_and_finite`: true
