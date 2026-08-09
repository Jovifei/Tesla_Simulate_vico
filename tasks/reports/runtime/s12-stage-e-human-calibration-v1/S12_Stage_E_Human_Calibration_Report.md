# S12 Stage E Human Calibration Report

## Status

`WAITING_FOR_JOVI_AUDITION`

This is a synthetic, uncalibrated candidate package. It is not an OEM reproduction and is not an Approved Profile.

## Evidence freeze

- Stage E branch: `agent/s12-stage-e-human-calibration`
- Stage E current commit: `2b58bf5` (full `2b58bf5` in Git; local-only)
- Stage E base: `4e363c66b92e51848a35700650ee1464925c479a`
- Stage C reference baseline: `a5d048145c29b20d687376c0b73226bc4a2435c7`
- Stage D local/remote relation: local `4e363c6` is eight commits ahead of remote `a5d0481`; it is not remote-synchronized.
- No Jovi response CSV, playback context, or confusion matrix existed at package creation.
- Git-external Listener ZIP SHA-256: `c85ec7c0fd5fa3c81e6bc674fe4a1ff123fe3b0140e8376ccc9dd451e914b954`; Answer Key ZIP SHA-256: `4dd8ae5398cd7c09ec1ed29d8389a322da523927fa43fe4fa4c903feba1d2806`.

## Corrected candidate path

`source with overrides -> idle overrides -> deterministic afterfire -> LF body -> rumble -> shift -> named transient peak shaping -> common Pre-PTR EQ -> frozen PTR -> fixed whole-cycle gain -> PCM24`.

Stage E v2 profiles are actual rendering inputs. Ferrari bank timing/metallic decay, Hellcat blower boost envelope, RX-7 rotary phase and turbo time constants, and idle parameters are recorded in diagnostics as `candidate_parameter_usage`. Stage D v1 JSON and package bytes remain historical and untouched.

The Hellcat transient shaper handles only named short stems (`shift_impact`, `shift_recovery_boom`, `afterfire`, and optional `blower_attack`); steady `blower` and `rumble` are not compressed.

## Automated evidence

The initial Stage E focused contract suite passed (`11 passed`) before package generation. Stage C/identity/Track-P focused commands were rerun after source compatibility changes; final counts are recorded in `stage_e_test_evidence.json` rather than copied from historical reports. Human identity and realism gates are intentionally not claimed here.

## Human gate

The v2 package contains two anonymous rounds of 15 trials (idle, cruise, acceleration, shift, lift) with a separate sealed answer key. The listener package records playback context and uses attenuation-only scene matching. Scoring is blocked until all 30 rows and playback context are supplied. Round recall denominators are five per vehicle; combined denominator is ten.

## Restrictions

No FVM, PTR core, Radiation Boundary, Runtime, Android, MATLAB, Simulink, Track-P guard, Stage-C shared LF/rumble/EQ, or formal loudness-manager policy was changed. No push, merge, rebase, or main integration was performed.
