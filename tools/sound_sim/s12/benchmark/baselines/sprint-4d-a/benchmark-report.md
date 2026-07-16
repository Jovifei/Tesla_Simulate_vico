# S12 Numerical Benchmark Report

- Schema: `benchmark.schema.v1`
- Profile: `full`
- Selector: `case:unflanged_open_end_radiation_impedance`
- Git commit: `c3dcd9f057635fea2a74fa7d8d6035f81e63f91d`
- MATLAB: `R2026a`
- Overall acceptance: **PASSED**

| Case | Category | Status | Finest order | Conservation | Runtime (s) |
|---|---|---:|---:|---:|---:|
| unflanged_open_end_radiation_impedance | radiation_impedance | passed | NaN | NaN | 1.1853378 |

## Artifacts

Machine acceptance is stored in `benchmark-result.json`; this report does not recompute it.

## Unflanged open-end radiation impedance

- Geometry: `circular_unflanged`; reference plane: `bore_end`.
- Reference: `levine_schwinger_direct_quadrature.v1`; candidate: `silva_2009_causal_pade_1_2.v1`.
- Maximum complex reflection error: 0.0486927355841
- Maximum phase error: 0.12853374385 rad
- Minimum passivity margin: 0.00011009404248
- Fit stability margin: 19845.6992636
- Frequency arrays are retained in `radiation-impedance-frequency.csv`; this report does not recompute acceptance.
