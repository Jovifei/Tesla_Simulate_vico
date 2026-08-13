# S12 Stage L Hellcat Intake and Roughness — Task10 Report

## Assessment

| Field | Value |
| --- | --- |
| overall_status | PARTIAL |
| automated_gate_status | AUTOMATED_GATE_FAIL |
| qualification_status | UNQUALIFIED_DIAGNOSTIC_ONLY |
| feedback_status | DIAGNOSTIC_FEEDBACK_ALLOWED |

This report indexes Task10 diagnostic evidence only. It is not a Human PASS, approval, calibration completion, OEM acknowledgement, or Simulink integration claim.

## Named v3 package: diagnostic PCM transport health

- Named package: `E:/Tesla_speed/review_packages/s12-stage-l-hellcat-intake-roughness-v3`
- producer SHA-256: `26a32dbd96d2a9f9c93ec0044a9edf011ffa924589a9988c64ed17555d8b74ca`
- manifest SHA-256: `fbf43684e337ab6e65c0bbf50724f4094a124dc9d477a2cbf89273b6209c4e7f`
- ZIP SHA-256: `16a9ee4fd02eb4d625170049889dedf2bb5bd0892219bd04760fbb2c160fd3f9`
- All 13 WAV files are PCM24, 48 kHz, stereo, finite, and have `clipping=0`.
- Diagnostic transport health: `AVAILABLE / PASS_FOR_DIAGNOSTIC_TRANSPORT_ONLY`.

The named v3 package health establishes only that its WAVs are usable diagnostic transport artifacts. It does not establish formal qualification provenance.

## Recorded WAV loudness and headroom measurements

These are the actual package values, retained for diagnostic reporting only; they are not a qualification result.

| Artifact | Final LUFS | Peak (dBFS) | SHA-256 |
| --- | ---: | ---: | --- |
| Parent WAV | -21.034908867444564 | -3.9567540362869122 | `973f85e2d465642a631758f4b692ffa2b7812b3be081d0f44205375b26c4b548` |
| Candidate WAV | -22.488648102210213 | -1.5000012507616982 | `7e3d17b0cb2d67ab5c6702bc01dce934fcc1701969efdc2c0e472434b3db3d2b` |

- Common actual gain: `-20.739979471403824 dB`
- Requested gain: `+1.9382 dB`
- `headroom_limited=true`

## Formal qualification provenance

- Formal qualification provenance: `NOT_AVAILABLE / AUTOMATED_GATE_FAIL`.
- Reason: Task6 did not establish formal qualification provenance.
- No calibration, approval, or reference-distance qualification follows from diagnostic transport health.

## Test-evidence index

- The 21-plan-command inventory is in `stage_l_test_evidence.json` and identifies whether each datum came from the Task10 fresh session controller or JUnit.
- Full-combo JUnit: `1221` tests, `0` failures, `0` errors, `0` skipped, pytest duration `1190.061` seconds, SHA-256 `f2966a4a710208ab97d67f94453753d645b77dd0d076fc8c7eeb8f300cba4e82`.
- Full-combo shell exit: `NOT_CAPTURED`; this JUnit record does not prove independent execution or formal qualification.
- Additional TrackP: `21 passed`, pytest duration `1.39` seconds, wall duration `2.08` seconds, exit `0`.

## Feedback boundary and next step

Named feedback remains `NOT_PERFORMED / WAITING_FOR_JOVI`. No CSV content was read. A later Jovi-directed diagnostic-feedback step remains allowed, but it must not be represented as calibration, approval, or reference-distance qualification.
