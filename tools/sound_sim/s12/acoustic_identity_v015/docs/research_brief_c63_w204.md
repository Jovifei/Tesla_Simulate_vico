# Research Brief — Mercedes C63 AMG W204 (`c63_w204`) — S12 Acoustic Realism

**Scope boundary:** Synthetic, uncalibrated source. This brief covers only *public,
non-copyrighted engineering specifications and tonal descriptors* (B/C class). No
reference audio, waveforms, or proprietary recording content is reproduced here.
All acoustic values in `reference_database/c63_w204_reference_targets.json` are
*derived relative metrics* (`B/R2`) and remain recording-dependent, not OEM
calibration.

---

## 1. Engine & platform (public specs)

| Attribute | Value | Source |
|---|---|---|
| Engine code | M156 E 63 (hand-assembled, Affalterbach, one technician/engine) | evo.co.uk, motorinspektion.de |
| Configuration | 90° cross-plane V8, naturally aspirated (no turbo/supercharger) | evo.co.uk, threepiece.us |
| Displacement | 6,208 cc (nominally "6.3") | pistonheads.com, grokipedia.com |
| Bore × stroke | 102.2 mm × 94.6 mm | pistonheads.com |
| Valvetrain | DOHC, 32 valves (4 per cyl), variable cam timing all shafts | motorinspektion.de |
| Compression | 11.3 : 1 | motorinspektion.de |
| Peak power | 457 hp @ 6,800 rpm (480–520 hp variants) | pistonheads.com, evo.co.uk |
| Peak torque | 442 lb·ft @ 5,000 rpm | pistonheads.com |
| Redline | ~7,200 rpm | evo.co.uk, motorinspektion.de |
| Induction | Multipoint port injection, premium fuel | motorinspektion.de |

## 2. Firing order (cross-plane V8)

The M156 uses the classic **cross-plane / "same-bank-priority"** firing order
**`1-5-4-8-6-3-7-2`** (cylinders 1-3-5-7 = left bank, 2-4-6-8 = right bank). This
irregular (non-alternating-bank) sequence produces the characteristic uneven
exhaust-pulse spacing — the "potato-potato" lumpy cadence — rather than the
alternating bark of a flat-plane V8.

- Cross-plane order reference (generic V8 sports-car order): `1-5-4-8-6-3-7-2`
  — b2bwiki.baidu.com/article/719194284090933251 (states this order keeps the
  same bank firing consecutively for a concentrated exhaust note in sports cars).
- This is mirrored directly in the source `bank_pattern=(0,1,0,1,1,0,1,0)` +
  `events_per_rev=4.0` (8 combustion events / 2 revs).

## 3. Idle behaviour

- Documented warm idle settles at **~600–700 rpm** (evo.co.uk: "the needle
  steadying at just 600 rpm"). Cold-start is a loud V8 "bark". The synthetic
  scenario trace uses 750 rpm idle (`render_realism_v10._scenario_trace`); this is
  a *scenario input*, not a claimed measured idle. No change made to the frozen
  scenario trace.

## 4. Exhaust bank / outlet configuration

- Quad tailpipes; equal-length-ish bank headers feeding a performance exhaust.
- The source models **two independent banks** (`left_impulses` / `right_impulses`
  split by `bank_pattern`), each rendered with a mid-low fundamental (140/180 Hz)
  and a small phase offset (+0.2 rad right bank) to evoke the bank-to-bank
  asymmetry of a cross-plane V8.

## 5. Tonal signature (1–2 sentences, descriptor only)

A deep, muscular, naturally-aspirated cross-plane V8 with a lumpy "potato-potato"
idle and a heavy mid-band burble, punctuated by an aggressive AMG "blip-bark"
crack on throttle — a full-throated, immediate, lag-free V8 roar rather than a
high-strung shriek.

## 6. Mapping to tuning knobs (`sources/mercedes_v8_source.py`)

| Reference trait | Knob (file:line) | Setting |
|---|---|---|
| Cross-plane irregularity | `events_per_rev=4.0` (:32), `bank_pattern=(0,1,0,1,1,0,1,0)` (:33) | unchanged (frozen-faithful) |
| Combustion thump / low band (20–250 Hz) | exhaust `140/180 Hz`, gain `0.072` (:46–49) | raised gain to carry `accel_low≈0.18` |
| Mid burble | bark `540/820 Hz` weights `0.50/0.40` (:60–62) | trimmed to relieve swollen mid |
| AMG blip-bark (high 1–4 kHz) | bark `1100/1500 Hz` weights `0.42/0.10`, gain `0.125`, idle floor `0.60` (:60–65) | rebalanced to lift `accel_high` + idle centroid |
| NA intake roar (low band) | intake `200 Hz`, gain `0.040`, load-gated (:68–69) | raised to add `accel_low` without sinking idle centroid |
| Mechanical texture / valvetrain | `texture strength 0.08 seed 5.9` (:73), `valvetrain 0.009` (:74) | unchanged |

> Note: the 1500 Hz bark component is a **perceptual high-band compensation**
> exercised only via upstream excitation; the radiation model (>5.5 kHz) is frozen
> and unvalidated, so no energy is pushed past validated radiation.

## 7. Compliant reference provenance

- **Derived relative metrics (used as acceptance target):** `reference_database/c63_w204_reference_targets.json`
  - Title: `c63_w204_reference_targets.json` (schema `s12.c63_reference_targets.v1`)
  - SHA-256: `1ebd2abc8e76a886bf558e783ecd02e6577a49747dd637134ef9a4f5789871cf`
  - Provenance tag: `B/R2 extracted from external recording; microphone/AGC/config dependent; not OEM calibration`
- **Reference media (non-redistributable, local):** `local:tesla-sound-research/c63_w204_performance_accel.wav`,
  `local:tesla-sound-research/c63_w204_close_downshift.wav`,
  `local:tesla-sound-research/c63_w204_headers_backfire.wav` — recorded external
  media; SHA-256 / URL consolidated in the project `realism_reference_manifest.json`
  (out of scope of this per-car brief). No audio is embedded or reconstructed here.
- **Public spec sources (cited, not copied):** evo.co.uk/mercedes/c63-amg;
  pistonheads.com; grokipedia.com/page/Mercedes-Benz_C63_AMG_W204;
  motorinspektion.de/mercedes-m156-6-3-amg-motor; threepiece.us (M156 ownership).
- **Compliance:** No copyrighted audio, waveforms, or OEM calibration data are
  included. Only open engineering specs and a one-sentence tonal descriptor are used.
