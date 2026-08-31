---
title: Stage Y Source-Layer Status
project: Tesla-Speed-Sound
subproject: S12
stage: Stage-Y
document_type: engineering_status
status: final_map_pass_full_s12_pending_r1_human_pending
updated: 2026-08-31
evidence_head: f498c99352ad559897b6157d6722d64e05e68a32
---

<!-- S12-STAGE-Y:AUTO:BEGIN -->
# Stage Y current status

Repository final closure report: [Stage Y final software closure](../../../../../docs/08-reports/07-s12-stage-y-final-closure.md). The earlier WIP checkpoint remains historical; its failed-map state is superseded by the fresh final fitted-map receipt.

Y1–Y6 retain their bounded software evidence. The fresh final P3/post_ptr
selected-16 receipt now proves the committed fitted map bilaterally; the
bounded local coupling is recorded in the engine diagnostics. Current state is
`Y9_FINAL_QUALIFICATION / IN_PROGRESS / FULL_S12_PENDING`; the earlier whole-S12
receipt (`1369 passed, 2 skipped`, exit `0`, tested HEAD `a73322b`) is historical
and superseded by the canonical fixture-hash repair. One complete S12 run is
required on the canonical code HEAD. The first canonical attempt at `65b3374`
had `1368 passed, 2 skipped`, exit `1`, only because Track-P rejected CRLF in
the new v2 receipt; the failed receipt is retained as historical.
All evidence below is synthetic, uncalibrated, vehicle-inspired and
not an OEM reproduction. It does not establish an approved Profile, human
acceptance, calibration, ESP32/Runtime integration or product release.

## Signal chain and implementation boundary

The current offline path is a persistent 20 ms state-frame renderer:

`rpm/load/throttle/acceleration_mps2`
→ `CrankPhasePLL` + event scheduler/chamber/path
→ optional `waveguide_v1` and `harmonic_v1`/fitted `timbre_map_v1`
→ optional `fixture_v1` cycle resynthesis
→ optional `state_v1` transient mixer
→ optional `dp_v1` pressure chain
→ optional frozen `FrozenPtrStereo`
→ published stereo PCM24 and the separate stateful audition monitor.

The orchestration and evidence path is [`PersistentEventDomainEngine`](../../../../../tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py),
with Stage-Y modules in [`stage_y/`](../../../../../tools/sound_sim/s12/acoustic_identity_v015/stage_y/).
`process_with_trace` keeps block-rate phase/event/path/monitor traces; this is
an offline Python source-domain path, not the ESP32 Runtime implementation.

## Layer contracts

| Layer | Current implementation and boundary |
| --- | --- |
| Parent | Legacy synthetic Hellcat source → frozen PTR adapter; baseline only. |
| Y1 event | Persistent event-domain engine with state-driven event/chamber/path processing. The 16-control probe proves data-flow movement, not perception. |
| Y2 map | [`harmonic_map_fit.py`](../../../../../tools/sound_sim/s12/acoustic_identity_v015/stage_y/harmonic_map_fit.py) loads a committed synthetic fixture map fail-closed; it is `FIXTURE_ONLY`, `NOT_TUNING_AUTHORITY`, `NOT_OEM`. |
| Y3 P4 | [`cycle_sync_resynth.py`](../../../../../tools/sound_sim/s12/acoustic_identity_v015/stage_y/cycle_sync_resynth.py) addresses a four-stroke fixture over a 720° crank clock (`4π`); `2π` is the second revolution, not a cycle reset. |
| Y4 transient | [`state_transients.py`](../../../../../tools/sound_sim/s12/acoustic_identity_v015/stage_y/state_transients.py) keeps tip-in/lift/shift/BOV latches, re-arm state and block-continuous tails. The transient tail capacity is 120 ms; mixer snapshots are `s12.stage_y.state_transients.v1`. |
| Y5 dP | [`audio_chain_dp.py`](../../../../../tools/sound_sim/s12/acoustic_identity_v015/stage_y/audio_chain_dp.py) performs per-sample stereo DC removal, dP predecessor state and persistent fractional delay. It is opt-in as `audio_chain="dp_v1"` and runs before frozen PTR. |
| Monitor | The package monitor is derived from the Y5 render through `PersistentEventDomainEngine.monitor_pcm`; its bounded attack/release/makeup policy is for audition only and is not raw dynamic evidence. |

### Y1 bilateral parameter probe versus human hearing

