# S12 Stage Y — Closed-Loop Remediation

Date: 2026-08-30  
Branch: `agent/s12-stage-y-closed-loop-remediation`  
Base: `f1714b969ecd033e991e04cfc59df06a05e3685a`  
Scope: Python acoustic source/comparator/governance remediation only. Frozen Track-P PTR/FVM/Radiation content is not modified.

## 1. Purpose

Stage X proved that the project could render and rank candidates, but the audit found that several parts of the feedback loop were not trustworthy enough to guide acoustic tuning. Stage Y repairs the parts that can be completed from repository code and public/diagnostic evidence:

```text
reference governance
→ scenario/session binding
→ comparator
→ parameter reachability
→ candidate rendering
→ engineering gates
→ human-feedback weighting
→ PCM24 reopen evidence
→ CI regression
```

The branch remains `synthetic / uncalibrated / vehicle-inspired / not OEM reproduction`.

## 2. External projects and methods retained

### Engine-Sim

Original source: https://github.com/ange-yaghi/engine-sim

Retained ideas already present in S12 and preserved by Stage Y:

- persistent crank phase and engine state;
- cylinder/rotor event scheduling rather than a single oscillator;
- event-domain combustion pressure packets and torque ripple;
- per-path primary delay, bank collection and collector routing;
- stateful waveguide and block-continuous rendering;
- source first, transfer/radiation later.

Stage Y does not copy Engine-Sim source code or vehicle scripts. It uses the architectural lessons in the clean-room S12 implementation.

### MoSQITo

Original source: https://github.com/Eomys/MoSQITo

Role: finalist psychoacoustic validation for loudness, sharpness, roughness and fluctuation-related checks. Stage Y keeps lightweight deterministic proxies in the inner search loop; MoSQITo remains an outer validation tool because running it for every candidate is too expensive.

### webMUSHRA

Original source: https://github.com/audiolabs/webMUSHRA

Role: hash-bound blinded human review. Stage Y adds a machine-readable Jovi feedback objective, but does not fabricate human results.

### ViSQOL

Original source: https://github.com/google/visqol

Role: optional regression/damage detection for aligned versions of the same signal. It is not used as an OEM-identity score.

### MATLAB order and psychoacoustic tools

Official references:

- https://www.mathworks.com/help/signal/ref/rpmordermap.html
- https://www.mathworks.com/help/signal/ref/ordertrack.html
- https://www.mathworks.com/help/audio/ref/acousticloudness.html
- https://www.mathworks.com/help/audio/ref/acousticsharpness.html

Role: outer-gate order/psychoacoustic verification when a synchronized RPM trace exists. Stage Y does not claim order qualification for unsynchronized video-derived audio.

## 3. Implemented remediation

### 3.1 Reference governance

New `reference_governance.py` classifies evidence from the actual rights/raw/synchronization fields. Video-derived audio cannot be promoted to R2 merely because it was downloaded and decoded. Independent evidence is counted by source SHA and recording session, not by the number of windows cut from one video.

The case-set output now separates:

- `bound_scenario_count`;
- `unique_audio_sha_count`;
- `independent_source_count`;
- `independent_session_count`.

### 3.2 Comparator correctness

`multi_reference_comparator.py` was repaired to use:

- explicit positive-width canonical frequency bands;
- normalized bin-wise spectral flux rather than total-frame-energy change;
- time-axis envelope modulation for the roughness proxy;
- a persistent narrowband-tone/whine proxy;
- stabilized relative error and robust median aggregation.

The inner-loop outputs are still proxies. They are not replacements for MATLAB/MoSQITo finalist validation.

### 3.3 Fail-closed engineering gates

Hard gates no longer default to `True`. Candidate evidence must explicitly prove:

- finite PCM;
- zero clipping;
- parent/candidate SHA difference;
- post-PTR presence;
- block-boundary continuity;
- raw/monitor separation;
- parameter consumption;
- scenario compatibility;
- clean reference binding.

A missing proof fails the gate.

### 3.4 Dynamic scenario search

