# P2 N2 Source Design Preregistration

Status: DESIGN_REVIEW

This package does not modify PR35 runtime hook behavior and does not enable a production candidate.

## Scope

New candidate ID:

`C63_N2_CONTINUOUS`

This is a new source representation candidate. It is not a renamed HY1 and must not reuse HY1 fitting results.

HY1 remains frozen:
- no parameter changes
- no seed selection
- no restart search
- no rescue fitting

## S18 mode meaning

S18 branches are:

- T: texture baseline branch
- S: new continuous source branch
- E: new event branch
- SE: combined branch

They are not throttle/state/event abbreviations.

## Source representation choice

The candidate source is separated into:

1. continuous excitation representation
2. texture contribution representation
3. event response representation
4. combined renderer composition

The implementation must keep event controls independent from continuous source controls.

## Qualification gates

A candidate can only proceed when all required gates pass:

- source identity
- profile identity
- artifact reproducibility
- digital safety
- state continuity
- event regression
- acoustic gate
- device gate
- human gate

No empty diagnostics or missing hashes can pass.

## Event improvement gate

Event acceptance uses distribution improvement, not energy allocation.

Required threshold:

`event_distance_new <= event_distance_baseline * 0.8`

Equivalent:

`improvement >= 20%`

This is a comparison gate and does not mean events are limited to 20% total energy.

## Budget preregistration

Budget is selected after failure-root analysis and before execution.

The HY1 64/32 evaluation counts are not copied automatically.

The new budget must be recorded together with:

- source representation choice
- failure root addressed
- objective definition
- stop conditions

## Protected bands

Optimization must preserve:

- low frequency behavior
- mid frequency structure
- source energy bounds

Low and mid protection are constraints, not hidden tuning targets.

## Measurement contract

Reference clips remain local. No raw reference upload.

Local execution provides:

- feature extraction
- deterministic PCM comparison
- numeric regression
- device evidence when available

Remote implementation provides:

- reproducible tools
- manifests
- report schemas
- deterministic tests

## Stop conditions

Stop candidate progress when:

- identity mismatch
- invalid PCM
- missing artifact hash
- gate failure
- uncontrolled retuning request

No candidate is promoted by changing the objective after failure.
