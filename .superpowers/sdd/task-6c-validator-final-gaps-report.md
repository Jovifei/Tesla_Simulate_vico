# Task 6C validator final gaps report

## Scope

Only the bake-off and vehicle-migration validators, their self-contained tests,
this report, and the scoped test-output capture were changed. No generated
evidence, metadata, Vault, frozen Track-P, push, merge, PR, or full S12
execution was performed.

## RED

The new bake-off PCM tamper test was run against the pre-change validator:

```text
python -m pytest -q --disable-warnings -k recomputes_parent_candidate_difference_from_reopened_pcm tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_bakeoff_validator.py
1 failed, 31 deselected in 117.47s
```

The failure showed that rebinding the case SHA receipts did not cause the
validator to recompute the parent/candidate delta from reopened Post-PTR PCM.

## GREEN

Post-change verification is recorded below from the fresh scoped runs on
2026-08-28 (Asia/Shanghai). Both commands redirected their test output to
`.superpowers/sdd/task-6c-green-output.txt`; the captured summaries are:

```text
python -m pytest -q --disable-warnings tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_bakeoff_validator.py
................................                                         [100%]
32 passed in 135.95s (0:02:15)
process exit code: 0
```

```text
python -m pytest -q --disable-warnings tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_bakeoff.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_vehicle_migration.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_final_remediation.py
........................................................................ [ 84%]
.............                                                            [100%]
85 passed in 1301.48s (0:21:41)
process exit code: 0
```

The controller terminated an orphan previous-agent affected-suite chain
(`53976/9024/56344`) before this run; the recorded affected suite above was a
single instance (`61572/33912/11116`).

Post-test checks were run after the report update:

```text
python -m compileall -q tools/sound_sim/s12/acoustic_identity_v015
process exit code: 0

git diff --check
process exit code: 0
```

## Changes

- Recompute each candidate/P1 Post-PTR RMS delta directly from reopened PCM and
  compare it with both persisted summaries.
- Return descriptive missing/hash diagnostics for late artifacts.
- Require migration `manifest.files` to be a mapping with an exact root/case
  inventory, rejecting unsafe, duplicate, extra-listed, and unlisted paths.
- Deep-validate exact P4/P6 placeholder records and their null selection
  boundary.

## Review addendum RED (2026-08-28)

The two new focused tests in each validator module were run before the
production change. The captured failures are retained in the command history
and summarized in `.superpowers/sdd/task-6c-green-output.txt`:

```text
python -m pytest -q --disable-warnings tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_bakeoff_validator.py -k "nested_same_name_manifest or all_cross_platform_unsafe_manifest_paths"
2 failed, 32 deselected in 113.57s (0:01:53)
process exit code: 1

python -m pytest -q --disable-warnings tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_vehicle_migration.py -k "nested_same_name_manifest or all_cross_platform_unsafe_manifest_paths"
2 failed, 26 deselected in 56.37s
process exit code: 1
```

Bake-off omitted the nested same-name file and did not report normalized unsafe
forms. Migration omitted the nested same-name file and raised `IndexError:
tuple index out of range` while indexing an empty path's parts.

## Review addendum GREEN

Focused post-change checks:

```text
python -m pytest -q --disable-warnings tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_bakeoff_validator.py -k "nested_same_name_manifest or all_cross_platform_unsafe_manifest_paths"
2 passed, 32 deselected in 113.27s (0:01:53)
process exit code: 0

python -m pytest -q --disable-warnings tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_vehicle_migration.py -k "nested_same_name_manifest or all_cross_platform_unsafe_manifest_paths"
2 passed, 26 deselected in 55.11s
process exit code: 0

python -m pytest -q --disable-warnings tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_vehicle_migration.py -k "unsafe_and_duplicate_inventory_paths or nested_same_name_manifest or all_cross_platform_unsafe_manifest_paths"
3 passed, 25 deselected in 82.78s (0:01:22)
process exit code: 0
```

Final sequential regression after the duplicate-inventory compatibility fix:

```text
python -m pytest -q --disable-warnings tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_bakeoff_validator.py
..................................                                       [100%]
34 passed in 137.58s (0:02:17)
process exit code: 0

python -m pytest -q --disable-warnings tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_bakeoff.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_vehicle_migration.py
..................................                                       [100%]
34 passed in 1331.64s (0:22:11)
process exit code: 0
```

The first full affected run before the compatibility fix was `1 failed, 33
passed in 1335.81s`; the failure was the pre-existing duplicate-inventory
assertion for `P1/hot_idle/raw_source.wav`. The focused `3 passed` run above
then confirmed the fix before the final full regression.

The validator path policy now excludes only the exact root manifest from
actual-file inventory, rejects both Windows and POSIX anchor/drive/UNC/root
forms plus empty/dot/parent/repeated-separator paths, and records normalized
duplicate inventory without indexing empty path parts.

Post-test static checks:

```text
python -m compileall -q tools/sound_sim/s12/acoustic_identity_v015
process exit code: 0

git diff --check -- . ':!/.superpowers/sdd/task-6c-green-output.txt'
process exit code: 0
```

The raw pytest capture intentionally preserves progress-line trailing spaces;
the diff check therefore excludes only that evidence-output file.
