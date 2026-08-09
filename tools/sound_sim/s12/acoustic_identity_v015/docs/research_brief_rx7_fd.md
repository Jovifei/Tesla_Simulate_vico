# Research Brief — Mazda RX-7 FD3S (13B-REW) Rotary Turbo

**Scope of this brief:** public technical specifications, engine-operating principles, and the
*qualitative* sound signature described in words only. **No copyrighted audio was accessed,
transcribed, extracted, or reproduced.** All acoustic tuning targets in this project are
uncalibrated relative metrics (`reference_database/rx7_fd_reference_targets.json`, R2/B
relative cues) and are NOT OEM calibration. Output remains `synthetic; uncalibrated; not OEM
reproduction`.

## 1. Engine architecture (13B-REW)

| Item | Value (public spec, FD3S RX-7 1992–2002) |
|------|-------------------------------------------|
| Type | Twin-rotor Wankel (no pistons / no valvetrain) |
| Displacement | 1,308 cc (2 × 654 cc per rotor) |
| Compression | 9.0 : 1 |
| Output | 255 PS (USDM) → 280 PS (JDM "gentleman's agreement") |
| Torque | ~294 N·m @ 5,000 rpm |
| Redline | ~8,000 rpm (fuel cut ~8,500) |
| Induction | Sequential twin-turbo (Hitachi HT-10/HT-12) |
| Aspiration | Not a piston engine: eccentric shaft + two triangular rotors in epitrochoid housings |

### 1.1 Firing / "no pistons" modulation
- Each rotor has 3 faces; one power stroke per rotor revolution. Two rotors offset 180° give
  **2 combustion events per eccentric-shaft revolution** (the output shaft does 3 revolutions per
  rotor revolution — this is why a rotary revs freely and why there is no piston reciprocating mass).
- Acoustic consequence: the rotary fundamental is at **2 × engine_order** (2 firing events/rev),
  not a piston firing order. This is the basis for the source's two offset impulse trains and the
  low-order "buzz" comb.
- Idle speed: FD RX-7 idles ~850–900 rpm (this project's scenario uses 920 rpm). The reference
  idle is **low-frequency dominant** (centroid 155.9 Hz, band0 ≈ 0.968) — a buzzy, mechanical
  "brap-brap-brap" thrum, not a high-pitched note.

### 1.2 Sequential twin-turbo + BOV/lift
- **Primary turbo** spools from low rpm (~2,500 rpm) → boost onset under load/rpm.
- **Secondary turbo** engages in a transition band (~4,500–5,500 rpm) gated by rpm AND load,
  producing the characteristic "second turbo" surge (pre-spool then parallel operation).
- On **throttle lift**, the compressed air has nowhere to go → **blow-off valve (BOV)** release
  (the "lift"/flutter heard on decel). Rotaries also famously **backfire** on lift (oil injected
  for apex-seal lubrication burns in the exhaust) — modeled elsewhere by the shared afterfire layer.

## 2. Tonal signature (words only)

At idle: a distinct, low-frequency, mechanical *thrumming / brap-brap-brap* with a buzzy, almost
"alien" quality. Under partial throttle the sequential turbos add a high-pitched **turbine whine**
overlay. At full throttle / high rpm the engine emits a smooth, intensely high-pitched **scream /
"buzzsaw"** with a synthetic, electronic character. The reference metrics confirm the car is
overwhelmingly **low-dominant** (accel band0 ≈ 0.936; negligible >1 kHz energy), i.e. the dominant
identity is the low buzzy body + turbo character, not a bright high-frequency timbre.

## 3. Mapping to source knobs (`sources/rotary_turbo_source.py`)

| Real-world feature | Knob in source | Note |
|--------------------|----------------|------|
| 2 combustion events/rev (no pistons) | Two offset impulse trains at `phase` and `phase+0.5`; `2/rev` fundamental | Fundamental stays 31 Hz (idle) → 253 Hz (7600 rpm) → always in 20–250 Hz |
| Non-piston buzzy modulation | Low-order harmonic comb (2/4/6/8/10/12/rev) with **rpm-dependent weighting** (`idle_gate`) | Rich higher orders at idle lift centroid to ~156 Hz; fundamental-only under load keeps accel band0 ≈ 0.94 |
| Rotor-housing resonance | LOW-order housing (4/6/8/10/rev) at modest gain | Replaces the old, inversion-causing 72/96-order excitation that pushed energy into 1–12 kHz |
| Sequential turbo onset | `primary_spool` (rpm/load), `secondary_gate` (rpm>4300 & load>0.35) → `boost_state` | Asymmetric attack/release spool dynamics |
| Boost release / BOV / lift | `blow_off_state` injected on positive `(throttle[n-1]-throttle[n])` | Separate `blow_off` / `lift` stem (kept low-gain; reference carries ~0 >1 kHz energy) |

## 4. Compliance / provenance

- Sources consulted (public, text-only): Mazda RX-7 FD model histories and 13B-REW technical
  write-ups (motortap, projectjdm, jspec-garage, fullysorted, specsnode, hpacademy, etc.).
  These describe **specs, operating principle, and the sound described in words**; none were
  audio sources.
- No recording, sample, or waveform was copied. The acoustic reference targets are **relative**
  listening/feature cues (`boundary: synthetic; uncalibrated; not OEM reproduction`) used only to
  steer the independent synthetic source.
- Frozen boundaries respected: `idle_dynamics.py` untouched; radiation model, PTR core, FVM,
  Runtime, MATLAB/Simulink untouched; `_health` gate and loudness framework untouched.

---
*This brief supports the per-car coarse-realism tuning of `rx7_fd` in the S12 Engine Acoustic
Realism project. All synthesis directions are `C/synthetic`; external values remain recording-
dependent `B/R2` feature context.*
