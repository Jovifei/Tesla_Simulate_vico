# S12 Stage B — Unified Acceptance Report (8 Vehicles)

**Scope:** §4.2 coarse metric gates only. Human audition and deep realism are **NOT qualified** in this stage (see Stage C–E plan).

**Generated:** 2026-08-06 | **Commit:** 6e7484b (feat(s12): Stage A coarse tuning — §4.2 gates + GT-R/ferrari/rx7 idle fixes)

## §4.2 Acceptance Criteria

- **Acceleration:** absolute per-band power-share error ≤ 0.05 (all four bands 20–250 / 250–1k / 1k–4k / 4k–12k Hz).
- **Idle centroid:** absolute error ≤ max(25 Hz, target × 10%).
- **Improvement:** ≥ 30% distance reduction vs pre-tuning baseline (informational gate).

## Summary Table

| Vehicle | Idle err (Hz) | Idle gate (Hz) | Idle PASS | Max accel err | Accel gate | Accel PASS | Accel impr% | Idle impr% |
|---|---|---|---|---|---|---|---|---|
| aventador_lp700 | 3.60 | 64.8 | ✅ | 0.0234 | 0.05 | ✅ | 36.9% | 99.2% |
| c63_w204 | 4.70 | 68.7 | ✅ | 0.0182 | 0.05 | ✅ | 87.4% | 95.8% |
| gtr_r35 | 32.30 | 40.0 | ✅ | 0.0268 | 0.05 | ✅ | 87.3% | 89.5% |
| lfa | 0.10 | 136.6 | ✅ | 0.0255 | 0.05 | ✅ | 0.0% | 100.0% |
| supra_jza80 | 1.20 | 25.0 | ✅ | 0.0387 | 0.05 | ✅ | 88.0% | 98.1% |
| ferrari_458 | 30.50 | 98.0 | ✅ | 0.0213 | 0.05 | ✅ | 95.3% | 96.4% |
| hellcat | 26.60 | 29.0 | ✅ | 0.0103 | 0.05 | ✅ | 95.2% | 82.8% |
| rx7_fd | 22.40 | 25.0 | ✅ | 0.0040 | 0.05 | ✅ | 98.5% | 97.7% |

**Coarse gate result: idle PASS = True (8/8), accel PASS = True (8/8).**

## Production Publisher (3 anchors)

`publish_identity_v02` over ferrari_458 / hellcat / rx7_fd across idle/cruise/acceleration/lift/full_pull (frozen PTR + single bundle gain + `_health` + loudness + one-fixed-gain + same-state identity comparison):

| Anchor | health_all | loudness_ok | one_gain | gain_db | comparison |
|---|---|---|---|---|---|
| ferrari_458 | True | True | True | -7.32 | passes |
| hellcat | True | True | True | 3.62 | passes |
| rx7_fd | True | True | True | 3.30 | passes |

**Publisher result: PUBLISH OK (all anchors green).**

## Per-Vehicle Parameter Diff & Limitations

### aventador_lp700

- **Parameter diff (Track S):** Sub-agent coarse tuning (prior session). Naturally-aspirated V12 with cylinder-bank order content; idle filler + valve dynamics retained.
- **Limitations:** Human audition pending. Deep realism not qualified (Stage C-E).

### c63_w204

- **Parameter diff (Track S):** Sub-agent coarse tuning (prior session). M156 NA V8 cross-plane with uneven firing; accel band balance retained.
- **Limitations:** Human audition pending. Deep realism not qualified (Stage C-E).

### gtr_r35

- **Parameter diff (Track S):** THIS SESSION: idle_mid filler raised to 540/700/900 Hz (gain 0.100); idle_gate = clip((1850-rpm)/850, 0, 1) so accel is untouched. idle_dynamics.py valve_hz 200->440 (prior session, shared file).
- **Limitations:** Idle centroid 291->432.2 Hz (dist 108.9->32.3, gate 40) PASS. No new pytest failures introduced. Human audition pending.

### lfa

- **Parameter diff (Track S):** Sub-agent coarse tuning (prior session). High-revving V10 with deliberately high idle centroid; band shares retained.
- **Limitations:** Idle centroid err 0.1 Hz (essentially exact). Human audition pending. Deep realism not qualified (Stage C-E).

### supra_jza80

