# Task 1 report — shared fail-closed qualification

Status: `DONE`

## Scope delivered

- Added `stage_ah/qualification.py` as the shared Stage-AH report/WAV qualifier.
- Moved the existing `numeric_ok()` contract into that shared module and kept the
  public import through `reference_feedback_cli` compatible.
- Bound every nonblocked feedback vehicle to exactly the ten canonical scene IDs
  for both baseline and tuned roles.
- Required matching trace SHA, seed, flags, parent peak key, normalization
  denominator, output policy, and 48 kHz sample rate between roles.
- Required 48 kHz stereo int16 final WAVs, recomputed decoded little-endian PCM
  SHA-256, and exact report-to-WAV PCM identity.
- Recomputed the existing 4x/8x/16x reconstruction receipt from decoded PCM and
  rejected stored PASS claims, overshoot, or stored/recomputed drift.
- Added the versioned `s12.stage_ah.independent_qualification.v1` receipt with
  separate WAV-file SHA, decoded-PCM SHA, report SHA/identity, reconstruction
  method/domain/factors, and PASS/BLOCKED state.
- Made `run_plan()` create and seal `qualification.json`; made `verify_run()`
  require and independently recompute it. Historical packages without this
  evidence therefore cannot pass current qualification.
- Did not change sound generation, audio parameters, K/C, IR, Reference media,
  old package bytes, or Human/OEM claims.

## RED evidence

Command:

```text
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ai6_qualification.py -q
```

Observed before production changes:

```text
22 failed in 2.18s
ModuleNotFoundError: No module named
'tools.sound_sim.s12.acoustic_identity_v015.stage_ah.qualification'
```

The focused `verify_run` case was then isolated from unrelated HTML parsing and
re-run before implementation. It failed with `DID NOT RAISE`, proving the old
verifier accepted a sealed inventory with no independent qualification receipt.

## GREEN evidence

Primary new suite after implementation:

```text
22 passed in 2.05s
```

Combined affected suite after the implementation commit:

```text
python -m pytest \
  tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ai6_qualification.py \
  tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ai5_reconstruction_peak.py \
  tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ah_reference_feedback_adapter.py \
  tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ah_reference_feedback_package.py \
  tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ah_reference_feedback.py \
  tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ah_three_way_audition.py \
  tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ai_threeway.py \
  tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ai_fourcar.py -q

83 passed in 50.66s
```

The end-to-end package test was intentionally rerun after committing the scoped
source because `_runtime_identity()` rejects dirty source. Fresh result:

```text
6 passed in 21.02s
```

Static verification:

```text
compileall PASS
diff-check PASS
```

## Files changed

- `tools/sound_sim/s12/acoustic_identity_v015/stage_ah/qualification.py`
- `tools/sound_sim/s12/acoustic_identity_v015/stage_ah/reference_feedback_cli.py`
- `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ai6_qualification.py`
- `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ai5_reconstruction_peak.py`
- `.superpowers/sdd/task-1-report.md`

## Commit

Implementation commit:
`abeb4ce5a1a2e5ebca68987f3fe6954332184fe1`

## Self-review and concerns

- The qualifier stays separate from rendering and only reads final evidence.
- Legacy pre-guard exceedance remains a nonblocking diagnostic; post-guard,
  emergency, identity, and post-identity clip counts/errors must be zero.
- Existing sealed historical packages remain inventory evidence but intentionally
  fail current `verify_run()` until they contain the new independent receipt.
- No material implementation concern remains. Full-repository validation is left
  to the parent AI-6 integration task; this task ran only the directly affected
  83-test set, package smoke, compileall, and diff check.

## Reviewer correction — preserve all-blocked evidence

Review found that an all-baseline-blocked run called the PASS-only qualification
verifier before writing its receipt. The exception removed staging and therefore
lost the failure receipts. A RED regression reproduced the issue:

```text
python -m pytest \
  tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ah_reference_feedback_package.py::test_all_baselines_block_publish_diagnostics_but_refuse_b_ready_verify_and_serve -q

1 failed in 1.31s
ValueError: independent qualification is BLOCKED
```

The fix separates sealed evidence consistency from B-ready acceptance. Internal
transaction publication accepts a freshly recomputed BLOCKED receipt so the run,
both vehicle diagnostics, summary, and inventory are retained. Public
`verify_run()` and `serve_run()` keep `require_qualified=True` by default and both
reject the same package with `independent qualification is BLOCKED`.

Fix commit:
`65b95e7c410bbb60d422fbc851dd9d7ea57516ab`

Fresh focused verification after that commit:

```text
29 passed in 21.49s
compileall PASS
diff-check PASS
```

The correction adds no sound-generation change and resolves the reviewer concern.
