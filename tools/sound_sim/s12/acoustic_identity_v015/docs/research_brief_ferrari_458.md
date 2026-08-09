# Research Brief — Ferrari 458 Italia (F136 V8 flat-plane)

**Scope of this brief:** public technical specifications, engine-operating principles, and the
*qualitative* sound signature described in words only. **No copyrighted audio was accessed,
transcribed, extracted, or reproduced.** All acoustic tuning targets in this project are
uncalibrated relative metrics (`reference_database/ferrari_458_reference_targets.json`, R2/B
relative cues) and are NOT OEM calibration. Output remains `synthetic; uncalibrated; not OEM
reproduction`.

## 1. Engine architecture (F136, 458 Italia)

| Item | Value (public spec, Ferrari 458 Italia 2009–2015) |
|------|---------------------------------------------------|
| Type | 4.5 L naturally-aspirated 90° V8, *flat-plane* crank |
| Bore × stroke | 94.0 mm × 81.0 mm |
| Valvetrain | DOHC 4 valves/cyl, direct + port injection |
| Output | 570 PS (562 hp) @ 9,000 rpm |
| Torque | 540 N·m @ 6,000 rpm |
| Redline | 9,000 rpm (fuel cut ~9,250) |
| Idle | ~800–900 rpm (this project uses ~800 rpm) |
| Firing order | 1-6-5-8-3-4-7-2 at even **180°** intervals (flat-plane) |
| Induction | N/A, variable intake geometry; no turbos/superchargers |

### 1.1 Flat-plane crank and even-fire 180° spacing
- A flat-plane V8 pairs crank throws at 180° (all in one plane), so each bank fires as a
  perfectly even **180°** pulse train — no cross-plane "potato-potato" uneven firing.
- Acoustic consequence: a clean, high-order combustion harmonic ladder with **no low-order
  lumpiness**, and the chassis/induction resonances ring freely. This is the basis for the
  source's even impulse train with left/right bank alternation and the rpm-scaled metallic comb.
- Idle: the 458 idles ~800–900 rpm. The reference idle is **mid-frequency dominant**
  (centroid 980.4 Hz, band0 ≈ 0.009), *not* the sub-250 Hz thrum a low-cut dyno recording would
  suggest — a bright, mechanical, ticking idle.

### 1.2 High-rpm metallic "shriek"
- With no forced induction and a 9,000 rpm ceiling, the 458's identity is a **metallic,
  glassy high-rpm scream** from valve/header/intake resonance. This lives above ~3 kHz at high
  rpm but is deliberately *restrained* under acceleration (reference accel high band ≈ 0.068) and
  the **mid band (250–1000 Hz) dominates acceleration** (≈ 0.569). The stock car is therefore
  "mid-dominant accel + bright high-rpm ring", NOT a bass-heavy muscle note.

## 2. Tonal signature (words only)

At idle: a bright, mechanical, slightly busy *ticking / buzzing* with the even flat-plane pulse
clearly audible — higher-pitched than a cross-plane V8. Under acceleration: a smooth, urgent
**mid-body howl** that climbs into a **metallic, glassy shriek** near redline. The reference
metrics confirm mid-dominance (accel band0 ≈ 0.356, band1 ≈ 0.569, band2 ≈ 0.068) and a bright
idle (centroid ≈ 980 Hz), i.e. the dominant identity is the flat-plane even-pulse mid howl plus
the high-rpm ring, not a low-frequency rumble.

## 3. Mapping to source knobs (`sources/flat_plane_v8_source.py`)

| Real-world feature | Knob in source | Note |
|--------------------|----------------|------|
| Flat-plane even 180° firing | Even `phase` impulse train, `event_id % 2` left/right bank alternation | Clean combustion pulse, no cross-plane lumpiness |
| Mid-dominant acceleration (band1 ≈ 0.569) | Combustion carrier weighted `(0.68·N2 + 0.62·N4 + 0.50·N6)`, low `comb_gain=0.15` | N2 kept modest, N4/N6 boosted → energy in 250–1000 Hz |
| Restrained high-rpm ring (accel high ≈ 0.068) | `met_accel` metallic resonator, `met_scale` rpm-scaled, `comb_idle_factor` | Loud at idle, restrained under load |
| Bright idle (centroid ≈ 980 Hz) | `idle_mid` ~1000 Hz + `idle_hi` ~1450 Hz tonal filler, rpm-gated via `idle_mask` | Survives the frozen low-cut PTR; fixes the loudness regression |
| Regression fix (idle not deleted by PTR) | `comb_idle_factor = (1-idle_mask) + idle_mask·0.02` suppresses the <250 Hz carrier at idle | Single shared bundle gain now lands idle at ~-16 LUFS |

## 4. Compliance / provenance

- Sources consulted (public, text-only): Ferrari 458 Italia model histories and F136 engine
  technical write-ups (ferrari.com press archive, car magazines, engineering explainers on the
  flat-plane crank and 1-6-5-8-3-4-7-2 firing order, redline/idle figures). These describe
  **specs, operating principle, and the sound described in words**; none were audio sources.
- No recording, sample, or waveform was copied. The acoustic reference targets are **relative**
  listening/feature cues (`boundary: synthetic; uncalibrated; not OEM reproduction`) used only to
  steer the independent synthetic source.
- Frozen boundaries respected: `idle_dynamics.py` untouched; radiation package, PTR core, FVM,
  Runtime, MATLAB/Simulink untouched; `_health` gate and loudness framework untouched.

---
*This brief supports the per-car coarse-realism tuning + regression fix of `ferrari_458` in the
S12 Engine Acoustic Realism project. All synthesis directions are `C/synthetic`; external values
remain recording-dependent `B/R2` feature context.*
