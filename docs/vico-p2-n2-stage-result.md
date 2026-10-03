# N2 PR37 implementation result

Status: REMOTE_IMPLEMENTED / LOCAL_VALIDATION_NOT_RUN
Candidate: C63_N2_CONTINUOUS_V1

## Rejected iterations

- 4aba809488b221fe991de97da0ba7bf31bcd8828: rejected because it was a block-reset sinusoid/noise stub,
  did not implement the preregistered finite-response candidate and did not preserve the frozen chain.
- 14459e0ac0d658f6804067148365dca2ce6ae92f: rejected by local compile/DSP review. It contained an
  illegal Kotlin operator, stale tests, block-dependent phase, no real 8x4096 FIR bank, truncated event
  handling, no frozen T chain and incomplete snapshot/measurement contracts.

Neither rejected iteration is qualification evidence and neither should be installed on a device.

## Replacement implementation

The PR37 replacement package:
- consumes the real com.vico.simulator.sound.SoundState at the renderer boundary.
- keeps C63HybridSource(T) as the frozen source baseline.
- substitutes only bark for S/SE using eight real C63FiniteResponseSource queues, each 4096 samples.
- uses the frozen combustion impulse/bank as the causal N2 FIR excitation.
- maintains an independent persistent texture RNG and queue state across blocks.
- replaces only event response for E/SE using frozen seeded occurrence logic plus an independent
  response RNG and a persistent 12288-sample finite-response queue.
- advances event occurrence/response state identically when E/SE event audio is muted.
- keeps frozen idle, shift, FrozenC63Output and C63HeadroomProfile processing in N2Renderer.
- makes T use the exact frozen T source rather than silence.
- binds profile identity, baseline identity, queues, RNGs, occurrence thermal/event state and renderer
  delays/output state into validated snapshots.
- rejects empty PCM as qualification evidence and promotes Float samples to Double before squaring.
- exports T/S/E/SE plus E_EVENT_OFF and SE_EVENT_OFF from the actual renderer.
- provides a persistent 48/24 budget ledger and hard-feasibility checker that rejects before scoring.

## Remote execution boundary

Remote Gradle/tests: NOT_RUN.
Remote device install/playback: NOT_RUN.
Reference computation: NOT_RUN.
Protected-band gate: NOT_RUN.
Event distribution 20% gate: NOT_RUN.
Human listening: NOT_RUN.

Local Codex owns compilation, unit/state/numeric tests, reference computation and device qualification.
No source from this PR is eligible for installation until the full local gate package passes.

## Preserved frozen/default state

- HY1 source/profile code is unchanged.
- Existing old sound bank and AudioEngine routing are unchanged.
- No main merge is performed.
- No sound-quality acceptance is claimed.

## Local fail/stop rules

Stop and return evidence to PR37 on any:
- compile/test failure;
- T-chain identity mismatch;
- partition-invariance or snapshot-replay failure;
- nonfinite/empty evidence;
- profile/artifact identity mismatch;
- continuous budget >48 or event budget >24;
- protected low/mid/source-energy violation;
- per-provenance regression beyond the registered bound;
- event distance failing D_new <= 0.8 * D_baseline.

## Cloud evidence-gate repair (2026-10-02)

The later cloud patch replaces the Python echo/hash-only gate paths with artifact-bound,
process-locked reservations and fail-closed checks. It adds result-digest sealing, persistent
identity-failure stop rules and real function/CLI/concurrency tests. See
[vico-n2-evidence-gate-validation.md](vico-n2-evidence-gate-validation.md) for schemas, invocation,
executed checks and the trusted-producer boundary.

34 focused Python/JVM-fixture tests passed in the cloud. This supersedes NOT_RUN only for those
specific software gate/helper tests; it does not supersede the unrun acoustic, full Android,
reference, device or human qualification gates above.

## Cloud historical-state diagnostics (2026-10-03)

The later test-only stage reconstructs the exact 630-entry historical inventory, retaining
292 missing-input entries without substituting trajectories. On the 338 available cases,
actual rendering of six controlled branches with explicit generated test-only artifacts
completed 2,028 digital checks with zero failures. All limits and production DSP remain frozen.

Fresh local Linux rehearsal passed 81 Python tests and 41 JVM tests, with two named opt-in
JVM skips; the seven historical tests also passed from the app-module working directory.
Independent reconstruction verified every available historical fixture/input hash.
See [historical-state validation](vico-n2-historical-state-validation.md) for exact receipts,
synthetic-artifact provenance and separately bounded partition, frozen-T and snapshot checks.

This supersedes NOT_RUN only for the stated software/digital checks. The absent two phone
cases and 290 holdout RPM cases, full 630-case qualification, acoustic/reference gates,
Android/device execution and human acceptance remain unresolved. No installation is authorized.
