# Stage AI-4B project audit and verification (2026-09-19)

## Scope

This audit covers the current AI-4B source branch at audit source commit
`66b935223fd804590d251a3c2d7db6f88c0914aa`, based on the verified AI-4B
repair commit `37b9b54f23d6a0a8967ac25743890f385788e342`. `origin/main` was
`d98a6238c091187595e71c0c88e8fa0e718548c2` and was not modified. The existing
AI-4B worktree with user changes was preserved; this audit ran in a clean
isolated worktree.

The audit did not change DSP parameters, IRs, References, seeds, source WAVs,
or the existing real-material package. The only implementation-adjacent
changes are regression coverage and workflow coverage for the already
authorized AI-4B repair.

## RED to GREEN findings

### Measured-feedback workflow omitted AI-4B regressions

The new RED test demonstrated that
`.github/workflows/s12-stage-ai-measured-feedback.yml` did not run
`test_s12_stage_ai4b_rx7_boundary_repair.py`. The workflow now has an explicit
`RX-7 startup boundary true-peak repair` step. The regression test and the
workflow assertion pass.

### Syntax warning in the GT-R test module

`python -W error::SyntaxWarning -m py_compile` failed on the invalid escape
sequence in `test_s12_stage_k_gtr_parallel_turbo_v3.py`. The diagnostic string
is now a raw string. Strict compilation passes with warnings treated as
errors.

## Verification

- Full S12 suite: `1716 passed, 3 skipped, 232 subtests passed` in
  `3394.98s`; exit code `0`.
- Focused skip audit: `97 passed, 3 skipped` in `18.42s`.
- Skip 1: explicit real-material test requires `S12_LOCAL_ASSET_ROOT`.
- Skips 2 and 3: explicit 3000-block acceptance tests require
  `S12_RUN_SLOW=1`.
- Strict acoustic-identity compileall with `SyntaxWarning` as errors: pass.
- Track-P guard: pass; 180 frozen files and 2 frozen symbols unchanged.
- Track-P tests: `32 passed`.
- `git diff --check`: pass.

The audit branch also retains the prior focused evidence: AI-4B/AI-4A and
feedback regressions pass, and the workflow-aligned selected set is green
after the source commit.

## Existing real-material evidence retained

The sealed package remains
`E:\\Tesla_speed\\review_packages\\s12-stage-ai4b-rx7-boundary-feedback-20260918-v1`.
It was not regenerated or overwritten.

- `ARTIFACTS.json` SHA-256:
  `547b4e655d1a03bed6b906d33abc96dd8fbf9a9edc7c43d4dc9d2ca968d26d73`
- `summary.json` SHA-256:
  `2b537f4f8cd482ea551509ee3a03e7d5ee36a346409268cf8afdf82fe20845bd`
- baseline comparison receipt SHA-256:
  `6db1aa8306b1a02b48ed58a3eb07a9a1006795bf992c2f96fd6d768bed7ebe71`
- true-peak summary SHA-256:
  `df35782affe0003bcf9670488ea7cbb7d822285d8677205c6be4b614db25a76b`

The prior AI-4B run still reports `promotable=false` and
`human_status=NOT_EVALUATED`. RX-7 selected scenes have 4x/8x/16x peaks below
1.0 and zero hard/identity clipping. The R3 recordings remain unsynchronized
and unverified, so this is relative diagnostic evidence, not an OEM match,
similarity percentage, or Human PASS.

## Remaining limits

No new source-level defect was found in the current production audio path by
this audit. The three skips are environment-gated evidence boundaries, not
green results. A full local-asset run requires the governed real-material root;
the slow 3000-block tests require an explicit slow-run authorization. Remote
CI has not yet produced a conclusion for this new audit SHA; it must be read
after the ordinary push and exact-head workflow run.

## Status

`SOFTWARE_REVIEW_FIXES_QUALIFIED_LOCALLY`

`RX7_AUDIO_UNCHANGED`

`WAITING_FOR_EXACT_HEAD_REMOTE_CI_AND_JOVI_ACOUSTIC_REVIEW`
