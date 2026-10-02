# Vico P2/P3 Remote Audit

Branch: `codex-remote-p2-p3-audit-20261002`
Base reviewed: `feature/publish-vico-android-20261002`

## Scope

GitHub source-level audit completed. No shell, Gradle, Kotlin compiler, Android device or acoustic measurement runner was available. Runtime/build/device claims remain NOT_RUN.

Reviewed source:

- `sound/s18/C63HybridRenderer.kt`
- `sound/s18/C63HybridSource.kt`
- `sound/s18/C63HybridAfterfire.kt`
- `sound/s18/C63HybridProfile.kt`
- `sound/AudioEngine.kt`
- `sound/MatlabPowertrainController.kt`
- `web/VicoBridge.kt`

## Confirmed source observations

### P2 S18 renderer/source/profile/afterfire

`C63HybridRenderer`

Confirmed symbols:
- `candidateId`
- `snapshot()/restore()`
- `qualificationTaps()`
- `render(state,count,validInput)`

Findings:

1. Candidate identity is fixed to HY1 naming:
   - `C63_HY1`
   - `C63_HY1_<mode>`
   - event-off variants

   This preserves frozen HY1 traceability but does not provide a future candidate registry. New candidates should not reuse this identity.

2. `qualificationOnly` correctly prevents normal runtime observation tap exposure.

3. Render path has explicit safety checks:
   - input finite/range checks
   - output finite check
   - peak contract check when not qualification-only

Trigger conditions for local tests:
- invalid rpm/load/throttle
- nonfinite generated sample
- snapshot identity mismatch
- output peak overflow

### `C63HybridSource`

Confirmed symbols:
- `sample(...)`
- `eventObservation()`
- `lastStems`
- `afterfireEvents`

Findings:

1. Sustained/event paths are separated by `C63HybridMode` T/S/E/SE.
2. Afterfire event generation has separate audible switch through `eventsAudible`.
3. Source snapshot contains deterministic state restoration checks.

Potential follow-up:
- add explicit candidate metadata instead of embedding HY1 identity assumptions.

### `C63HybridAfterfire`

Confirmed symbols:
- `sample(...)`
- `legacySignal`
- `lastImpulse`
- finite response injection

Finding:

- Frozen occurrence logic and new response layer are separated.
- Existing legacy response is calculated but not mixed.
- No confirmed defect requiring immediate source modification.

### `C63HybridProfile`

Confirmed symbols:
- `C63HybridMode`
- binary identity generation
- kernel validation

Finding:

- Profile integrity checks are present.
- Binary identity prevents silent parameter drift.

## P3 Android integration

### `AudioEngine`

Confirmed symbols:
- `start()`
- `stop()`
- `setVehicle()`
- `pushState()`
- `mapPoint()`
- `playLoop()`

Findings:

- Existing engine remains centered around `MatlabV6SoundBankEngine`.
- PCM route, capture and lifecycle infrastructure exists.
- No confirmed replacement point for S18 candidate integration was modified.

Required future implementation:
- explicit S18 renderer ownership path
- default-off candidate switch
- fallback to existing sound bank

### `MatlabPowertrainController`

Confirmed symbols:
- `update(...)`
- shift state machine
- afterfire trigger generation

Findings:

- Input contract is speed/acceleration/throttle to rpm/load/gear.
- Shift and afterfire triggers are deterministic.

Local validation triggers:
- acceleration upshift
- deceleration downshift
- throttle closure after armed condition
- minimum shift interval boundary

### `VicoBridge`

Confirmed symbols:
- audio start/stop bridge
- vehicle/profile selection
- calibration methods
- state export

Finding:

- Bridge methods marshal calls to UI thread.
- No S18-specific bridge entry was found in reviewed file.

## Code changes

No source code defect was modified in this audit commit. Reason:
- source behavior requires runtime/audio qualification to safely change;
- no confirmed compile/runtime defect was proven from static inspection alone.

## Test status

| Item | Status |
|-|-|
| Kotlin compile | NOT_RUN |
| Unit tests | NOT_RUN |
| APK build | NOT_RUN |
| Device lifecycle | NOT_RUN |
| PCM comparison | NOT_RUN |
| Acoustic qualification | NOT_RUN |
| Human listening | PENDING_HUMAN |

Frozen HY1 remains unchanged. Production default old sound path remains required until a separately registered candidate passes gates.
