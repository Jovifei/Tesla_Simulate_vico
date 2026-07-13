# S12 Numerical Benchmark Report

- Schema: `benchmark.schema.v1`
- Profile: `full`
- Selector: `all`
- Git commit: `0b955043c9ab309f8bc7b8c3d6b1d954def9f588`
- MATLAB: `R2026a`
- Overall acceptance: **PASSED**

| Case | Category | Status | Finest order | Conservation | Runtime (s) |
|---|---|---:|---:|---:|---:|
| uniform_state | conservation | passed | NaN | 2.77555756156e-17 | 4.4280703 |
| long_time_sod | shock_tube | passed | NaN | 7.51482058344e-15 | 0.5264944 |
| smooth_periodic_entropy_wave | temporal_accuracy | passed | 3.00024402539 | 1.90125692967e-15 | 15.1949186 |

## Artifacts

Machine acceptance is stored in `benchmark-result.json`; this report does not recompute it.
