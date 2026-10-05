# N2 artifact-bound evidence gate

Status: CLOUD_POSIX_GATE_TESTED / WINDOWS_API_CONTRACT_TESTED / WINDOWS_RUNTIME_NOT_RUN / ACOUSTIC_AND_DEVICE_QUALIFICATION_NOT_RUN

Baseline: PR37 `538258543961d4a6c045c0ef0eab786e1015bda0` on
`p2-n2-source-implementation-20261002`. This patch does not incorporate PR35.

## What changed

- Both Python entry points perform actual verification and exit 2 on rejected evidence.
- Artifact bytes must decode as the frozen N2 binary v2 profile. The checker recomputes the
  stored profile identity and the frozen unit-profile identity from the imported arrays;
  it does not regenerate kernels or trust a caller-provided profile hash.
- Source/event calibration, seeds, coefficients, dimensions and normalized response constraints
  remain frozen. The preregistration file is pinned to its exact existing bytes.
- The actual artifact, calibration receipt, preregistration and nonempty reference-target bytes
  are hashed and bound to every reservation and result.
- One stable OS process lock covers ledger read/validate/modify/write. Unique temporary files,
  fsync and atomic replacement prevent lost reservations and partial writes.
- Limits remain 48 continuous and 24 event attempts. IDs are unique across both kinds. There is
  no reset, refund, migration or limit override. Missing/malformed old ledgers are not accepted.
- A reservation is sealed to the first identity-valid result's exact byte digest, including a
  hard-metric rejection. Only the same bytes can be verified again. A returned decision binds
  its result digest, reservation and artifact hashes, so downstream code must check those values.
- Identity/representation failures during verification or reservation on an existing valid
  ledger persist a terminal stop. Subsequent reservations/verification fail closed.
- Protected low-band maximum absolute delta, optional median/p90 summaries, mid-band rise and
  absolute source RMS change all use the registered 1 dB limit. There is no 1.5 dB p90 exception.
- Nonfinite JSON, overflow, booleans as numbers, duplicate keys, malformed shapes, deep nesting,
  absent evidence, altered artifacts and forged receipts are rejected.

## Supported invocation

Runtime: Python standard library with POSIX `fcntl.flock` or Windows `msvcrt.locking`.
No Android SDK is needed. Windows adapter logic is covered with mocks; actual Windows execution
and process-lock behavior remain NOT_RUN and must pass the same suite before real evaluation.
Tests additionally use the installed JDK 21 to create a temporary test-only binary fixture whose
unit-profile hash must equal the already frozen calibration identity. Production gates only
read imported binary bytes; they never invoke this generator.

Reserve before the evaluator runs:

```sh
python vico_app/tools/python/n2_hard_gate.py reserve \
  --ledger /approved-run/n2-budget.json --trial-id trial-001 --kind continuous \
  --artifact /approved-run/profile.bin \
  --preregistration docs/vico-p2-n2-implementation-preregistration.md \
  --reference /approved-run/reference-targets.json \
  --calibration /approved-run/calibration.json
```

The reservation JSON returned on stdout must be preserved unchanged in the result. Check with
these same six common arguments and one of:

```sh
python vico_app/tools/python/n2_hard_gate.py check --result /approved-run/result.json ...
python vico_app/tools/python/n2_artifact_gate.py --verify /approved-run/result.json ...
```

`python -m vico_app.tools.python.n2_hard_gate` and the equivalent artifact module also work from
repository root. The ellipses above mean the same explicit common arguments, not a shell flag.
Successful reservation/check exits 0. Evidence rejection exits 2 with JSON; missing CLI arguments
exit nonzero through argparse. The old hash-only reserve and echo-only verify flows are removed.

## Producer contract

Calibration receipt schema is `c63.n2.calibration.v1`, with:

- candidate: `C63_N2_CONTINUOUS_V1`
- profile_sha256: recomputed imported calibrated profile identity
- artifact_sha256: SHA-256 of the full imported binary file
- calibration_profile_id: `98dec5a954e836a0105241a04e920b8209f239441a51d039a46eb6b4f8e287c0`
- source_scale: `13.728409855272066`
- event_unit_energy: `331.3820481828321`
- event_unit_l2: `18.2039020043`
- pre_objective: true
- heldout_used_for_fitting: false

Result schema is `c63.n2.reference_result.v2`, with:

- candidate, trial_id and kind matching the reservation
- bindings: the unchanged reservation bindings object
- reservation: the complete returned reservation object
- evidence: positive integer sample_count; finite and energy_finite both true
- partition_invariant, snapshot_replay, baseline_t_identity and state_continuity: true
- heldout_used_for_fitting: false; gain_changes_after_calibration: integer 0
- continuous: low_max_db (maximum absolute 20–200 Hz delta), mid_max_rise_db,
  source_rms_change_db; optional low_median_db and low_p90_db
- continuous.provenance_groups: nonempty group mapping, each with positive baseline_distance
  and nonnegative candidate_distance; candidate/baseline must not exceed 1.1
- event: positive baseline_distance and nonnegative candidate_distance;
  candidate/baseline must not exceed 0.8

The on-disk ledger schema is `c63.n2.budget.v3`. Existing evidence without these bindings remains
unqualified; do not reset a spent ledger merely to use the new schema. Reconcile old spent
attempts and obtain a separately authorized migration before a real candidate evaluation.

## Trust boundary and outstanding work

