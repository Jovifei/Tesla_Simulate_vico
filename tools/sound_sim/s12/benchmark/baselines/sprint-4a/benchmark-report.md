# S12 Numerical Benchmark Report

- Schema: `benchmark.schema.v1`
- Profile: `full`
- Selector: `case:fanno_pipe_g_cross_validation`
- Git commit: `fcfe6deb2175237866633ee7804cfa3be64aef23`
- MATLAB: `R2026a`
- Overall acceptance: **PASSED**

| Case | Category | Status | Finest order | Conservation | Runtime (s) |
|---|---|---:|---:|---:|---:|
| fanno_pipe_g_cross_validation | cross_validation | passed | NaN | NaN | 29.6659162 |

## Artifacts

Machine acceptance is stored in `benchmark-result.json`; this report does not recompute it.

## Fanno / Pipe (G) cross-validation

- Reference: `analytical_fanno_exact_relation`
- Single-pipe maximum relative error: 0.0111416637098
- Five-segment maximum relative error: 0.00105167676678
