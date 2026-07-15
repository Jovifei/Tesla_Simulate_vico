# S12 Numerical Benchmark Report

- Schema: `benchmark.schema.v1`
- Profile: `full`
- Selector: `case:fanno_fvm_three_way_cross_validation`
- Git commit: `c517c14685898901d1cf93f1272f222b2f0ebcba`
- MATLAB: `R2026a`
- Overall acceptance: **PASSED**

| Case | Category | Status | Finest order | Conservation | Runtime (s) |
|---|---|---:|---:|---:|---:|
| fanno_fvm_three_way_cross_validation | cross_validation | passed | 1.99045018947 | 0.00409980326549 | 130.5646438 |

## Artifacts

Machine acceptance is stored in `benchmark-result.json`; this report does not recompute it.

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
