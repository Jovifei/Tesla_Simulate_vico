# S12 Numerical Benchmark Report

- Schema: `benchmark.schema.v1`
- Profile: `full`
- Selector: `all`
- Git commit: `2f6aaa2fb663419a0580dd5428b330edf1623d50`
- MATLAB: `R2026a`
- Overall acceptance: **PASSED**

| Case | Category | Status | Finest order | Conservation | Runtime (s) |
|---|---|---:|---:|---:|---:|
| uniform_state | conservation | passed | NaN | 2.77555756156e-17 | 0.3081525 |
| long_time_sod | shock_tube | passed | NaN | 7.51482058344e-15 | 0.2637557 |
| smooth_periodic_entropy_wave | temporal_accuracy | passed | 3.00024402539 | 1.90125692967e-15 | 12.8078887 |
| lax_shock_tube | standard_shock_tube | passed | NaN | 6.46239087126e-14 | 0.7634363 |
| shu_osher_shock_entropy | standard_shock_entropy | passed | NaN | 2.77439383757e-13 | 1.2130443 |
| woodward_colella_blast_wave | standard_blast_wave | passed | NaN | 1.25055521494e-12 | 1.2378578 |

## Artifacts

Machine acceptance is stored in `benchmark-result.json`; this report does not recompute it.
