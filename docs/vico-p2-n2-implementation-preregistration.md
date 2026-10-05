# C63 N2 Source Implementation Preregistration

Status: PRE_REGISTERED_BEFORE_IMPLEMENTATION
Candidate: C63_N2_CONTINUOUS_V1

## Boundaries

- HY1 remains frozen and is not modified.
- This candidate is not a renamed HY1 fit.
- Production AudioEngine route remains disabled until qualification gates pass.
- Raw reference clips remain local.

## S18 branch meaning

T = texture baseline branch.
S = new continuous source branch.
E = new event branch.
SE = combined S + E branch.

## Failure-root addressed

Continuous failure root:
- protect 20-200Hz and 200-4000Hz behavior as feasibility constraints.
- prevent a trial that improves aggregate distance by violating protected bands.

Event failure root:
- event distribution distance improvement was insufficient.
- acceptance requires distribution distance improvement, not event energy allocation.

## Representation

Continuous source:

S[n] = envelope(x[n]) * sum(k=1..8)(c_k * h_k[n]) + textureResidual[n]

Eight fixed basis responses:
- length: 4096 samples
- sample rate: 48000Hz
- causal finite response
- generated from deterministic constrained spectral basis
- zero DC constraint
- L2 normalized before coefficient scaling

Texture residual:
- independent deterministic RNG stream
- separate from event RNG
- cannot compensate protected-band violations

Event response:

E[n] = occurrence[n] * kernelEvent[n] + responseNoise[n]

- occurrence and response RNG streams remain independent.
- event response length: 12288 samples.

## Budget

Continuous search budget:
- maximum 48 evaluations.

Event search budget:
- maximum 24 evaluations.

Budgets are selected for this candidate representation and are not copied from HY1.

## Hard feasibility

A trial is rejected before scoring when:

- nonfinite PCM
- identity mismatch
- invalid artifact hash
- 20-200Hz protected power delta > 1dB
- 200-4000Hz rise > 1dB
- source RMS deviation > 1dB
- invalid state continuity

No soft penalty can rescue a rejected trial.

## Acceptance gates

Event:

D_event_new <= 0.8 * D_event_baseline

Continuous:
- digital safety pass
- state continuity pass
- deterministic repeatability pass

Held-out data is evaluation only and is never used for fitting.

## Stop rules

Stop candidate search on:
- exhausted budget
- representation constraint failure
- identity mismatch
- request to retune objective after failure

## Implementation binding after rejected PR37 stubs

This section binds the representation before any N2 objective evaluation. It records implementation
details that the original short preregistration left underspecified. The rejected PR37 stubs at
4aba809 and 14459e0 were not evaluated as N2 candidates and are not accepted evidence.

Continuous basis:
- fixed band edges: 80, 140, 220, 340, 520, 800, 1250, 2000, 3200 Hz.
- one causal 4096-sample damped response per adjacent band, centered at the geometric mean.
- decay constants are 38, 35, 32, 29, 26, 23, 20, 17 ms.
- deterministic phases are k * 0.17 rad for k=0..7.
- each response is mean removed, residual-DC corrected and L2 normalized.
- fixed coefficients: 0.52, 0.46, 0.39, 0.33, 0.27, 0.22, 0.17, 0.12.
- fixed global source scale: 1.0.
- independent texture fraction: 0.08.
- source/texture RNG seed: 0x4e325f535243.

Continuous excitation:
- no block-local oscillator is used.
- the frozen T source combustion impulse and bank identity drive all eight finite-response queues.
- pending tails and texture RNG state persist across block boundaries and are snapshot-restorable.
- S/SE replace only the frozen bark stem; exhaust, intake, mechanical, body and rumble remain from T.

Event representation:
- occurrence process uses the frozen seeded opportunity-domain afterfire runtime with seed 5900017.
- response RNG seed: 0x4e325f525350 and is independent from the occurrence RNG.
- main response: 12288-sample, zero-DC/L2-normalized damped response centered at 95 Hz, 55 ms decay.
- response-noise bases: 430 Hz/45 ms and 1250 Hz/30 ms, each 12288 samples and normalized.
- fixed event scale: 1.0; response-noise fraction: 0.20.
- event responses are injected once into a persistent C63FiniteResponseSource queue; no modulo replay,
  block-trigger reinjection or tail truncation is permitted.

Controlled branches:
- T: exact frozen C63HybridSource(T) source through frozen idle/shift/output/headroom.
- S: T with only bark replaced by N2 continuous source.
- E: T with only the event response replaced by N2 event response.
- SE: T with both bark and event response replaced.
- E_EVENT_OFF / SE_EVENT_OFF: advance the same event occurrence and response streams but mute only the
  N2 event stem at the mixing point.

Qualification-only boundary:
- all N2 implementation classes are internal.
- N2Renderer requires qualificationOnly=true.
- no AudioEngine or old sound-bank selection code is modified.
- source/profile identities, all queues, RNGs, occurrence thermal state and frozen-chain state are
  included in snapshot binding.
