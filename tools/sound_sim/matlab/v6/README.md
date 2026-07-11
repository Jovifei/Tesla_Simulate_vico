# C63 V6 Physical-Acoustics Simulation

V6.0 is an isolated C63 W204 vertical slice. It preserves all V4 code and
artifacts while introducing a 96 kHz, temperature-aware engine-sound path.

## Run

From MATLAB:

```matlab
run("E:\Tesla_speed\prj\tools\sound_sim\matlab\v6\run_c63_v6.m")
run("E:\Tesla_speed\prj\tools\sound_sim\matlab\v6\run_c63_v6_autofit.m")
open_system("E:\Tesla_speed\prj\tools\sound_sim\simulink\engine_sound_v6.slx")
```

The baseline is written to `iteration_00_physical_baseline`. The accepted
reference-fitted C63 listenable output is written to
`iteration_03_afterfire_autofit_wideband`.

## Model

`v6_vehicle_profile.m` owns all profile values. `v6_build_cycle.m` calculates
control-rate speed, gear, torque interruption, RPM, Lambda, DFCO, fuel-film,
spark, EGT, and speed of sound. `v6_synthesize_engine_sound.m` renders the
following 96 kHz layers:

- M156 firing-order blowdown pulses split to left and right banks.
- Temperature-dependent primary, collector, catalyst, mid-pipe, muffler, and
  tail-pipe delays with reflection and crossover coefficients.
- Shift and lift afterfire gated by RPM, EGT, throttle lift, DFCO, and residual
  fuel rather than a fixed audio trigger.
- Order-locked mechanical texture and separate external, cabin, and speaker
  preview paths.

`engine_sound_v6.slx` is the editable multi-rate state harness. Its eight
subsystems are DriveCycle, EngineECU, ThermalState, ExhaustWaveguide,
AfterfireShift, MechanicalTexture, PropagationMetrics, and ReferenceMetrics.
It exposes the profile, thermal, reflection, DFCO, and audio-rate parameters
in the model workspace. The high-rate audio renderer remains in MATLAB so its
sample-exact layers can be exported and tested deterministically.

`..\simulink\v6_exhaust_thermal_plant.slx` is the separate, executed
Simscape Gas low-frequency calibration plant. It contains a 900 K / 250 kPa
blowdown reservoir, a dynamic and inertial 1.15 m `Pipe (G)`, a 350 K /
101325 Pa ambient reservoir, Gas Properties, Solver Configuration, and a
Thermal Reference. It is deliberately not used as a 96 kHz standing-wave
solver; its pressure and thermal behavior calibrate the waveguide seeds.

## Autofit

`v6_fit_afterfire.m` reads only derived features from
`c63_w204_headers_backfire.wav`. It performs an explicit 63-case scan:

1. 27 combinations of body, metal, and crack gain.
2. 9 body/metal decay combinations after the best gain candidate.
3. Comparison uses spectral centroid, four frequency-band shares, and spectral
   flatness. Candidate values and objective scores are stored in the V6 JSON.

The accepted V6 fit selected body gain `0.90`, metal gain `2.80`, crack gain
`0.80`, body decay `40 ms`, and metal decay `18 ms`. The generated isolated
afterfire centroid was `641 Hz` against the reference `562 Hz`; its
250-1000 Hz share was `75.8%` against `70.8%`.

## Validation

```matlab
results = runtests("E:\Tesla_speed\prj\tools\sound_sim\matlab\v6\tests\test_v6_sound_synthesis.m");
assertSuccess(results);
run("E:\Tesla_speed\prj\tools\sound_sim\simulink\init_engine_sound_v6_model.m")
```

The V6 tests cover profile structure, 96 kHz steady rendering, thermal
afterfire plus DFCO, deterministic output, and mono/column reference-feature
handling. The Simulink model must pass `model_check(["all"])` after rebuild.

## Boundary

This is a low-order physical-acoustics synthesis model, not a validated
full-engine CFD or GT-SUITE replacement. The engine dimensions are fixed from
published data; pipe dimensions, valve area, EVO pressure, and loss/reflection
values are identification seeds. The low-frequency Simscape Gas plant is now
executed separately; Powertrain Blockset is not yet coupled to the V6 solver.
The next fidelity increase needs synchronized RPM, throttle, gear, microphone,
and exhaust-temperature data.

## V6.1 vehicle isolation

- Shared synthesis stays in this directory.
- C63 parameters and its render entry point live in `vehicles/c63_w204/`.
- Its Simulink top model and `.sldd` dictionary live in
  `tools/sound_sim/simulink/v6/vehicles/c63_w204/`.
- Run `vehicles/c63_w204/run_c63_w204_v6_1.m` for the reviewed listening set.
