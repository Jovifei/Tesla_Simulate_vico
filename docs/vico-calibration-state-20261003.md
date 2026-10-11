# Vico calibration acknowledgement repair — 2026-10-03

## Scope and branch boundary

Publication target: existing PR #37 branch `p2-n2-source-implementation-20261002`, parent `b4e1ea1abb7cce7dc943a67845c781ff83fc9976`. No merge, branch reset, force push, new branch, or PR base change.

The same calibration patch was independently applied to source fetched at integrated main `6e4cf1437972caf383baab3f987de0ebf2db373d`. All affected baseline files were byte-identical between the two commits. The 13 integration-different files were fetched separately and their Git blob and SHA-256 hashes were verified unchanged in the main replay. This is a focused source-subset replay, not a full integrated-main Android qualification.

Code/test/workflow patch SHA-256: `dfeea1d0521def6ca12a0926f0a01a5284af5d24d17fc50afeb1f5320a8000e0`. The companion [PR37 receipt](evidence/vico-calibration-state-20261003-pr37.json) and [main replay receipt](evidence/vico-calibration-state-20261003-main.json) bind baseline commits, per-file before/after hashes, compiled JVM source hashes, test results, and logs. Report and receipt files are outside that implementation patch hash.

## Defect and repair

The previous HTML marked calibration successful after 800 ms even with zero samples or native `finishCalibration()` returning false. Repeated clicks created independent timers. Native begin retained an old successful flag; reset/stop did not cancel sampling. False native states did not fully clear the page's success decoration.

- Native `CalibrationSession` now owns attempt identity, status, accepted sample count, and a monotonically increasing snapshot revision. Begin clears the previous success and bias. Finish accepts only the active matching attempt with the existing 24-sample requirement.
- Only samples already accepted by `LinearAccelerationState` reach calibration; pre-begin timestamps and nonfinite/short samples cannot count. Finite-input accumulation overflow fails closed and clears bias before it can reach corrected sensor output. GPS/IMU freshness thresholds, ordering rules, and source configuration are unchanged.
- The UI waits for the native session's COMPLETE acknowledgement. At 24 accepted samples it sends one finish command; elapsed time never authorizes success. Five seconds without completion cancels the attempt and offers retry.
- Duplicate clicks are suppressed. Old status updates, old completions, timeout callbacks, hidden pages, Back, navigation, pause, stop, and reset cannot complete an abandoned attempt. Native page epochs also reject commands queued across navigation/lifecycle transitions.
- Legacy consumers retain the `calibrated` boolean, emitted from the same immutable snapshot as the detailed status; the additional `calibration` object is additive. A fresh false state clears the calibration page's button, step indicator, and gravity reference.
- CI watches web bridge and asset/JS changes and runs the executable fake-DOM suite.

Audio, sound sources, qualification thresholds, and the existing project ledger were not edited. No APK was installed, and an old PR37 APK is not an integrated-main candidate.

## Verification

Before implementation, seven executable fake-DOM cases failed against the original page, including the direct zero-sample 800 ms false-success reproduction. Kotlin lifecycle tests were authored before the new class existed; their initial compilation failure is test-first scaffolding evidence, not a behavioral baseline pass/fail result.

Independent review added a 24-large-finite-sample overflow regression: it first failed (31/32 passed), then passed after the nonfinite-bias guard was added.

The final identical implementation patch passed on both independently materialized baseline subsets:

- 32 pure Kotlin tests, 32 passed, 0 failed, ignored, or skipped; SHA-pinned Kotlin 1.9.24/JUnit dependencies
- 9 executable fake-DOM JavaScript tests, all passed; 0/23/24 samples, native false/invalid acknowledgement, duplicate click, timeout, stale session/revision, delayed old idle/sampling updates, navigation/visibility, and bridge failure
- 7 Android source-wiring checks, all passed; these are complementary static checks, not Android runtime tests

Android adapter compilation, Android JVM tests, lint, and APK generation must be established by hosted CI for the exact published commit. They were not run in this source-subset cloud workspace. Device GPS accuracy, road latency, physical mounting validity, and human acoustic acceptance remain NOT_RUN. Calibration still uses the documented fixed-device-axis stationary bias model; this repair does not establish vehicle-frame or hardware accuracy.