The search contract now covers all ten engineering scenarios:

- hot idle;
- steady low/mid/high RPM;
- tip-in;
- full pull;
- shift;
- lift;
- afterfire;
- idle return.

This prevents a model from being selected only because it matches four steady-state clips while its acceleration, lift or afterfire behavior regresses.

### 3.5 Parameter domains

Categorical controls are sampled as exact categories rather than continuous numbers. Physical time/gain parameters receive bounded domains. This removes dead regions such as a continuous afterfire-location value that almost never selected the non-default category.

### 3.6 Human-feedback objective

`human_feedback_objective.py` and `jovi_guided_feedback_v2.json` convert named feedback into bounded dimension weights. Examples:

- “fixed electronic whistle” penalizes persistent tonality and forced-induction synthetic artifacts;
- “low frequency has no impact” increases emphasis on 120–400 Hz attack rather than blindly increasing sub-bass;
- speech-contaminated RX-7 feedback is rejected as a tuning authority.

Human feedback can change ranking only within a bounded adjustment; it cannot bypass runtime or evidence gates.

### 3.7 Actual audio evidence

The best candidate writes per-scenario PCM24 raw/post-PTR/monitor WAV files, reopens them, verifies finite stereo/48 kHz/24-bit/no clipping, and records SHA-256 receipts. This closes the prior gap between an in-memory candidate and a published audition candidate.

### 3.8 Historical evidence integrity and CI

A dedicated restoration/integrity tool checks the Stage-W W9 receipt-bound log hashes. GitHub Actions runs:

- Stage X/Y focused tests;
- historical log integrity;
- complete S12 Python regression;
- artifact publication for logs.

The workflow intentionally does not rewrite an old receipt to make a new log appear valid.

## 4. What this branch proves

It proves that the software feedback loop is materially safer and more complete:

```text
candidate really rendered
+ reference class not silently inflated
+ independent recordings not double-counted
+ comparator math repaired
+ human feedback consumed in a bounded way
+ gates fail closed
+ output WAV reopened and hashed
```

It does **not** prove that Hellcat, Ferrari 458 or RX-7 now match a real OEM vehicle.

## 5. External work that cannot be completed from GitHub alone

The following require local files, licensed data, hardware, MATLAB, or a human listener and therefore remain explicit handoff items:

1. **Real R1 capture** — original WAV/FLAC, rights receipt, exact trim/stock state, microphone/AGC record and synchronized RPM/load/throttle/gear/shift traces.
2. **Real harmonic/order timbre map** — must be extracted from authorized synchronized recordings; the repository cannot invent it.
3. **Cycle-synchronous PSOLA/OLA clip bank** — requires authorized clean cycles by RPM/load/state. No third-party copyrighted audio is embedded.
4. **ENSIM4/CFD transfer-model identification** — requires local ENSIM4 sweeps or equivalent pressure/impedance data. The present two-scalar teacher reduction is not a full transfer model.
5. **MATLAB/MoSQITo finalist execution on private recordings** — GitHub CI has no access to the local licensed media or MATLAB desktop/license.
6. **Jovi listening result** — must come from an actual blinded review; it cannot be generated by an agent.
7. **Eight-vehicle calibration** — the new loop is vehicle-agnostic, but real per-vehicle optimization requires each vehicle’s accepted references.

## 6. Recommended next stage

Do not start another large blind Sobol search first. The next local stage should be:

```text
R1/R2 authorized intake
→ synchronized scenario slicing
→ real order/harmonic map extraction
→ event-domain + recorded-residual hybrid source
→ ten-scenario bounded search
→ MATLAB/MoSQITo finalist gate
→ Jovi blinded A/B
→ one narrow corrective iteration
```

Until those external inputs exist, the correct terminal state is:

```text
STAGE_Y_SOFTWARE_LOOP_REMEDIATED
REAL_REFERENCE_CALIBRATION_PENDING
HUMAN_REVIEW_PENDING
NOT_PROFILE_FREEZE_READY
```
