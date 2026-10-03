# N2 available historical partition and frozen-T verification

Status: AVAILABLE_MATRIX_PARTITION_AND_FROZEN_T_PASSED / ACOUSTIC_QUALIFICATION_NOT_RUN

This test-only extension addresses the broader state-coverage gap in the
[historical digital diagnostics](vico-n2-historical-state-validation.md). The exact catalog,
630-entry inventory and missing-input behavior are unchanged. Production DSP, HY1, gains,
calibration, thresholds, budgets, routing and device state are unchanged.

## Checks and evidence contract

`N2HistoricalStateVerification` accepts explicit trace, baseline and N2 artifact files and a
fresh output directory. It never generates or silently substitutes an input. `representative`
selects the existing nine representative cases; `all-available` selects the exact 338 available
cases (331 Q + 7 H). The remaining 292 cases keep missing-input status and are never passes.

For each selected case:

1. Compare actual N2(T) output against a separate `C63HybridRenderer(T)` instance, sample for
   sample across the complete trajectory, using cyclic requests 17,333,71,960,5,241
2. Render the six frozen ordered controlled branches under cyclic requests 960 and 333,297
3. Compare the two retained Result records exactly: little-endian Float32 PCM SHA-256,
   nine-channel Float64 tap SHA-256, frame counts, PCM/renderer peak, energy/RMS, nine tap
   peaks/energies, first ceiling exceedance, raw-arrival and distinct-impulse counts,
   pending-frame count and observation-truncation flag
4. Independently require both renders to satisfy the unchanged digital checks

The renderer's full event episodes and arrival/impulse arrays are not retained by Result and
are not directly compared here. This does not test full snapshot-state equality. PCM/tap hashes
bind the streamed bytes; no large PCM dump or all-case buffer is retained.

Partition sizes are requested chunk lengths, not relocated control points. Each request is
clipped at the next historical input-segment boundary, and the cyclic index advances even for
a clipped request. Every original input state, frame count and boundary is preserved. These
specific schedules produce different realized output-block sequences; they do not prove all
possible partitions, all profiles, arbitrary inputs or snapshot boundaries.

An explicit independent six-identity guard rejects missing, duplicate, reordered or altered
controlled branches before rendering. The expected result count is fixed separately from the
executed branch list. The six identities are T/on, S/on, E/on, E/off, SE/on and SE/off.

Outputs:

- `catalog.tsv`: the unchanged complete inventory, including explicit missing entries
- `partition-results.tsv`: one row per case/branch with both PCM/tap hashes, peaks, digital
  outcomes and exact retained-Result equality
- `frozen-t-results.tsv`: one row per case with input identity, frame count and number of
  sample-for-sample equal N2(T)/independent frozen-T frames
- `receipt.tsv`: explicit artifact/profile identities, requested schedules, counts, result
  hashes and exclusions; written last

Existing output directories/files are never overwritten. Frozen-T mismatch or malformed input
fails before a final completion receipt; partial output is incomplete evidence. Partition or
digital mismatches are recorded and cause a nonzero exit. A failure never permits retuning.

## Regression coverage

Five new JUnit tests cover a complete historical event case in all six branches plus frozen T;
identity and all retained Result-field mutations; independent six-branch inventory checks;
schedule-copy immutability; and CLI invalid selection/existing-output rejection. Missing,
duplicate and reordered branches cannot be laundered into a six-branch success. Equal unsafe
results remain a digital failure even when their retained fields match exactly.

## Provenance and unresolved gates

The executed inputs are generated **test-only** artifacts from the existing
`N2SyntheticArtifactFixture`, with the same bytes as the prior historical stage:

- Baseline artifact SHA-256:
  `edc163411548958f27186b5f2a144baa166caf813719da4f61574feace55759c`
- N2 artifact SHA-256:
  `dfa032013ab6552175346758833669d8b6405f6f09ab0504f6f3b47fe1ae0889`
- Historical catalog SHA-256:
  `32ca93bb3284f95bc4a6a383d5bd12053fd7d95eeb02cfd5a12451f985b0b60a`

The baseline remains synthetic. These state checks are not acoustic/reference qualification,
protected-band acceptance, event-distance scoring, a new candidate evaluation or permission
to install. No objective reservation is made. The full 630-case matrix still needs the exact
phone capture and frozen 290-RPM holdout manifest; approved non-synthetic artifacts/reference
targets, Android/device execution and human listening remain separate requirements. Snapshot
coverage remains the earlier bounded tests and is not expanded by this CLI.

## Executed evidence, 2026-10-03 UTC

Linux cloud, OpenJDK 21.0.12.1, Kotlin 1.9.24 and Python 3.12.14. The exact compiled-source
receipt SHA-256 is `c316efbc4bcf705bbebef2192675dc1e23ca6678a12889c00e8817812dee9e79`.

- Final local Linux CI: **81 Python passes, zero skips; 46 JVM passes, two named opt-in skips**
- Both historical test classes from the app-module working directory: **12 passes, zero skips**
- Representative CLI: **54 exact partition matches, 108 digital passes, nine frozen-T cases**
- All-available CLI: **2,028 exact partition matches, 4,056 digital passes, 338 frozen-T cases**
- No partition mismatch, digital failure or frozen-T mismatch occurred
- Frozen T: **74,697,600 sample-for-sample equal frames** across the 338 complete trajectories
- All-available runtime: approximately **403 seconds**; representative runtime approximately 22 seconds

Both schedule outputs for every one of the 2,028 case/branch pairs reproduce the previously
published historical digital output PCM/tap hashes, input identities, frame counts and peaks.
The prior output table SHA-256 is
`21f5c0afac59d5764ed760e45b16013204b88fa325d5241f6b0dec7947b3f53b`.
Representative rows also match their full-run counterparts exactly.

- All-available partition results SHA-256:
  `d79d48a500161136c14f691bf28429a645a46b58fe7cade948987580932eaeb5`
- All-available frozen-T results SHA-256:
  `8920db2db16d2e600b373a76c717fadc0564cd78ec665f3a4a99f30dd7a08396`

Independent code review prompted the explicit six-identity guard, additional field-mutation
regressions and narrower observation wording; all were applied before the final runs.
Raw logs, hashes, result tables, runtime and source receipts are in
[06-testing/n2-cloud-historical-continuity-20261003](06-testing/n2-cloud-historical-continuity-20261003/).
No PCM dump, private input, artifact binary, source/gain adjustment or objective reservation
was introduced. These are the exact observed state checks, with the limits described above.

## Reproduction

Compile with the existing standalone JVM runner and the pinned official Maven dependencies:

```sh
python vico_app/tools/python/run_n2_jvm_tests.py \
  --deps /path/to/pinned-jars --build-dir /path/to/new-build
```

Use a classpath containing the resulting tests.jar, build directory and the pinned jars. Use
colons on Linux or semicolons on Windows. All inputs and the fresh output path are explicit:

```sh
java -Xmx2g -cp "$CLASSPATH" \
  com.vico.simulator.sound.n2.N2HistoricalStateVerification \
  vico_app/Project/android/app/src/main/assets/s12_v10/c63_w204_v6/common_input_trace.json \
  /path/to/baseline.bin /path/to/profile.bin /path/to/new-output all-available
```

Use `representative` for the fixed nine-case subset. A successful command certifies only the
stated diagnostic comparisons with those supplied artifacts and schedules.
