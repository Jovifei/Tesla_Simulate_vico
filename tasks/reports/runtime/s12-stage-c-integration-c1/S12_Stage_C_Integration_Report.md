# S12 Stage C Deep Realism Integration C1

## Decision status

`AUTOMATED_REALISM_CANDIDATE / HUMAN_AUDITION_PENDING`.

This report is a synthetic engineering candidate. It is uncalibrated and is not an OEM reproduction. Automatic metrics do not replace Jovi's blind audition.

## Scope and provenance

- Base: `c08eb4c0d557c32e0896bef9be4f4eddf5d296ea`.
- Working branch: `agent/s12-stage-c-realism-integration`.
- Pre-evidence implementation commit: `adddb75` (the documentation commit will be the final branch tip).
- Current evidence commit: `HEAD` at report publication; verify with `git rev-parse HEAD` on this branch.
- Eight vehicle profile fields and Stage C parameters are `C/synthetic`; the existing R2 video records are listening context only.
- No FVM, PTR core, Radiation Boundary, Runtime, Android, MATLAB, Simulink, loudness-manager contract, health gate, guard baseline, or allowlist was changed.

## Integrated chain

```text
independent source
→ idle dynamics
→ deterministic state-dependent afterfire
→ low-frequency pressure/body
→ pressure-coupled exhaust rumble
→ RPM-step shift dynamics
→ causal pre-PTR equalization
→ frozen PTR
→ edge fade
→ one fixed whole-cycle gain
→ PCM24
```

The new layers return `SourceRender`, preserve named stereo stems, and record diagnostics. The equalizer applies the same causal transform to pressure and every stem. Shift recovery uses seconds (`np.arange()/sample_rate_hz`), not a normalised 0–1 vector.

## Vehicle registry

The shared frozen profile registry contains exactly eight IDs: Ferrari 458, Hellcat, RX-7 FD, LFA, Aventador LP700, C63 W204, GT-R R35, and Supra JZA80. Tests assert that formal renderers, idle profiles, low-frequency profiles, drive-cycle profiles, and the reference manifest have the same eight-key set. Every profile is marked `C/synthetic`.

## Corrections from the prototype

- Corrected 26/6 false shift counts to three local RPM drop/recovery events in the formal 30/60 second cycle.
- Removed the second afterfire implementation; the formal afterfire model is deterministic, thermal/history gated, and architecture-specific (RX-7 does not use piston firing order).
- Removed hash-seed dependence and fixed sparse-trace interpolation at each audio layer.
- Fixed the 70 Hz recovery boom to use real seconds.
- Added finite/PCM24/stereo/length/zero-excitation checks and vehicle-specific identity metrics for all eight vehicles.

## Evidence

- Stage C integration: 9 passed.
- Existing realism suite: 9 passed.
- Existing identity suite: 58 passed, 78 subtests passed.
- Deep-realism/Track-P selected suite: 61 passed, 118 subtests passed.
- Full `tools/sound_sim/s12/tests` plus `acoustic_identity_v015/tests`: 415 passed, 232 subtests passed.
- Track-P guard: 21/21 passed; no frozen path or symbol changed.
- Remaining-vehicle verifier: executes successfully; historical reference acceptance is intentionally `PARTIAL` because five R2 records are pending/un-calibrated. This is not promoted to a realism PASS.

Three-anchor before/after measurements are in `stage_c_before_after_metrics.json`. Full machine-readable evidence is in `stage_c_test_evidence.json`.

## Audition package

The Git-external package is `E:\Tesla_speed\review_packages\s12-stage-c-integration-c1\S12_Stage_C_Integration_A_B.zip`.

- `before/`: main baseline three-anchor 60-second continuous cycles.
- `after/`: Stage C three-anchor 60-second continuous cycles.
- `eight_vehicle_30s/`: all eight formal vehicles at the compatible 30-second cycle.
- `S12_Stage_C_Audition_Guide.md`: blind-listening timeline and rubric.

The Hellcat after cycle is peak/headroom limited and measures 1.359 LU below its old baseline package; it is explicitly retained as an audition/calibration item rather than hidden by a gain or threshold change.

## Limitations and next gate

All numerical targets remain C-level synthetic directions. Human review is required for Ferrari metallic scream, Hellcat low-frequency/blower identity, and RX-7 rotary/turbo identity. Stop at C1; only Jovi's audition can authorise C3 deep listening calibration.
