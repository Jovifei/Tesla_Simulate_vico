# S12 Numerical Benchmark Suite

Sprint 0.5 adds a qualification and regression plane around the existing S12
solver models. It does not replace HLLC/FVM code, add MUSCL, or implement a
positivity limiter.

## Entry points

Run from `E:\Tesla_speed\prj` after adding this directory to the MATLAB path:

```matlab
addpath('tools/sound_sim/s12/benchmark')
run_s12_benchmarks('case:uniform_state', Profile='quick');
run_s12_benchmarks('category:temporal_accuracy', Profile='quick');
run_s12_benchmarks('all', Profile='full');
run_s12_benchmarks('report-only', ...
    SourceManifest='path/to/benchmark-result.json', ...
    OutputDirectory='path/to/rebuilt');
```

The ordered registry is `config/registry.json`; deterministic `quick` and
`full` profiles live in `config/profiles/`. Every factory returns the same
functional contract: `configure`, `run`, `analyze`, and `accept`.

## Cases

- `uniform_state`: invokes the existing transmissive SSP-RK3 model and checks
  long-time state preservation, CFL, and conservation.
- `long_time_sod`: invokes the same validated model and compares density,
  velocity, and pressure with an independent exact Riemann solution.
- `smooth_periodic_entropy_wave`: composes the existing periodic Forward-Euler
  FVM step with the dedicated SSP-RK3 stage model. It uses the same requested
  dt in all three stages and fails if any stage is CFL-clipped. Fixed-grid
  `dt`, `dt/2`, `dt/4`, and `dt/8` self-convergence establishes time order.

The periodic adapter never copies HLLC/FVM equations. The original
`s12_euler_fvm_periodic_step_ref.slx` remains the only Forward-Euler operator
used by the benchmark path.

## Result contract and artifacts

`benchmark.schema.v1` is defined in `schema/benchmark.schema.v1.json`. A single
Canonical Result produces:

- `benchmark-result.json`: machine manifest and authoritative acceptance;
- `benchmark-report.md`: human review;
- `benchmark-summary.csv` and `smooth-time-scan.csv`: tabular metrics;
- `smooth-convergence.png`, `conservation-residual.png`, and
  `sod-analytic-comparison.png`: deterministic plots.

Report-only rendering never reruns a case or recomputes acceptance. JSON key
order, case order, numeric formatting, filenames, and PNG metadata policy are
fixed. Runtime duration is a measured metric; no current timestamp is written.

Ordinary runs go to ignored `benchmark/out/`. Promotion is deliberately a
separate explicit operation:

```matlab
promote_s12_benchmark_baseline( ...
    'benchmark/out/full-all/benchmark-result.json', ...
    'benchmark/baselines/sprint-0.5', ...
    ApprovalToken='PROMOTE_ACCEPTED_BASELINE');
```

Promotion rejects a non-passing manifest, a missing artifact, an absent token,
or a non-empty destination. Accepted baseline artifacts are versioned; raw
temporary fields and large simulation traces are not.

## Deferred gates

Sprint 1 adds Lax, Shu-Osher, and Woodward-Colella. Sprint 2 adds minmod MUSCL
with first-order fallback. Sprint 3 adds Zhang-Shu-style positivity preservation
at reconstruction, RK-stage, and update levels. Sprint 4 performs FVM versus
Simscape Pipe(G) and analytic Fanno cross-validation. None is implemented here.
