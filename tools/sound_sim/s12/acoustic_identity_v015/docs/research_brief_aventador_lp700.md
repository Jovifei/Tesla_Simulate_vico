# Research Brief — Lamborghini Aventador LP700-4 (`aventador_lp700`)

**Project:** S12 Engine Acoustic Realism — per-car acoustic optimization (V12 vertical slice)
**Author:** per-car agent (autonomous)
**Boundary:** synthetic; uncalibrated; not OEM reproduction. No copyrighted audio is copied into the repository.

---

## 1. Engine specification (public, factual — non-copyrighted)

| Parameter | Value | Source |
|---|---|---|
| Model | Aventador LP700-4 (2011–2016) | Wikipedia / manufacturer |
| Engine code | L539 | Wikipedia |
| Layout | 60° V12, naturally aspirated (NA) | Wikipedia |
| Displacement | 6,498 cc (6.5 L) | Wikipedia |
| Max power | 700 PS (515 kW; 690 hp) @ 8,250 rpm | Wikipedia |
| Max torque | 690 N·m @ 5,500 rpm | Wikipedia |
| Redline | 8,250 rpm (limiter) | Wikipedia |
| Idle | ~950 rpm (matches project scenario trace & `idle_dynamics` profile) | project trace |
| Induction | Naturally aspirated (no forced induction) | Wikipedia |
| Exhaust | Side-mounted, high-exit twin-pipe; characteristic low/mid bark, NA V12 scream | public reviews |
| Transmission | 7-speed ISR single-clutch (Graziano) | Wikipedia |

**Firing order (per plan §5.1, used in this slice):** `1-7-5-11-3-9-6-12-2-10-4-8`.
> Note / discrepancy: Public Wikipedia lists the L539 firing order as `1-12-4-9-2-11-6-7-3-10-5-8`. The even-fire source model here uses `events_per_rev=6.0` (uniform 6 impulses/rev) and does **not** encode an explicit cylinder firing order, so the discrepancy does not affect the synthesis. Recorded for traceability; the plan value is authoritative for this car's slice.

---

## 2. Tonal signature (synthesis target — descriptive, not a recording)

The Aventador L539 is renowned for a **raw, high-RPM "operatic" V12 wail that climbs into a metallic, screaming shriek toward redline**, underpinned by a surprisingly smooth, even-fire mid-body (no lumpy V8 rumble) and a tight, barking NA exhaust. Its identity is mid-dominant with a strong upper-harmonic sheen rather than a deep low-frequency growl.

---

## 3. Reference audio provenance

- **Compliance:** No external recording was downloaded, embedded, or copied into this repository. All tuning is against relative feature targets only.
- **Source of truth for this slice:** `reference_database/aventador_lp700_reference_targets.json` (`stock_median`), which holds B/R2 *relative* metrics (band shares, centroid) — explicitly "not OEM calibration".
- **External recording SHA-256 / URL:** **Not fetched in this per-car slice.** Per plan, the shared `reference_database/realism_reference_manifest.json` (URL, SHA-256, segment intent, recording risks) is consolidated by the main agent. This brief therefore records *no* audio file; the manifest entry (if any) is owned by the main agent and out of scope here.

---

## 4. Parameter-mapping: research → my tuning knobs

| Research fact | Knob (file:line) | Mapping decision |
|---|---|---|
| Even-fire 60° V12, smooth not lumpy | `events_per_rev=6.0` (:32) | Kept even-fire (6 impulses/rev) — matches published even-fire character. |
| NA, mid-dominant, no forced induction | `pressure_exp=1.05`, `max_comp=1.8` (:32) | Kept; controls combustion pressure shape. |
| High-RPM screaming shriek | new `scream` stem (2000/2800/3600 Hz, :~62) | Added genuine 1–4 kHz decaying-tone excitation, **gated to `high_rpm`** so it lifts the acceleration HIGH band without touching idle. Perceptual high-freq compensation (radiation model frozen >5.5 kHz — trap #4). |
| ~950 rpm idle, centroid target 648 Hz | new idle-gated `idle_mid` (700 Hz) + `idle_high` (1700 Hz, :~66) | Added idle-only (`idle_factor = clip((1850-rpm)/850,0,1)`) mid+high stems to lift idle centroid; reference idle itself carries ~0.11 of energy in 1–4 kHz, so an idle-gated high tone was required. |
| Smooth mid "wail" (400/540 Hz) | `wail` (:56-59), idle floor 0.15→0.60 | Raised idle floor so the mid wail carries the idle clip (mid-dominant per ref). Accel wail effectively unchanged. |
| Low exhaust fundamental (92 Hz) | exhaust (:46-47), throttle-gated | Made `(0.18 + 0.82·throttle)` so the 92 Hz fundamental does not dominate the idle low band; accel exhaust ~unchanged. |
| 12 ITBs intake roar (240 Hz) | intake (:62-63), throttle-gated | `(0.30 + 0.70·throttle)` — reduces idle low-band bloat. |
| `mechanical_texture` is a sub-60 Hz low-pass (trap #1) | `texture` (:68) | **Not** used for high-freq; left as low-freq accessory only. |
| `to_stereo(crossfeed)` is R-channel gain (trap #2) | `to_stereo` calls (:72-77) | Used only for L/R balance, per contract. |

---

## 5. Traps explicitly honored

1. `mechanical_texture` cutoff `int(sr/60)` is a kernel length (≈26 Hz low-pass) → kept low-band only; no high-freq reliance on it.
2. `to_stereo` `crossfeed` = right-channel gain → used for balance only.
3. Verifier uses the **power** spectrum (|FFT|²) — left unchanged (consistent with reference targets).
4. Radiation model frozen/unvalidated >5.5 kHz → high-freq realism added only via upstream `scream` excitation, declared here as perceptual compensation.

## 6. Frozen boundaries — NOT modified

`benchmark/.../radiation-boundary-package.json`, radiation model, PTR core, FVM, Runtime, MATLAB/Simulink, `render_identity_v02._health` gate, `manage_bundle_loudness`, and `synth_primitives` signatures were all left untouched. Only `sources/lamborghini_v12_source.py` was edited.
