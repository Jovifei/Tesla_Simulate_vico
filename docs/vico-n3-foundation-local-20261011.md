# PR38 / N3 foundation local delivery, 2026-10-11

Jovi selected chat planning/review with local execution. The earlier reported remote safety denial was withdrawn after no actual failed call could be evidenced; subsequent GitHub writes succeeded. No Work execution is used for this delivery.

Normal playback now consumes a validated profile derived from its already-loaded bank. The profile preserves every existing powertrain field, separates reference manifest/WAV SHA-256 from the existing C63 live variant manifest/WAV SHA-256, and reuses the original decoding/overlay route. The six existing vehicles remain supported; this is a compatibility foundation, not general admission of new vehicles or sound sources.

Finished full-window PCM export now includes `acoustic_features` in the existing capture JSON. It verifies the actual f32le bytes, preserves capture domain and trace/source/bank/event binding, and reports RMS, bounded FFT band energies, peak/crest, adjacent step and explicitly named lag-one correlation. One-sided Parseval uses N² normalization: unit bin-aligned sine energy is 0.5, fixing the independently reproduced ~512 result. Spectrum coverage and trailing samples are declared. No analysis runs in the AudioTrack writer.

Idle preview prepares a fresh controller before start. Preparation/start rejection restores the original vehicle, character and preview flags; running preview keeps the current session. The production helper has rejection, retry and running-session regressions. Renderer phase, events, frozen WAV/gain and candidate_count/budget=0 remain unchanged.

Validation of the delivered source:
- Android full JVM tests: **482 tests, 0 failures, 0 errors, 29 skipped** opt-in acoustic/export cases.
- `lintDebug` and `assembleDebug`: **PASS**, existing JDK21, SDK34 and cached Gradle8.9 offline, SDK download disabled.
- Vico Python discovery: **157 tests, 0 failures/errors, 4 skipped** (2 opt-in exports, 2 Windows symlink privilege).
- Legacy sound Python discovery: **84 tests, 0 failures/errors**; separate legacy evidence, not device qualification.
- Independent local review: no P0/P1; the P2 reference/variant scope issue was fixed and re-reviewed.
- Original chat remote read-only review: **APPROVED**, no required repair. Final commit/CI receipt remains separately bound to its actual SHA.

APK: `vico_app/Project/android/app/build/outputs/apk/debug/app-debug.apk`.
SHA-256: `5cbbf6a201f6df60fd835c9fd3b0b66d306fce6513e5f8e79cbdb20e2b4343f8`.
Debug signer certificate SHA-256: `9ab144e824abf26a5941819abb06831288c36a8bfe622657e3dc9d88281fc774`.
Package/version: `com.vico.simulator`, `1.0`, code `1`. **Not installed**.

Local evidence: `E:/Tesla_speed/review_packages/remote-stage-20261011/local-n3-validation.json`, `local-n3-final-build.log`, `local-n3-final-python.log`, `n3-spectrum-analytic-red.log` and the source-review packet. New helpers and tests must be included in the final source commit; owner main/V4 trees stay intact.

Limits: source fixtures exercise real manifest/WAV bytes and production pure adapters; they do not prove Android AssetManager/AudioTrack behavior on a device. Reference metadata or a Boolean never establishes an independent aligned comparison. Comparison errors remain null/NOT_EVALUATED; harmonic/order lacks time-aligned RPM state. Real-road input, acoustic similarity, microphone transfer, OBD/CAN, human listening and the later Web Studio remain unaccepted/deferred. No MATLAB, new candidate, gain fit, main merge or phone update occurred.

Capture `source_commit` retains the original S13 fixture contract identity; APK/build source identity belongs to the final Git commit and external validation receipt. This software delivery does not claim the user's road speed, gear feel or audible periodic noise has been solved.
