# Task 6AA: Track-P historical output attribute repair report

## Status

`DONE` — configuration-only repair completed and committed.

Worktree: `E:\Tesla_speed\worktrees\s12-stage-w-ecosystem-bakeoff`

## Scope and preservation

Only `.gitattributes` was staged and committed. The historical output
`.superpowers/sdd/task-6c-green-output.txt`, all runtime logs, and the v25/v26/v27
evidence roots were not rewritten. No Stage-W suite, generator, migration,
Vault, or metadata action was run.

The exact added line is:

```gitattributes
.superpowers/sdd/task-6c-green-output.txt -text -diff -whitespace
```

The following content-tree SHA-256 snapshots were identical before and after
the commit. Each tree digest is computed from sorted relative-path, file-SHA256,
and byte-length records.

| Content set | Files | Bytes | SHA-256 before | SHA-256 after |
| --- | ---: | ---: | --- | --- |
| `.superpowers/sdd/task-6c-green-output.txt` | 1 | 3,255 | `ae631b7064c8cb204226fac12590449c46ded9545898cf69c1356e54ffed97fa` | `ae631b7064c8cb204226fac12590449c46ded9545898cf69c1356e54ffed97fa` |
| `tasks/reports/runtime/s12-stage-w/logs` | 255 | 9,405,530 | `a062dd0634079762ac133f906ffdce877ae8c45dc24962bf073eee89d9e3bf36` | `a062dd0634079762ac133f906ffdce877ae8c45dc24962bf073eee89d9e3bf36` |
| `.../bakeoff_final_remediation_v25` | 517 | 235,329,364 | `39e86058e14745d3ca10059ce74d4822f51465926733bfb99dd21a6cc5c1919b` | `39e86058e14745d3ca10059ce74d4822f51465926733bfb99dd21a6cc5c1919b` |
| `.../bakeoff_final_remediation_v26` | 121 | 19,142,723 | `d66efe2b27a47418d80a663626480ae1bb131fc6c8356e5eaa5b1a089e2a8f2a` | `d66efe2b27a47418d80a663626480ae1bb131fc6c8356e5eaa5b1a089e2a8f2a` |
| `.../bakeoff_final_remediation_v27` | 666 | 361,341,672 | `a5c60c4c8b73685f98d201d1a2ec0147b92e0d44dc921a5ed0877d540601ec2c` | `a5c60c4c8b73685f98d201d1a2ec0147b92e0d44dc921a5ed0877d540601ec2c` |
| `.../migration_final_remediation_rx7_v27` | 167 | 2,749,686 | `da82478441280db180d55ab2fe6c82c00a11f5571aeaaf88c7b8ab983b90536a` | `da82478441280db180d55ab2fe6c82c00a11f5571aeaaf88c7b8ab983b90536a` |
| `.../migration_final_remediation_ferrari_v27` | 167 | 2,758,737 | `d82755268c15f7fd2bf579da5376a7991ee02bb50997a1d231ad1cda70e92bc3` | `d82755268c15f7fd2bf579da5376a7991ee02bb50997a1d231ad1cda70e92bc3` |
| `.../v27_stages_20260829` | 665 | 360,353,392 | `b4e25edd9f2a272a88400f055666db605b53e61a26334d5e9a20e77259da2b1b` | `b4e25edd9f2a272a88400f055666db605b53e61a26334d5e9a20e77259da2b1b` |

The raw SHA-256 of `task-6c-green-output.txt` also remained
`be64f29f7a2ca253d95c32aea331a09c33aecbdf362791086ad163bc330338bd`
(3,255 bytes).

## Required checks

### Before change

- `git check-attr whitespace -- .superpowers/sdd/task-6c-green-output.txt`:
  `whitespace: unspecified`, exit 0.
- `python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py`:
  exit 1; it reported the intentional trailing spaces in the historical
  output as `git diff --check` whitespace errors.
- Direct `git diff --check`: no output on the pre-change worktree.

### After change and after commit

- `git check-attr whitespace -- .superpowers/sdd/task-6c-green-output.txt`:
  `whitespace: unset`, exit 0.
- `python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py`:
  exit 0; `OK: Track P 未改动`.
- `git diff --check`: exit 0.

## Commit

`803c31f90d292de80862dc0d78481d658dd5a7d7`

Message: `chore(s12): mark historical pytest output opaque`

`git diff-tree --no-commit-id --name-status -r HEAD` reports only:

```text
M       .gitattributes
```

