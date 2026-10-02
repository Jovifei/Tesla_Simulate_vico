# N2 actual-export measurement diagnostics

Status: SYNTHETIC_PCM_METRICS_TESTED / REFERENCE_ACCEPTANCE_NOT_RUN

Base: PR37 `1e69dd1cdc395eba1145018c94bd7ca840037942`.
This stage replaces the Python manifest-only helpers with an actual binary export reader and
measurement CLI. It does not create a `c63.n2.reference_result.v2`, reserve a trial, spend an
objective evaluation, fit parameters, or enable N2. The frozen calibration, HY1, Kotlin DSP,
AudioEngine/default sound path and preregistration bytes remain unchanged.

## Exact inputs and checks

The only accepted input format is the existing JVM `c63.n2.render_receipt.v1` export described
in [the stem-export contract](vico-n2-stem-export-validation.md). No second render format is
introduced. An export must contain the complete twelve PCM/tap entries and the three bound
binary input records. The reader:

- validates metadata/branch/channel identities, frame counts, byte sizes and SHA-256 of actual
  files, rather than trusting the receipt's precomputed measurements;
- uses the existing evidence gate's frozen N2 binary decoder/identity constraints;
- validates the HY1 baseline binary constraints and its full-byte identity;
- parses the existing trajectory record, including all finite SoundState fields, canonical
  booleans, ASCII fixture ID, segment lengths and exact end of record;
- recomputes whole-run finite/energy-finite, RMS and peak for all six mono PCM branches and all
  nine source/impulse channels; Float32 PCM is promoted to Float64 before squaring;
- compares the computed PCM RMS/peak with the producer's reported values, allowing only a
  1e-11 relative reduction-roundoff tolerance;
- recomputes distinct afterfire impulse frames from tap channel 8; raw-arrival and pending-frame
  counters remain explicitly producer-reported because a merged impulse loses individual
  arrival information and the export has no full queue-state record;
- rejects missing/truncated/duplicate/unknown entries, hash mismatch, malformed binary inputs,
  nonfinite samples or energy, invalid dimensions and symlinked payloads/export roots;
- checks that source channels outside bark are preserved in T→S and E→SE, non-event channels
  (including bark) are preserved in T→E and S→SE, event-off silences
  only the afterfire stem, and on/off occurrence/pending observations match.

A second export can demonstrate byte equality across two **different realized** partition schedules.
It must have the same input/fixture/profile identities and all fifteen payload hashes. Supplying
one export leaves `partition_invariant` null. Equivalent executed block sequences are rejected,
including repeated schedules such as 960 versus 960,960 and schedules made equivalent by
trajectory-boundary clipping. The partition index advances across clipped segment boundaries,
matching the renderer. These cases were added after independent review. This observes those exact outputs; it does not prove every partition,
independent frozen-T equivalence, queue continuity or snapshot replay.

## Measured quantities and scope

The selected analysis interval is explicit and half-open in source/output frames. Default:
`[0, frames)`. It must contain at least 24000 samples. The tool does not select calibration,
reference or held-out windows and does not treat a convenient synthetic trajectory as the
qualification fixture matrix.

Protected output powers use the already implemented
`build_c63_hybrid_targets.features` absolute-power definition: 48 kHz mono, 8192-point Hann
Welch PSD, 6144-sample overlap, no detrending, density integration and half-open bands
`[20,200)`, `[200,4000)`, `[4000,12000)` Hz. Tests compare these values directly against the
existing extractor. PCM is not gain-normalized. Zero/nonfinite comparison powers or bark RMS
are rejected instead of manufacturing a finite dB result with a floor.

Two controlled comparisons use actual output PCM and actual pre-chain bark taps:

- T→S: replacement of continuous bark with the same baseline event source
- E_EVENT_OFF→SE_EVENT_OFF: replacement of continuous bark with the new event stem muted

Fields reuse the hard gate names: `low_max_db` is the absolute low-band power delta,
`mid_max_rise_db` is the signed mid-band delta, and `source_rms_change_db` is the signed bark
RMS delta. Median/p90 are the same value for this **one window** and carry `window_count=1`.
They are not summaries/maxima over the unrun qualification matrix. Bark taps are before delay,
idle, shift, filtering and headroom, so they are not substituted for final output PCM.

E and SE also report measurements of the real Float64 `event-on PCM − event-off PCM` and the
separate afterfire source stem. This is not an event-distribution distance or an event-quality
score. No new weighting, event detector, episode segmentation or reference standard is chosen.

The output `c63.n2.render_metrics.v1` is a diagnostic receipt, **not an alternative acceptance
schema**. It binds the exact consumed input/manifest/payload hashes, analysis window, measurement
source-file hashes and Python/NumPy/SciPy versions. It has no reservation, reference binding,
provenance-group scores, acceptance boolean or runtime eligibility. The existing hard gate
continues to require its unchanged `reference_result.v2` contract. Tests ensure this diagnostic
output lacks required qualification evidence and cannot be mistaken for a full result.

## Reproduction

Requires the pinned JVM dependencies from the existing export instructions plus Python 3,
NumPy and SciPy. These numerical packages were already installed in the cloud; this stage did
not change the environment or install packages. The old manifest-only `export_fixture`,
`export_manifest` and calibration convenience helpers were removed rather than left as a
misleading second output path. No repository callers outside their replaced tests used them.

