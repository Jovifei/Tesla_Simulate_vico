# Direction A · Step 1: original engine-sim offline package

This is an isolated Windows-first packaging experiment. It is **not built or smoke-tested on Windows yet**. It does not integrate with S12, change any default timbre, or prove acoustic quality. No merge, deployment, Community Edition binary, OEM calibration, real-time playback, vehicle fitting, or DSP tuning is included.

The package is self-contained tooling: Python 3.10+ standard library, Git, and existing Windows VS2022 C++ x64/CMake tools. The source snapshot is generated offline from already available Git objects. It is intentionally not a bundled Community Edition distribution or a claim that the host sources have already been exported. After export, the workspace contains all selected source/header files, full MIT licenses, archives, build files, harness and verification scripts; building needs no fetch, install, GUI, scripting runtime or external assets.

## Provenance and boundary

- Product base: `Jovifei/Tesla_Simulate_vico` main `6e4cf1437972caf383baab3f987de0ebf2db373d`.
- New branch: `dot/direction-a-step1-20261112`; only this new top-level directory is added.
- Method reviewed: `codex-hellcat-continuous-stage-20261025` at `149ab01e3e6fb4b9df7b9aef60df9fbb5365fc8b`, especially the five requested files in `tools/engine_sim_offline/`, plus its capture adapters and README. No branch ancestry or old result files are imported.
- Original MIT engine: [ange-yaghi/engine-sim](https://github.com/ange-yaghi/engine-sim/tree/85f7c3b959a908ed5232ede4f1a4ac7eafe6b630), fixed commit `85f7c3b959a908ed5232ede4f1a4ac7eafe6b630`.
- Solver: [simple-2d-constraint-solver](https://github.com/ange-yaghi/simple-2d-constraint-solver), exported from the **actual supplied checkout HEAD**, never dirty working files. The engine pin's gitlink is `e009f4ff1c9c4c5874e865e893cdb62e208fb2b3`. Both identities and whether they agree are recorded. A mismatch exports evidence but stops host build acceptance pending compatibility review; it never silently substitutes the historical SHA.
- `LICENSE-engine-sim.txt` and `LICENSE-solver.txt` carry complete upstream MIT texts. Export checks the actual committed license against that reviewed text and records its unnormalized SHA-256. It refuses a differing license. Existing root notices and clean-room files remain untouched.

## Method, unchanged parameters

The generic crossplane V8 model preserves the prior experiment's fixed programmatic translation of upstream `assets/engines/atg-video-2/07_gm_ls.mr` and helper defaults. It is **not a Hellcat**, not a measured engine, and has no OEM calibration. Model parameters are copied without tuning; the new harness exposes only the existing smoke setpoint, 910 rpm / 0.08 speed control. A dyno holds speed: this is not free-running road behavior.

The exporter keeps pristine `archives/engine.tar`, `archives/solver.tar` and `snapshot/{engine,solver}/` from `git archive SHA src include LICENSE`. The separate `upstream/` and `solver/` build copies receive four documented file adaptations with checked, unique patch anchors and before/after hashes:

1. Solver include path redirected to the exported solver.
2. Real-time queue-latency step adjustment removed for fixed 10 kHz offline physics; dyno sample buffer released at teardown.
3. Read-only physical tap before synthesizer input.
4. Unused GUI include removed; read-only audio taps and invalid-value guard. DSP coefficients, operation order, gains and model parameters are not tuned.

This adapted offline executable is **not byte-identical to upstream GUI execution**. DTV and DISCORD_ENABLED default OFF and ON is rejected. The minimal CMake does not execute the upstream root CMake, FetchContent, gtest, Delta, Discord, scripting, GUI or audio-device targets. Windows/MSVC is enforced; Linux portability is not claimed.

## Capture contract

Five seconds of warmup, first 0.5 s using the upstream starter, then negative signed crank velocity verified before hold-dyno enable. Capture length is 0.01–60 s in whole 10 ms blocks. C RNG seed is 24817; the upstream jitter generator keeps its original default state. Identity IR is the declared analytic one-sample `[32767]`, not a downloaded recording. Existing upstream DSP remains frozen and may clip; clipping is reported, not repaired.

- `pressure-input.f32le`: 10 kHz × 18 IEEE754 little-endian float32. First eight cylinder and next eight runner absolute pressures are Pa. Last two exhaust staging excitations are **not Pa**.
- `signed-omega.f32le`: 10 kHz × one float32 signed rad/s. Negative throughout capture is required; absolute RPM cannot establish direction.
- `audio-taps.f32le`: 44.1 kHz × six float32: resampled/prefiltered input sum, post-DSP, pre-clamp leveler output, normalized int16 PCM, leveler gain, integer-clamp flag. Input sum already includes upstream 1900 Hz antialiasing; it is not raw pressure. Clamp flag is computed after rounding, before clamping, without modifying output.
- `state.csv` and `dyno.csv`: 100 Hz, completed-block endpoints 0.01 s through duration. Unlike the historical file, state time is not 100 µs early. `throttle_plate` retains the historical raw linkage scalar meaning, not physical load.
- `physical-validity.json`: mandatory signed extrema and lit-cylinder-step aggregate, not an ignition-event count or measured power.

`verify_capture.py` independently checks bytes, frame counts including warmup, finite binary/CSV/JSON values, positive absolute pressures, the entire signed rotation stream, mandatory physical evidence, PCM/clamp consistency, exact CSV timing, and coarse naturally aspirated MAP sanity. It uses explicit exceptions, not optimizable assertions. Missing evidence fails. A successful check is only basic offline mechanical/data sanity, **not acoustic realism, OEM, S12, mobile or product acceptance**.

## Files and use

- `prepare_workspace.py`, `prepare_capture.py`: read-only original checkouts; new workspace and export receipts.
- `CMakeLists.txt`: C++17 `solver_core`, `engine_core`, `engine_offline`; VS2022 x64 Release.
- `model_builder.*`, `offline_main.cpp`, `offline_taps.h`: frozen model and offline capture.
- `verify_capture.py`, `test_package.py`: fail-closed validation and synthetic test coverage.
- Two full license files; `source-identity.json` is explicitly an unfilled template.
- `HOST-RUNBOOK.md`: host commands and before/after status acceptance for both original repositories.
- `validation/`: actual cloud script-test evidence and explicit unrun Windows stages.

Run the synthetic contract suite with `python -B test_package.py`. These fixtures do not simulate an engine.

Follow `HOST-RUNBOOK.md`; use a brand-new output and preserve failures. No script fetches, installs, checks out, cleans, resets or writes an original Git repository. Never reuse the old experiment's Windows pass as evidence for this package. Muse performs host validation separately.