- **Parameter diff (Track S):** Sub-agent coarse tuning (prior session). 2JZ inline-6 turbo with smooth order content; accel band balance retained.
- **Limitations:** Human audition pending. Deep realism not qualified (Stage C-E).

### ferrari_458

- **Parameter diff (Track S):** THIS SESSION: gated cruise filler 760/1080 Hz (gain 0.40) fixes cruise loudness regression (-30.6->-27.8 LUFS); engine-order-coupled idle filler (phase*54.5 / phase*79.0, rpm>0 gated) fixes zero-rpm silence and trace-time-origin invariance.
- **Limitations:** Known pre-existing pytest backlogs (NOT introduced this session): test_ferrari_rms_stays_bounded_from_idle_to_redline, test_ferrari_high_frequency_energy_grows_with_rpm, +2 LUFS/RMS integration subtests. Publisher anchor: PUBLISH OK. Human audition pending. Deep realism not qualified (Stage C-E).

### hellcat

- **Parameter diff (Track S):** Sub-agent coarse tuning (prior session). Supercharged Hemi with blower shaft lobe + upper families; accel band balance retained.
- **Limitations:** Known pre-existing pytest backlog (NOT introduced this session): test_hellcat_blower_has_shaft_lobe_and_upper_families_with_audible_stem_balance +1 LUFS integration subtest. Publisher anchor: PUBLISH OK. Human audition pending. Deep realism not qualified (Stage C-E).

### rx7_fd

- **Parameter diff (Track S):** THIS SESSION: gated high-mid idle filler (phase*57.4 / phase*62.0, gain 0.30, rpm>0 gated, idle_loud_gate=clip((1800-rpm)/900,0,1)) fixes POST-PTR idle loudness (-34.6->-28.96 LUFS) within §4.2 idle err<=25 Hz.
- **Limitations:** Known pre-existing pytest backlogs (NOT introduced this session): test_rx7_housing_resonance_is_event_and_engine_phase_coupled, test_rx7_uses_phase_offset_rotary_events_and_stateful_turbo_lift, test_rx7_acceleration_stem_balance_keeps_turbo_and_turbine_audible (rpm 2800-6800, unaffected by idle filler), test_rx_constant_state_full_pressure_qualifies_order_shape_and_stem_balance +2 LUFS/RMS integration subtests. Publisher anchor: PUBLISH OK. Human audition pending. Deep realism not qualified (Stage C-E).

## Known Backlogs (deferred to Stage B/C)

12 pytest failures in `test_s12_engine_acoustic_identity_v015.py` are **pre-existing sub-agent regressions, NOT introduced this session** (verified: zeroing the ferrari cruise filler still failed; rx7 accel test uses rpm 2800–6800 where the idle filler is gated off). They trade off finer-grained physical/stem-balance assertions against the coarse §4.2 tuning and belong to Stage B/C Deep Realism work:

- ferrari_458 ×2: `rms_stays_bounded_from_idle_to_redline`, `high_frequency_energy_grows_with_rpm`
- hellcat ×1: `blower_has_shaft_lobe_and_upper_families_with_audible_stem_balance`
- rx7_fd ×4: `housing_resonance_is_event_and_engine_phase_coupled`, `uses_phase_offset_rotary_events_and_stateful_turbo_lift`, `acceleration_stem_balance_keeps_turbo_and_turbine_audible`, `rx_constant_state_full_pressure_qualifies_order_shape_and_stem_balance`
- LUFS-RMS integration subtests ×5 (in `test_same_load_rpm_probes_change_timbre_without_gross_level_spread`): ferrari_458 (LUFS,RMS), hellcat (LUFS), rx7_fd (LUFS,RMS)

## Freeze-Boundary Compliance

All changes confined to **Track S** (sources/idle_dynamics/loudness/afterfire + verification scripts). No edits to radiation package, PTR core, FVM, runtime, MATLAB, `render_identity_v02._health`, or `manage_bundle_loudness` signature. `git diff --check` clean (exit 0).

## Status & Next Steps

- ✅ Stage A complete: 8-car §4.2 coarse gates PASS; 3 anchors PUBLISH OK.
- ⏸️ Local commit `6e7484b` created; **NOT pushed** (pending Jovi authorization).
- 🔜 Stage C–E: Deep Realism for ferrari/hellcat/rx7 (idle/steady/accel/full pull/lift-afterfire/idle return); human blind-listening gate (confusion matrix); product convergence (AudioParameterPackage only after 3 anchors pass).
