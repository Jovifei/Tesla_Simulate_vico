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
- Simulink connectivity checks for all four models.

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

Research specifications live in:

- `E:\Tesla_speed\docs\sound-simulation\S12_全物理Simulink一维发动机排气声学研究规格.md`
- `E:\Tesla_speed\docs\sound-simulation\S12_C63_Hellcat参数证据矩阵.md`
- `E:\Tesla_speed\docs\sound-simulation\S12_Simulink一维气体动力学架构决策.md`

The V1--V7 history and exact V7 reproduction record is indexed in Obsidian:

- `E:\AI_Tools\Obsidian\data\notes-personal\tesla\2026-07-12-MATLAB发动机声浪V1-V7演进与V7操作记录.md`
