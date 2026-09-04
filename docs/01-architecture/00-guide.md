# 01-architecture

Purpose: current product architecture, sound-authoring authority, state flow, runtime boundaries and integration contracts.

Read first:
- `../knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md`
- `../knowledge/obsidian/S12/Engine-Audio-Ecosystem/Research-Sources-And-Adoption-History.md`

Authoritative architecture: `01-project-system-architecture.md` — App-first realtime sound architecture.

Boundaries:
- current runtime = Android App；
- minimum input = speed + acceleration；
- App derives VirtualEngineState；
- S12 Python is sound-authoring/validation authority；
- Track-P frozen vs Track-S identity；
- software vs human vs R1 evidence；
- ESP32 = `DEFERRED_FUTURE_OPTION`。
