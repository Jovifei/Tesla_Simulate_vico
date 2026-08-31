# Y4 transient and snapshot replay report

Status: `PASS` for bounded Y4 scope at source commit `7e2e41e779eca41100aaf412ce2f9bb4475b6d63`.

The RED capture reproduced two independent defects: the equal-power assertion used correlated constant inputs and incorrectly discarded the cross term; and the persistent engine omitted `_path_filter_state`, so snapshot restore did not reproduce raw PCM exactly. The strengthened RED contract also showed the old mixer emitted no inter-block tails and the P5 renderer did not consume its equal-power helper.

The committed repair keeps the layer post-collector/pre-PTR. `StateTransientMixer` now exposes independently measurable tip-in, lift, shift, and BOV tails, triggers each event once per qualifying transition, and persists its state. P5 crossfades the dry and transient-mixed pre-PTR signal with the specified cosine/sine law; no post-PTR pop is introduced. Snapshot schema v2 now includes path-filter state, runtime model identity, and transient state. Old v1 snapshots are accepted only at sample counter zero; nonzero v1 snapshots are rejected rather than fabricating omitted nonzero state.

Pre-review post-commit focused receipt: [y4-focused-postcommit-20260831T000000Z.json](../../../../../../tasks/reports/runtime/s12-stage-y/y4_transients/logs/y4-focused-postcommit-20260831T000000Z.json), exit `0`, actual `2026-08-31T04:49:53.084521Z` to `2026-08-31T04:50:14.392308Z`, `62 passed, 1 skipped in 20.72s`, stdout SHA-256 `CB6591BDBB12555F26932B0B9553BE967B2CC3B0D5EBB0827C8224E0382023F5`.

No Y5 dP/DC/warmup implementation, harmonic-map change, PLL/default-source-voicing change, frozen PTR/radiation change, push, merge, or PR occurred.

## Review remediation

Code `98358a7` adds latch/re-arm for lift/shift/BOV, full 120ms shift tail capacity, all four engine/bakeoff diagnostics, and expanded atomic/streaming/reset tests. The preserved RED2 run was 3 failed/9 passed; targeted GREEN was 12 passed plus 3 replay tests. Final parent-captured post-commit proof is `y4_transients-20260831T052411180625Z`: 71 passed, 1 skipped in 21.61s, actual exit0, UTC 05:24:11.214617 to 05:24:33.487349 on 2026-08-31. Exact command and log hashes are in its JSON under Y4 logs and the updated phase receipt. No additional full-suite run was performed.
