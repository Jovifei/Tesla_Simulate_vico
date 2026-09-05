# 当前产品方向：App-first 实时声浪

更新：2026-09-05
状态：`ACTIVE_AUTHORITY`

最终产品：车内 Android App，而不是当前 ESP32 盒子。

```text
speed + acceleration
→ VirtualEngineState
→ selected Vehicle Profile
→ realtime engine-sound core
→ Android playback
```

当前不是立即写 App UI 的阶段；当前优先完成声音算法的 reference/Human 闭环。Stage AD 是 App 之前的 authoring/calibration 工程阶段。

完成声音 profile 后：

```text
Engineering Profiles
→ AudioParameterPackage
→ Golden traces / PCM
→ portable C++
→ Python↔C++ equivalence
→ Android NDK + Oboe/AAudio
→ vehicle selector
→ in-car validation
```

App MVP 不依赖 Tesla CAN；CAN/OBD/真实 RPM 是未来 richer adapter。ESP32 = `DEFERRED_FUTURE_OPTION`。
