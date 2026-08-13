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

## Task10 Obsidian handoff

The planned external knowledge handoff was applied with per-page SHA-256 preconditions. Its local control receipt is `.superpowers/sdd/task10_obsidian_v5_receipt.json` (schema `s12-stage-l-task10-obsidian-handoff-v1`); it records `csv_content_read=false`, `feedback_values_read=false`, and the post-write UTF-8 read-only verification result (`7/7` SHA, `6/6` existing-page markers, `1/1` new-page YAML/internal link).

| Page role | Before SHA-256 | After SHA-256 |
| --- | --- | --- |
| Tesla index | `0a3b234e05597f787695e50c2647bb1e67fdcb5941ed75db0b8bcd5c4235053b` | `621f6ee2bee778bede9f09cc07a8cf457b9a0acfea889ea91c1f2f1f38fa195d` |
| S12 overall plan/current progress | `9f1d3830a50c09abb80b9ffa13f881170e513dc9507b39a79f6d2d852abd461e` | `8022071f60c186a9eb47af9a88a24df4e73903cbbec3776fecf0358cf7e06daf` |
| Hellcat card | `63bb17df0ee97ded0df3fd6c072e295325b5b00a7ba71d0598f04ddc96b3eaa3` | `2b7e1b18902fa723b984220c6753e3b76ee61021dece7fca9a32bd3afa51e4ff` |
| Workflow, reusable knowledge, and Stage K history | SHA-guarded | `0f8adf0e57f2b90063322aa7d20cfe7ac29c429a2a8c1f979fc40f9b3e1b0352`, `ef63abaf77073451ede66206ba731529b0cbdb8076e666c19f49d80c67b09fb9`, `fda7b3250895881da750d128377c1dda55629f7c8ed8f23ca6662dbc1b2836be` |
| New Stage L page | absent | `3b225e6c83b0fa7f6be8733ad4e597bc443e4307ffed0e8964687f1cc1e88681` |

The receiving page maps the Stage K continuity, intake/casing cat-call path, cross-plane combustion/blowdown/structure low-frequency path, frozen-final-PCM order, feedback boundary, and zero MATLAB/Simulink scope. The receipt's post-write verification records the 7/7 SHA and page-structure checks. The status remains `PARTIAL / AUTOMATED_GATE_FAIL / UNQUALIFIED_DIAGNOSTIC_ONLY`.
