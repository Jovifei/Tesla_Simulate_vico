# S12 Stage D Human Listening Deep Realism Report

## Status

`AUTOMATED_REALISM_CANDIDATE / HUMAN_AUDITION_PENDING`

- Branch: `agent/s12-stage-c-realism-integration`
- Stage C baseline: `a5d048145c29b20d687376c0b73226bc4a2435c7`
- Scope: offline Track-S Candidate overlays only
- Provenance: `synthetic / uncalibrated / not OEM reproduction`
- Push, merge, main, Simulink, Runtime and Android: not performed

## Implemented

Stage D adds a strict Candidate schema/loader, three anchor Candidate v1 profiles, final-PCM reference-distance tooling, Hellcat named-transient peak shaping, deterministic two-round blind package generation, response scoring contract, and artifact verification. Stage C public profiles, shared Pre-PTR EQ, frozen PTR, loudness manager, and the five non-anchor vehicle paths remain locked.

The candidate overlay remains before the frozen boundary:

`source → idle → afterfire → LF body → rumble → shift → Candidate overlay/peak shaping → Pre-PTR EQ → frozen PTR → PCM24`

`candidate=None` remains the Stage C baseline path. A changed anchor candidate must not change the other two anchor PCM outputs.

## Automatic evidence

| Evidence | Result |
| --- | --- |
| Stage D focused tests | 14 passed |
| Stage C integration baseline | 9 passed |
| Realism suite baseline | 9 passed |
| Identity suite baseline | 58 passed / 78 subtests |
| Full acoustic regression (including Stage D) | 429 passed / 232 subtests |
| Track-P guard baseline | 21/21 |
| Blind listener trials generated | 30 (2 rounds × 15) |
| Listener ZIP leak scan | 0 leaks |
| PCM artifact verifier | PASS: 48 kHz, stereo, PCM24, finite, no clipping |

The full regression and guard must be rerun after final local commits; the numbers above are the captured baseline/evidence before that rerun.

`verify_remaining_vehicles.py` exited 0 and regenerated its informational report, but its historical rough acceptance fields remain FAIL for the eight-vehicle synthetic comparison. This is not promoted to a Stage-D gate and no non-anchor profile was changed; the formal full regression and Track-P guard are the protected acceptance evidence.

## Reference-distance result

The comparison is final PCM against the existing B/R2 relative target features. It does not compare reference LUFS/RMS and does not claim OEM calibration.

| Vehicle | Stage C mean distance | Candidate mean distance | Improvement | Gate |
| --- | ---: | ---: | ---: | --- |
| Ferrari 458 | 0.130345 | 0.135494 | -3.95% | PARTIAL |
| Hellcat | 0.058980 | 0.058978 | 0.003% | PARTIAL |
| RX-7 FD | 0.269799 | 0.261754 | 2.98% | PARTIAL |

The required 30% improvement is not met. The formula and threshold were not weakened. This is an honest `PARTIAL` result, not a reason to promote Candidate or to start Simulink.

## Jovi audition package

Git-external package: `E:\Tesla_speed\review_packages\s12-stage-d-human-audition-v1\`

- Listener package: `S12_Stage_D_Listener_Package.zip`
- Sealed answer key: `S12_Stage_D_Answer_Key.zip`
- Answer-key SHA-256: `52ec36474dc39265cd46b1c09398a417d5d3073237f683603e283969bd8605ff`
- Full-cycle pair-key SHA-256: `e45db100286f2fdceb87f0cbf4b5af24c4ef01c883eb00a9c37a1f58c07610d9`
- Listener content: anonymous `R1_T01.wav` … `R2_T30.wav`, response template, playback-context template, and three anonymous 60-second A/B pairs
- No answer sheet is filled in. No confusion matrix is fabricated.

Jovi must return both rounds (15/15 each), playback context, and A/B preference notes. Only then may the sealed key be opened and scored. Identity recognition and “more realistic than Stage C” remain separate human gates.

## Stop condition

The only valid current stop state is `WAITING_FOR_JOVI_AUDITION`. Candidate is not Approved, and no `ApprovedProfile.sldd`, Simulink integration, Runtime integration, Android preset, OEM reproduction, or calibrated claim is authorized.
