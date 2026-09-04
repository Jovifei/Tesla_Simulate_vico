# 01-architecture

Purpose: current product architecture, sound-authoring authority, state flow, runtime boundaries and integration contracts.

Before reading architecture details, read the canonical project memory:

- `../knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md`
- `../knowledge/obsidian/S12/Engine-Audio-Ecosystem/Research-Sources-And-Adoption-History.md`

Current authoritative architecture entry:

- `01-project-system-architecture.md` — **App-first realtime sound architecture**.

Keep these boundaries visible:

- current product runtime = Android App；
- current minimum input = speed + acceleration；
- App derives VirtualEngineState such as virtual RPM/load/gear/shift；
- S12 Python remains current sound-authoring/validation authority；
- Track-P frozen physics vs Track-S acoustic identity；
- Raw/analysis evidence vs realtime/audition playback；
- AudioParameterPackage / portable C++ vs platform I/O adapters；
- software evidence vs human evidence vs R1 evidence；
- ESP32 is `DEFERRED_FUTURE_OPTION`, not a current architecture gate。
