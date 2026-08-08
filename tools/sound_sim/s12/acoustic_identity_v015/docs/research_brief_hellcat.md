# Research Brief — Dodge Challenger SRT Hellcat (`hellcat`) — S12 Acoustic Realism

**Scope boundary:** Synthetic, uncalibrated source. This brief covers only *public,
non-copyrighted engineering specifications and tonal descriptors* (B/C class). No
reference audio, waveforms, or proprietary recording content is reproduced here.
All acoustic values in `reference_database/hellcat_reference_targets.json` are
*derived relative metrics* (`B/R2`) and remain recording-dependent, not OEM
calibration.

---

## 1. Engine & forced induction (public specs)

| Attribute | Value | Source |
|---|---|---|
| Engine code | 6.2 L HEMI Hellcat (supercharged V8) | dodge.com/hellcat, motor1.com |
| Configuration | 90° cross-plane V8, OHV, 16-valve (2 per cyl) pushrod | motor1.com, motortrend.com |
| Displacement | 6,162 cc ("6.2 L") | dodge.com/hellcat |
| Bore × stroke | 103.9 mm × 90.9 mm | motor1.com |
| Supercharger | 2.4 L Lysholm-type twin-screw (Eaton TVS) with RPM-dependent step-up | dodge.com/hellcat, motortrend.com |
| Boost pressure | ~11.6 psi (0.80 bar) peak factory | motor1.com |
| Compression | 9.5 : 1 (lowered for forced induction) | motor1.com |
| Peak power | 707 hp @ 6,000 rpm | dodge.com/hellcat |
| Peak torque | 650 lb·ft @ 4,000 rpm | dodge.com/hellcat |
| Redline | ~6,200–6,400 rpm | motortrend.com |
| Induction | Supercharged; the TVS rotor spins at ~2.3–2.9× crankshaft speed | dodge.com/hellcat |

## 2. Firing order (cross-plane V8)

The Hellcat HEMI is a classic **cross-plane V8** with the irregular
(`1-8-4-3-6-5-7-2`) firing sequence — non-alternating banks producing uneven
exhaust-pulse spacing. The synthetic source mirrors this with
`bank_pattern=(0,1,0,1,1,0,1,0)` + `events_per_rev=4.0` (8 combustion events / 2 revs),
giving the lumpy cross-plane cadence rather than a flat-plane bark.

## 3. Idle behaviour

- Documented warm idle settles near **~650–850 rpm** with a low, chest-thumping
  cross-plane rumble; the supercharger adds a faint continuous whine even at idle.
- The synthetic scenario trace uses **820 rpm idle** (`render_realism_v10._scenario_trace`);
  this is a *scenario input*, not a claimed measured idle. No change made to the
  frozen scenario trace. Idle tuning is performed entirely via the source (the
  shared `idle_dynamics.py` Hellcat profile is NOT edited).

## 4. Supercharger (TVS) signature

- The 2.4 L TVS twin-screw is driven at ~2.36× crank speed; `shaft_ratio =
  2.36·(0.93 + 0.16·boost_state)` in the source reproduces the rotor-speed
  dependence. Its whine is a broadband, RPM/load/boost-driven order family
  (rotor fundamental ~30 Hz rising with boost; strong 5th/10th harmonics into the
  mid band) — distinct from turbine spool, present even at light throttle.
- Inlet restriction + rotor mesh give the characteristic "whine", while the heavy
  cast-iron-feel HEMI block and large displacement deliver the **heavy low-end
  body (40–200 Hz)** that the Hellcat is known for.

## 5. Tonal signature (1–2 sentences, descriptor only)

A massively heavy, supercharged cross-plane V8 with a deep 40–200 Hz body and a
continuous TVS blower whine, overlaid with mechanical weight (belt/valvetrain/
casing) — a thunderous, low-end-dominant muscle-car roar rather than a high-strung
shriek, yet with a clear mid-band attack from the forced-induction and firing
impulses.

## 6. Mapping to tuning knobs (`sources/supercharged_hemi_source.py`)

| Reference trait | Knob (file:line) | Setting direction (handover §5.7) |
|---|---|---|
| Heavy low-end body (40–200 Hz) | exhaust low-band fundamental + LFB `body_hz=51`/`exhaust_hz=74` (frozen) | preserve characteristic low; reduce exhaust fundamental weight so low share falls from 0.91→~0.48 |
| Mid-band attack (100–400 Hz) | exhaust higher harmonics (`ex_w_l/r` 5.4/7.2 & 6.9/9.2 orders) + `blower` mid family (`shaft_phase·5/10`) + `intake` (~250 Hz) | lifted to raise `accel_mid` 0.08→~0.49 |
| TVS blower inertia / load mapping | `boost_state` 1st-order lags (`boost_tau` 0.075/0.22), `load_boost_state`, `bypass_state`; `blower_gain` multiplier | strengthened mid-band blower energy under load |
| Mechanical weight (idle + accel) | `blower`/`mechanical`/`casing` gains; casing orders lowered into mid band (perceptual 100–400 Hz attack) | `casing` kept in mid (<1 kHz at redline) to avoid inflating the 1–4 kHz gate band |
| Idle mechanical weight → centroid 290 Hz | source `casing`/`intake`/`valvetrain` amplitude at idle (NOT `idle_dynamics.py`) | raised so idle spectral centroid climbs 136→~290 Hz |

> Note: the >5.5 kHz radiation model is frozen and unvalidated, so no energy is
> pushed past validated radiation. High-band compensation is exercised only via
> upstream (source-domain) excitation; the `idle_dynamics.py` Hellcat profile
> (`valve_hz=850`) is SHARED and is NOT edited — all idle correction is in-source.

## 7. Compliant reference provenance

- **Derived relative metrics (acceptance target):** `reference_database/hellcat_reference_targets.json`
  - Schema `s12.hellcat_reference_targets.v1`; provenance tag `B/R2 extracted from
    external recording; microphone/AGC/config dependent; not OEM calibration`.
  - `stock_median.acceleration_band_shares = [0.4837, 0.4879, 0.0030, 3.66e-5]`
  - `stock_median.idle_spectral_centroid_hz = 290.43`
- **Reference media (non-redistributable, local):** `local:tesla-sound-research/...`
  external recordings; SHA-256 / URL consolidated in the project
  `realism_reference_manifest.json`. No audio is embedded or reconstructed here.
- **Public spec sources (cited, not copied):** dodge.com/hellcat (official specs);
  motor1.com (Hellcat engine teardown/specs); motortrend.com (drive/induction notes).
- **Compliance:** No copyrighted audio, waveforms, or OEM calibration data are
  included. Only open engineering specs and a one-sentence tonal descriptor are used.
