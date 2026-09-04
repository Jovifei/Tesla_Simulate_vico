# 当前产品方向：App-first 实时声浪

**当前产品 = 车内 Android App。ESP32 = `DEFERRED_FUTURE_OPTION`。**

Evidence: `S12_Handoff_Package_2026-09-03` ≈90%, old chat/summary ≈10%, current user decisions override historical plans.

```text
speed + acceleration
→ VirtualEngineState
→ Vehicle Profile
→ S12 realtime sound
→ Android playback
```

Current minimum input = speed + acceleration. Virtual RPM/load/gear/shift/lift/overrun are derived in App. CAN/OBD is future richer input.

Current sequence:

```text
AC8
→ Jovi V3
→ AA-C3 accept OR ONE source-causal Round2
→ Hellcat Engineering Profile
→ Ferrari/RX-7
→ AudioParameterPackage
→ Golden traces/PCM
→ portable C++
→ Python↔C++ equivalence
→ Android realtime
→ profile selector
→ in-car validation
→ R1 when available
```

No current ESP32 board/IRAM/BLE/WiFi/OTA/advanced-port work.
