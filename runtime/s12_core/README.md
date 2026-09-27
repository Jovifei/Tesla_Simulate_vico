# APP-1 portable runtime subset

This is a bounded technical-MVP renderer, not a qualified vehicle sound model. It accepts validated monotonic `MotionSample` values, maps speed and longitudinal acceleration to virtual RPM/load/gears, then produces phase-continuous additive orders, a small acceleration/shift transient, and a soft-limited 48 kHz stereo float stream. The only bundled profiles are original synthetic V8-like and rotary-like test configurations.

`Engine::render` writes into caller-owned memory and performs no allocation, file access, JSON parsing, blocking synchronization, or JNI/UI work. Construction, profile validation, snapshots, and input mapping happen outside render. A future Android adapter must serialize state/profile updates onto the audio thread through a bounded queue; `Engine` itself is single-thread-owned and is not safe for concurrent calls.

Invalid, stale, non-finite, out-of-range, and non-monotonic inputs fail closed to a smooth idle target. Profile changes preserve oscillator phase and crossfade at a render boundary. The Python oracle and predeclared tolerances are in `tools/sound_sim/s12/runtime_validation/`.

## Deliberately unsupported

- PTR/Radiation, FVM, captured recordings, IRs, or external audio assets.
- Stage-W/X architecture selection, real vehicle identity, OEM calibration, Human acceptance, or rights claims.
- CAN/OBD/BLE, vehicle sensors, foreground permissions, and production Android lifecycle; these belong to the later app adapter phase.

## Verification

With the approved portable host compiler selected for this process:

```powershell
$env:APP1_ZIG = 'path-to-zig.exe'
python -m unittest discover -s tools\sound_sim\s12\runtime_validation\tests -v
```

The Python test builds the C ABI bridge in a temporary build directory, compares the C++ output/state against all ten deterministic Python golden cases, and removes its trace bundle afterward. Native unit tests can be built directly with Zig and run as a host executable; Android CMake builds use the SDK's NDK toolchain and keep host tests disabled.

All output remains `EXPERIMENTAL_SYNTHETIC_NOT_QUALIFIED`; it is not a release or device-acceptance artifact.
