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
