# PR38 legacy qualification repair — 2026-10-13

Android compatibility assets were incorrectly included in the Track-P physical-model lock. The original180 entries and2 symbol hashes are preserved; the exact Android matlab_v6 root has an independent36-entry hash. Git status, ignored files, tree manifests and changed paths now use NUL-delimited UTF-8 paths, including Unicode names and both rename endpoints.

AF fixed-base diff checking remains enabled. Explicit CRLF whitespace semantics preserve historical bytes; only the unchanged archived unified patch permits its legal single-space context markers. Eight redundant source/test EOF blank lines were removed. The archive patch SHA remains bbdb52d8361c17d45ebf692c0d4f68728a556a2cb80d66402e55c14bda2ed017. No workflow base, cleanup gate, frozen WAV/gain, renderer behavior or candidate budget was relaxed.

Actual local evidence at the implementation checkpoint:
- Focused Track-P plus Stage W:96 passed.
- Final Track-P and real Git whitespace-policy regressions:54 passed.
- Independent final guard review:46 passed; rename into/out/within exact root protected.
- Android JDK21/SDK34 offline test/lint/assemble:482 tests,0 failures,0 errors,29 skipped; build successful.
- APK SHA256 fc63059555b1c7aec0ee52da5073e02441ce35b0dacd621a1dd53e7a1033a60d, Android Debug certificate9ab144e824abf26a5941819abb06831288c36a8bfe622657e3dc9d88281fc774. This checkpoint APK was not installed.
- AF ancestry/cleanup and fixed-base working-tree diff:PASS. Original hosted AF log unavailable; this is local command diagnosis, not hosted CI acceptance.
- Full S12 dirty-tree run interrupted after source-identity guards rejected uncommitted scoped changes. Clean-commit full qualification is PENDING, not PASS. Local Python lacks pyloudnorm/mosqito; no global dependency changes.

Main and12 local V4 file hashes remain unchanged. MATLAB was not started; candidate_count/budget remain0. Jovi reports improvement in the APK installed on2026-10-11, with further optimization required. Road, independent acoustic and human acceptance remain open.

ChatGPT chat-only planning/read review is saved in the local closeout package. Next stage investigates Preview playback ownership and reuses existing audio diagnostics; no DSP/gain changes or automatic phone update.

## Preview playback ownership closure

Playback and a fading writer now reject vehicle selection before any model/publication mutation. Preview requires stopped audio; its owned completion stops once and restores the original bank only after actual writer exit, with bounded retries and cancellation by epoch. Ordinary prepare/start failures roll back once. AudioTrack initialization failures return false and finish a failed capture through the existing diagnostic path.

Actual integrated verification: Android498 tests,0 failures,0 errors,29 skipped; lint/assembleDebug PASS. Vico Python157 tests PASS,4 skipped. Independent real-helper and engine regression20 tests PASS; actual-target review PASS. JVM test allocation uses reflection to remain compatible with Android javac's bootclasspath. Monotonic input/preview deadline checks remain enabled after moving restoration into the owned helper.

Full S12 was actually executed at4b44f01844964ca9cf447890bf523657780778fe:1794 passed,6 skipped,232 subtests passed,4294.07seconds. Four skipped tests require explicit external R2 assets; two require S12_RUN_SLOW=1. S12 source/test tree, .gitattributes and Android matlab_v6 tree are unchanged by this Preview stage, so this is explicitly inherited scope evidence, not a new fullS12 run at the later commit.

New APK SHA2567e1822720f0c37eb9d9d68799ff7bd54bc798974dea31c91caacfc46831a57d3; Debug certificate9ab144e824abf26a5941819abb06831288c36a8bfe622657e3dc9d88281fc774. This APK has not been installed. Existing10-11 phone version and data were untouched. Acoustic/road/human gates remain open; improved prior-phone feedback is not acceptance of this build.

Hosted Y/AF final outcome is still pending confirmation; status reads encountered transport/time-out errors. No main merge or source qualification promotion.
