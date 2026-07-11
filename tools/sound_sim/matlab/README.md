# MATLAB Classic Engine Sound Simulation

This folder contains eight procedural classic-engine profiles:

- `hellcat`: Dodge Hellcat 6.2 supercharged cross-plane V8
- `gtr_r35`: Nissan R35 GT-R VR38DETT twin-turbo V6
- `c63_w204`: Mercedes-Benz W204 C63 6.2 naturally aspirated V8
- `supra_jza80`: Toyota Supra JZA80 2JZ-GTE inline-six
- `rx7_fd`: Mazda RX-7 FD 13B-REW twin rotor
- `lexus_lfa`: Lexus LFA 1LR-GUE V10
- `ferrari_458`: Ferrari 458 Italia F136 F flat-plane V8
- `aventador_lp700`: Lamborghini Aventador LP700-4 L539 V12

Version 4 adds piston/rotary cycle support, 1-2-3 acceleration followed by 3-2-1 deceleration, main-track shift torque interruption and re-engagement, and non-stationary upshift/downshift/overrun backfires. Backfires consume derived parameters from real reference events: background-subtracted envelope, spectral residual, resonant modes, cluster timing, and a 65-tap FIR.

## Run

From MATLAB:

```matlab
run("E:\Tesla_speed\prj\tools\sound_sim\matlab\run_classic_sound_batch.m")
```

Or through the configured MATLAB MCP, run the same script file.

Outputs are written to:

```text
E:\Tesla_speed\prj\build\sound-sim\matlab-classics-v4
```

Each profile produces:

- `*_demo.wav`: 48 kHz, mono, 16-bit listening artifact
- `*_backfire_solo.wav`: isolated backfire layer for direct comparison
- `*_induction_solo.wav`: isolated supercharger, turbo, or intake layer
- `*_shift_solo.wav`: isolated gearbox-specific shift transient layer
- `*_trace.csv`: 100 Hz RPM, throttle, layer, and backfire trace
- `*_params.json`: profile and backfire event metadata
- `*_analysis.png`: waveform, drive cycle, and normalized spectrum
- `backfire_feature_comparison.csv`: measured reference versus generated frequency-band features
- `v3_v4_backfire_comparison.csv`: generated V3 versus V4 backfire features

For interactive tuning, edit and run `launch_sound_tuner.m`. The macro-dynamics Simulink harness is `..\simulink\classic_sound_tuner.slx`.

For an equal-condition engine-layout comparison, run `run_engine_layout_comparison.m`. It renders Corvette LS3 V8, Supra 2JZ inline-six turbo, LFA V10, and Aventador V12 without shifts or backfires.

## Reference Analysis

`analyze_reference_audio.m` analyzes temporary public-video audio tracks under `E:\Claude_allow\Download\tesla-sound-research`. It writes only derived spectral and transient data to `build\sound-sim\reference-analysis`; copyrighted source audio is not copied into the repository or synthesized output.

`calibrate_backfire_references.m` rejects low-contrast events, subtracts the local background, and writes non-audio calibration data to `calibration\backfire_calibration.json`. Run it only when the temporary reference recordings change.

## Test

```matlab
results = runtests("E:\Tesla_speed\prj\tools\sound_sim\matlab\tests\test_sound_synthesis.m");
assertSuccess(results);
```

These files are simulations, not recordings of the named vehicles. They target recognizable engine layout and event behavior without redistributing third-party vehicle audio.

## V6 C63 Physical-Acoustics Slice

V6 is kept in `v6` so the eight-vehicle V4 baseline remains reproducible. It
adds a 96 kHz C63 W204 engine/ECU/thermal state, temperature-dependent left and
right exhaust waveguide, physical afterfire gating, high-frequency mechanical
texture, external/cabin/speaker paths, reference-feature fitting, and an
eight-subsystem Simulink state harness.

```matlab
run("E:\Tesla_speed\prj\tools\sound_sim\matlab\v6\run_c63_v6_autofit.m")
open_system("E:\Tesla_speed\prj\tools\sound_sim\simulink\engine_sound_v6.slx")
```

Read `v6\README.md` before tuning. V6 is a low-order physical model, not a
claim of original-equipment CFD validation.