The canonical artifact [`parameter_reachability.json`](../../../../../tasks/reports/runtime/s12-stage-y/y1_reachability/final_fitted_map_canonical/parameter_reachability.json)
records 16/16 `PARAMETER_REACHABLE` controls. Each declared probe renders
baseline, minus and plus values on its declared architecture/scene/stem; both
directions must be finite, change selected-stem PCM bytes, move a target metric
by more than the existing `0.02` tolerance, and stay within guard bounds. The
selected controls are `crank_inertia`, `idle_governor`,
`primary_attenuation_spread`, `blower_sideband_mix`, `blower_broadband_mix`,
`blower_casing_mix`, `boost_attack`, `boost_release`, `bypass_threshold`,
`afterfire_reservoir_rate`, `afterfire_ignition_delay`,
`afterfire_location_mix`, `afterfire_energy`, `monitor_attack`,
`monitor_release` and `monitor_max_makeup`.

For the fitted-map path only, the local source-layer balance is broadband
coupling `4.0` and forced-layer coupling `2.0`; the legacy formula-map path
remains `0.28` and `1.0`. Boost attack/release gates use scale-invariant
high-band share in their declared transition windows, with short windows
zero-padded to the comparator's 23-frame roughness-trend kernel.

This is bilateral software reachability evidence only. It does not measure
human identification, confusion rates or listening preference, and cannot
create a Human PASS.

### Normalized coefficients and the 720° clock

The fitted map stores one-sided Fourier amplitudes: non-DC/non-Nyquist bins
use `2/N`, while DC and Nyquist use `1/N`. The fixture cycle bank is derived
from the Hellcat firing schedule and spans one four-stroke 720° cycle. The P4
resampler maps absolute PLL phase through `4π`, preserving the second crank
revolution rather than silently repeating after 360°.

### Snapshot and pressure-state compatibility

`StateTransientMixer` persists latches, last state, event totals, stem energy,
crossfade activity and audio/mix tails. The persistent engine emits
`s12.stage_w.persistent_engine_state.v4`, validates runtime-model identity and
all path/filter/PLL/tail state atomically, and embeds the active transient and
pressure-chain states. Legacy zero-state v1 snapshots are migrated from fresh
state only; pre-Y5 v2 is accepted only for chain-off targets, while an active
chain requires its complete state. Dirty nonzero legacy state is rejected.

The Y5 chain uses a configured-rate one-time warmup of `max(0.1 * sample_rate,
1)` samples (discarded and not counted as caller audio), per-sample DC state,
the previous sample for dP, and linear fractional delay over persistent stereo
history. The fixed dry/delayed mix is `0.65/0.35`; dP contribution is `0.35`.

## Cumulative package and review domains

[`stage_y/package.py`](../../../../../tools/sound_sim/s12/acoustic_identity_v015/stage_y/package.py)
publishes seven cumulative stems in this order: `parent`, `y1_event`,
`y2_map`, `y3_p4`, `y4_transients`, `y5_dp`, `monitor`. Each non-monitor stem
adds the named layer to the preceding topology; the monitor reuses Y5 output
and applies the bounded monitor policy. `OUTPUT_SCALE` is applied exactly once
after source/PTR/monitor work, with no per-scene dynamic normalization.

The Dynamic Review A–F files are unaltered published PCM24 stems and retain
relative idle→WOT/transient dynamics. The G/Monitor file is
`policy_processed_audition_monitor`, not raw dynamic. Timbre Review uses
separate shared-RMS matched derivatives only for relative timbre comparison;
the match is not LUFS, SPL, calibration or dynamic evidence. Parent-vs-final
15% values are diagnostics, not a similarity score or qualification gate.

## Verified phase receipts

