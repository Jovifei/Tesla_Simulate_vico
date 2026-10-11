# PR38 controller session reception, 2026-10-11

Normal playback startup now resets the digital controller before the first input mapping and refuses preparation while an audio writer remains alive. Reset clears virtual cruise hysteresis while preserving event/input provenance. Ordinary start and renderer phase behavior remain unchanged.

Remote proposal: 5e4daeea27ccf20c2cde6da56ccd672e446fa841, tools/patches/controller-session-stage-20261111.json (filename date typo). Local receiver corrected only the proposal's cruiseGear declaration anchor from var to the existing val, materialized its six changes, and strengthened the regression test with REAL 30 km/h hysteresis overlap and synthetic restart cases. This is local reception implementation of the remote proposal, not a claim that remote ran the local commands.

Validation of this source tree:
- Lifecycle mutation: replacing cruiseGear.resetSession with invalidate makes the overlap regression fail; restored source passes all three lifecycle tests.
- Android testDebugUnitTest, lintDebug, assembleDebug: PASS, 454 tests, 0 failures, 0 errors, 29 skipped opt-in acoustic/export cases.
- Python discovery: PASS, 157 tests, 0 failures, 0 errors, 4 skipped (2 opt-in exports, 2 Windows symlink privilege).
- APK SHA256: 907d2da16e16b91c6cd78b7343a0cac63baafb5296392193d583aaea4ebdfb63.
- Debug signer certificate SHA256: 9ab144e824abf26a5941819abb06831288c36a8bfe622657e3dc9d88281fc774.

Commands used JDK21/SDK34 and the cached Gradle wrapper offline with SDK download disabled. Detailed local logs and skipped test names are in review_packages/remote-stage-20261011/v5-validation-receipt.json and v5-*-build*.log in the owner workspace; logs are not uploaded.

Limits: preview/resume direct-start entry points still require review. Device AudioTrack lifecycle, real-road input, periodic noise, acoustic and human listening acceptance are NOT_RUN. APK not installed. Main and owner V4 drafts untouched. Frozen WAV/gain unchanged, candidate_count/budget=0, no MATLAB. N3 profile/extractor implementation remains pending; this receipt does not accept the full stage.
