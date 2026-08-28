# Task 5B: Geometry/migration/restore contract finalization report

## Scope and takeover

- Worktree: `E:/Tesla_speed/worktrees/s12-stage-w-ecosystem-bakeoff`
- Starting HEAD: `16b7f38` (`fix(s12): close bakeoff validator review gaps`)
- Brief: `.superpowers/sdd/task-5b-geometry-migration-restore.md`
- The controller handed over the existing six-file, uncommitted Task5B
  patch. Its fresh selector result was `25 passed, 19 deselected in 270.39s`.
- Duplicate-process incident: the stalled attempt left a live pytest launcher
  and its Python worker for one command. Process inspection showed one logical
  pytest invocation, so the takeover waited for it to finish before starting
  fresh checks; no process was killed and no reset/stash/cleanup was used.
- No recovery metadata, receipts, generated evidence, Vault/Obsidian state,
  Track-P/frozen PTR files, push, merge, PR, or full Stage-W/S12 run was done.

## Changes reviewed and finalized

- `migration.py` now loads the live `parameter_usage_matrix.json`, validates
  the required piston/rotary geometry contract, and rejects missing,
  malformed, or mismatched matrix data. P2H/P3 diagnostics must match the
  vehicle's expected `crankpin_geometry`/`rotor_geometry` pair.
- Migration validation now cross-checks raw, post-PTR, and monitor hashes in
  nested `migration_results.json`; the tests rebind only the outer manifest
  SHA and prove nested tampering remains rejected, including missing inventory.
- Boundary, stateful waveguide, and waveguide-network restore paths now fully
  preflight channel/queue/header topology and finite state before mutation.
  Invalid queue lengths and topology leave live state unchanged.
- Final hardening also rejects non-mapping snapshots, non-list boundary
  queues, and non-integral delay/sample-counter/network headers instead of
  raising incidental exceptions or silently truncating values.

## RED/GREEN evidence

The takeover added minimal regression tests before the corresponding fixes:

```text
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_boundary_adapter.py -k "non_mapping" -q
F                                                                        [100%]
1 failed, 8 deselected in 1.09s
Failure: AttributeError from list.get() instead of the required ValueError.
```

```text
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_waveguide.py -k "non_integral or non_mapping_frequency or malformed_header" -q
F.F                                                                      [100%]
2 failed, 1 passed, 18 deselected in 1.08s
Failures: non-integral fields were silently truncated; malformed network
header raised TypeError.
```

```text
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_boundary_adapter.py -k "non_list_queue" -q
F                                                                        [100%]
1 failed, 9 deselected in 1.03s
Failure: tuple queue was accepted before the list-type gate.
```

After the minimal fixes, the new checks were green:

```text
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_boundary_adapter.py -k "non_mapping" -q
1 passed, 8 deselected in 0.84s

python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_waveguide.py -k "non_integral or non_mapping_frequency or malformed_header" -q
3 passed, 18 deselected in 0.84s
```

## Fresh affected-suite verification

Commands were run sequentially, with no concurrent pytest instance:

```text
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_boundary_adapter.py -q
10 passed in 0.94s

python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_waveguide.py -q
22 passed in 3.59s

python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_vehicle_migration.py -q
18 passed in 484.74s (0:08:04)

python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_final_remediation.py -q
52 passed in 19.43s

git diff --check
exit code 0
```

The complete affected total is `102 passed` across the four suites. No full
Stage-W or full S12 suite was run.

## Status and concerns

Status at finalization: source, tests, and this report are ready for the
requested local commit. The changes prove fail-closed synthetic migration and
restore contracts only; they do not promote any architecture, alter frozen
PTR/Track-P behavior, or change the separate R1/W10 selection gate.

Remaining concern: the migration validator intentionally depends on the
current repository `parameter_usage_matrix.json`; replacing or relocating that
matrix remains an external contract change and was not attempted here.
