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
  - Valve lift, effective curtain area, and port-area limit.
  - Choked and subcritical compressible-flow branches.

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
- Simulink connectivity checks for all three models.

## Known Boundaries

- The closed-cylinder reference currently uses constant `cv`; the next model
  replaces it with temperature- and composition-dependent properties.
- Valve flow is independently verified but not yet coupled back into cylinder
  mass and energy states.
- M156 cam event angles, `Cd(lift)`, connecting-rod length, and exhaust geometry
  remain bounded identification parameters until stronger evidence is found.
- No 1D manifold, catalyst, muffler, tailpipe radiation, or audio export exists
  in S12 yet.

Research specifications live in:

- `E:\Tesla_speed\docs\sound-simulation\S12_全物理Simulink一维发动机排气声学研究规格.md`
- `E:\Tesla_speed\docs\sound-simulation\S12_C63_Hellcat参数证据矩阵.md`
- `E:\Tesla_speed\docs\sound-simulation\S12_Simulink一维气体动力学架构决策.md`
