# N2 source-tap and artifact-bound PCM export

Status: CLOUD_JVM_SYNTHETIC_RENDER_TESTED / REFERENCE_AND_DEVICE_QUALIFICATION_NOT_RUN

Base: PR37 `3ea2ebb2480daf1e47e28373c2761b14f3bbf270`.
This is a qualification-tooling follow-up, not a sound-quality acceptance or runtime enablement.

## Changes and contract

- The caller-owned tap stores **all seven source stems plus two impulse channels**. The old code
  overwrote body/rumble with impulses; it also silently discarded overflowing frames. Both defects
  are removed. A whole block's tap capacity is checked before any DSP state advances. Bad append
  shapes and nonfinite values are rejected before a frame is recorded.
- N2Renderer optionally records every source frame immediately after N2Source.sample. The stage is
  **before body delay, idle addition, shift, output filtering and headroom**. These are source-time
  channels; their sum is not the final output PCM. Channel order is exhaust, bark, intake,
  mechanical, afterfire, body, rumble, combustion_impulse, afterfire_impulse.
- Tap state is external observation storage. Renderer snapshots keep their existing frozen-chain
  meaning; the caller supplies a new/reset tap for replay. Tapping does not select an AudioEngine
  route and does not change the frozen HY1/source/profile/calibration code.
- Offline export and file I/O now live in **src/test**, along with their fixture types. This avoids
  introducing java.nio.file's API-26 dependency into the app's minSdk-24 production source set.
  The tap and optional renderer seam remain internal src/main classes.
- Export requires exact baseline and N2 binary artifact bytes. It imports/validates both profiles;
  there is no default kernel generation or profile fallback. The separately named
  N2SyntheticArtifactFixture utility creates synthetic test inputs only.
- A fixture owns copied SoundState/harmonics, explicit segment frame counts and validInput flags.
  The binary trajectory identity covers the fixture ID and every SoundState field, including
  fields unused by the current renderer. Each segment holds its state constant; chunk sizes are
  clipped at its boundary. Requested partition sizes cycle across the entire trajectory.
- T/S/E/SE plus E/SE-event-off produce mono Float32 little-endian PCM and frame-major 9-channel
  Float64 little-endian taps. The reused 960-frame renderer buffer is copied immediately.
- The receipt binds the exact profile artifact, profile identity, baseline artifact/identity,
  fixture bytes, partitions, every output's byte size and SHA-256, and observed event counts.
  A new output directory is created exclusively; every file uses CREATE_NEW. Existing files,
  directories and dangling symlinks are rejected. manifest.tsv is written last, and the success
  digest is returned only after that write finishes. An interruption can leave a partial manifest;
  consumers must validate all 12 entries and payload hashes, never infer completion from manifest
  existence alone. Incomplete directories are retained for inspection without overwrite.

### Trajectory wire format

trajectory.bin uses Java DataOutputStream encoding (big-endian numbers and modified-UTF strings).
The ordered fields are: UTF `c63.n2.trajectory.v1`, UTF fixture ID, int segment count, then for each
segment: int frames, boolean validInput; doubles timeS/rpm/frequencyHz/amplitude/brightness/
throttle/load/shiftGain; int harmonic count and float harmonics; booleans muted/braking; int gear;
booleans afterfireTrigger/shiftTrigger. The exact bytes are included and hashed in each export.
The current callable API consumes N2QualificationFixture; this binary is an audit input record,
not a newly claimed general-purpose fixture parser or reference-dataset importer.

## Reproduce JVM software checks

Requires Python 3, a JDK with the compiler module, and the pinned Maven dependencies listed in
`vico_app/tools/jvm/dependencies.json` (official repo.maven.apache.org URLs and SHA-256). Obtain
those exact files in one dependency directory; the runner verifies every hash and does not
install or download anything. Use new build/export paths:

```sh
python vico_app/tools/python/run_n2_jvm_tests.py \
  --deps /path/to/pinned-jars --build-dir /path/to/new-build \
  --synthetic-export /path/to/new-synthetic-export
```

The runner compiles the actual Kotlin N2 and frozen C63 S15–18 sources without Android stubs,
plus their test sources, using Kotlin 1.9.24 and JVM target 1.8. Its default `--suite n2` executes
N2 tests. `--suite all-c63` additionally executes the historical C63 tests, including tests that
require local phone/reference files. Java compiler invocation uses its JDK module rather than
assuming a separate javac launcher is present. Every assumption skip is printed and excluded
from the pass count. Compilation, test failure or missing dependency returns nonzero.

Synthetic export is optional and occurs only after the selected suite succeeds. It creates
explicit test-only input files, imports those files into both real renderer runs, and emits a
separate execution receipt. The build directory records the exact compiled source hashes,
dependency hashes, runtime version and test log. No candidate/objective evaluation or budget
reservation is performed by these reference-free software tests.

