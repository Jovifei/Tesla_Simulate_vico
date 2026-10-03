# N2 historical-input state and digital diagnostics

Status: AVAILABLE_MATRIX_DIGITAL_MEASUREMENT_TESTED / FULL_630_AND_ACOUSTIC_QUALIFICATION_NOT_RUN

This test-only stage reconstructs the available historical control trajectories and measures
actual N2 renderer outputs without retaining large PCM/tap dumps. It changes no production
DSP, HY1/profile bytes, calibration, thresholds, budget, AudioEngine route, private inputs or
device state. Its receipts are diagnostic evidence, not `reference_result.v2` acceptance.

## Exact historical inventory

The source contracts are `C63HeadroomCalibrationTest` (Q0–Q4) and
`C63HeadroomHoldoutTest` (H1–H3). The catalog has exactly **630 entries: 333 Q + 297 H**:

| Group | Inventory | Available | Missing |
| --- | ---: | ---: | ---: |
| Q0 | 49 | 48 | 1 phone capture |
| Q1 | 2 | 1 | 1 phone capture + hold |
| Q2 | 76 | 76 | 0 |
| Q3 | 6 | 6 | 0 |
| Q4 | 200 | 200 | 0 |
| H1 | 290 | 0 | 290 absent holdout RPMs |
| H2 | 6 | 6 | 0 |
| H3 | 1 | 1 | 0 |
| Total | 630 | 338 | 292 |

The 338 available cases are **331 Q + 7 H**, totaling 74,697,600 frames per branch.
The two missing phone cases retain their explicit missing-input status; no uniform 960-frame
substitute is invented for the recorded frame counts. The missing H1 RPMs require the original
holdout manifest with SHA-256
`757d9405b5e9b69a3247a671e27079081d373dfc012b77c3d525b871cd2954b1`.
Each missing entry has no frames, segments or trajectory hash and refuses rendering.

Q1 binds the existing checked-in trace's exact CRLF bytes:
`ab1bf8c8335ec5224b18d501bf1fcf16d70c84f6a6371cdb88da5a08db554619`.
The `.gitattributes` addition preserves those existing bytes across platforms. It does not
modify the trace. The historical generator deliberately uses the first 1,500 of its 1,501
records, with shift triggers at indices 306, 432 and 558. Q4 retains negative-time hot
conditioning. H2 retains repeated floating-point `time += .02`, including its accumulated
roundoff, rather than replacing it with index multiplication.

Every available entry records both the existing full `c63.n2.trajectory.v1` identity and the
historical little-endian six-double row hash (time, RPM, load, throttle, shift, frame count).
The frozen ordered catalog SHA-256 is
`32ca93bb3284f95bc4a6a383d5bd12053fd7d95eeb02cfd5a12451f985b0b60a`.

## Bounded measurement and fail-closed scope

`N2HistoricalDigitalVerification` imports explicit baseline and N2 binary artifacts. It does
not generate, fit or choose profiles. For each case it renders the existing six controlled
branches: T, S, E, E_EVENT_OFF, SE and SE_EVENT_OFF. It streams blocks of at most 4,800 frames,
hashes little-endian Float32 PCM and all nine Float64 tap channels, and accumulates finite
energy, RMS, PCM/renderer peak, first ceiling exceedance and producer event observations.
The default CLI partition schedule is 960 frames; input segment boundaries are never moved.

`digital_pass` means the actual Float32 PCM and renderer peak remain at or below the existing
0.8413951416451951 ceiling and event observations did not truncate. Nonfinite samples/taps or
energy, incomplete frame counts and invalid artifacts fail before a result is produced.
Pending queue frames are reported, not silently dropped or redefined as an acceptance gate.
This does not compute protected-band power deltas, event distances or acoustic scores.

Outputs contain hashes and metrics only. PCM and tap arrays are retained for the current block,
not the whole case or matrix. A fresh directory is required; existing output is never overwritten.
The CLI writes its final receipt after all results and exits nonzero if any recorded digital
branch fails. A run interrupted before the receipt is incomplete. No failed output permits
retuning. Retaining raw output for all available cases would cost roughly 34 GB per schedule
or 68 GB for two schedules; this command avoids that storage.

## Artifact provenance and bounded state coverage

These executions use the existing generated **test-only** `N2SyntheticArtifactFixture`
baseline/profile inputs, not approved private reference artifacts. The historical trajectories
are reconstructions of their source contracts; the baseline profile remains a synthetic test
fixture. Actual rendering does not make it production or acoustic qualification evidence.

- Test baseline artifact SHA-256:
  `edc163411548958f27186b5f2a144baa166caf813719da4f61574feace55759c`
- Test N2 artifact SHA-256:
  `dfa032013ab6552175346758833669d8b6405f6f09ab0504f6f3b47fe1ae0889`
- Imported N2 profile identity:
  `b4d5269ef63f9b06b15caa580b6fa0e2aa4ff31f444cfc79db001078aa85e074`

