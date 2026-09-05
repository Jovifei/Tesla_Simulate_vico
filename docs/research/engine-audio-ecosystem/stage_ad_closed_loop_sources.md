# Stage AD Closed-Loop / Sound-Matching Source Study

Date: 2026-09-04
Scope: method study only unless separately approved. No external code/audio/weights are copied by Stage AD.

## Priority A — directly useful to our negative-feedback architecture

### DiffMoog

- Repo: `https://github.com/aisynth/diffmoog`
- Pin studied: `f3a367a044225c0f9bc25e024bdf869638a25e79`
- License: MIT
- Useful idea: differentiable modular synthesizer + sound-matching training/evaluation platform.
- Adopt: explicit synth parameter domain, rendered-audio loss, parameter inversion as analysis-by-synthesis.
- Do not adopt now: replacing S12 persistent event-domain engine with DiffMoog modules.

### Magenta DDSP

- Repo: `https://github.com/magenta/ddsp`
- Pin studied: `cf5e62dfe5d5c80aa14761832233a2e68e840e53`
- License: Apache-2.0
- Useful idea: differentiable DSP processors, harmonic/noise/filter modules and audio-domain losses.
- Adopt now: architectural idea that the optimization objective should be measured after synthesis, not only in parameter space.
- Future option: differentiable surrogate for local continuous source submodules.
- Do not do: rewrite all S12/Track-P as TensorFlow DDSP.

### Semi-Supervised Synthesizer Sound Matching with Differentiable DSP (SSSSM-DDSP)

- Repo: `https://github.com/hyakuchiki/SSSSM-DDSP`
- Pin studied: `9068d9489808300d2b06bad3f1ab47c1aa40aee3`
- Public repo indicates MIT licensing.
- Useful idea: sound matching when synthetic training sounds and real query sounds have a domain gap.
- Adopt: keep synthetic renderer evidence and real reference evidence as different domains; compare in audio/perceptual space and fail closed on unusable real references.

### Modulation Discovery with DDSP

- Repo: `https://github.com/christhetree/mod_discovery`
- Pin: `HEAD_PIN_REQUIRED_BEFORE_CODE_USE`
- Useful idea: constrained low-dimensional modulation curves instead of unconstrained frame-wise controls.
- Adopt later: model boost/load/shift/lift envelopes with interpretable time constants and routing rather than per-frame optimizer noise.

## Priority B — useful parameter-inversion patterns

### InverSynth revival

- Repo: `https://github.com/crodriguez1a/inver-synth`
- Pin: `HEAD_PIN_REQUIRED_BEFORE_CODE_USE`
- Useful idea: audio → parameter estimate → re-render → audio similarity confidence.
- Adopt cautiously: re-synthesis confidence as a secondary diagnostic/warm-start signal.
- Do not use as primary truth: generic embedding similarity can reward perceptually similar but mechanically wrong engine sounds.

### synth-setter

- Repo: `https://github.com/tinaudio/synth-setter`
- Pin: `HEAD_PIN_REQUIRED_BEFORE_CODE_USE`
- Useful idea: explicit synth inversion / sound matching / preset exploration pipeline.
- Status: early-stage; use as workflow reference, not dependency.

### TorchSynth

- Repo: `https://github.com/torchsynth/torchsynth`
- Pin: `HEAD_PIN_REQUIRED_BEFORE_CODE_USE`
- Useful idea: differentiable modular synth with high-throughput parameter-labelled data generation.
- Future use: generate surrogate-training corpora if Stage AD later learns a proposal network.

## Priority C — directly useful to our App state model

### SenaTaka / engine-simulator

- Repo: `https://github.com/SenaTaka/engine-simulator`
- Pin studied: `c03a43e7da473a693f2b2079ce0eaca00b3042f8`
- Useful idea: browser AudioWorklet engine simulation plus Real Vehicle Mode using GPS and accelerometer-derived motion.
- Adopt: separate motion input conditioning from sound renderer; derive throttle/load/RPM state continuously; keep audio callback independent of sensor update frequency.
- Do not copy its sound identity as our final engine model.

### BitResonant / EV-engine-sound-sonification

- Repo: `https://github.com/BitResonant/EV-engine-sound-sonification`
- Pin: `HEAD_PIN_REQUIRED_BEFORE_CODE_USE`
- Useful idea: real road telemetry arrives much slower/less regularly than DSP blocks, so the key problem is continuous state reconstruction and late-frame handling.
- Adopt strongly for Android App: timestamped input, interpolation/smoothing, freshness, late/missing frame policy, state buffer.

### yoshiomiyamae / engine-sound-simulator

- Repo: `https://github.com/yoshiomiyamae/engine-sound-simulator`
- Pin: `HEAD_PIN_REQUIRED_BEFORE_CODE_USE`
- Useful idea: procedural engine core independent of Unity, automatic driving mode, engine RPM/load state and real-time parameter preview.
- Adopt: core/runtime separation and testable state logic; not its exact synthesis algorithm.

### ddsp-realtime

- Repo: `https://github.com/woosukji/ddsp-realtime`
- Pin: `HEAD_PIN_REQUIRED_BEFORE_CODE_USE`
- Useful idea: framework-independent C++ real-time DDSP core and mobile-oriented latency discipline.
- Future App value: reference for C++/mobile DSP packaging after our Python profile is frozen.

## Stage AD adoption decision

We do **not** import any of the above implementations in this phase.

We adopt the following clean-room architecture ideas:

1. **analysis-by-synthesis loop**: optimize rendered audio error, not parameter error;
2. **bounded parameter domains**: preserve physical and source-causal constraints;
3. **iterative recenter + shrink**: use each best candidate as next search center;
4. **domain gap awareness**: synthetic and real recordings are not interchangeable evidence;
5. **interpretable modulation**: time-varying controls should use small stateful envelopes, not arbitrary framewise knobs;
6. **re-synthesis confidence**: useful as diagnostic/warm-start, never sole selection truth;
7. **input/DSP rate separation**: phone/vehicle motion data is slower and jitterier than audio callbacks;
8. **authoritative renderer remains S12** until any surrogate/differentiable path proves equivalence.

## Current bottleneck after this study

More repository discovery is not the next priority. The next practical work is:

```text
bind local real references
→ run Stage AD closed loop
→ generate audition WAVs
→ Jovi listens
→ feed Jovi feedback into source-causal parameter family
→ iterate once if needed
```
