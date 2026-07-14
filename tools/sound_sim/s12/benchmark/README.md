# S12 Numerical Benchmark Suite

Sprint 0.5 established a qualification and regression plane around the
existing S12 solver models. Sprint 1 expands that plane with standard Euler
benchmarks. Sprint 2 adds selectable minmod MUSCL validation without replacing
the frozen first-order HLLC/FVM models. Sprint 3 adds a separate
`muscl_minmod_pp` positivity-preserving mode and accepted baseline while
keeping `first_order` and `muscl_minmod` frozen.

## Entry points

Run from `E:\Tesla_speed\prj` after adding this directory to the MATLAB path:

```matlab
addpath('tools/sound_sim/s12/benchmark')
run_s12_benchmarks('case:uniform_state', Profile='quick');
run_s12_benchmarks('category:temporal_accuracy', Profile='quick');
run_s12_benchmarks('case:lax_shock_tube', Profile='full');
run_s12_benchmarks('case:lax_shock_tube', Profile='full', ...
    Reconstruction='muscl_minmod');
run_s12_benchmarks('category:standard_shock_entropy', Profile='quick');
run_s12_benchmarks('all', Profile='full');
run_s12_muscl_final_qualification('run', Profile='full');
run_s12_positivity_final_qualification('run', Profile='full');
run_s12_benchmarks('report-only', ...
    SourceManifest='path/to/benchmark-result.json', ...
    OutputDirectory='path/to/rebuilt');
run_s12_muscl_final_qualification('report-only', ...
    SourceManifest='path/to/sprint2/benchmark-result.json', ...
    OutputDirectory='path/to/rebuilt-sprint2');
run_s12_positivity_final_qualification('report-only', ...
    SourceManifest='path/to/sprint3/benchmark-result.json', ...
    OutputDirectory='path/to/rebuilt-sprint3');
```

The ordered registry is `config/registry.json`; deterministic `quick` and
`full` profiles live in `config/profiles/`. Every factory returns the same
functional contract: `configure`, `run`, `analyze`, and `accept`.

`Reconstruction` is a mode carried by the profile into each case config. It is
either `first_order` (the default, using the frozen Sprint 1 models),
`muscl_minmod` (dedicated Sprint 2 derived models), or `muscl_minmod_pp`
(dedicated Sprint 3 positivity-preserving derived models). This is
adapter-level model selection, not a second runner, reporter, result schema,
or external FVM/HLLC implementation.

`run_s12_muscl_final_qualification` is the Sprint 2 cross-mode gate. It runs
the existing Full suite once in each mode, then writes a single
`benchmark.schema.v1` minor-1 Canonical Result for the comparison. Its
Markdown, PNG, CSV, and JSON are views of that result; report-only preserves
the source manifest bytes and never reruns a case or recomputes acceptance.

`run_s12_positivity_final_qualification` is the Sprint 3 gate. It compares
the frozen Sprint 2 accepted baseline with the Full `muscl_minmod_pp` suite,
records positivity evidence for every case, and writes a
`benchmark.schema.v1` minor-2 Canonical Result. Report-only also preserves the
source manifest bytes.

## Cases

- `uniform_state`: invokes the existing transmissive SSP-RK3 model and checks
  long-time state preservation, CFL, and conservation.
- `long_time_sod`: invokes the same validated model and compares density,
  velocity, and pressure with an independent exact Riemann solution.
- `smooth_periodic_entropy_wave`: composes the existing periodic Forward-Euler
  FVM step with the dedicated SSP-RK3 stage model. It uses the same requested
  dt in all three stages and fails if any stage is CFL-clipped. Fixed-grid
  `dt`, `dt/2`, `dt/4`, and `dt/8` self-convergence establishes time order.
- `smooth_periodic_entropy_wave_spatial`: uses finite-volume cell-average
  initial data and cell-average analytic reference on `N=50/100/200/400` in
  the Full profile. It records rho/u/p L1 values, observed rho spatial order,
  requested/effective dt, and CFL/end-time-clipping evidence for both modes.
