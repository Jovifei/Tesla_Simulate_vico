# N2 qualification-tool CI

This workflow checks reference-free software tooling. A green result does not qualify N2's
sound, alter its frozen gains, spend an evaluation budget, enable an app route, or authorize
installation. HY1, the DSP sources, calibration, preregistration and existing workflows are
unchanged by this CI stage.

## Trigger and permission scope

`.github/workflows/vico-n2-qualification.yml` runs for relevant pull-request paths against
**any base branch**, including PR37's `codex-remote-p2-p3-audit-20261002` base. Relevant pushes
to `main`, `p2-n2-*` and `codex-remote-p2-p3-*` also run it. Paths cover the workflow, exact-byte
attributes, N2 documentation, JVM/Python tooling, and the sound production/test source trees.
Manual dispatch is available when GitHub exposes the workflow on the default branch.

Both jobs check out and verify the triggering **head SHA**, rather than claiming a test of a
synthetic merge commit. The workflow uses only official actions pinned to full commit IDs,
`contents: read`, no persisted checkout credentials, no secrets, and no deployment or repository
write step. Newer runs cancel only earlier runs for the same event/PR or event/ref. PR and push
runs are intentionally independent, so an exact-PR-head result remains visible.

## Linux: actual synthetic exports and measurements

On `ubuntu-24.04`, Python 3.12 and Temurin Java 21:

1. Install SHA-256-pinned binary NumPy 2.3.5 / SciPy 1.17.0 wheels from official PyPI.
   `requirements-n2-ci-linux.txt` targets CPython 3.12 / Linux x86_64; unpinned sources or
   another platform's wheels are rejected. Force-reinstall prevents a preinstalled matching
   version from bypassing wheel-byte verification
2. Explicitly download the existing Kotlin 1.9.24 / JUnit dependencies from their exact official
   Maven Central URLs; verify every SHA-256 before using any jar
3. Compile the real Kotlin N2 and frozen C63 code through `run_n2_jvm_tests.py`
4. Run all selected N2 JUnit tests, then render the two actual synthetic partition exports
5. Run all `test_n2_*.py` tests and the existing nine absolute-feature regressions. The actual
   JVM export integration tests are enabled; any Python skip, expected failure, unexpected
   success, empty selection, or normal failure fails CI
6. Execute the metrics CLI against both real exports. Print its complete diagnostic JSON,
   input/payload hashes and non-accepting status in the job log

The wrapper prints an execution receipt and appends it to the GitHub job summary. It records
actual platform, checkout SHA, runtime versions, test counts, exact compiled-source receipt
hash, both actual manifest hashes and the metrics-file hash. The reader recomputes the actual
payload hashes, validates all fifteen payloads, and verifies two distinct partition schedules
produce equal output bytes. Outputs stay in runner temporary storage; no generated PCM,
private inputs, binary dependencies or large artifacts are committed/uploaded.

## Windows: real msvcrt process locks and gate CLIs

On `windows-2025`, Python 3.12 and Temurin Java 21, the Python suite uses only the standard
library. Java creates the synthetic frozen binary fixture used by the gate tests; no Kotlin
compiler, Android SDK or numeric Python package is needed.

The job runs `test_n2_artifact_gate.py`, `test_n2_process_lock.py` and `test_n2_ci.py`:

- Real production `_ledger_lock` calls, with independent child processes probing the native
  `msvcrt` byte-range lock while held and after normal/exceptional release
- Concurrent CLI reservations enforcing both 48/24 budgets with no lost updates; exactly-once
  duplicate reservation and concurrent result sealing
- Direct and module gate/CLI invocations, artifact-bound identities, malformed input rejection,
  atomic replacement and existing adapter error-path contracts

The wrapper refuses `--platform windows` unless `sys.platform == 'win32'`. Mock-CRT contract
passes on Linux cannot be reported as Windows execution. The independent native probes and
whole-process gate tests run without CRT/platform mocks. This is process-concurrency evidence,
not a power-loss or filesystem crash-durability guarantee.

## Explicit exclusions, never converted into passes

The default JVM N2 suite retains exactly two named assumption skips:

- `N2PcmFixtureTest.exportSixControlledBranchesForLocalReferenceComputation`: opt-in export
  requires approved artifact paths and an explicit output destination
- `N2UnitCalibrationTest.measureInitialUnitSourceBeforeObjectiveEvaluation`: opt-in one-time
  calibration, not a CI recalibration

Both names are printed and excluded from the pass count. Any other JVM skip/ignore or test
failure fails CI. The historical `--suite all-c63` remains available in the existing JVM runner;
it requires external phone/reference fixtures and is **not run** by this narrow workflow.
Its known missing-fixture failures are not hidden, changed to skips, or treated as passes.

Full Android/Gradle build, private reference inputs, the full qualification matrix, event-distance
acceptance, device and human acceptance remain NOT_RUN. The synthetic diagnostic retains the
observed mid-band +4.6397081085 dB and bark-RMS +4.2647339192 dB values from the prior stage;
this CI does not normalize them away or redefine the registered 1 dB bounds.

## Reproduction and pre-publication verification

From the repository, using a fresh output path:

```sh
python vico_app/tools/python/run_n2_ci.py --platform linux \
  --deps /path/to/already-pinned-jars --output /path/to/new-ci-run
```

Use `--download-deps` instead of `--deps` to explicitly obtain and verify the official Maven
jars. On a real Windows host with Python and Java installed:

```powershell
python vico_app/tools/python/run_n2_ci.py --platform windows --output C:/temp/new-n2-ci-run
```

The staged Linux rehearsal on 2026-10-02 UTC used Python 3.12.14, OpenJDK 21.0.12.1,
Kotlin 1.9.24, NumPy 2.3.5 and SciPy 1.17.0. It passed **81 Python tests, zero skips**, plus
**34 JVM tests with the two explicit opt-in skips**. Both actual exports and the metrics CLI
completed. A second isolated-venv rehearsal also passed all checks after installing the
hash-pinned wheels and exercising the actual official Maven download/hash-validation path. Exact receipts reproduced the prior synthetic export/measurement evidence:

- Compiled-source receipt: `309367eeccdd3d9b3a1de5e973a5c3a09930d073a5f8bd3d0b0cb56e0e58b669`
- block960 manifest: `e93adc1353172093e505cb534ed0388fb9b8a9cd8b62672e670c9f09befa3589`
- split333_297 manifest: `d9ff7bf0b0cbba6b2c6ea470b3a4b806b7fc9f9c47256edbfe2c05d820376a9b`
- Metrics JSON: `3efce9b55c181e02c60f42454e7c4e9d524cae4b825d50755557b3523871cbfb`

This Linux rehearsal is not a Windows or GitHub-hosted result. After publication, use the
[GitHub workflow runs](https://github.com/Jovifei/Tesla_Simulate_vico/actions/workflows/vico-n2-qualification.yml)
and each run's exact `head_sha`, job outcomes and receipts to establish those results. Do not
infer success from workflow creation, a pending run, or another commit's green check.
