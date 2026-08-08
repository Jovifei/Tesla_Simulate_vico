# LFA V10 (Lexus LFA, 1LR-GUE) — Acoustic Realism Research Brief

**Car:** `lfa` · **Focus:** HIGH-FREQUENCY COMPENSATION (5.5–12 kHz upstream excitation)
**Project:** S12 Engine Acoustic Realism · **Phase:** Per-car tuning (vertical slice)
**Author scope:** synthetic; uncalibrated; not OEM reproduction.

> **Compliance statement.** This brief records only publicly documented *specification,
> engineering, and tonal-signature* facts (engine layout, firing order, redline, Yamaha
> acoustic co-development). It contains **no copyrighted audio, no waveform data, no
> OEM-calibrated coefficients**. The synthesis is `C/synthetic`; all reference numbers in
> `reference_database/lfa_reference_targets.json` are treated as `B/R2` relative feature
> cues only. No item is claimed as stock-verified, OEM-measured, or OEM reproduction.

---

## 1. Engineering facts (public / spec-level only)

| Item | Value | Source |
|------|-------|--------|
| Engine | 1LR-GUE, 4.8 L (4805 cc), **72° V10**, NA | Wikipedia/Toyota LR engine |
| Firing order | **1-6-5-10-2-7-3-8-4-9** (even-fire, 5 events/rev) | technical write-ups |
| Redline / fuel cut | **9000 rpm / 9500 rpm** | Toyota LR engine |
| Valvetrain | DOHC, 4 valves/cyl, dual VVT-i | Toyota LR engine |
| Induction | **10 individual (electronically controlled) throttle bodies** | Toyota LR engine |
| Acoustic co-dev | **Yamaha** (music-division) tuned intake manifold + exhaust/"angel's cry" | Toyota LR engine, Lexus LF-A |
| Idle (warm) | **≈ 900 rpm** (factory; matches scenario trace) | scenario trace `lfa:idle` |
| Signature quote | "roar of an Angel" / F1-like high scream | Toyota/Lexus engineering |

The 72° bank angle gives the V10 near-perfect primary/secondary balance without balance
shafts; combined with forged-titanium rods and the Yamaha-tuned equal-length headers and
surge tank, the engine is famously **free-revving** (idle→redline in ~0.6 s) and produces a
distinctive **clean, high, "angel's cry" wail** rather than a low burble.

## 2. Tonal signature (1–2 sentences)

The LFA's identity is a **bright, clean, high-centered V10 scream** — a fixed-center
"angel's cry" tone that stays mid/high across the rev range with almost no low-end body,
and is **audible even at idle** as a high-pitch shriek.

## 3. Mapping to synthesis knobs (`sources/lexus_v10_source.py`)

- **72° even-fire V10, no low burble** → modeled as **pure fixed-center sinusoids, NO impulse
  train** (`render_lfa`), `events_per_rev=5.0`. The low-frequency body layer gain is
  near-zero (frozen profile), so the low band stays empty.
- **Yamaha "angel's cry" scream** → `scream_mid` (600/720 Hz) + `scream_high`
  (1100–2200 Hz) + `scream_vhigh` (4800–7200 Hz) partials.
- **Idle shriek (high-pitch even at idle)** → high/vhigh partials gated by an
  **idle-biased `high_floor`** (`0.58 * clip((0.45 - throttle)/0.32, 0, 1)`): ~0.58 at
  idle (throttle≈0.14), collapsing to 0 by throttle 0.45. This pushes the idle spectral
  centroid up toward the 1366 Hz reference without inflating the acceleration band.
- **10 individual throttle bodies / intake roar** → fixed-center `intake` sinusoid (480 Hz),
  load-floored, kept small so it does not add low-end.
- **Refined mechanical texture** → tiny `mechanical_texture` (cutoff = `sr/60` ≈ 26 Hz
  sub-rumble, NOT a high shelf) + near-zero valvetrain; does not spill into the high band.

## 4. High-frequency compensation (5.5–12 kHz strategy) — DECLARED PERCEPTUAL

**Frozen boundary:** the radiation model is frozen and its **effective band is 55–5459 Hz;
the 5.5–12 kHz region is UNVALIDATED / not physically covered.** The LFA's most iconic
"angel's cry" energy lives precisely in this 5.5–12 kHz window, which the frozen chain
cannot reproduce.

Therefore, per plan §5.4, I compensate **ONLY via upstream excitation** — never by altering
the radiation model:

- `scream_vhigh_env` adds partials at **4800 / 6000 / 7200 Hz** (4800 sits just inside the
  radiation edge; 6000/7200 are the declared 5.5–12 kHz perceptual tail). Gain `0.288 *
  high_floor`.
- This is explicitly **perceptual compensation, NOT physical correction**: the frozen
  radiation model is untouched, and the high-freq tail is present where the scream is heard
  (idle / light load) and intentionally suppressed at full acceleration where the mid band
  dominates (matching the reference accel `vhigh ≈ 0.001`).
- **Measured compensation energy** (source-domain power spectrum, this tuning):
  - idle: **2.83 %** of total power in 5.5–12 kHz (present — the perceptual scream tail).
  - acceleration: **0.0 %** (high_floor collapsed — mid dominates, as in the reference).
- The LFA idle high-band (1000–4000 Hz) share also rises to ~0.42 and the vhigh (4000–12000
  Hz) share to ~0.088 at idle, carrying the centroid to **1365.6 Hz** (reference 1365.65,
  distance **0.1 Hz**).

This approach keeps the frozen radiation/PTR/FVM/Runtime code completely untouched while
delivering the LFA's signature high wail in the validated (source-domain) sense.

## 5. Provenance / compliance recap

- All synthesis directions are `C/synthetic`; reference band/centroid values are `B/R2`
  relative feature cues only.
- No copyrighted audio is stored, reproduced, or redistributed.
- Frozen modules (radiation boundary package, PTR core, FVM, Runtime, MATLAB/Simulink) and
  `synth_primitives` signatures are **not modified**.
