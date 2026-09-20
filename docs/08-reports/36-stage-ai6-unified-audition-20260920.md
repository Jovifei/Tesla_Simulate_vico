# Stage AI-6 unified audition and continuous-drive delivery (2026-09-20)

## Scope and source

This report records the AI-6 implementation branch `feature/stage-ai6-unified-audition-20260920`, based on AI-5 HEAD `5029eb4cf38a28246ee9865a2f53cb9fadfe0e66`. Old three-way package `s12-stage-ai-qualified-three-way-20260916-v2` and AI-5 run `s12-stage-ai5-multirate-peak-20260919-v1` were read-only inputs. No old package, WAV, IR, Reference, or main branch was changed.

## Implemented gates

- `stage_ah/qualification.py` independently decodes final 48 kHz stereo int16 WAVs, recomputes PCM SHA and 4x/8x/16x reconstructed peaks, and checks report/trace/seed/flags/parent denominator/output policy/clip fields fail-closed.
- The unified A/B/C builder persists per-vehicle qualification receipts, full source summary and Task-1 receipt bindings, trial journal chains, visible and machine-readable fit evidence, RX-7 byte-level boundary differences, and truthful B-unavailable roles.
- A/B/C pages retain the original rich workbench and eight-vehicle switcher. C remains R3/R2 reference material and is not an OEM/Human PASS.

## Continuous-drive evidence

The new `continuous_drive` scene uses one 30-second stateful render per role at 48 kHz stereo int16: idle → acceleration with three shifts → loaded pull → closed-throttle lift → coast → idle return. A/B share trace, events, seed `20260908`, IR array/source identity, parent denominator, and output policy. RX-7 uses `rx7_start_boundary_fade_v1` exactly once for 24 startup frames; Aventador has a disabled boundary policy. Renderer reports provide actual shift and afterfire diagnostics, including post-lift afterfire stem energy and onset time. Feedback-off rerender PCM identity is recorded.

Real continuous results:

- RX-7: A PCM `decea5f9d9b775aba4568a20331f7466ec3efcc7b93bf72244c24270ddd24ac`, B PCM `d6efea70a7433cceb5d4856e18467c350fab0852ebce30d95eafb68662c9071f`, 3 shifts, 24 afterfire events, post-lift stem energy `7416.911880966162`, boundary 24 frames.
- Aventador: A PCM `8a7f52152bf63993602a1491e713638fa6819f9b2d3f8ddcfc609b574bcfcacd`, B PCM `e9adb09e3c2c8337595630dc3b39e5e15cbf2901edce5515138b8efd84ff58e5`, 3 shifts, 63 afterfire events, post-lift stem energy `753.218394411114`, boundary disabled.

## Fresh package

The current fresh package is `E:\Tesla_speed\review_packages\s12-stage-ai6-unified-audition-20260920-v2`.

- `ARTIFACTS.json` SHA-256: `28ef0738097e7e28bb4d49136a47a17dac5b3f80bff229dfbbe2161f1bb8cb13`
- `summary.json` SHA-256: `226fb189df31ad6ffaaee0220ac0730331e5172826ce911b84dbeb753a16fe61`
- package status: `PARTIAL_B_AVAILABILITY`; B-ready vehicles: RX-7 and Aventador; C63, Supra, Hellcat, Ferrari, LFA and GT-R B remain unavailable with explicit reasons.
- browser review URL: `http://127.0.0.1:29780/rx7_fd/index.html` and `http://127.0.0.1:29780/aventador_lp700/index.html`.

## Current verification boundary

The final affected focused suite is green: `82 passed in 93.54s`. Strict SyntaxWarning compilation, Track-P guard (180 frozen files/2 symbols unchanged), and the current package verification are also green. Full S12 on the code-equivalent HEAD completed with `1322 passed, 118 subtests passed` in `3883.76s`, with no failure or skip output. The branch is finally pushed at HEAD `941c7b6f2ff5a9d527ebc1c75ea90606e2d3ca2a`; Draft PR/remote exact-head CI status remains pending GitHub authentication. Human listening remains Jovi's decision; no similarity percentage, Human PASS, OEM synchronization, or profile freeze is claimed.
