# Task 5A: Strict bakeoff validator finalization report

## Scope and takeover

- Worktree: `E:/Tesla_speed/worktrees/s12-stage-w-ecosystem-bakeoff`
- Starting/current pre-commit HEAD: `436e8ea991a33f72f056d55ccb79b51439e4f468`
  (`docs(s12): record task5 addendum2 final guard`)
- Brief: `.superpowers/sdd/task-5a-strict-bakeoff-validator.md`
- Takeover: the controller handed off an already-implemented and already-tested
  Task5A patch. Two prior agents stalled after attempting additional affected
  test runs; no stalled-agent commit, metadata update, evidence regeneration,
  or scope expansion was adopted by this takeover.
- Finalization boundary: only the two Stage-W source files, the new validator
  test, and this report are in scope. No recovery metadata, receipts, generated
  audio, Track-P/frozen PTR, Vault, push, merge, PR, or full S12 work was done.

## Implemented coverage reviewed

The patch in `stage_w/bakeoff.py` now fail-closes on the Task5A classes:

- required outer summary/case inventories and rejection of missing/extra files;
- outer and nested SHA-256 verification;
- recursive non-finite JSON rejection;
- finite, nonnegative CPU/memory/latency checks for the current emitted schema;
- reopened PCM24 WAV clipping/frame/sample-rate/separation checks;
- recomputed audio and click metrics with explicit PCM24 tolerance;
- required afterfire counts and zero wrong-condition events;
- candidate parameter-consumption and matrix-driven geometry flags;
- parent/candidate/ablation scene inventories, hashes, and truth checks;
- manifest/reference/selection-null consistency.

`stage_w/migration.py` supplies an explicit zero
`afterfire_event_count` for the legacy parent event trace, satisfying the
validator's required field without claiming legacy event-domain availability.
The new test module is self-contained: it creates one bounded fixture under
`tmp_path_factory` and copies it per tamper test, with no dependency on ignored
evidence roots.

## RED/GREEN history

- RED was completed before takeover by the implementation agents for the
  missing/extra inventory, non-finite trace, latency, audio metric, afterfire,
  parameter/geometry, and nested summary/ablation tamper classes. The original
  failing runs are part of the controller's prior Task5A execution history;
  this takeover did not revert source or intentionally destroy a working tree
  to recreate RED.
- GREEN was reported by the controller before takeover and independently
  reconfirmed below after takeover. The exact affected test file contains
  seven tamper tests.

## Historical pre-addendum verification (not current)

The earlier `7 passed` validator run and the optional-reference concern below
are pre-addendum historical records. They do not describe the current v23
validator result or current Task5C source/test head.

## Fresh verification evidence

All commands ran in the worktree above on 2026-08-28 (Asia/Shanghai).

```text
python -m pytest -q tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_bakeoff_validator.py
.......                                                                  [100%]
7 passed in 117.51s (0:01:57)
process exit code: 0
```

```text
git diff --check
process exit code: 0
```

Pre-commit scope check showed only these four intended paths (the report is
ignored by the repository and is explicitly staged by path):

```text
tools/sound_sim/s12/acoustic_identity_v015/stage_w/bakeoff.py
tools/sound_sim/s12/acoustic_identity_v015/stage_w/migration.py
tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_bakeoff_validator.py
.superpowers/sdd/task-5a-strict-bakeoff-validator-report.md
```

No remediation tests, affected legacy suites, full Stage-W, Stage-V, slow
3000-call gate, generated evidence, or full S12 suite were run during this
takeover, per the explicit finalization instruction.

## Concerns and status

1. Historical pre-addendum concern: `run_hellcat_bakeoff(..., reference=<array>)` emits case-level
   `R2_DIAGNOSTIC_READY` / `EXTERNAL_R2_POINTER`, while the validator's case
   identity gate currently requires `REFERENCE_TARGET_MISSING` /
   `REFERENCE_POINTER_ONLY`. This optional-reference path is not exercised by
   the new fixture and remains an integration concern for a future separately
   authorized change; it was not redesigned here.
2. The validator reads the repository `parameter_usage_matrix.json` as a
   current external contract. A missing or malformed matrix correctly causes
   fail-closed validation, but fixture-only tests do not exercise a matrix
   replacement.

Status at finalization: source/test/report are ready for the requested local
commit only; formal Stage-W qualification, architecture selection, R1, and
full-S12 status remain unchanged and unclaimed.

## Review addendum closure (2026-08-28)

The follow-up review required exact R2 identity handling, explicit selection
fields, finite parent-candidate differences, and one tamper test for every
listed class. The root causes were confirmed before the production change:

```text
python -m pytest -q tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_bakeoff_validator.py
......F.FFFF..FF........                                                 [100%]
7 failed, 17 passed in 128.34s (0:02:08)
process exit code: 1
```

The seven RED failures were the legal R2 pair acceptance, missing selection
fields in manifest/summary/case metrics, non-null selection, and result-side
missing/null parent-candidate differences. The three newly found behavior
classes were therefore observed failing before the corresponding validator
changes.

After the minimal fixes and complete tamper expansion:

```text
python -m pytest -q tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_bakeoff_validator.py
........................                                                 [100%]
24 passed in 128.61s (0:02:08)
process exit code: 0
```

The required affected bakeoff/migration/remediation files then ran together:

```text
python -m pytest -q tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_bakeoff.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_vehicle_migration.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_final_remediation.py
.....................................................       [100%]
66 passed in 765.50s (0:12:45)
process exit code: 0
```

The earlier optional-reference concern is closed: case identity now compares
exactly against the manifest's permitted pair, including
`R2_DIAGNOSTIC_READY`/`EXTERNAL_R2_POINTER`. The remaining concern is that the
validator intentionally depends on the repository
`parameter_usage_matrix.json`; a replacement matrix remains an external
contract boundary and was not in this review's scope.

The post-review source/test/report commit is intentionally local only. No
metadata, evidence roots, Vault, push, merge, PR, or full S12 execution was
performed.

## Final pre-commit verification

After the report/test cleanup, the current Task5A module was rerun:

```text
python -m pytest -q tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_bakeoff_validator.py
.......................                                                 [100%]
24 passed in 127.11s (0:02:07)
process exit code: 0
```

The affected three-file run remains the exact `66 passed in 765.50s`
verification recorded above; no production source changed after that run.
