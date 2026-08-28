# Task 6C validator final gaps report

## Scope

Only the bake-off and vehicle-migration validators, their self-contained tests,
and this report were changed. No generated evidence, metadata, Vault, frozen
Track-P, push, merge, PR, or full S12 execution was performed.

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
