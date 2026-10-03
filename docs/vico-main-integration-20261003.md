# Vico/N2 main integration — 2026-10-03

Jovi authorized merging only the current Vico/N2 development chain. AI-7, AI-8 and android_vehicle_sound_demo APP-1 are excluded.

## Handoff
- Goal: consolidate current Vico/N2 work onto main, validate locally and deploy without losing phone data.
- Integrated: N2 b4e1ea1a, P3 05c0c1e, publication ca1286e and design 631bc42. Three merges resolved automatically; no merge conflicts. N2 contains the earlier local profile and atomic-restore repairs.
- Local repair: corrected an event-morphology test fixture to meet the unchanged 12/25 sample window guard; symlink tests explicitly skip only Windows privilege error 1314. No production sound parameters changed.
- Verification: Android testDebugUnitTest/lintDebug/assembleDebug successful. 285 tests, 0 failures/errors, 29 external/opt-in skips. Python discovery: 120 tests, 116 passed, 4 skips (2 opt-in exports, 2 unavailable symlink privileges), 0 failures/errors. Windows N2 CI: 44 tests, 0 skips/failures. Progress-view check and diff whitespace check pass.
- Phone: GM1910, serial 6e4fa92f, current ADB server 5037. Same-signature install -r successful, cold start and HOME/hot return successful. PID 24030 remained alive; bounded own-process log contained no FATAL EXCEPTION/ANR. firstInstallTime remains 2026-07-10 11:43:13; selected_vehicle remains gtr_r35.
- APK SHA256: a6e7e3d047c35e9c03492cfa80df2b341c3c85b28552475001194851e69fa09d. Signing certificate SHA256: 9ab144e824abf26a5941819abb06831288c36a8bfe622657e3dc9d88281fc774.
- Blocker: full private-reference/630-case acoustic qualification and human acceptance remain pending; installation/startup does not prove those gates. No new candidate qualification or road-driving accuracy claimed.
- Key files: vico_app/Project/android; vico_app/tools/python; docs/project-ledger.json; docs/vico-input-timing-repair-validation.md; docs/vico-n2-historical-continuity-validation.md.
- Next: remote review of integrated main and remaining acoustic qualification, followed by exact-commit local/device verification.

Local logs: E:/Tesla_speed/review_packages/main-integration-20261003-android.log, main-integration-20261003-python-all-fixed.log, main-integration-20261003-n2/receipt.json. Installed APK backup retained only in E:/Claude_allow/Download/vico-main-integration-before-20261003.apk. Owner untracked handoff is preserved.
