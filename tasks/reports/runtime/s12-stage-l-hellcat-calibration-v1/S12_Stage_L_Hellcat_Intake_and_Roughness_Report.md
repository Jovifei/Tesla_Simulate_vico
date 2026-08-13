# S12 Stage L Hellcat Intake and Roughness — Task10 Report

## Assessment

| Field | Value |
| --- | --- |
| overall_status | PARTIAL |
| automated_gate_status | AUTOMATED_GATE_FAIL |
| qualification_status | UNQUALIFIED_DIAGNOSTIC_ONLY |
| feedback_status | DIAGNOSTIC_FEEDBACK_ALLOWED |

This report indexes Task10 diagnostic evidence only. It is not a Human PASS, approval, calibration completion, OEM acknowledgement, or Simulink integration claim.

## Named v5 package: frozen-final-PCM diagnostic transport health

- Named package: `E:/Tesla_speed/review_packages/s12-stage-l-hellcat-intake-roughness-v5`
- producer SHA-256: `73eba07f818b78680083e7f230aab8a222c2d9ecfbaf31e614fb8dbc6240af16`
- manifest SHA-256: `9d2c93a0509b00e612d74dbc646541b74f165cdd286b3d07f46add625d8228c8`
- ZIP central-directory member count: `23`; ZIP content hash was not recomputed to avoid reading feedback CSV content.
- All 13 WAV files are PCM24, 48 kHz, stereo, finite, and have `clipping=0`.
- Diagnostic transport health: `AVAILABLE / PASS_FOR_DIAGNOSTIC_TRANSPORT_ONLY`.

The formal parent/candidate v5 WAVs use `Frozen PTR -> Edge Fade -> One Whole-Cycle Gain -> PCM24`; their receipts bind actual PCM payload hashes. Their pre-gain metrics are directly measured after Frozen PTR and Edge Fade, and final metrics are measured from emitted PCM24. Candidate comfort starts from that final candidate PCM and then applies only its separately recorded static gain. SHA256SUMS was recomputed for 21 non-CSV entries; the feedback CSV itself was not read or hashed. The v1, v2, pre-remediation v3, and pre-actual-metric-layer v4 packages remain retained historical artifacts and are not current evidence.

The named v5 package health establishes only that its WAVs are usable diagnostic transport artifacts. It does not establish formal qualification provenance.

## Recorded WAV loudness and headroom measurements

These are the actual package values, retained for diagnostic reporting only; they are not a qualification result.

| Artifact | Pre-gain LUFS | Final LUFS | Final peak (dBFS) | SHA-256 |
| --- | ---: | ---: | ---: | --- |
| Parent WAV | -20.629257368470288 | -19.92069310438389 | -1.5000002153229033 | `239692db2d11ca0349998dce6a8515e810000be957dff990a66ce0b871e2c345` |
| Candidate WAV | -22.28028138572734 | -21.571717122578164 | -6.486224000631787 | `419678e0ab20128ae2bd145bd1a129c61f41e6277ea1a212551f9dda0b4218b0` |

- Common actual gain: `+0.7085642670226164 dB`
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