The seven new JUnit tests cover exact inventory and durations, missing-input rejection, source
binding and immutability, stream/export byte equivalence, malformed-input rejection, and these
separately scoped state checks:

- All six branches for three complete historical cases compare exactly under 960 versus
  333,297 partitions: Q0_steady_700.0_0.0, Q4_1849.0_0.32_0.35_true and H3_events
- Frozen T is compared sample-for-sample against independent C63HybridRenderer(T) on the full
  Q0_transition_7200.0_700.0 and H3_events trajectories using 17,333,71,960,5,241 partitions
- Snapshot replay is checked in all six branches 333 frames into H3's hot shift at segment
  250, through the remaining 627 frames and the next 30 segments, including PCM, nine-channel
  taps, renderer counters, pending-frame counts and arrival frames

These checks use the same explicit test artifacts. They do not prove every state, partition,
snapshot boundary or production profile. The CLI's receipt correctly says those broader
state properties were not run by the CLI itself; JUnit evidence is separate.

The opt-in export and one-time initial unit-calibration tests remain named skips, excluded
from pass counts. Historical `all-c63` tests requiring missing private inputs are not run or
converted to passes. The full 630-case matrix, protected-band and event-distance gates,
approved reference/held-out evaluation, Android/Gradle build, device installation and human
acceptance remain **NOT_RUN**. No objective-budget reservation is made.

## Executed evidence, 2026-10-03 UTC

Fresh compilation and execution used Linux, OpenJDK 21.0.12.1, Kotlin 1.9.24 and Python 3.12.14.
The reconstructed sources exactly match the prior reviewed compiled-source receipt SHA-256:
`f49de0ba29b270f91652559dc998c967fde8fe30de235207af07a2277594c1bc`.
The new evidence directory contains fresh execution logs and the full compiled-source list.

- **41 JVM tests passed, zero failed**, with exactly the two named opt-in assumption skips
- The seven historical tests separately passed from the Gradle app-module working directory
- Full local Linux CI: **81 Python tests passed, zero skips**, 41 JVM passes plus the two named
  skips, both actual synthetic exports and the metrics CLI completed
- Nine representative historical cases × six branches: **54 digital passes, zero failures**,
  3,772,800 frames per branch, approximately 11 seconds runtime
- All **338 available historical cases × six branches: 2,028 digital passes, zero failures**,
  74,697,600 frames per branch (448,185,600 total), approximately 187 seconds runtime
- Highest all-available PCM peak: **0.750049889087677** on Q2_820.0_6 / T

Fresh catalog, representative results and all-available results reproduce the prior reviewed
hashes exactly. Representative results SHA-256:
`f6d496dbea75c31ff7249d3d02b6ef62e9b3c635d43d8efa53e96bbbff133681`.
All-available results (1,246,125 bytes of hashes/metrics) SHA-256:
`21f5c0afac59d5764ed760e45b16013204b88fa325d5241f6b0dec7947b3f53b`.
The receipt/inventory cross-check verifies the exact 338-case set, six branch identities per
case, every fixture hash and frame count, finite metrics, ceiling flags and no truncation.
The single 960-frame CLI schedule does not extend the bounded state tests to every case.

The representative cases are Q0_steady_700.0_0.0, Q0_transition_7200.0_700.0, Q1_original,
Q2_540.0_2, Q3_hot_events, Q3_restart_0, Q4_1849.0_0.32_0.35_true, H2_0.12_true and H3_events.

Independent reconstruction of the historical generators matches all 338 available fixture
hashes and six-double row hashes, including 77,810 control rows. The prior review's test-root
portability defect is fixed: the resolver accepts exactly the Android project or app-module
root and retains exact source hashing. Both working-directory runs passed again.

Raw receipts, metrics, logs and source hashes are in
[06-testing/n2-cloud-historical-state-20261003](06-testing/n2-cloud-historical-state-20261003/).
No private inputs, artifact binaries or PCM/tap dumps are committed. These results use the
explicit generated test artifacts described above; they do not establish acoustic acceptance.

## Reproduction

Compile and run the default N2 suite using the already pinned official Maven dependencies:

```sh
python vico_app/tools/python/run_n2_jvm_tests.py \
  --deps /path/to/pinned-jars --build-dir /path/to/new-build
```

Build the Java classpath from `new-build/tests.jar`, `new-build`, and the verified jars listed
in `vico_app/tools/jvm/dependencies.json` (colon-separated on Linux, semicolon on Windows).
Use explicit artifact inputs and a new output directory:

```sh
java -Xmx2g -cp "$CLASSPATH" \
  com.vico.simulator.sound.n2.N2HistoricalDigitalVerification \
  vico_app/Project/android/app/src/main/assets/s12_v10/c63_w204_v6/common_input_trace.json \
  /path/to/explicit-baseline.bin /path/to/explicit-n2-profile.bin \
  /path/to/new-output representative
```

The `all-available` option selects all 338 reconstructible cases, never all 630. Selecting the
option alone is not evidence of success. A complete qualification still needs the exact missing
phone/holdout inputs, approved artifacts and unchanged reference/acceptance gates.
