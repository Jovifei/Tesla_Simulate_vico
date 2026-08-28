# Task 6B: Atomic PersistentEventDomainEngine restore

## Scope

Only persistent engine/component restore validation and focused tests were
changed. No metadata, evidence, receipts, Vault, Track-P, push, merge, PR, or
full S12 artifacts were touched.

## RED

Command:

```text
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_persistent_engine.py -q --disable-warnings
```

Result: `6 failed, 13 passed, 1 skipped`.

The failures reproduced partial mutation after late component corruption,
accepted unexpected/missing active component state, and accepted bool,
fractional, and negative delay-line sample counters.

## GREEN

Command:

```text
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_persistent_engine.py -q --disable-warnings
```

Result: `23 passed, 1 skipped`.

Specified restore/component regression command:

```text
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_persistent_engine.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_boundary_adapter.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_waveguide.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_afterfire_localization.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_final_remediation.py -q --disable-warnings
```

Result: `116 passed, 1 skipped`.

Compile check:

```text
python -m compileall -q tools/sound_sim/s12/acoustic_identity_v015/stage_w
```

Result: pass.

## Implemented guarantees

- Complete top-level snapshot, scalar, array, mapping, counter, queue, and
  topology validation runs before any live engine field is changed.
- Active PTR, waveguide, and teacher component snapshots are required;
  unexpected inactive component state is rejected.
- Delay lines reject bool, fractional, negative, malformed, nonfinite, and
  topology-mismatched counters/history without mutation.
- Pending afterfire queues enforce event shape, finite values, capacity, and
  sorted `(scheduled_sample, sequence)` order.
- Valid snapshots preserve replay-equivalent state, including RNG and all
  active component histories.

## Review

Commit: `fix(s12): make engine restore atomic`

Status: ready for parent-agent review. No provider/device/release or formal
qualification claim is made.

## Review addendum correction

Prior implementation commit reviewed and rejected: `14170ac`.

RED during correction: the affected restore suites exposed route-validation
failures and then the focused malformed-payload tests exposed an incorrect
test fixture that treated scheduled sample zero as invalid at engine counter
zero. The fixture was corrected to use a schedule before the engine counter.

GREEN after correction:

```text
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_persistent_engine.py -q --disable-warnings
38 passed, 1 skipped

python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_persistent_engine.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_boundary_adapter.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_waveguide.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_afterfire_localization.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_final_remediation.py -q --disable-warnings
135 passed, 1 skipped
```

The correction rejects noncanonical afterfire aliases, malformed or missing
route fields, invalid path/bank relationships, stale schedules, nonpositive
or duplicate queue sequences, unsorted queues, invalid arrival ordering, and
non-numeric fractional-delay histories without mutating live state.

New correction implementation commit SHA: `ead8553`.

## Review addendum 2 closure

The required afterfire-route fields `scheduled_sample_exact`, `energy`, and
`pressure_energy_factor` now reject missing and null values with controlled
`ValueError` before comparisons or state application. Six atomic tests cover
both forms for all three fields.

Focused result: `48 passed, 1 skipped`.

Affecting restore suites result: `141 passed, 1 skipped`.

Full commit SHAs:

- Prior Task6B implementation: `14170ac89153056f64bb4c48236e62eff2cc896b`
- First review correction: `ead8553accddd82b499a85a7e24e9ade3ecd627e`
- Report closure: `6bc1b1298ca38420ff632d161fdc51581acaf6a0`
- Null-field source/test correction: `7ef04cabf1c20a05432fb3f03c4f1af31223c266`