| Phase | Verified scope | Exact proof |
| --- | --- | --- |
| Y1 | Current canonical committed fitted-map 16/16 bilateral probes; source/test head `f498c99352ad559897b6157d6722d64e05e68a32`; artifact SHA `3609D1DDA341C271A0A983FE5E66C1C868746B336CDEA151DC50DA97DC36B1DF`; map SHA `59690572E189D2CA4A5005EA0297C75622DCA244112AC3747635D9FB16AC9519`; fixture SHA `060F511881CD2D5994AFAC7678222BCA95F9239620884BF342BB8C054D4C06D1`. | [`current final fitted-map receipt`](../../../../../tasks/reports/runtime/s12-stage-y/final_qualification/y1_final_fitted_map_reachability_receipt_v2.json) and [`current artifact`](../../../../../tasks/reports/runtime/s12-stage-y/y1_reachability/final_fitted_map_canonical/parameter_reachability.json) |
| Y2 | Fitted synthetic map load/contract; map-build source head `293dcb23768d67f54c5c2bd783aa650e6328ebda`; current map SHA `59690572E189D2CA4A5005EA0297C75622DCA244112AC3747635D9FB16AC9519`; fixture SHA `060F511881CD2D5994AFAC7678222BCA95F9239620884BF342BB8C054D4C06D1`; focused result `12 passed`. | [`y2_harmonic_map_receipt.json`](../../../../../tasks/reports/runtime/s12-stage-y/y2_harmonic_map/y2_harmonic_map_receipt.json) and current [`final fitted-map receipt`](../../../../../tasks/reports/runtime/s12-stage-y/final_qualification/y1_final_fitted_map_reachability_receipt_v2.json) |
| Y3 | Normalized-map integration `66 passed`; final P4 720°/persistent 20 ms postfix `5 passed in 5.09s`; source head `c4b06e6897f449b05f6e30a2f29f72dc0624475e`. | [`y3_normalized_revalidation_receipt.json`](../../../../../tasks/reports/runtime/s12-stage-y/y3_cycle_sync_p4/y3_normalized_revalidation_receipt.json) and [`y3-postfix execution receipt`](../../../../../tasks/reports/runtime/s12-stage-y/y3_cycle_sync_p4/logs/y3-postfix-20260831T043010185968Z.json) |
| Y4 | Latch/re-arm, 120 ms tails, snapshot/replay and focused regressions; final result `80 passed, 1 skipped`; source head `fc92a68a147d5fb40b3d5444773d116f59fb3b1e`. | [`y4_transients_receipt.json`](../../../../../tasks/reports/runtime/s12-stage-y/y4_transients/y4_transients_receipt.json) |
| Y5 | Per-sample DC/dP, warmup, fractional delay, v3 snapshot compatibility, click contract and deterministic 3000×960 equivalence; `43 passed in 28.92s`, no skip; source head `1f3a9cba27fe2ca212ce7f488ebdd5f11b5c83bc`. | [`y5_dp_chain_receipt.json`](../../../../../tasks/reports/runtime/s12-stage-y/y5_dp_chain/y5_dp_chain_receipt.json) |
| Y6 | Production package `11` scenes/`154` synthetic 48 kHz stereo PCM24 WAVs; manifest SHA `9376d90c57e4efad7dc1e9b8ce15e09f1ed2c124f23a753d389039664506826c`; browser pages each loaded `77` players and sampled playback; source head `091696936abc8ec310f2f937579bc136cf21bc0e`. | [`y6_audition_receipt.json`](../../../../../tasks/reports/runtime/s12-stage-y/y6_audition/y6_audition_receipt.json), [`browser_playback_receipt.json`](../../../../../tasks/reports/runtime/s12-stage-y/y6_audition/browser_playback_receipt.json) |

The phase ledger is [`execution_state.json`](../../../../../tasks/reports/runtime/s12-stage-y/execution_state.json). The historical full-run receipt is [`full_s12_final_receipt.json`](../../../../../tasks/reports/runtime/s12-stage-y/final_qualification/full_s12_final_receipt.json); the failed canonical attempt is [`full_s12_final_receipt_v2_failed_track_p.json`](../../../../../tasks/reports/runtime/s12-stage-y/final_qualification/full_s12_final_receipt_v2_failed_track_p.json); the next current receipt is expected at `full_s12_final_receipt_v2.json` after the authorized rerun.
Y6 is `PASS` for package/browser evidence, while its receipt still records
`human_status=WAITING_FOR_JOVI_LAYER_AUDITION`,
`formal_status=FORMAL_R1_REFERENCE_MISSING`,
`profile_status=NOT_PROFILE_FREEZE_READY`, and the old
`full_s12_status=PASS` receipt is historical; because fitted-map renderer inputs changed,
future regenerated audio must be published as v2 and must not overwrite v1.

## Remaining gates

The parent must run one complete S12 qualification on the canonical metadata/code
HEAD before claiming whole-branch software closure or proposing main merge. After that, human layer audition, a legal
RPM/state-synchronised R1 Reference, the R1 formal gate, Profile Freeze and
explicit approval remain separate gates. No receipt in this note authorizes
OEM reproduction, calibrated output, product Runtime integration, or hardware
acceptance.
<!-- S12-STAGE-Y:AUTO:END -->
