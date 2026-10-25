# HC-C1 local A: playback correctness

Parent: `7f5c35016bec159effa635e6f76cba15e4cdb86b`; PR41 feature branch, no main merge. Jovi approved local A+B after the technical review. This receipt covers A only; B is an isolated offline study and is not in the Android sound engine.

Native writer now latches cancellation on owner/mute/input/epoch rejection. It retains the verified continuous tail and existing envelopes, cancels at zero, and requires explicit fresh preparation. A new candidate is admitted through the first valid DEMO transition. When no candidate is installed, ordinary renderer behavior remains unchanged. Source/internal renderer sample rates must match in Web and Native; this does not restrict the existing device-output resampler.

Executed locally on JDK21/SDK34 with cached dependencies: Web133/133, native UI JS31/31, Windows N244/44, wiring3/3, actual Kotlin policy lifecycle replay exit0. Android558 total:529PASS/29 explicit opt-in or external-fixture SKIP/0failure/error;122 fresh JUnit XML. Lint0errors/6 existing warnings; assembleDebug exit0. `summary.json` and `source-files.json` bind the results to actual app/test files. A writer regression independently fails10 cases on the parent; rate guards have explicit RED/GREEN checks. These are synthetic/software checks, not physical AudioTrack/GPS/road qualification.

APK SHA256: `8911314e08fd28dd13c1210d4cf14c3a4aec68227f352b8e3419da99fe98e55f`. Package `com.vico.simulator`, versionCode1/versionName1.0, debug v2 signature verified. Certificate SHA256: `9ab144e824abf26a5941819abb06831288c36a8bfe622657e3dc9d88281fc774`. Not installed or publicly deployed. The APK is the existing default sound plus A correctness repairs; it does not claim a remedy for 0.5–0.6s texture. Its local copy is in `E:/Tesla_speed/reports/ab-execution-20261025/a-final-verification/app-debug.apk`; full local logs/XML/skips are in that directory.

Frozen WAV/gain, S13/S14 source/reference, Owner/V4, main and user data were not edited. Existing source budgets remain0. New sound-source promotion, C architecture, real-Hellcat likeness and device/human acceptance remain open.
