# Tesla Simulate Vico / S12 项目总路线图

Current mainline: **声音真实性 → Human Gate → Android App realtime**。Detailed history: `docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md`。

```text
M0 AC8 post-merge closeout
M1 Jovi Hellcat V3 Human Gate
M2 ONE source-causal Round2 if needed
M3 Hellcat Engineering Profile
M4 Ferrari / RX-7 profiles
M5 speed + acceleration → VirtualEngineState contract
M6 AudioParameterPackage + Golden Evidence
M7 portable C++
M8 Python↔C++ equivalence
M9 Android App realtime engine
M10 vehicle selector + in-car validation
M11 R1 formal calibration when data exists
M12 ESP32 only if explicitly reopened later
```

Current minimum input = speed + acceleration; App derives virtual RPM/load/gear/shift/lift/overrun. CAN/OBD is future richer input.

ESP32 = `DEFERRED_FUTURE_OPTION`.
