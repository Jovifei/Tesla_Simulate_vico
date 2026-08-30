# Y1-B afterfire reachability report

Status: `DONE_WITH_CONCERNS`

Implementation commit: `a89573c32a12f8e9731e0f8fb0c79fd99332995a`

## Scope and root cause

Only Y1-B afterfire source/test files changed. No receipt or Stage Y state file
was written, and no push, merge, or PR was made. The probe remains synthetic,
uncalibrated, vehicle-inspired, and not an OEM reproduction.

`afterfire_reservoir_rate` previously charged `_afterfire_fuel_reservoir` and
used the state only for the `>= 0.2` eligibility condition. Scheduled event
energy then used only `afterfire.gain`, load, and collector pressure. The RED
behavior test rendered eligible lifts at rate `0.52` and `0.92` and observed
identical scheduled energy: `0.048148997864733` in both cases.

`PersistentEventDomainEngine._reservoir_to_energy` now maps actual accumulated
reservoir state through `0.25 + 0.75 * reservoir / (reservoir + 4.0)`. It runs
only after the unchanged eligibility decision when a packet is scheduled; rate
remains a state charge rate rather than a direct master gain. Ineligible events
remain zero.

## Residual probe

The four afterfire controls now declare `afterfire_residual` probe mode. For
each actual P3/post-PTR render, the probe renders an otherwise identical control
with only `afterfire.gain=0`, then computes metrics on actual minus control. SHA
acceptance still compares actual selected post-PTR PCM. The residual analysis is
event-local: a declared 40%-of-scene lift reference plus a 55 ms packet window.

- reservoir rate: residual energy envelope;
- ignition delay: residual onset and peak offsets;
- location: residual stereo path balance and peak arrival offset;
- energy: residual energy envelope and residual crest.

The original location encoding mapped baseline and low to the same `primary`
route, so it could never satisfy bilateral SHA. The probe now keeps default
baseline `primary`, uses `central_collector` for low, and `bank_collector` for
high; every route is an existing runtime route.

## RED and GREEN evidence

RED command:

```powershell
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py::test_afterfire_reservoir_state_fraction_modulates_scheduled_energy -vv --tb=short
```

Result before implementation: `1 failed in 6.86s`.

GREEN command:

```powershell
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py::test_afterfire_reservoir_state_fraction_modulates_scheduled_energy -q
```

Result: `1 passed in 7.57s`.

After correcting a residual-window return-value defect found by the delay probe,
the one-control directional evidence was:

| Control | Minus target movement | Plus target movement | Actual post-PTR SHA |
| --- | ---: | ---: | --- |
| `afterfire_reservoir_rate` | 0.03349256008613694 | 0.02040856036511632 | changed / changed |
| `afterfire_ignition_delay` | 0.12141652613827991 | 0.12141652613828005 | changed / changed |
| `afterfire_location_mix` | 1.000000000000046 | 0.10798122065727696 | changed / changed |
| `afterfire_energy` | 0.3333333333333196 | 0.33333333333345155 | changed / changed |

All PCM directions were finite and every target movement is strictly greater
than the unchanged `0.02` gate. Ignition onset/peak movements were
`0.12141652613827991/0.11267605633802814` for minus and
`0.12141652613828005/0.11267605633802814` for plus. Location low changed both
balance (`1.000000000000046`) and arrival (`0.0798122065727699`); location high
changed arrival (`0.10798122065727696`) while its balance was effectively
unchanged. Energy passes through residual envelope; crest is scale-invariant.

## Verification

Four-control targeted command:

```powershell
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py::test_afterfire_reservoir_state_fraction_modulates_scheduled_energy tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py::test_afterfire_ineligible_stays_zero tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py::test_y1_afterfire_controls_are_bilateral_event_local_residual_probes -q
```

Result: `3 passed in 77.10s`.

Relevant Stage W command:

```powershell
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_afterfire_localization.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_persistent_engine.py::test_snapshot_restore_replays_exact_audio_and_reset_starts_new_state tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_persistent_engine.py::test_restore_round_trip_preserves_canonical_afterfire_queue tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_persistent_engine.py::test_afterfire_location_and_delay_change_path_output_and_sha -q
```

Result: `9 passed, 1 failed in 8.06s`.

The failure is the existing exact raw-PMC replay assertion in
`test_snapshot_restore_replays_exact_audio_and_reset_starts_new_state`. Its trace
has monotonically increasing throttle, so it never has `d_throttle < -0.8`; Y1-B
reservoir-to-energy is behind the unchanged `if not eligible: return` branch and
cannot execute. Expected/replayed max PCM difference was
`0.013295538051860456` over 170 samples, but recursive comparison of their
post-process `snapshot_state()` values found no difference. The canonical
afterfire queue snapshot round-trip passed for all three routes. Treat the exact
raw replay gap as a pre-existing Y4/Y5 state-chain blocker.

Additional checks completed with exit code 0:

```powershell
python -m compileall -q tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py tools/sound_sim/s12/acoustic_identity_v015/stage_x/search_parameters.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py
git diff --check
```

No selected-12, selected-16, or full S12 suite was run.

## Concerns

- The Stage W exact raw-PMC snapshot replay failure remains unresolved.
- Location high is proven by residual arrival, while low proves both balance and
  arrival.
- This closes only the four afterfire controls. It does not mark Y1 PASS, update
  receipt/state, select an architecture, or provide R1/OEM/human qualification.
