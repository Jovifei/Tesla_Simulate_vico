# Vico P2/P3 Remote Audit

Branch: `codex-remote-p2-p3-audit-20261002`

## Added isolated implementation

Added qualification-only modules:

- `C63CandidateQualification`
  - candidate gate state
  - digital/state/continuity/acoustic/device/human separation
  - no production routing changes

- `C63QualificationDiagnostics`
  - frame/finite/peak diagnostic export model

- `C63EventModeExport`
  - same candidate metadata for events-on and event-off comparison
  - 48 kHz mono contract

## Existing verified integration points

`C63HybridRenderer`:
- `snapshot()/restore()`
- `qualificationTaps()`
- `render(state,count,validInput)`

`C63HybridSource`:
- `sample(...)`
- `eventObservation()`

The new code does not alter frozen HY1 parameters and does not enable a production candidate.

## Remaining implementation boundary

S18 candidate routing into AudioEngine remains a separate controlled step. Existing production path stays default.

## Validation

Kotlin compile: NOT_RUN
Unit tests: NOT_RUN
APK: NOT_RUN
Device: NOT_RUN
Acoustic: NOT_RUN
Human listening: PENDING_HUMAN