- `lax_shock_tube`: uses the exact Euler Riemann sampler for `rho/u/p` L1
  errors, wave locations, positivity, conservation, CFL, and a two-grid error
  trend. The numerical rarefaction-front locator is a documented 5%-of-fan-
  amplitude diagnostic, not an acceptance threshold.
- `shu_osher_shock_entropy`: records the literature-defined shock--entropy
  interaction on three grids. It deliberately reports shock position,
  post-shock density amplitude, and total variation as self-convergence
  indicators; no unavailable reference array is represented as exact truth.
- `woodward_colella_blast_wave`: records the literature-defined, reflecting-
  wall blast wave on two physical grids. The unchanged transmissive solver is
  driven from a symmetric mirror extension, so the boundary contract is not
  modified. Positivity, finite-state, conservation, CFL, feature-position,
  and failure diagnostics remain visible in the Canonical Result.
- `double_rarefaction`: Sprint 3 exact-vacuum stress case from Hu--Adams--Shu
  style positivity literature. It is not an analytic pressure-value comparison;
  it verifies positive cell/interface/partial states, actual PP activation,
  finiteness, conservation, and honest no-clipping/no-fallback diagnostics.

The periodic adapter never copies HLLC/FVM equations. `first_order` uses the
frozen `s12_euler_fvm_periodic_step_ref.slx`; `muscl_minmod` uses its dedicated
minmod derivative. Both compose the same existing SSP-RK3 stage model and use
one requested dt for all three stages.

## Result contract and artifacts

`benchmark.schema.v1` is defined in `schema/benchmark.schema.v1.json`. A single
Canonical Result produces:

- `benchmark-result.json`: machine manifest and authoritative acceptance;
- `benchmark-report.md`: human review;
- `benchmark-summary.csv`, `smooth-time-scan.csv`, and (when standard cases
  are selected) `standard-grid-scan.csv`: tabular metrics;
- `smooth-convergence.png`, `conservation-residual.png`, and
  `sod-analytic-comparison.png`: deterministic foundation plots;
- `lax-analytic-comparison.png`, `shu-osher-density.png`, and
  `woodward-colella-density.png` when their respective cases are selected.
- Sprint 2 qualification adds `sprint2-cross-mode-comparison.csv` and the
  smooth spatial convergence plot.
- Sprint 3 qualification adds `sprint3-case-comparison.csv`,
  `sprint3-positivity-diagnostics.csv`,
  `sprint3-smooth-spatial-convergence.png`, and
  `sprint3-double-rarefaction.png`.

Report-only rendering never reruns a case or recomputes acceptance. JSON key
order, case order, numeric formatting, filenames, and PNG metadata policy are
fixed. Runtime duration is a measured metric; no current timestamp is written.

Ordinary runs go to ignored `benchmark/out/`. Promotion is deliberately a
separate explicit operation:

```matlab
promote_s12_benchmark_baseline( ...
    'benchmark/out/full/all/benchmark-result.json', ...
    'benchmark/baselines/sprint-1', ...
    ApprovalToken='PROMOTE_ACCEPTED_BASELINE');
```

Promotion rejects a non-passing manifest, a missing artifact, an absent token,
or a non-empty destination. Accepted baseline artifacts are versioned; raw
temporary fields and large simulation traces are not.

## Deferred gates

Sprint 1 added Lax, Shu-Osher, and Woodward-Colella without changing the
solver. Sprint 2 has an accepted `benchmark/baselines/sprint-2` baseline from
implementation commit `715f8cb`. Its Full qualification reports rho spatial
orders of `0.99956` (first order) and `1.93607` (MUSCL/minmod) on the finest
pair, with no smooth-wave CFL or end-time clipping. Constant u/p entropy-wave
errors are at floating-point round-off and are reported, not used to infer an
order. Sprint 3 has an accepted `benchmark/baselines/sprint-3` baseline from
qualification commit `d3986cf`. It validates `muscl_minmod_pp` over the
current ideal-gas Euler benchmark domain with no clipping, no HLLC fallback,
no invalid RK stage, and deterministic report-only SHA-256 regeneration.
Sprint 4 performs FVM versus Simscape Pipe(G) and analytic Fanno
cross-validation. Engine Library, exhaust network, radiation, and audio DSP
remain blocked until Sprint 4 is complete.
