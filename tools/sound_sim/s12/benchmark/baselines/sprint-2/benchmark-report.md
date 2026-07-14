# S12 Sprint 2 MUSCL Final Qualification

- Schema: `benchmark.schema.v1` minor `1`
- Profile: `full`
- Git commit: `715f8cb383acd8b62c0ab62c99b38c4f7f2612c4`
- MATLAB: `R2026a`
- Acceptance: **PASSED**

| Case | First-order rho L1 | MUSCL rho L1 | MUSCL/first |
|---|---:|---:|---:|
| uniform_state | 0 | 0 | NaN |
| long_time_sod | 0.0133237115957 | 0.00420537883454 | 0.315631181622 |
| smooth_periodic_entropy_wave | NaN | NaN | NaN |
| smooth_periodic_entropy_wave_spatial | 0.000501334423713 | 6.37170820847e-05 | 0.127094967094 |
| lax_shock_tube | 0.0230969955377 | 0.00936506958234 | 0.405467004011 |
| shu_osher_shock_entropy | NaN | NaN | NaN |
| woodward_colella_blast_wave | NaN | NaN | NaN |

## Smooth Periodic Entropy Wave
Cell-average initial data and analytic reference are used at every grid.

| Scheme | Finest rho order | CFL clipped | End-time clipped |
|---|---:|---:|---:|
| first_order | 0.999555210171 | 0 | 0 |
| muscl_minmod | 1.93606788833 | 0 | 0 |

## Acceptance

Machine acceptance is stored in `benchmark-result.json`; this report does not recompute it.
