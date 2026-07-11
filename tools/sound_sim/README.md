# Jovi Sound Simulation Prototype

This folder contains the first offline sound-model prototype for the Tesla_speed firmware.
It is intentionally Python standard-library only, so it can run before MATLAB/Octave is installed.

## Why This Exists

The current firmware audio path is a stable I2S baseline: one sine oscillator driven by virtual RPM.
The final PRD goal needs richer sound that reacts to speed, throttle, acceleration, braking, and overspeed.
This prototype creates a reproducible simulation layer before porting parameters to ESP32.

## References Used

- `E:\Tesla_speed\docs\reference\simulating-EV-sound-main`
  - Useful idea: variable-speed EV sound can start from a simple controllable oscillator model.
- `E:\Tesla_speed\docs\reference\tesla-engine-sound-main`
  - Useful idea: map speed, pedal, and power-like demand into virtual RPM, then smooth it.
- `E:\Tesla_speed\docs\reference\VehicleNoiseSynthesizer-main`
  - Useful idea: acceleration and deceleration should not share one identical tone; brightness and harmonics should change with load.

## Run Tests

```powershell
cd E:\Tesla_speed\prj
python -m unittest discover -s tools\sound_sim\tests -v
```

## Generate Demo Artifacts

```powershell
cd E:\Tesla_speed\prj
python tools\sound_sim\simulate_sound.py --out build\sound-sim
```

Outputs:

- `build\sound-sim\jovi_ev_sound_demo.wav`
  - Listen to this file first. It is the audible prototype.
- `build\sound-sim\jovi_ev_sound_trace.csv`
  - Trace of RPM, frequency, amplitude, brightness, harmonics, and mute state.
- `build\sound-sim\jovi_sound_params_v1.json`
  - Small firmware-porting parameter table with RPM breakpoints and Q15 harmonic gains.

## Current Algorithm

Inputs:

- `speed_kmh`
- `throttle`
- `accel_mps2`
- `brake`

Model:

1. Speed maps to base virtual RPM.
2. Throttle increases target RPM and amplitude.
3. Positive acceleration increases brightness and upper harmonics.
4. Braking or strong negative acceleration damps RPM, amplitude, and brightness.
5. Overspeed at `150 km/h` mutes output but keeps the trace visible.
6. The oscillator is additive: fundamental plus four harmonics.

## Not Final Yet

This is not the final PRD sound algorithm. Missing items:

- MATLAB/Octave or Python spectral plots.
- Listening notes across real vehicle traces.
- Fixed-point C++ port inside `components/audio`.
- BLE/SD-configurable sound profiles.
- Real hardware I2S listening verification.

The intended next step is to tune the generated WAV, then port the small parameter table and harmonic oscillator logic into ESP32 firmware.