For approved binary inputs, the compiled test CLI can be invoked directly:

```sh
java -cp <compiled-tests-and-dependencies> \
  com.vico.simulator.sound.n2.diagnostic.N2SyntheticReferenceExporter \
  /approved/baseline.bin /approved/profile.bin /new/output 333,297
```

This CLI uses the named synthetic trajectory. Arbitrary qualification trajectories use the
N2QualificationExport API with explicit segments and artifacts. The existing opt-in
N2PcmFixtureTest now requires VICO_C63_BASELINE_ARTIFACT and VICO_C63_N2_ARTIFACT when
VICO_C63_N2_FIXTURE_OUTPUT is set; VICO_C63_N2_PARTITIONS defaults to `960`.

## Executed evidence (2026-10-02 UTC)

OpenJDK 21.0.12.1, Kotlin 1.9.24, JUnit 4.13.2, Python 3.12.14, Linux cloud execution.

- Focused N2: **34 passed, 0 failed, 2 assumption-skipped** (36 discovered/run by JUnit). The two
  skips are the opt-in external-fixture export and one-time calibration, not passed gates.
- Two actual synthetic exports ran through the CLI after tests: 960 and 333+297 partitions.
  Each contains all six controlled branches and **140160 frames per branch** (2.92 seconds).
  All 15 payload files (12 PCM/tap files plus both artifacts and trajectory) were byte-identical
  across partitions. Manifests differ because they record the partition selection.
- The hot-load/lift/shift/invalid-input-tail fixture produced 23 raw event arrivals and 20 distinct
  event impulse frames for E/SE, identically for event-on/off. Tests assert source channels other
  than the event stem remain identical, on/off final PCM differs, late response samples beyond
  frame 8192 are nonzero, and the 12288-frame event queue eventually drains without replay.
- Tests also execute 960/333+297 partition equivalence, snapshot and reused-buffer isolation,
  unchanged T-chain identity, exact artifact/fixture/disk output hash binding, malformed artifact
  rejection, nonfinite append rejection, overflow atomicity, and existing-output rejection.
- Python evidence-gate integration: **43 tests passed** after fast-forwarding the Windows-locking
  follow-up. No Python gate or frozen calibration bytes were changed by this patch.
- Independent review reran the focused tests and exports, verified all 106 compiled-source hashes,
  and additionally exercised dangling-symlink rejection and two concurrent exporters targeting
  one new directory: exactly one succeeded, the other rejected, and the winner matched the
  complete 16-file expected output. These are separate checks, not extra JUnit passes.
- `git diff --check` and Python runner compilation passed.

The compact actual render receipts and exact source hashes are checked in at
[06-testing/n2-cloud-stem-export-20261002](06-testing/n2-cloud-stem-export-20261002/).
Generated PCM/tap binaries remain reproducible test outputs, not repository assets.

Receipt SHA-256:

- 960 manifest: `e93adc1353172093e505cb534ed0388fb9b8a9cd8b62672e670c9f09befa3589`
- 333+297 manifest: `d9ff7bf0b0cbba6b2c6ea470b3a4b806b7fc9f9c47256edbfe2c05d820376a9b`
- N2 artifact: `dfa032013ab6552175346758833669d8b6405f6f09ab0504f6f3b47fe1ae0889`
- N2 profile identity: `b4d5269ef63f9b06b15caa580b6fa0e2aa4ff31f444cfc79db001078aa85e074`
- Synthetic fixture: `63600032d415df81b13ee263774b7072436cdfda2fe55d42c17df12990d84da9`

## Broader checks and remaining blockers

The broader C63 JVM attempt executed 144 tests: **122 passed, 20 assumption-skipped, 2 failed**.
Both failures are missing existing local phone-capture input, not silently skipped or repaired:

- C63HeadroomHoldoutTest.recorded_phone_repeated_timestamps_and_frame_counts_survive_partitioning
- C63RuntimeRendererTest.recorded_phone_startup_input_must_not_violate_peak_gate

Both read the pre-existing hardcoded file
`E:\Tesla_speed\review_packages\s15-20261001\device-smoke-performance-fix.json`, absent in the cloud.
No private reference/capture files were fetched. The broader suite remains unpassed.

Full Gradle/Android build and instrumentation did not run: the initial wrapper attempt could not
reach its Gradle 8.9 distribution with the Java network route, and no Android SDK was found in
this environment. Maven dependency downloads through curl worked, enabling the genuine standalone
JVM checks above. This is not an Android build result.

The 630-case qualification matrix, actual reference/provenance groups, protected-band/objective
metrics, held-out comparison, physical capture and human listening remain unrun. The Python
reference driver is still a separate unfinished producer task; this patch does not issue its
reference_result.v2 acceptance evidence or bypass its reservation/budget/hard-gate contract.
PR37 remains draft. Default playback, phone installation, deployment and main merge are unchanged.
