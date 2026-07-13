# S12 Physical Engine and Exhaust Model

S12 replaces the V6 procedural pressure-pulse path with inspectable Simulink
physics. The models in this directory are reference tests, not final vehicle
audio and not yet App assets.

## Current Models

- `models/cylinder_ref/c63_cylinder_adiabatic_ref.slx`
  - M156 crank-slider volume.
  - Analytic adiabatic compression reference.
- `models/cylinder_ref/c63_cylinder_combustion_ref.slx`
  - Crank-angle-resolved Wiebe heat release.
  - Closed-cylinder first law with boundary work and Woschni wall heat.
  - Pressure derived from cylinder mass, temperature, and volume.
- `models/cylinder_ref/c63_exhaust_valve_flow_ref.slx`
  - Lift-dependent `Cd(lift)`, effective curtain area, and port-area limit.
  - Bidirectional choked/subcritical mass flow and enthalpy-flow sign.
- `models/cylinder_ref/c63_cylinder_blowdown_ref.slx`
  - NASA-polynomial fresh-air and burned-product property tables.
  - Temperature- and burn-fraction-dependent `cp`, `cv`, `R`, and `gamma`.
  - Coupled cylinder mass, temperature, pressure, valve flow, and flow energy.
- `models/pipe_ref/c63_primary_pipe_wave_ref.slx`
  - Eight Simscape Gas control volumes over a 0.48 m primary pipe.
  - 700 K wall boundary and finite-impedance outlet restriction.
  - Pressure-pulse propagation, compressibility, inertia, friction, and heat transfer.
- `models/pipe_ref/c63_primary_pipe_wave_ref_{4,16}cell.slx`
  - Coarse/fine variants around the eight-cell reference, all 0.48 m long.
  - Component-level propagation-delay and outlet-amplitude convergence check.
- `models/pipe_ref/c63_primary_pipe_open_end_ref.slx`
  - Eight-cell pressure-release boundary with a probe 0.06 m from the inlet.
  - Separates the incident pulse from the negative open-end reflection.
- `models/fvm_ref/s12_euler_hllc_flux_ref.slx`
  - Embedded MATLAB Function implementation of the Euler HLLC interface flux.
  - Exposes mass, momentum, energy fluxes and the three HLLC wave speeds.
- `models/fvm_ref/s12_euler_fvm_periodic_step_ref.slx`
  - First-order periodic finite-volume update for eight conservative cells.
  - HLLC interfaces and automatic CFL time-step limiting are embedded in the model.
- `models/fvm_ref/s12_euler_ssprk3_sod_ref.slx`
  - First-order HLLC spatial operator with three-stage SSP-RK3 time integration.
  - Transmissive ghost cells, per-step CFL control, exact end-time clipping, and
    open-boundary flux accounting for the 200-cell Sod reference.
- `models/fvm_ref/s12_euler_ssprk3_periodic_ref.slx`
  - Canonical SSP-RK3 stage convex combinations for periodic validation.
  - Contains no duplicate HLLC/FVM implementation; the Benchmark adapter calls
    the existing periodic Forward-Euler model for every stage.

Property-table source:

- `library/properties/s12_nasa_mixture_tables.m`
- NASA/TP-2002-211556, *NASA Glenn Coefficients for Calculating
  Thermodynamic Properties of Individual Species*.

All fixed and provisional values are stored as documented `Simulink.Parameter`
objects in each model workspace. Grade D values are identification initial
conditions and must not be reported as OEM specifications.

## Verification

Run from MATLAB:

```matlab
cd('E:\Tesla_speed\prj\tools\sound_sim\s12')
results = runtests('tests');
assertSuccess(results);
```

Current acceptance covers:

- TDC/BDC geometry and compression ratio.
- Closed-cycle pressure, temperature, burn fraction, heat, and wall loss.
- Analytic choked and subcritical valve mass flow.
- Forward/reverse valve-flow direction, `Cd(lift)`, and enthalpy flow.
- Integrated exhaust mass flow against cylinder mass loss.
- Temperature-dependent fresh/burned mixture properties.
- Primary-pipe pulse propagation delay and attenuation.
- Primary-pipe 4/8/16-cell grid convergence.
- Open-end pressure-release boundary and negative reflected-wave timing.
- Uniform-flow Euler flux, stationary-contact preservation, and HLLC mirror symmetry.
- Uniform-state preservation, periodic Euler conservation, and one-step Sod positivity.
- Long-time SSP-RK3 uniform-state preservation and Sod exact-Riemann comparison.
- Config-driven Numerical Benchmark Suite with uniform, Sod, and smooth periodic
  entropy-wave cases.
- Fixed-grid `dt/dt/2/dt/4/dt/8` SSP-RK3 self-convergence near third order,
  explicit no-CFL-clipping checks, deterministic reports, and gated baseline
  promotion.
- Simulink connectivity checks for the four cylinder/property models.
- Compile, simulation, and behavioral propagation checks for the pipe model.

## Known Boundaries

