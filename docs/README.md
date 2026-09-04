# Tesla Simulate Vico Documentation

当前主线：**S12 声音真实性 → Human Gate → Android App 实时声浪**。

## Read First

1. [项目长期记忆](knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md)
2. [研究来源与方法吸收历史](knowledge/obsidian/S12/Engine-Audio-Ecosystem/Research-Sources-And-Adoption-History.md)
3. [当前 App-first 产品方向](04-planning/03-current-app-product-direction.md)
4. [当前系统架构](01-architecture/01-project-system-architecture.md)
5. [项目总路线图](04-planning/02-project-master-roadmap.md)
6. [当前状态](08-reports/10-project-status-20260904.md)
7. [项目总 Backlog](09-backlog/02-project-master-backlog.md)

证据：handoff package ≈90%，旧聊天/总结 ≈10%；动态 GitHub 真值现场复核；当前用户决策优先。

当前产品：

```text
Android App
→ speed + acceleration
→ VirtualEngineState
→ Vehicle Profile
→ S12 realtime sound
→ playback
```

当前最小输入 = `speed + acceleration`。CAN/OBD 后续可选。ESP32 = `DEFERRED_FUTURE_OPTION`。

当前 gate：`AC8 → Jovi V3 audition → AA-C3 accept/ONE Round2 → Engineering Profile → App productization`。
