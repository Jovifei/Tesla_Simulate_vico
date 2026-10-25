# engine-sim offline causal study

A diagnostic tool only. It does not change Android/Web default voices, fit a real recording, or claim Hellcat/OEM realism. The programmatic generic LS-example V8 has no Hellcat supercharger/OEM-exhaust calibration.

Exact engine source: `85f7c3b959a908ed5232ede4f1a4ac7eafe6b630`; exact simple-2d solver: `e009f4ff1c9c4c5874e865e893cdb62e208fb2b3`. Both MIT notices are included. `prepare_workspace.py` reads only these committed objects from an existing local checkout and creates a NEW workspace. It never checks out, changes, cleans, fetches, or installs into the original repository. No recordings or IR assets are downloaded; the IR is a declared analytic identity tap.

## Reproduce on the tested Windows environment

Existing MSVC2022, CMake3.31 and SDK10.0.26100 were used. Existing Python with numpy/scipy/matplotlib/psutil and Node is required by diagnostics. No global environment changes/installations are performed.

```
python tools/engine_sim_offline/prepare_workspace.py --engine-repo E:/project/engine-sim --out E:/Tesla_speed/experiments/NEW_ENGINE_TRIAL
cmake -S E:/Tesla_speed/experiments/NEW_ENGINE_TRIAL -B E:/Tesla_speed/experiments/NEW_ENGINE_TRIAL/build -G "Visual Studio 17 2022" -A x64
cmake --build E:/Tesla_speed/experiments/NEW_ENGINE_TRIAL/build --config Release --parallel 4
E:/Tesla_speed/experiments/NEW_ENGINE_TRIAL/build/Release/engine_offline.exe NEW_CAPTURE_DIRECTORY main 60
```

`low 30`, `high 30`, and `holdout 60` are the other frozen scenes. No reset occurs within a scene. Original realtime queue-latency feedback is removed only from this offline snapshot so each10ms has100 physical steps. Five-second warmup precedes capture. Use the original starter for the first0.5s; engage hold dyno only after verified negative crank rotation. The dyno imposes RPM: this is a bench study, not natural road acceleration. Model/seed/DSP/scenes remain fixed. Existing default DSP can clip and must not be promoted without a separate reviewed change.

## Signals and domains

- `pressure-input.f32le`:10kHz,18 float32LE columns:8 absolute cylinder pressures Pa,8 runner pressures Pa,2 audio-like exhaust staging inputs. Last2 are not Pa.
- `audio-taps.f32le`:44.1kHz,6 float32LE columns:sum of resampled input channels;post-DSP/prelevel;leveled/pre-int16-clamp;final normalized PCM;leveler gain;clip flag. The first tap already includes upstream interpolation and1900Hz input antialiasing. It is not untouched physical pressure.
- `state.csv`:100Hz actual RPM, command, linkage scalar, MAP, cycle phase/count. The historical `throttle_plate` name denotes raw linkage scalar, not actual plate angle or load. Completed-step timestamps are labeled100us early; `dyno.csv` uses block endpoints. Do not silently rewrite or fit old traces.
- `physical-validity.json`:signed rotation extrema and active-lit-cylinder-step aggregate. The latter is not ignition-event count, burnt-fuel rate or OEM calibration.

C RNG seed24817 and the jitter filter's separately default-constructed C++ RNG are fixed for this binary/platform. No additional random draws are added by taps. Cross-platform or asynchronously rendered GUI sample identity is not claimed.

`verify_capture.py` checks exact frames/bytes, finite values, positive absolute pressures, clip consistency, CSV timing and basic signed-direction/combustion/NA-pressure sanity. A C++ exit0 alone is insufficient. Preserve failed/partial output rather than cleaning it.

## Four routes

V0 uses the actual existing BankRenderer, actual RPM and declared clamp(MAP/ambient,.05,1) load proxy. It is a different source/timbre and not a physical-load equivalence claim. E0 is the unchanged resampled input sum; E1 is the same source with frozen actual DSP; E2 is defined only for low/high steady scenes from the first complete-cycle crop after5s, near0.55s, with a fixed5ms continuation/preroll seam blend that preserves cycle period. Dynamic acceleration is never looped as steady audio.

Measured signals retain original values. Cross-domain absolute powers are not directly comparable. Fractional ACF,10/20ms envelope power over0.5–10Hz and1/0.6–1/0.5Hz, orders, sidebands, dynamics, clipping and source mixing are reported together. Normal combustion can itself recur near0.527s at910RPM; waveform ACF alone is not a noise/realism gate. Separate48k listening copies use one declared pooled scalar per route with a peak constraint; they are not measurement inputs or guaranteed loudness-equal blind trials. No automatic acoustic PASS is issued.

## Preserved failures

The first180s batch incorrectly engaged the hold dyno at rest, selecting reverse rotation; absolute-RPM reporting hid the sign. The resulting NA manifold pressure reached8.48MPa. That batch and frozen executable are retained locally as INVALID. The corrected starter initialization was independently reviewed and mechanically verified without tuning gain, model, seed or acoustic windows. Original source/WAV/gain, S13/S14, Owner/V4, main and user data remain outside this tool's writes.


## Analysis commands

Use explicit actual product sources/dist; V0 is never a generated fixture:

```
node tools/engine_sim_offline/render_vico_trace.mjs --core ABS_PRODUCT/vico_web/src/core.mjs --dist VERIFIED_WEB_DIST --capture CAPTURE/main --out NEW_V0/main --vehicle hellcat_v6 --ambient-pa 101325
python tools/engine_sim_offline/analyze_captures.py --capture main=CAPTURE/main --capture low=CAPTURE/low --capture high=CAPTURE/high --capture holdout=CAPTURE/holdout --v0 main=NEW_V0/main --v0 low=NEW_V0/low --v0 high=NEW_V0/high --v0 holdout=NEW_V0/holdout --prereg FROZEN_PREREGISTRATION.json --out NEW_ANALYSIS
python tools/engine_sim_offline/test_analysis.py
```

Render all four V0 scenes before analysis. Original input paths/hashes and frozen settings are retained in receipts. Missing/invalid physical-direction evidence fails closed and cannot become a coarse physics pass. Known100us timestamps are corrected deterministically for analysis, never fitted or rewritten in original CSV. Tested Python/numpy/scipy/Node versions are in `tested-environment.json`; Windows C++ build plus independent reconstruction/bit-exact smoke are verified, not other platforms or mobile runtime.
