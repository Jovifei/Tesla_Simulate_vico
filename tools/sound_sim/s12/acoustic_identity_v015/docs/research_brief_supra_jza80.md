# Research Brief — Toyota Supra JZA80 (2JZ-GTE 3.0 L I6 Twin-Turbo)

**Vehicle:** `supra_jza80` · **Scope:** synthetic; uncalibrated; not OEM reproduction.
**Compliance:** public engineering specifications, firing order, and tonal *signature*
description only. No copyrighted audio, no OEM calibration data, no verbatim recordings
were ingested, copied, or reproduced. Provenance is text/spec-based (URL/title below);
SHA-256 applies only to binary media and is deferred to the consolidated manifest
built by the main agent, since no audio file was fetched for this brief.

## 1. Engine facts (public, non-copyrighted)

- **2JZ-GTE** — 2,997 cc (3.0 L) DOHC 24-valve **inline-6**, square bore/stroke
  (86.0 × 86.0 mm), aluminium head, reinforced block / metal head gasket.
  Factory rating ~280 PS (Japanese limit) with ~430 N·m (≈320 lb·ft) of torque.
- **Forced induction:** parallel **sequential twin CT20B** turbochargers — the
  first spools at low rpm for low lag, the second joins at higher load/rpm
  ("sequential-ish" spool character, not simultaneous boost).
- **Firing order (cited public spec, even-fire I6):** `1-5-3-6-2-4`
  (cylinders 1–6 inline). Even-fire ⇒ evenly spaced combustion pulses ⇒ a
  smooth, low-frequency exhaust cadence with minimal lumpiness.
- **Idle:** ~700–800 rpm (scenario trace uses 800 rpm, load 0.15).
- **Redline:** ~7,000 rpm (scenario trace top).
- **Tonal signature:** a *smooth, deep inline-six burble* with a *soft twin-turbo
  whoosh/spool* and a *faint high-frequency compressor whistle* — low/mid
  dominant and never shrill; the defining identity is the deep, even I6 rumble,
  not a screaming top end.

## 2. Signature → model knob mapping (source file only)

| Signature trait | Source knob (`toyota_i6_turbo_source.py`) | Notes |
|---|---|---|
| Even-fire I6, deep smooth rumble | `combustion_impulse_train` `events_per_rev=3.0`; `exhaust` 120 Hz carrier with 1st–6th engine-order mix | Raised carrier (60→120 Hz) + higher orders lift the idle spectral centroid from baseline ~53 Hz to ~118 Hz while staying a deep I6 (all <250 Hz). |
| Heavy low-end (reference accel 20–250 Hz ≈ 0.73) | Frozen `low_frequency_body` (Hellcat-class) + `exhaust` fundamental | Low band supplied largely by the frozen shared layer; source keeps the carrier present. |
| Mid racy/intake edge (accel 250–1000 Hz ≈ 0.253) | `edge` `decaying_tone` 360 Hz, gain 0.052→0.080, accel-gated | Fixed-center mid tone, no engine-order modulation, hard-gated at idle so the deep idle target is preserved. |
| Twin CT20B sequential spool | `turbo_layer` `shaft_ratio_base=1.8`, orders `(1.0,)`, boost attack/release 0.08/0.20 | 1st shaft order only ⇒ whine stays out of 1–4 kHz; boost-state inertia models the sequential spool. |
| Faint high-band compressor whistle (accel 1000–4000 Hz ≈ 0.016) | `hiband` `decaying_tone` 1800 Hz, gain 0.012, accel-gated | **Declared perceptual high-frequency compensation** (upstream excitation, inside the validated 55–5459 Hz band); does not run at idle. |
| Mechanical / valvetrain | `mechanical_texture` (seed 4.4), `valvetrain` 0.009 | Kept light, idle-gated; not used for high-frequency content (per trap note). |

## 3. Provenance (brief; full manifest later)

- All synthesis is `C/synthetic`, uncalibrated, not OEM reproduction.
- Reference target `stock_median` is B/R2 *relative feature* context only
  (per `reference_database/supra_jza80_reference_targets.json` boundary note).
- Public specification references consulted (text only, no media fetched):
  - Toyota 2JZ-GTE — public encyclopedic engine article
    (e.g., `https://en.wikipedia.org/wiki/Toyota_JZ_engine`), title "Toyota JZ engine".
  - Toyota Supra (A80/JZA80) model overview / press material
    (e.g., `https://en.wikipedia.org/wiki/Toyota_Supra`), title "Toyota Supra".
  - Public firing-order / service references for the 2JZ-GTE (`1-5-3-6-2-4`).
- SHA-256: N/A for this text-only brief. Any binary media fetched later will have
  its SHA-256 recorded in the consolidated `realism_reference_manifest.json` by the
  main agent; none was required or ingested here.

## 4. Tuning finding (idle centroid)

The idle spectral centroid target (≈117.6 Hz) is reachable from the source file:
raising the exhaust carrier to 120 Hz and using a 1st–6th engine-order mix shifts
the low-band energy upward (toward 100–250 Hz) so the idle centroid lands at 116.4 Hz
(error 1.2 Hz, within the 25 Hz new-gate window and the "excellent" ≤5 Hz band).
The shared `idle_dynamics` layer (28 Hz combustion ring) was **not** modified; the
centroid lift was achieved entirely through source-domain excitation, as required.