This is an integrity and reported-metric gate, not a renderer or proof of sound quality.
Reference-target content is opaque, nonempty, byte-bound input. A trusted producer must establish
its provenance, fixture/group completeness, metric correctness and separation from held-out
fitting data. Likewise, the checker validates digital/state assertions but does not independently
render PCM or measure those assertions. The evaluator must reserve before evaluation, use the
same protected ledger for the entire candidate, and bind any scoring input to the returned
result digest. Filesystem administrators can replace a ledger; this is not a signed attestation
or a defense against untracked offline evaluations. Keep artifacts and the ledger immutable to
other writers during the run. There is no runtime enablement or deployment path in these tools.

The existing `n2_reference_driver.py` and `n2_reference_export.py` still only create manifest
metadata. Their replacement tests execute those actual functions and explicitly do not claim
PCM export. Full rendered six-mode/stem/partition evidence remains a separate next task.

## Executed checks (2026-10-02 UTC)

Cloud environment: Python 3.12.14, OpenJDK 21.0.12.1, POSIX process locks.

```sh
python -m unittest discover -s vico_app/tools/python -p 'test_n2_*.py' -v
python -m compileall -q vico_app/tools/python
python -m vico_app.tools.python.n2_hard_gate --help
python -m vico_app.tools.python.n2_artifact_gate --help
git diff --check
```

Result: 43 tests passed (34 existing executable gate/helper tests plus nine mocked Windows
locking/replacement contract tests). This includes both direct-script and module CLIs, package APIs, pass and
nonzero rejection fixtures, tampered/malformed/nonfinite input, both budget ceilings under 85
competing subprocess reservations, 16 competing duplicate reservations, and two competing result
payloads for one reservation. The temporary golden-format fixture is generated only for the
wire/identity test; no real reference clips are read.

Not run by this patch: full Android/Kotlin project build/tests, 630-case qualification matrix,
real reference/held-out comparisons, device installation/playback, physical acoustic capture,
human listening. Earlier 246-test local receipts are historical; they are not this patch's test
count. HY1, calibrated constants, renderer/source Kotlin and default AudioEngine routing are
unchanged. PR37 remains draft and qualification-only.

## Windows handoff compatibility follow-up

The Windows adapter uses a byte-zero lock on the same stable sidecar as the POSIX adapter.
It opens the sidecar unbuffered, seeks to byte zero before every lock/unlock, and may lock the
byte beyond EOF without modifying the file. It retries `LK_NBLCK` only for the documented
`EACCES` contention error. Unlike `LK_LOCK`, this does not abandon a legitimate waiter after
10 attempts. Other errors fail closed; interruption before acquisition never unlocks an
unacquired range. Context exit releases an acquired range even when validation raises.

Official API contracts: [Python msvcrt](https://docs.python.org/3/library/msvcrt.html) and
[Microsoft CRT _locking](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/locking?view=msvc-170).

Windows still flushes/fsyncs the unique temporary ledger file before replacement. It does not
attempt the unsupported POSIX directory-open/fsync step. Windows power-loss directory durability
is not established by these tests. A replacement/sharing failure propagates as rejection and
cleans up the unused temporary file. Use one protected ledger on a local filesystem; network
filesystem semantics have not been verified.

`docs/.gitattributes` fixes the preregistration file to LF line endings. This preserves its
registered byte hash when Git's Windows checkout policy would otherwise use CRLF; the gate does
not normalize or silently accept altered preregistration bytes. Adding the attribute does not rewrite an existing CRLF worktree copy. First inspect its bytes:

```powershell
Get-FileHash -Algorithm SHA256 docs/vico-p2-n2-implementation-preregistration.md
```

Expected: `16c22a5e313e49d10a8986312f6b63512bbdbc6fbf44f05276c4117f90e92b1f`.
Check this before using an authoritative ledger. If it differs, preserve any local edits;
if the content changed beyond line endings, stop for contract review. For a line-ending-only
difference, a safe alternative to replacing the tracked file is to
materialize the accepted Git blob into a **new** run-local file, then pass that file as
`--preregistration`. The following command refuses to overwrite an existing file and avoids
PowerShell's text-redirection encoding/line-ending conversions:

```sh
python -c "import pathlib,subprocess; data=subprocess.check_output(['git','show','240a861c705ce7c14fcf7e92c0564a4e8b8150b5:docs/vico-p2-n2-implementation-preregistration.md']); pathlib.Path('n2-preregistration.git.md').open('xb').write(data)"
```

This copies preregistration bytes only; it does not restore, discard or modify worktree edits.

Executed here: real POSIX process-contention tests, mocked Windows seek/range/retry/error/unlock
and file-replacement contracts, and Git's `eol=lf` attribute check. Not executed here: Windows
Python/JVM fixture generation, real Windows competing processes, Windows antivirus/sharing-lock
interactions, or Windows crash recovery. These distinctions are deliberate; passing mocks is
not Windows qualification.

## Later actual-export diagnostics (2026-10-02)

The Python manifest-only producer limitation recorded above is partially superseded by
[actual-export measurement diagnostics](vico-n2-render-metrics-validation.md). The new CLI reads
and validates real render_receipt.v1 PCM/tap files and reports measured diagnostics. Its
render_metrics.v1 output is not acceptance evidence; the unchanged reference_result.v2 schema,
reservation, budget, source/reference bindings and remaining trusted-producer requirements
still apply. No candidate objective evaluation or budget reservation occurred in that stage.
