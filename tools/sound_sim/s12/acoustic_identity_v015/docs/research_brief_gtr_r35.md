# Research Brief — Nissan GT-R R35 (VR38DETT 3.8 L V6 Twin-Turbo)

**Vehicle:** `gtr_r35` · **Scope:** synthetic; uncalibrated; not OEM reproduction.
**Compliance:** public engineering specifications and tonal *signature* description only. No copyrighted audio, no OEM calibration data, no verbatim recordings.

## 1. Engine facts (public, non-copyrighted)

- **VR38DETT** — 3,799 cc (3.8 L) DOHC 24-valve **V6**, **54° bank angle**,
  aluminium block, twin **IHI** ball-bearing turbochargers (RHF55-class),
  equal-length exhaust manifolds.
- **Forced induction:** parallel twin turbo, ~0.9–1.0 bar nominal boost
  (higher on NISMO/upgraded maps). Quick spool is a defining trait.
- **Firing order (cited public spec, even-fire 54° V6):** `1-4-3-6-2-5`
  (cylinders ordered L1-L2-L3-R1-R2-R3). Even-fire ⇒ evenly spaced
  combustion pulses ⇒ relatively smooth low-frequency exhaust cadence.
- **Idle:** ~700–1000 rpm (scenario trace uses 1000 rpm, load 0.15).
- **Redline:** ~6800 rpm (scenario trace top).
- **Tonal signature:** a *crisp, mid-frequency racy V6 bark* over a *prominent
  high-pitched twin-turbo whistle/spool* — the forced-induction whine, not a
  supercharger, is the identifying upper-frequency signature; low-end exhaust
  is present but not dominant.

## 2. Signature → model knob mapping

| Signature trait | Source knob (nissan_v6_turbo_source.py) | Notes |
|---|---|---|
| Even-fire V6, moderate low exhaust | `exhaust` 85 Hz, 1st+2nd order (2nd≈0.4) | Gain trimmed 0.060→0.033 to ease accel-low toward reference 0.373. |
| Mid racy V6 bark (300/420 Hz) | `racy` `decaying_tone` 300/420 Hz + idle floor | Floor raised (0.10→0.90) and gain raised (0.028→0.068) to carry mid band + idle mid. Added 1150 Hz component for 1–4 kHz high band. |
| Twin-turbo IHI whistle | `turbo_layer` shaft_ratio 2.0, orders (1,5,8), whistle gain 0.070→0.110 | 8th shaft order lands ~1–2 kHz at redline; 10th dropped to avoid high-band overshoot. |
| Mechanical / valvetrain | `mechanical_texture` (seed 8.8), `valvetrain` | Kept light (no blower). |

## 3. Provenance (brief; full manifest later)

- All synthesis is `C/synthetic`, uncalibrated, not OEM reproduction.
- Reference target `stock_median` is B/R2 *relative feature* context only
  (per `reference_database/gtr_r35_reference_targets.json` boundary note).
- No external audio was ingested, copied, or reproduced. The full
  `realism_reference_manifest.json` provenance record will accompany the
  published bundle.

## 4. Tuning finding (relevant to idle centroid)

Source-domain acceleration band shares meet acceptance (low/mid/high each
≤0.03 of reference). The **idle spectral centroid target (≈400 Hz) is not
reachable from the source file alone**: the shared `idle_dynamics` layer for
`gtr_r35` injects a combustion ring at `valve_hz*0.47 = 94 Hz` with gain
`0.080`, which dominates the idle low band (chain pressure RMS roughly
doubles at idle). Its own profile comment states the intended value is
`valve_hz 440` (→≈207 Hz mid ring), but the code carries `200.0` (→94 Hz).
This is a shared-layer profile issue outside the source file's scope and is
reported as the documented idle-centroid gap.