- The older closed-cylinder reference intentionally retains constant `cv` as a
  comparison baseline. The coupled blowdown model uses NASA-derived tables.
- The coupled model currently supports forward exhaust outflow. Reverse flow
  and intake-valve exchange remain pending.
- Burned composition currently assumes complete stoichiometric iso-octane
  products (`N2`, `CO2`, `H2O`). Rich combustion species and dissociation must
  be added before full-load M156 calibration.
- M156 cam event angles, `Cd(lift)`, connecting-rod length, and exhaust geometry
  remain bounded identification parameters until stronger evidence is found.
- No 1D manifold, catalyst, muffler, tailpipe radiation, or audio export exists
  in S12 yet.

## Primary-Pipe Reference Result

The 5 ms reference solve completes in about 5 seconds on the current machine.
A 5 kPa inlet pulse produces a 3.078 kPa outlet response with a measured
0.891 ms arrival delay. This is a component-level propagation reference, not
yet the complete C63 exhaust network or calibrated tailpipe sound pressure.

The dedicated `model_check` tool currently reports false unconnected-port
warnings on branched Simscape conserving-port networks. The pipe acceptance
therefore uses successful model compilation plus the behavioral propagation
test as the authoritative connectivity evidence.

The 4/8/16-cell delays are 0.868, 0.891, and 0.895 ms. Their outlet pulse
peaks are 2.459, 3.078, and 3.133 kPa. The 8-to-16-cell change is 0.46% for
delay and 1.77% for peak amplitude. Open-end reflection is validated
separately below; the production full-exhaust finite-volume solver remains
pending beyond the validated HLLC/SSP-RK3 reference models.

The open-end probe records a +5.653 kPa incident peak and a -3.409 kPa
reflected peak. The magnitude ratio is 0.603, and the negative wave crosses
the 10% threshold at 1.996 ms. The ideal atmospheric boundary remains within
1 Pa of its initial pressure. This validates the reference boundary behavior,
not final tailpipe radiation impedance or free-field sound pressure.

The embedded HLLC block returns `[36, 102405, 10655325]` for the accepted
uniform-flow case and `[0, 100000, 0]` for a stationary contact at equal
pressure. Mirrored left/right states preserve momentum flux and reverse mass,
energy, and wave-speed directions. The first-order finite-volume update and
SSP-RK3 long-time reference are validated below; MUSCL reconstruction,
positivity limiting, and production boundary conditions remain pending.

The periodic FVM step preserves a uniform state and closes total mass,
momentum, and energy over the periodic domain. For the accepted eight-cell Sod
initial state, a requested 1 ms step is limited to 12.026756 us at CFL 0.45;
density and pressure remain positive after the update. This is a first-order
single-step reference and remains unchanged as the spatial-update baseline.

The separate SSP-RK3 model advances a 200-cell dimensionless Sod problem to
`t=0.2` with transmissive boundaries. It accepts 191 global steps, reaches a
maximum recorded Courant number of `0.45000000000000012`, and keeps minimum
density and pressure at `0.1250000000005` and `0.1000000000006`. The numerical
shock and contact positions are `0.855` and `0.680`, compared against an
independent Toro-style exact Riemann solution with tolerances of `2*dx` and
`4*dx`. The largest scaled open-boundary conservation residual is
`1.03e-15`. A uniform-state case runs 119 steps with maximum state error
`2.78e-17`.

This establishes SSP-RK3 time integration on the existing first-order HLLC
spatial operator. It does not establish second-order spatial accuracy or
unconditional positivity. MUSCL reconstruction, a positivity limiter,
FVM/Simscape cross-validation, and production exhaust boundaries remain pending.

## Numerical Benchmark Suite

Sprint 0.5 is documented in `benchmark/README.md`. The default products are a
Markdown report, deterministic PNG plots, CSV metric tables, and one canonical
JSON manifest. Single-case, category, full-suite, and report-only entry points
all use `run_s12_benchmarks`; report-only rendering preserves the acceptance
stored in JSON.

The accepted Full profile uses 200 cells for Sod and 64 cells for the smooth
periodic wave. The validated Full result has Sod density/velocity/pressure L1
errors `0.0133237/0.0236653/0.0114884`; Smooth observed orders are
`3.00048/3.00024`, with maximum scaled conservation error `1.90e-15`. These
figures qualify the current time integrator only; the spatial operator remains
first order.

Research specifications live in:

- `E:\Tesla_speed\docs\sound-simulation\S12_全物理Simulink一维发动机排气声学研究规格.md`
- `E:\Tesla_speed\docs\sound-simulation\S12_C63_Hellcat参数证据矩阵.md`
- `E:\Tesla_speed\docs\sound-simulation\S12_Simulink一维气体动力学架构决策.md`
- `E:\Tesla_speed\docs\sound-simulation\S12_Platform_Architecture_v1.md`

The V1--V7 history and exact V7 reproduction record is indexed in Obsidian:

- `E:\AI_Tools\Obsidian\data\notes-personal\tesla\2026-07-12-MATLAB发动机声浪V1-V7演进与V7操作记录.md`
