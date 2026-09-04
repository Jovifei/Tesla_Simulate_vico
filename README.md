# Tesla Simulate Vico

## 当前主线

**S12 声音真实性 → Jovi Human Gate → Android App 实时声浪。**

当前 App：

```text
speed + acceleration
→ VirtualEngineState
→ Vehicle Profile (Hellcat/Ferrari/RX-7/...)
→ S12 realtime sound
→ App playback
```

真实 RPM/CAN 不是当前前置条件；CAN/OBD 可后续作为 richer input adapter。

ESP32 代码保留，但统一状态：`DEFERRED_FUTURE_OPTION`，不是当前 blocker。

## 先读项目长期记忆

- [Project Long-Term Memory](docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md)
- [Research Sources And Adoption History](docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Research-Sources-And-Adoption-History.md)
- [App-first Current Direction](docs/04-planning/03-current-app-product-direction.md)
- [Master Roadmap](docs/04-planning/02-project-master-roadmap.md)
- [Current Status](docs/08-reports/10-project-status-20260904.md)

证据规则：handoff package ≈90%，旧聊天/此前总结 ≈10%；动态 GitHub 状态现场复核；用户当前明确决策优先。

## 当前状态

```text
PR #5 = MERGED
qualified head = 021fe294...
CI 33703659821 = SUCCESS
full S12 = 1423 passed / 10 skipped / 232 subtests
Track-P = PASS
AC8 = PENDING
Hellcat AA-C3 = Engineering candidate
Human = not passed yet
R1 = MISSING
```

## 下一步

```text
AC8 post-merge receipt
→ Jovi Hellcat V3 audition
→ AA-C3 accept OR ONE source-causal Round2
→ Engineering Profile
→ Ferrari/RX-7
→ AudioParameterPackage
→ speed/acceleration state model
→ portable C++
→ Android realtime App
→ in-car validation
```

当前禁止：feedback 前调音/揭盲、whole-mix/master gain Round2、把 CI 当 Human PASS、把 ESP32 重新拉回当前主线。