# Tesla Simulate Vico / S12 当前系统架构

Current product = Android App. ESP32 = `DEFERRED_FUTURE_OPTION`.

```text
speed + acceleration
→ VehicleState / VirtualEngineState
→ Vehicle Profile
→ Persistent Event-Domain Engine
→ Pressure Audio Chain
→ Frozen PTR/Radiation
→ Realtime PCM
→ Android Audio Output
```

Minimum input = speed + acceleration. App derives virtual RPM/load/gear/shift/lift/overrun. CAN/OBD is future richer adapter.

S12 Python remains acoustic-authoring/validation authority. Productization: Engineering Profile → AudioParameterPackage → Golden Evidence → portable C++ → Python↔C++ equivalence → Android NDK/AAudio/Oboe → in-car validation.

Vehicle order: Hellcat → Ferrari 458 → RX-7 FD.

Detailed history and boundaries: `docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md`.
