# 当前产品方向：App-first 实时声浪

> 当前产品载体是车内 Android App。主证据：`S12_Handoff_Package_2026-09-03` ≈90%，旧聊天/此前总结 ≈10%。ESP32 = `DEFERRED_FUTURE_OPTION`。

```text
speed + acceleration
→ VirtualEngineState
→ Vehicle Profile (Hellcat/Ferrari/RX-7/...)
→ S12 realtime sound
→ Android App playback
```

当前最小输入是 speed + acceleration；virtual RPM/load/gear/shift/lift/overrun 由 App 内部推导。CAN/OBD 是 future richer adapter，不是前置条件。

当前顺序：

```text
AC8
→ Jovi V3 blind audition
→ AA-C3 accept OR ONE source-causal Round2
→ Hellcat Engineering Profile
→ Ferrari/RX-7
→ AudioParameterPackage
→ speed/acceleration state model
→ Golden traces/PCM
→ portable C++
→ Python↔C++ equivalence
→ Android realtime
→ vehicle selector
→ in-car validation
→ R1 when available
```

当前不做 ESP32 board/IRAM/BLE/WiFi/OTA/advanced sound port。只有 App 版本成熟后且用户明确重新开启时才评估嵌入式简化版。