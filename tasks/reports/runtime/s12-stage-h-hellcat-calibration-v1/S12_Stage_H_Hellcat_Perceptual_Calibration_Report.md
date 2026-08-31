# S12 Stage H Hellcat Perceptual Calibration Report

Status: `WAITING_FOR_JOVI_NAMED_CALIBRATION`

This report records a named engineering audition candidate. It is not an
approval, an OEM reproduction, or a calibrated measurement.

## Baseline and boundary

- Base commit: `60bca7cccac91c520a12c0b058f3f70d56dcf4b8`
- Branch: `agent/s12-stage-h-hellcat-perceptual-calibration`
- Worktree: `E:\Tesla_speed\worktrees\s12-stage-h-hellcat-perceptual-calibration`
- Stage G sealed key: not read; anonymous P01/P02/P03 mapping was not inferred.
- Frozen: FVM, PTR core, Radiation Boundary, Runtime, Android, MATLAB,
  Simulink, Track-P guard, Stage C shared LF body/rumble/Pre-PTR EQ and
  loudness policy.
- Official hardware facts are not acoustic calibration. All tunable values are
  `C/synthetic/candidate_assumption`.

## Model change

Stage H replaces the Hellcat candidate blower aggregate before the shared
Pre-PTR boundary with named stems:

```text
blower_shaft + blower_lobe_family + blower_upper_family
  + blower_sidebands + blower_bypass_release = blower
```

The fixed architecture hypothesis is RPM -> 2.36:1 shaft phase -> 11.8/23.6
families -> four-events-per-revolution V8 sidebands -> load/throttle/boost
envelope -> boost-history bypass release -> synthetic intake/casing transfer.
It contains no white noise, random crackle, fixed-frequency tone or global-gain
blower substitute.
The final implementation also gates the envelope at zero load/zero throttle;
with no boost history the blower and bypass stems are exactly silent.

Final order remains:

```text
Independent Source -> Idle -> Afterfire -> LF Body -> Rumble -> Shift
-> Named Transient Peak Shaping -> Common Pre-PTR EQ -> Frozen PTR
-> Edge Fade -> One Fixed Whole-Cycle Gain -> PCM24
```

## Online evidence boundary

- Stellantis public material: twin-screw, 2.36:1 drive ratio, approximately
  14,600 rpm blower speed and electronic bypass path.
- DodgeGarage public driving context: qualitative combination of deep exhaust
  pressure and distinct blower whine.
- SAE NVH context: narrow-band order families and casing/intake transfer are
  reasonable modeling abstractions.

Links and limitations are stored in
`reference_database/Hellcat_Supercharger_Acoustic_Study_v1.md` and
`targets/hellcat_supercharger_target_v1.json`.

## Automated evidence

See the JSON artifacts in this directory:

- `stage_h_parameter_reachability.json`
- `stage_h_hellcat_metrics.json`
- `stage_h_reference_distance.json`
- `stage_h_test_evidence.json`
- `stage_h_artifact_manifest.json`

The 30% relative reference-distance requirement remains independent of named
listening. If it is not met, the automated status remains
`PARTIAL / AUTOMATED_GATE_FAIL` even when the candidate is useful for hearing.

Fresh final-PCM evidence for the named package:

| metric | Stage G | Stage H |
|---|---:|---:|
| integrated loudness | -19.0533 LUFS | -18.2679 LUFS |
| peak | -1.5000 dBFS | -1.5000 dBFS |
| clipping | 0 | 0 |
| blower/load correlation | -0.3022 | 0.9764 |
| shaft order error | n/a | 0.00621% |
| lobe order error | n/a | 0.00656% |
| sideband/main ratio | n/a | 0.0816 |
| bypass events | n/a | 2 |

The measured final-PCM reference-distance improvement is `8.479%` (idle
`12.198%`, acceleration `12.999%`, afterfire `0.239%`), below the fixed 30%
gate. Therefore the automatic qualification is
`PARTIAL / AUTOMATED_GATE_FAIL`; the package is for diagnosis and listening,
not Profile Freeze.

Fresh verification evidence:

- Stage H focused: `14 passed` in `71.04 s` (including zero-load/zero-throttle silence).
- Stage G focused: `12 passed` in `230.87 s`.
- Stage C realism/identity: `67 passed / 78 subtests` in `142.80 s`.
- Full S12 offline suite: `488 passed / 232 subtests` in `708.51 s`.
- Track-P pytest: `21 passed`; unchanged guard: `OK` (180 frozen files, 2
  frozen symbols, zero frozen-path changes).
- `git diff --check`: clean.

Package SHA-256:

- ZIP: `5a459753cc41bd1be046bd076cc524ad08f52eca08bd43dc80e9776d06320d3a`
- Stage G Hellcat WAV: `8fbf28f8136c661f59f85d0002d96af361a295413c26f19ed20116f9bc69bb47`
- Stage H Hellcat WAV: `6eacaad7ff2e0fb52734d130d597d43efb6573a5491d93b0f4a70e505232c486`

## Human gate

The named package is at:

`E:\Tesla_speed\review_packages\s12-stage-h-hellcat-perceptual-calibration-v1\`

Jovi must compare the Hellcat Stage G baseline and Stage H candidate, then
complete `04_Feedback/Jovi_Stage_H_Named_Feedback.csv`. The requested checks
are Hellcat likeness, whine presence/naturalness, low-frequency weight,
high-frequency harshness and artifact freedom. Only after named feedback may a
later anonymous Stage H package be built.

The feedback CSV is intentionally blank except for the named file rows. No
human score, confusion matrix, or vehicle mapping has been fabricated. The
Stage G sealed key remains unread.

## Claims

`synthetic / uncalibrated / Hellcat-inspired / not OEM reproduction`.
The correct next state is `WAITING_FOR_JOVI_NAMED_CALIBRATION`.