```sh
python vico_app/tools/python/run_n2_jvm_tests.py \
  --deps /path/to/pinned-jars --build-dir /path/to/new-build \
  --synthetic-export /path/to/new-synthetic-export

VICO_N2_RENDER_EXPORT=/path/to/new-synthetic-export \
  python -m unittest discover -s vico_app/tools/python -p 'test_n2_*.py' -v

python -m vico_app.tools.python.n2_reference_driver \
  --export /path/to/new-synthetic-export/block960 \
  --compare-export /path/to/new-synthetic-export/split333_297 \
  --out /path/to/new-diagnostic-metrics.json
```

Direct script invocation works too. `--start-frame` and `--stop-frame` select a different
explicit interval. The output file uses exclusive creation; existing files or dangling symlinks
are never overwritten. Invalid input exits 2 and writes no successful metrics receipt. Exit 0
means successful diagnostic measurement only, not protected-band or acoustic acceptance.

Without `VICO_N2_RENDER_EXPORT`, the two actual-export integration tests are explicitly skipped.
All other reader tests generate synthetic wire fixtures with real PCM/tap bytes and valid
frozen-format input artifacts. Those are parser/metric tests, not Kotlin render evidence.

## Executed evidence (2026-10-02 UTC)

Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0, OpenJDK 21.0.12.1, Kotlin 1.9.24, Linux cloud.

- Focused reader/measurement/CLI: **28 passed**, including both opt-in actual-export integration
  tests against the real Kotlin-generated six-branch outputs
- All N2 Python gate/lock/reader/measurement tests: **66 passed, 0 skipped** with actual exports
- Fresh standalone Kotlin/JUnit run: **34 passed, 2 assumption-skipped**, followed by both
  actual synthetic exports; the exact manifest hashes match the earlier 1e69dd1 export evidence
- Existing absolute-feature extractor regression: **9 passed**
- Known analytical gain doubling: measured `20*log10(2)` dB for protected low/mid and source RMS
- Existing Welch extractor equivalence, malformed/tampered/nonfinite inputs, branch isolation,
  different-schedule byte comparison, direct/module CLI and exclusive-output checks pass
- Independent review reran all 28 focused tests after both fixes and found no remaining blocking
  finding in this diagnostic scope; `compileall` and `git diff --check` also pass

The synthetic hot/lift/shift/tail export contains 140160 frames per branch. For its entire
`[0,140160)` window, T→S measures:

- low-band absolute delta: **0.0136754383 dB**
- mid-band rise: **4.6397081085 dB**
- source bark RMS change: **4.2647339192 dB**

The latter two numbers exceed the registered 1 dB bounds in this diagnostic window. They are
reported rather than hidden or normalized away. This input is a synthetic tooling fixture,
not the registered calibration/reference matrix, so these numbers are neither a candidate
qualification verdict nor permission to alter gains. No gain/source/artifact change followed.

Both real export partitions have identical payload bytes. E/SE contain 20 distinct impulse
frames and report 23 raw arrivals. Their actual event-on/off PCM differences are nonzero.
Reference/event distribution distance, held-out evaluation, 630-case matrix, independent T
oracle, snapshot replay, full Android/Gradle build, device and human acceptance remain NOT_RUN
by this diagnostic command. Existing broader-suite missing-phone-capture failures are not
converted into passes.

The exact final diagnostic receipt and raw focused execution evidence are stored in
[06-testing/n2-cloud-render-metrics-20261002](06-testing/n2-cloud-render-metrics-20261002/).
The fresh Kotlin compiled-source receipt SHA-256 is
`309367eeccdd3d9b3a1de5e973a5c3a09930d073a5f8bd3d0b0cb56e0e58b669`, identical to the
[prior complete source list](06-testing/n2-cloud-stem-export-20261002/source-sha256.json).
No generated PCM/tap binary was committed.

- Diagnostic JSON SHA-256: `3efce9b55c181e02c60f42454e7c4e9d524cae4b825d50755557b3523871cbfb`
- Reader SHA-256: `d41cdd8b39780df4d2d13c564a834f43193c406c973692b24b248fa470d91465`
- Driver SHA-256: `a6e0b0c1bd0bc228406a63eadb436d40fb9a0c1e37ce95ea8fd0e5b6ed991d31`

## Next bounded protocol work versus private input blockers

Engineering can prepare and review a minimal N2 measurement protocol without private files.
The following choices must be explicitly bound **before** a real N2 objective evaluation,
consistent with the unchanged limits and preregistered representation:

1. The complete named fixture/seed/trajectory matrix, ordered case identities and the precise
   per-case measurement windows; how a maximum over protected deltas and representative bark
   RMS statistic are formed, including silence/degenerate-window handling
2. A versioned reference-target schema with provenance groups, source/rights receipts, exact
   clip/window hashes, calibration/evaluation/held-out membership, frozen feature scales/weights,
   expected group coverage and rejection of missing/extra rows
3. The N2 event-distance protocol: observed signal (source stem or final on/off difference),
   baseline event-off/control export, event detector/version, alignment delay, opportunity/closure
   episode labels, treatment of merged arrivals/censored tails/missing categories, descriptor
   scales and distribution aggregation. The historical HY1 detector/Wasserstein implementation
   is a reviewable prior, not silently adopted as the N2 contract
4. Evidence inputs for independent frozen-T identity, snapshot replay and full continuity;
   these assertions cannot be inferred from one pair of equal partition exports
5. The trusted producer flow binding each frozen input/protocol to the existing pre-evaluation
   reservation, fail-closed hard gate and sealed exact result digest, without resetting or
   bypassing spent evaluation budgets

Execution then needs approved immutable artifacts/calibration receipts, the complete fixture
exports and authentic reference targets/rights evidence. Raw private reference/phone capture
files remain local and were not accessed or fetched here. Device/human stages require their
own evidence and authorization. Protocol design and remaining reference-free engineering can
continue while those private-input and physical stages remain blocked.
