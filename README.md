# Tesla Simulate Vico

## Current Direction

**S12 acoustic realism → Jovi Human Gate → Android App realtime engine sound.**

Current App model:

```text
speed + acceleration
→ VirtualEngineState
→ Vehicle Profile (Hellcat/Ferrari/RX-7/...)
→ S12 realtime sound engine
→ App playback
```

Real RPM/CAN is not a current prerequisite; CAN/OBD can be added later as a richer input adapter. ESP32 is `DEFERRED_FUTURE_OPTION`.

## Canonical Memory

- `docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md`
- `docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Research-Sources-And-Adoption-History.md`
- `docs/04-planning/03-current-app-product-direction.md`
- `docs/04-planning/02-project-master-roadmap.md`
- `docs/08-reports/10-project-status-20260904.md`

Evidence rule: `S12_Handoff_Package_2026-09-03` ≈90%, old chat/assistant summaries ≈10%; dynamic GitHub truth is always re-fetched; current user decisions override historical plans.

## Current Gate

```text
AC8 post-merge receipt
→ Jovi Hellcat V3 blind audition
→ AA-C3 accept OR ONE source-causal Round2
→ Engineering Profile
→ Ferrari/RX-7
→ AudioParameterPackage
→ speed/acceleration state model
→ portable C++
→ Android App realtime
→ in-car validation
```

Current boundaries: `HUMAN_PASS=false`, `R1=MISSING`, `ESP32=DEFERRED_FUTURE_OPTION`.
