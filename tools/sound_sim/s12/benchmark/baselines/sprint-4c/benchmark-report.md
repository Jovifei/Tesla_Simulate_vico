# S12 Numerical Benchmark Report

- Schema: `benchmark.schema.v1`
- Profile: `full`
- Selector: `case:transient_pipe_wave_cross_validation`
- Git commit: `48deed79ce45cf0a3066d6bd264821d0105f1c6b`
- MATLAB: `R2026a`
- Overall acceptance: **PASSED**

| Case | Category | Status | Finest order | Conservation | Runtime (s) |
|---|---|---:|---:|---:|---:|
| transient_pipe_wave_cross_validation | transient_wave | passed | 0.887656671168 | 2391.50914453 | 64.2875483 |

## Artifacts

Machine acceptance is stored in `benchmark-result.json`; this report does not recompute it.

## Transient pipe-wave cross-validation

- Reference wave speed: 530.385708706 m/s
- Maximum arrival-time error: 7.16890579078e-06 s
- Closed pressure reflection coefficient: 0.995097971984
- Open pressure reflection coefficient: -0.994250478727
- Pipe(G) open end is an ambient-pressure reservoir approximation, not analytical truth.
